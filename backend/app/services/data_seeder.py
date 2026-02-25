"""
데이터에서 책 제목을 추출하여 books DB에 시딩.

파이프라인:
  1. 파서별 book_title 추출 + 파서 내 퍼지 중복 제거
  2. 전체 합산 후 크로스-파서 퍼지 중복 제거
  3. DB 기존 책 필터링 (알라딘 API 호출 절약)
  4. 알라딘 실존 검증 → books DB 저장
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.services.aladin import search_books as aladin_search
from app.services.rag_pipeline.parsers.recommend_parser import RecommendParser
from app.services.rag_pipeline.parsers.book_reviews_parser import BookReviewsParser
from app.services.rag_pipeline.parsers.monthly_closing_parser import MonthlyClosingParser
from app.services.rag_pipeline.parsers.thread_reviews_parser import ThreadReviewsParser

logger = logging.getLogger(__name__)

# 알라딘 검증 설정
_FUZZY_THRESHOLD = 0.7            # 알라딘 결과 매칭 유사도 임계값
_ALADIN_MAX_RESULTS = 1           # 검증용 알라딘 검색 결과 수
_SEMAPHORE_LIMIT = 2              # 동시 알라딘 API 요청 제한 (rate limit 방지)
_REQUEST_DELAY = 0.4              # 요청 간 딜레이 (초)
_RETRY_DELAY = 2.0                # rate limit 감지 시 재시도 딜레이 (초)

# 제목 퍼지 중복 제거 설정
_TITLE_DEDUP_THRESHOLD = 0.90     # 제목 간 유사도 임계값

# Book 모델 컬럼 길이 제한
_MAX_TITLE = 500
_MAX_AUTHOR = 1000
_MAX_GENRE = 500
_MAX_COVER_URL = 500

# 소스별 파일명 매핑
SOURCE_FILES = {
    "recommend": "recommend.md",
    "reviews": "book_reviews.json",
    "monthly_closing": "monthly_closing_best.md",
    "thread_reviews": "thread_review.json",
}

# 로그 파일 경로 (output 볼륨에 저장 → 로컬에서 바로 확인 가능)
_LOG_FILE = Path("/app/output/data_seeder.log")


def _setup_file_logger() -> None:
    """data_seeder 전용 파일 로거 설정.

    /app/output/data_seeder.log 에 DEBUG 레벨로 기록.
    중복 핸들러 방지: FileHandler가 이미 있으면 스킵.
    """
    if any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        return
    try:
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
        )
        logger.addHandler(fh)
        logger.setLevel(logging.DEBUG)
    except Exception as e:
        logger.warning("[data-seeder] 파일 로거 설정 실패: %s", e)


_setup_file_logger()


@dataclass
class DataSeedResult:
    """데이터 시딩 결과."""
    total: int = 0       # 알라딘 검증 대상 고유 제목 수
    seeded: int = 0      # DB에 새로 저장된 책 수
    skipped: int = 0     # 이미 존재하거나 검증 실패한 책 수
    errors: int = 0      # 에러 발생 수


# 알라딘 부제 패턴: '제목 - 부제', '제목 : 부제', '제목 – 부제'
_ALADIN_SUBTITLE_RE = re.compile(r'\s+[-–:]\s+.+$')
# 알라딘 부가정보 패턴: '제목 (15만부 기념 특별판)'
_ALADIN_PAREN_RE = re.compile(r'\s+\([^)]+\)\s*$')


def _strip_aladin_subtitle(title: str) -> str:
    """알라딘 제목에서 부제/부가정보 제거.

    '제목 - 부제', '제목 : 부제', '제목 (특별판)' 형식을 처리합니다.
    """
    t = _ALADIN_PAREN_RE.sub('', title.strip())
    t = _ALADIN_SUBTITLE_RE.sub('', t.strip())
    return t.strip()


def _normalize_title(t: str) -> str:
    """유사도 비교용 정규화: 소문자 변환 + 공백 전체 제거."""
    return re.sub(r'\s+', '', t.strip().lower())


def _title_similarity(query: str, aladin_title: str) -> float:
    """쿼리와 알라딘 제목 간 유사도 계산 (0.0 ~ 1.0).

    알라딘은 ' - 부제' 또는 ' (특별판)' 형태를 자주 붙이므로
    부제 제거 버전과도 비교하고, prefix 매칭을 적용합니다.

    전략:
    1. prefix 체크: 알라딘 제목(공백 제거)이 쿼리로 시작하면 동일 도서
       - '5번레인' vs '5번레인-...' → 1.0
       - 오매칭 방지: 최소 3글자 이상에서만 적용
    2. 부제 제거 버전 vs full 버전 중 높은 유사도 선택
    """
    q_norm = _normalize_title(query)
    a_full_norm = _normalize_title(aladin_title)
    a_stripped_norm = _normalize_title(_strip_aladin_subtitle(aladin_title))

    # prefix 체크: 쿼리가 알라딘 제목의 앞부분과 정확히 일치
    if len(q_norm) >= 3 and (
        a_full_norm.startswith(q_norm)
        or a_stripped_norm == q_norm
    ):
        return 1.0

    # 부제 제거 버전과 full 버전 중 높은 유사도
    return max(
        SequenceMatcher(None, q_norm, a_full_norm).ratio(),
        SequenceMatcher(None, q_norm, a_stripped_norm).ratio(),
    )


def _clean_title(title: str) -> str:
    """제목 정제: 불필요한 요소 제거.

    처리 규칙:
    1. 앞뒤 따옴표 제거  ("컬렉터처럼, 아트투어" → 컬렉터처럼, 아트투어)
    2. 작가 소개 형식 필터 (책들 (...) 포함 → 빈 문자열 반환)
    3. ' -저자' 형식 저자 제거  (전국축제자랑 -김혼비, 박태하 → 전국축제자랑)
    4. '시리즈' 접미사 제거  (헝거게임 시리즈 → 헝거게임)
    5. 시리즈 번호+부제 제거  (2666 1. 비평가들에 대하여 → 2666)

    Returns:
        정제된 제목. 필터 대상이면 빈 문자열 반환.
    """
    t = title.strip()

    # 1. 앞뒤 따옴표 제거
    t = re.sub(r'^[\u201c\u201d"\u2018\u2019\']+|[\u201c\u201d"\u2018\u2019\']+$', '', t).strip()

    # 2. 작가 소개 형식 필터 (프레드릭 배크만 책들 (할머니가... 등))
    if re.search(r'책들?\s*\(', t):
        logger.debug("[clean] 작가소개 필터: '%s'", title)
        return ''

    # 3. ' -저자' 형식 저자 제거 (공백+하이픈+공백없이 한글 바로) → "전국축제자랑 -김혼비"
    t = re.sub(r'\s+-[가-힣][\w,\s가-힣]*$', '', t).strip()

    # 4. '시리즈' 접미사 제거
    t = re.sub(r'\s*시리즈\s*$', '', t).strip()

    # 5. 시리즈 번호+부제 제거 ("2666 1. 비평가들에 대하여" → "2666")
    t = re.sub(r'^(.+?)\s+\d+[.부]\s+.+$', r'\1', t).strip()

    return t


def _fuzzy_deduplicate_titles(titles: set[str]) -> set[str]:
    """유사한 제목 퍼지 중복 제거.

    짧은 제목(더 간결한 형태)을 우선 보존합니다.
    비교 전략:
    - 공백 제거 후 유사도 비교 ("회색 인간" == "회색인간")
    - prefix 체크 ("헝거게임 노래하는..." → "헝거게임"의 중복으로 처리)
    - "(숫자)" 횟수 표기 무시
    """
    def normalize(t: str) -> str:
        """공백 제거 + 횟수 표기 제거 (유사도 비교용)."""
        t = t.strip().lower()
        t = re.sub(r'\s*\(\d+\)\s*$', '', t)   # "(숫자)" 제거
        t = re.sub(r'\s+', '', t)               # 모든 공백 제거
        return t

    def spaced(t: str) -> str:
        """공백 정규화 (prefix 체크용)."""
        return ' '.join(t.strip().lower().split())

    sorted_titles = sorted(titles, key=len)  # 짧은 제목 우선
    kept: list[str] = []
    kept_norm: list[str] = []   # 공백 없는 정규화
    kept_spaced: list[str] = [] # 공백 포함 정규화
    removed = 0

    for title in sorted_titles:
        norm = normalize(title)
        sp = spaced(title)

        is_dup = False
        for kn, ks in zip(kept_norm, kept_spaced):
            if (
                SequenceMatcher(None, norm, kn).ratio() >= _TITLE_DEDUP_THRESHOLD
                or sp.startswith(ks + ' ')   # "헝거게임 노래하는..." ⊃ "헝거게임"
                or ks.startswith(sp + ' ')
            ):
                is_dup = True
                break

        if is_dup:
            removed += 1
            logger.debug("[dedup] 중복 제거: '%s'", title)
        else:
            kept.append(title)
            kept_norm.append(norm)
            kept_spaced.append(sp)

    if removed > 0:
        logger.info(
            "[dedup] 퍼지 중복 제거: %d개 제거 (%d → %d)",
            removed, len(titles), len(kept),
        )
    return set(kept)


def _extract_titles_per_parser(data_dir: Path) -> dict[str, set[str]]:
    """파서별 book_title 추출 후 파서 내 퍼지 중복 제거.

    Returns:
        source_name → 중복 제거된 제목 집합
    """
    parsers = {
        "recommend": RecommendParser(),
        "reviews": BookReviewsParser(),
        "monthly_closing": MonthlyClosingParser(),
        "thread_reviews": ThreadReviewsParser(),
    }

    per_parser: dict[str, set[str]] = {}

    for source_name, parser in parsers.items():
        file_name = SOURCE_FILES.get(source_name)
        if not file_name:
            continue

        file_path = data_dir / file_name
        if not file_path.exists():
            logger.warning("[extract] File not found: %s", file_path)
            continue

        try:
            chunks = parser.parse(str(file_path))
            raw: set[str] = set()
            for chunk in chunks:
                title = chunk.metadata.get("book_title", "").strip()
                cleaned = _clean_title(title) if title else ''
                if cleaned:
                    raw.add(cleaned)

            # 파서 내 퍼지 중복 제거
            deduped = _fuzzy_deduplicate_titles(raw)
            per_parser[source_name] = deduped
            logger.info(
                "[extract] %s: raw=%d → dedup=%d",
                source_name, len(raw), len(deduped),
            )
        except Exception as e:
            logger.error("[extract] Failed to parse %s: %s", source_name, e)

    return per_parser


def _merge_titles(per_parser: dict[str, set[str]]) -> set[str]:
    """파서별 제목을 합산하고 크로스-파서 퍼지 중복 제거.

    Returns:
        최종 고유 제목 집합
    """
    merged: set[str] = set()
    for titles in per_parser.values():
        merged |= titles

    logger.info("[merge] 전체 합산: %d개", len(merged))
    return _fuzzy_deduplicate_titles(merged)


async def _validate_and_fetch(title: str, semaphore: asyncio.Semaphore):
    """알라딘에서 제목을 검색하여 유사도 기준 검증된 책 반환.

    rate limit 대응: 요청 간 딜레이 + 빈 결과 시 1회 재시도.

    Returns:
        알라딘 BookSearchResult 또는 None
    """
    async with semaphore:
        await asyncio.sleep(_REQUEST_DELAY)
        logger.info("[aladin] → 검색 요청: '%s'", title)
        try:
            results = await aladin_search(title, max_results=_ALADIN_MAX_RESULTS)

            # 빈 결과 → rate limit 가능성, 1회 재시도
            if not results:
                logger.info("[aladin] ⚠ 결과없음 (재시도 대기 %.1fs): '%s'", _RETRY_DELAY, title)
                await asyncio.sleep(_RETRY_DELAY)
                results = await aladin_search(title, max_results=_ALADIN_MAX_RESULTS)

            if not results:
                logger.info("[aladin] ✗ 결과없음: '%s'", title)
                return None

            best = results[0]
            similarity = _title_similarity(title, best.title)

            if similarity >= _FUZZY_THRESHOLD:
                logger.info(
                    "[aladin] ✓ 검증 통과: '%s' → '%s' (sim=%.2f)",
                    title, best.title, similarity,
                )
                return best

            logger.info(
                "[aladin] ✗ 유사도 탈락: '%s' → '%s' (sim=%.2f < %.2f)",
                title, best.title, similarity, _FUZZY_THRESHOLD,
            )
        except Exception as e:
            logger.warning("[aladin] ✗ API 오류: '%s' — %s", title, e)

    return None


async def seed_books_from_data(
    db: AsyncSession,
    data_dir: Path = Path("/app/output"),
) -> DataSeedResult:
    """데이터에서 책을 추출하여 books DB에 시딩.

    Args:
        db: 비동기 DB 세션
        data_dir: 데이터 파일 경로

    Returns:
        DataSeedResult (total, seeded, skipped, errors)
    """
    logger.info("=" * 60)
    logger.info("[seed] 데이터 시딩 시작  (log: %s)", _LOG_FILE)
    logger.info("=" * 60)

    result = DataSeedResult()

    # 1단계: 파서별 추출 + 파서 내 중복 제거
    per_parser = _extract_titles_per_parser(data_dir)

    # 2단계: 전체 합산 + 크로스-파서 중복 제거
    titles = _merge_titles(per_parser)
    logger.info("[seed] 크로스-파서 중복 제거 후: %d개", len(titles))

    if not titles:
        logger.warning("[seed] 추출된 제목 없음 — 종료")
        return result

    # 3단계: DB 기존 책 조회 → 사전 필터링 (알라딘 API 호출 절약)
    all_books_result = await db.execute(select(Book))
    all_books = all_books_result.scalars().all()
    existing_isbns: set[str] = {b.isbn for b in all_books if b.isbn}
    existing_title_author: set[tuple[str, str]] = {
        (b.title.strip().lower(), (b.author or "").strip().lower())
        for b in all_books
    }
    existing_titles_lower: set[str] = {t for t, _ in existing_title_author}
    logger.info("[seed] 현재 DB 책 수: %d권", len(all_books))

    titles_to_validate = {
        title for title in titles
        if title.strip().lower() not in existing_titles_lower
    }
    pre_filtered = len(titles) - len(titles_to_validate)
    result.total = len(titles_to_validate)

    if pre_filtered > 0:
        logger.info(
            "[seed] DB 중복 사전 필터링: %d개 제외, 알라딘 검증 대상: %d개",
            pre_filtered, len(titles_to_validate),
        )

    if not titles_to_validate:
        logger.info("[seed] 신규 검증 대상 없음 — 종료")
        result.skipped += pre_filtered
        return result

    # 알라딘 검증 목록 파일에 기록
    logger.info("[seed] ─── 알라딘 검증 목록 (%d개) ───", len(titles_to_validate))
    for i, t in enumerate(sorted(titles_to_validate), 1):
        logger.info("[seed] %4d. %s", i, t)
    logger.info("[seed] ─────────────────────────────────")

    # 4단계: 알라딘 실존 검증
    semaphore = asyncio.Semaphore(_SEMAPHORE_LIMIT)
    validation_tasks = [_validate_and_fetch(title, semaphore) for title in titles_to_validate]
    validated_items = await asyncio.gather(*validation_tasks, return_exceptions=True)

    # 5단계: 검증 통과한 책 DB 저장
    logger.info("[seed] ─── DB 저장 단계 ───")
    for item in validated_items:
        if isinstance(item, Exception):
            logger.warning("[save] 예외 발생 (skipped): %s", item)
            result.errors += 1
            continue

        if item is None:
            result.skipped += 1
            continue

        # ISBN 중복 체크
        if item.isbn and item.isbn in existing_isbns:
            logger.info("[save] ✗ ISBN 중복: '%s' (isbn=%s)", item.title, item.isbn)
            result.skipped += 1
            continue

        # 제목+저자 중복 체크
        title_key = (item.title.strip().lower(), (item.author or "").strip().lower())
        if title_key in existing_title_author:
            logger.info("[save] ✗ 제목+저자 중복: '%s' / %s", item.title, item.author)
            result.skipped += 1
            continue

        try:
            book = Book(
                title=(item.title or "")[:_MAX_TITLE],
                author=(item.author or "")[:_MAX_AUTHOR],
                isbn=item.isbn,
                description=item.description,
                cover_image_url=(item.cover_image_url or "")[:_MAX_COVER_URL],
                genre=(item.genre or "")[:_MAX_GENRE],
                published_at=item.published_at,
            )
            db.add(book)
            await db.flush()

            if item.isbn:
                existing_isbns.add(item.isbn)
            existing_title_author.add(title_key)

            result.seeded += 1
            logger.info("[save] ✓ 저장 완료: '%s' / %s", item.title, item.author)

        except Exception as e:
            logger.error("[save] ✗ DB 저장 실패: '%s' — %s", item.title, e)
            result.errors += 1

    if result.seeded > 0:
        await db.commit()

    result.skipped += pre_filtered

    logger.info("=" * 60)
    logger.info(
        "[seed] 완료: total=%d  seeded=%d  skipped=%d  errors=%d",
        result.total, result.seeded, result.skipped, result.errors,
    )
    logger.info("=" * 60)
    return result
