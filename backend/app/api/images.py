"""AI 배경 이미지 생성 API."""

import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.generated_image import GeneratedImage
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["images"])

# 유저당 하루 최대 AI 생성 횟수
DAILY_LIMIT = 3
AI_BG_STYLE = "ai_background"


class GenerateBackgroundRequest(BaseModel):
    """AI 배경 생성 요청."""
    book_id: UUID
    title: str
    author: str
    genre: str | None = None
    description: str | None = None


class GenerateBackgroundResponse(BaseModel):
    """AI 배경 생성 응답."""
    image_url: str
    remaining_today: int


class DailyRemainingResponse(BaseModel):
    """오늘 남은 AI 생성 횟수."""
    remaining: int
    limit: int


def _build_prompt(title: str, author: str, genre: str | None, description: str | None) -> str:
    """책 정보를 바탕으로 DALL-E 프롬프트 생성."""
    genre_hint = f"Genre: {genre}. " if genre else ""
    desc_hint = f"Inspired by: {description[:100]}. " if description else ""

    return (
        f"Create a beautiful, atmospheric background image for a bookstagram post. "
        f"Book: '{title}' by {author}. "
        f"{genre_hint}{desc_hint}"
        "Style: abstract, painterly, cinematic mood. "
        "Soft bokeh, dreamy texture, moody color palette fitting the book's atmosphere. "
        "NO text, NO words, NO book covers, NO human figures. "
        "Pure atmospheric background, suitable for overlaying text. "
        "High quality, aesthetic, Instagram-worthy."
    )


async def _count_today_generations(db: AsyncSession, user_id: UUID) -> int:
    """오늘 UTC 기준 AI 배경 생성 횟수 조회."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(GeneratedImage.id)).where(
            GeneratedImage.user_id == user_id,
            GeneratedImage.style == AI_BG_STYLE,
            GeneratedImage.created_at >= today_start,
        )
    )
    return result.scalar() or 0


@router.get("/daily-remaining", response_model=DailyRemainingResponse)
async def get_daily_remaining(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """오늘 남은 AI 배경 생성 횟수 조회."""
    used = await _count_today_generations(db, current_user.id)
    return DailyRemainingResponse(remaining=max(0, DAILY_LIMIT - used), limit=DAILY_LIMIT)


@router.post("/generate-background", response_model=GenerateBackgroundResponse)
async def generate_background(
    body: GenerateBackgroundRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """DALL-E 3으로 책 분위기 AI 배경 이미지 생성.
    유저당 하루 최대 3회 제한.
    """
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API 키가 설정되지 않았습니다.")

    # 일일 한도 체크
    used = await _count_today_generations(db, current_user.id)
    if used >= DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"오늘의 AI 생성 횟수({DAILY_LIMIT}회)를 모두 사용했습니다. 내일 다시 시도해주세요.",
        )

    prompt = _build_prompt(body.title, body.author, body.genre, body.description)
    logger.info(f"[AI 배경] user={current_user.id} book={body.book_id} prompt_len={len(prompt)}")

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
    except Exception as e:
        logger.error(f"[AI 배경] DALL-E 3 호출 실패: {e}")
        raise HTTPException(status_code=502, detail="이미지 생성에 실패했습니다. 잠시 후 다시 시도해주세요.")

    # 생성 기록 저장 (일일 한도 추적용)
    record = GeneratedImage(
        user_id=current_user.id,
        book_id=body.book_id,
        image_url=image_url,
        style=AI_BG_STYLE,
        prompt_used=prompt,
    )
    db.add(record)
    await db.commit()

    remaining = max(0, DAILY_LIMIT - used - 1)
    logger.info(f"[AI 배경] 생성 완료. user={current_user.id} remaining={remaining}")

    return GenerateBackgroundResponse(image_url=image_url, remaining_today=remaining)
