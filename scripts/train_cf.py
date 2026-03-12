"""ALS 기반 Collaborative Filtering 모델 오프라인 학습.

thread_review.json(synthetic user) + DB user_books(real user)로
scipy sparse 행렬을 구성하고, implicit ALS 모델을 학습하여
backend/models/ 에 저장한다.

사용법:
    # Docker 컨테이너 내부에서 실행 (권장, /project 마운트 기준)
    docker compose exec -w /project backend python scripts/train_cf.py

    # 호스트에서 직접 실행 (DB가 localhost:5432인 경우)
    python scripts/train_cf.py
    python scripts/train_cf.py --factors 64 --iterations 20
"""

import argparse
import asyncio
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# 경로 상수
THREAD_REVIEW_PATH = PROJECT_ROOT / "output" / "thread_review.json"
MODEL_DIR = PROJECT_ROOT / "backend" / "models"
CF_MODEL_PATH = MODEL_DIR / "cf_model.npz"
CF_MAPPING_PATH = MODEL_DIR / "cf_mapping.json"
SYNTHETIC_CACHE_PATH = MODEL_DIR / "synthetic_interactions.json"


def _get_db_url() -> str:
    """DATABASE_URL에서 asyncpg DSN을 추출."""
    from app.core.config import settings

    url = settings.DATABASE_URL
    # postgresql+asyncpg:// → postgresql://
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return url


def _normalize_title(title: str) -> str:
    """제목 정규화: 소문자 변환 + 특수문자/공백 제거."""
    import re

    return re.sub(r"[\s\-_·:：\[\]()（）「」『』<>《》「」]+", "", title).lower()


def load_thread_reviews() -> list[dict]:
    """thread_review.json 로드.

    Returns:
        [{"post_num": str, "title": str}, ...]
    """
    if not THREAD_REVIEW_PATH.exists():
        logger.warning("[train_cf] thread_review.json 없음: %s (Synthetic 데이터 없이 진행)", THREAD_REVIEW_PATH)
        return []

    with open(THREAD_REVIEW_PATH, encoding="utf-8") as f:
        data = json.load(f)

    logger.info("[train_cf] thread_review.json 로드: %d개 레코드", len(data))
    return data


async def load_db_data(fetch_books: bool = True) -> tuple[dict[str, str], list[dict]]:
    """단일 DB 연결로 books와 user_books를 순차 조회.

    Returns:
        (title_to_book_id, user_books)
        - title_to_book_id: {normalized_title: book_id_str}
        - user_books: [{"user_id": str, "book_id": str, "rating": int|None}, ...]
    """
    import asyncpg

    db_url = _get_db_url()
    conn = await asyncpg.connect(db_url)
    try:
        book_rows = []
        if fetch_books:
            book_rows = await conn.fetch("SELECT id::text, title FROM books")
        ub_rows = await conn.fetch(
            "SELECT user_id::text, book_id::text, rating FROM user_books"
        )
    finally:
        await conn.close()

    title_to_book_id: dict[str, str] = {}
    for row in book_rows:
        normalized = _normalize_title(row["title"])
        title_to_book_id[normalized] = row["id"]

    user_books = [
        {"user_id": row["user_id"], "book_id": row["book_id"], "rating": row["rating"]}
        for row in ub_rows
    ]

    logger.info("[train_cf] DB books 로드: %d권", len(title_to_book_id))
    logger.info("[train_cf] DB user_books 로드: %d개 상호작용", len(user_books))
    return title_to_book_id, user_books


def build_synthetic_interactions(
    thread_reviews: list[dict],
    title_to_book_id: dict[str, str],
) -> tuple[list[tuple[str, str, float]], int, int]:
    """thread_review 데이터에서 synthetic user 상호작용 생성.

    같은 post_num = 한 게시글에 언급된 책 = 비슷한 취향 독자 그룹.

    Args:
        thread_reviews: thread_review.json 레코드 리스트
        title_to_book_id: normalized_title → book_id 매핑

    Returns:
        (interactions, match_count, total_count)
        interactions: [(synthetic_user_id, book_id, confidence), ...]
    """
    # post_num 그룹별 책 목록 수집
    post_books: dict[str, set[str]] = defaultdict(set)
    total_count = 0
    match_count = 0

    for record in thread_reviews:
        post_num = record.get("post_num", "")
        title = record.get("title", "").strip()
        if not post_num or not title:
            continue

        total_count += 1
        normalized = _normalize_title(title)
        book_id = title_to_book_id.get(normalized)

        if book_id:
            post_books[post_num].add(book_id)
            match_count += 1
        else:
            logger.debug("[train_cf] 매핑 실패: '%s' (normalized: '%s')", title, normalized)

    logger.info(
        "[train_cf] Synthetic 매핑 결과: %d/%d개 제목 매핑 성공 (%.1f%%)",
        match_count,
        total_count,
        (match_count / total_count * 100) if total_count > 0 else 0,
    )

    interactions: list[tuple[str, str, float]] = []
    for post_num, book_ids in post_books.items():
        user_key = f"syn_{post_num}"
        for book_id in book_ids:
            # binary implicit signal (confidence=1.0)
            interactions.append((user_key, book_id, 1.0))

    logger.info(
        "[train_cf] Synthetic users: %d명, 상호작용: %d개",
        len(post_books),
        len(interactions),
    )
    return interactions, match_count, total_count


def save_synthetic_cache(interactions: list[tuple[str, str, float]]) -> None:
    """synthetic interactions 캐시 저장."""
    try:
        with open(SYNTHETIC_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(interactions, f)
        logger.info("[train_cf] Synthetic 캐시 저장: %s", SYNTHETIC_CACHE_PATH)
    except Exception as e:
        logger.warning("[train_cf] 캐시 저장 실패: %s", e)


def load_synthetic_cache() -> list[tuple[str, str, float]] | None:
    """캐시된 synthetic interactions 로드."""
    if not SYNTHETIC_CACHE_PATH.exists():
        return None

    # thread_review.json 변경 시 캐시 무효화
    if THREAD_REVIEW_PATH.exists() and SYNTHETIC_CACHE_PATH.stat().st_mtime < THREAD_REVIEW_PATH.stat().st_mtime:
        logger.info("[train_cf] thread_review.json 변경됨 → 캐시 무시")
        return None

    try:
        with open(SYNTHETIC_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("[train_cf] Synthetic 캐시 로드: %d개 상호작용", len(data))
        # JSON loads list of lists, convert to list of tuples
        return [(item[0], item[1], float(item[2])) for item in data]
    except Exception as e:
        logger.warning("[train_cf] 캐시 로드 실패: %s", e)
        return None


def build_real_interactions(
    db_user_books: list[dict],
) -> list[tuple[str, str, float]]:
    """DB user_books에서 real user 상호작용 변환.

    confidence = rating/5.0 (있으면) or 0.5 (없으면)

    Returns:
        [(real_user_key, book_id, confidence), ...]
    """
    interactions: list[tuple[str, str, float]] = []
    for ub in db_user_books:
        user_key = f"real_{ub['user_id']}"
        book_id = ub["book_id"]
        rating = ub.get("rating")
        confidence = (rating / 5.0) if rating else 0.5
        interactions.append((user_key, book_id, confidence))

    logger.info("[train_cf] Real user 상호작용: %d개", len(interactions))
    return interactions


def build_sparse_matrix(
    all_interactions: list[tuple[str, str, float]],
) -> tuple[csr_matrix, dict[str, int], dict[str, int]]:
    """user × item sparse 행렬 구성.

    Args:
        all_interactions: [(user_key, book_id, confidence), ...]

    Returns:
        (matrix, user_map, item_map)
        - user_map: user_key → row_idx
        - item_map: book_id → col_idx
    """
    # 유니크 user/item 수집 (순서 보존)
    user_set: dict[str, int] = {}
    item_set: dict[str, int] = {}

    for user_key, book_id, _ in all_interactions:
        if user_key not in user_set:
            user_set[user_key] = len(user_set)
        if book_id not in item_set:
            item_set[book_id] = len(item_set)

    n_users = len(user_set)
    n_items = len(item_set)

    rows, cols, data = [], [], []
    for user_key, book_id, confidence in all_interactions:
        rows.append(user_set[user_key])
        cols.append(item_set[book_id])
        data.append(confidence)

    matrix = csr_matrix((data, (rows, cols)), shape=(n_users, n_items))

    total_cells = n_users * n_items
    density = (len(data) / total_cells * 100) if total_cells > 0 else 0
    logger.info(
        "[train_cf] Sparse 행렬: users=%d items=%d nnz=%d density=%.3f%%",
        n_users,
        n_items,
        len(data),
        density,
    )
    return matrix, user_set, item_set


def train_and_save(
    matrix: csr_matrix,
    user_map: dict[str, int],
    item_map: dict[str, int],
    factors: int = 64,
    iterations: int = 20,
    regularization: float = 0.1,
) -> None:
    """ALS 학습 후 모델/매핑 파일 저장.

    Args:
        matrix: user × item sparse 행렬
        user_map: user_key → row_idx
        item_map: book_id → col_idx
        factors: ALS 잠재 요인 수
        iterations: ALS 반복 횟수
        regularization: ALS 정규화 계수
    """
    from implicit.als import AlternatingLeastSquares

    logger.info(
        "[train_cf] ALS 학습 시작: factors=%d iterations=%d regularization=%.2f",
        factors,
        iterations,
        regularization,
    )

    model = AlternatingLeastSquares(
        factors=factors,
        iterations=iterations,
        regularization=regularization,
        use_gpu=False,
    )
    # implicit 0.7.x는 user × item 행렬을 입력받음 (전치 불필요)
    # user_factors.shape = (n_users, factors), item_factors.shape = (n_items, factors)
    model.fit(matrix.tocsr(), show_progress=True)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # user_factors, item_factors 저장
    np.savez(
        CF_MODEL_PATH,
        user_factors=model.user_factors,
        item_factors=model.item_factors,
    )

    # user/item 인덱스 매핑 저장 (real user만 — scorer가 사용)
    real_user_map = {
        key.replace("real_", ""): idx
        for key, idx in user_map.items()
        if key.startswith("real_")
    }

    mapping = {
        "user_map": real_user_map,   # {user_id_str: row_idx}
        "item_map": item_map,        # {book_id_str: col_idx}
        "n_users": len(user_map),
        "n_items": len(item_map),
        "factors": factors,
    }
    with open(CF_MAPPING_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    logger.info(
        "[train_cf] 모델 저장 완료: %s (%.1f KB)",
        CF_MODEL_PATH,
        CF_MODEL_PATH.stat().st_size / 1024,
    )
    logger.info("[train_cf] 매핑 저장 완료: real_users=%d items=%d", len(real_user_map), len(item_map))


async def _main_async(factors: int, iterations: int, regularization: float = 0.1, use_cache: bool = True) -> None:
    """비동기 메인 실행."""
    synthetic_interactions = None

    if use_cache:
        synthetic_interactions = load_synthetic_cache()

    # 1. 데이터 로드 (캐시 있으면 books 로드 생략)
    need_books = synthetic_interactions is None
    title_to_book_id, db_user_books = await load_db_data(fetch_books=need_books)

    # 2. Synthetic 상호작용 생성 (캐시 없으면)
    if synthetic_interactions is None:
        thread_reviews = load_thread_reviews()
        synthetic_interactions, match_count, total_count = build_synthetic_interactions(
            thread_reviews, title_to_book_id
        )
        if total_count > 0 and match_count / total_count < 0.3:
            logger.warning(
                "[train_cf] 매핑률이 낮습니다 (%.1f%%). books 인덱싱 여부를 확인하세요.",
                match_count / total_count * 100,
            )
        save_synthetic_cache(synthetic_interactions)

    # 3. Real 상호작용 변환
    real_interactions = build_real_interactions(db_user_books)

    # 4. 전체 상호작용 합산
    all_interactions = synthetic_interactions + real_interactions
    if not all_interactions:
        logger.error("[train_cf] 학습 데이터가 없습니다. 종료.")
        sys.exit(1)

    # 5. Sparse 행렬 구성
    matrix, user_map, item_map = build_sparse_matrix(all_interactions)

    # 6. ALS 학습 + 저장
    train_and_save(matrix, user_map, item_map, factors=factors, iterations=iterations, regularization=regularization)
    logger.info("[train_cf] === 학습 완료 ===")


def main() -> None:
    """스크립트 진입점."""
    parser = argparse.ArgumentParser(description="CF ALS 모델 학습")
    parser.add_argument("--factors", type=int, default=64, help="ALS 잠재 요인 수 (기본값: 64)")
    parser.add_argument("--iterations", type=int, default=20, help="ALS 반복 횟수 (기본값: 20)")
    parser.add_argument("--regularization", type=float, default=0.1, help="ALS 정규화 계수 (기본값: 0.1)")
    parser.add_argument("--no-cache", action="store_true", help="Synthetic 캐시 사용 안 함 (강제 재계산)")
    args = parser.parse_args()

    asyncio.run(_main_async(args.factors, args.iterations, args.regularization, use_cache=not args.no_cache))


if __name__ == "__main__":
    main()
