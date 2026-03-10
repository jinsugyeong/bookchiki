import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.book_import import BookImport
from app.models.recommendation import Recommendation
from app.models.generated_image import GeneratedImage
from app.schemas.user import TokenResponse, UserResponse, RefreshRequest, AccessTokenResponse, UserUpdateRequest
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/google", response_model=TokenResponse)
async def google_login(code: str, db: AsyncSession = Depends(get_db)):
    """Google OAuth 코드를 Access Token + Refresh Token으로 교환."""
    # Google 코드로 토큰 교환
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": f"{settings.FRONTEND_URL}/auth/callback",
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to exchange code")

        google_tokens = token_resp.json()

        # Google 유저 정보 조회
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {google_tokens['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to get user info")

        google_user = userinfo_resp.json()

    # 유저 조회 또는 생성
    # 활성 상태인 유저만 조회하거나, 탈퇴한 유저인 경우 새로 가입할 수 있도록 함
    result = await db.execute(select(User).where(User.email == google_user["email"], User.is_active == True))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=google_user["email"],
            name=google_user.get("name", ""),
            profile_image=google_user.get("picture"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Access Token + Refresh Token 발급
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token_str = create_refresh_token()

    refresh_token = RefreshToken(
        token=refresh_token_str,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(refresh_token)
    await db.commit()

    logger.info(f"[Auth] 로그인 성공: user_id={user.id}, email={user.email}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_access_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh Token으로 새 Access Token 발급."""
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == body.refresh_token)
    )
    rt = result.scalar_one_or_none()

    if rt is None or rt.is_revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if rt.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    new_access_token = create_access_token(data={"sub": str(rt.user_id)})
    logger.info(f"[Auth] Access Token 재발급: user_id={rt.user_id}")

    return AccessTokenResponse(access_token=new_access_token)


@router.post("/logout", status_code=204)
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh Token을 폐기(revoke)하여 로그아웃 처리."""
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == body.refresh_token)
    )
    rt = result.scalar_one_or_none()

    if rt is not None and not rt.is_revoked:
        rt.is_revoked = True
        await db.commit()
        logger.info(f"[Auth] 로그아웃: user_id={rt.user_id}")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """현재 인증된 사용자 정보 반환."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """현재 로그인한 사용자 프로필 업데이트 (인스타그램 계정명 등)."""
    if body.instagram_username is not None:
        current_user.instagram_username = body.instagram_username or None
    elif "instagram_username" in body.model_fields_set:
        current_user.instagram_username = None

    await db.commit()
    await db.refresh(current_user)
    logger.info(f"[Auth] 프로필 업데이트: user_id={current_user.id}, instagram={current_user.instagram_username}")
    return UserResponse.model_validate(current_user)


@router.delete("/me", status_code=204)
async def delete_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """현재 로그인한 사용자 계정을 비활성화하고 개인정보를 삭제한다. 
    단, user_books 등 활동 내역은 CF 통계 분석을 위해 유지한다."""
    # 1. 민감정보 파기 (Anonymization)
    user_id_str = str(current_user.id)
    # unique 제약조건을 피하면서 이메일 정보 파기
    current_user.email = f"deleted_{user_id_str}@deleted.com"
    current_user.name = "탈퇴 사용자"
    current_user.profile_image = None
    current_user.instagram_username = None
    current_user.is_active = False

    # 2. 강제 로그아웃을 위해 모든 Refresh Token 삭제
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == current_user.id))

    # 3. 기타 불필요한 연관 데이터 삭제 (user_books, preference_profile, dismissed_books 제외)
    # GeneratedImage, BookImport, Recommendation 등은 삭제하여 저장공간 확보 및 개인 흔적 제거
    await db.execute(delete(BookImport).where(BookImport.user_id == current_user.id))
    await db.execute(delete(Recommendation).where(Recommendation.user_id == current_user.id))
    await db.execute(delete(GeneratedImage).where(GeneratedImage.user_id == current_user.id))

    await db.commit()
    logger.info(f"[Auth] 사용자 탈퇴 처리 완료 (소프트 삭제): user_id={current_user.id}")
