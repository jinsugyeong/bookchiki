"""CF(Collaborative Filtering) 점수 조회 서비스 — 싱글톤 패턴.

ALS 모델 파일(backend/models/cf_model.npz + cf_mapping.json)을 로드하고,
후보 도서 목록에 대한 CF 점수를 반환한다.

모델 파일이 없거나 유저가 매핑에 없으면 빈 dict를 반환 (graceful degradation).
"""

import json
import logging
from pathlib import Path
from uuid import UUID

import numpy as np

logger = logging.getLogger(__name__)

# backend/ 디렉토리 기준 모델 경로
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = _BACKEND_DIR / "models"
CF_MODEL_PATH = MODEL_DIR / "cf_model.npz"
CF_MAPPING_PATH = MODEL_DIR / "cf_mapping.json"


class CFScorer:
    """ALS CF 모델 싱글톤. 모델 파일 없으면 graceful degradation."""

    def __init__(self) -> None:
        """모델 파일 로드 시도."""
        self._user_factors: np.ndarray | None = None
        self._item_factors: np.ndarray | None = None
        self._user_map: dict[str, int] = {}   # user_id_str → row_idx
        self._item_map: dict[str, int] = {}   # book_id_str → col_idx
        self._loaded = False
        self._try_load()

    def _try_load(self) -> None:
        """모델 파일 로드. 파일 없거나 손상된 경우 로그만 남기고 넘어감."""
        if not CF_MODEL_PATH.exists() or not CF_MAPPING_PATH.exists():
            logger.info(
                "[cf_scorer] 모델 파일 없음 → graceful degradation (OpenSearch만 사용). "
                "학습하려면: python scripts/train_cf.py"
            )
            return

        try:
            data = np.load(CF_MODEL_PATH)
            self._user_factors = data["user_factors"]
            self._item_factors = data["item_factors"]

            with open(CF_MAPPING_PATH, encoding="utf-8") as f:
                mapping = json.load(f)

            self._user_map = {str(k): int(v) for k, v in mapping["user_map"].items()}
            self._item_map = {str(k): int(v) for k, v in mapping["item_map"].items()}
            self._loaded = True

            logger.info(
                "[cf_scorer] 모델 로드 완료: users=%d items=%d factors=%d",
                self._user_factors.shape[0],
                self._item_factors.shape[0],
                self._item_factors.shape[1],
            )
        except Exception:
            logger.exception("[cf_scorer] 모델 파일 로드 실패 → graceful degradation")
            self._user_factors = None
            self._item_factors = None
            self._user_map = {}
            self._item_map = {}
            self._loaded = False

    def is_available(self) -> bool:
        """모델 로드 여부."""
        return self._loaded

    def get_scores(
        self,
        user_id: UUID,
        candidate_book_ids: list[str],
    ) -> dict[str, float]:
        """후보 도서에 대한 CF 점수 반환 (0.0~1.0 min-max 정규화).

        Args:
            user_id: 유저 UUID
            candidate_book_ids: 점수를 계산할 book_id 문자열 리스트

        Returns:
            {book_id: cf_score} — 모델 없거나 유저 미등록이면 빈 dict
        """
        if not self._loaded:
            return {}

        user_key = str(user_id)
        user_idx = self._user_map.get(user_key)
        if user_idx is None:
            logger.debug("[cf_scorer] 유저 매핑 없음: %s → 빈 점수 반환", user_key)
            return {}

        user_vec = self._user_factors[user_idx]  # (factors,)

        scores: dict[str, float] = {}
        raw_scores: list[tuple[str, float]] = []

        for book_id in candidate_book_ids:
            item_idx = self._item_map.get(book_id)
            if item_idx is None:
                continue
            item_vec = self._item_factors[item_idx]  # (factors,)
            raw_score = float(np.dot(user_vec, item_vec))
            raw_scores.append((book_id, raw_score))

        if not raw_scores:
            return {}

        # min-max 정규화 (0.0~1.0)
        values = [s for _, s in raw_scores]
        min_val, max_val = min(values), max(values)
        score_range = max_val - min_val

        for book_id, raw_score in raw_scores:
            if score_range > 0:
                normalized = (raw_score - min_val) / score_range
            else:
                normalized = 0.5  # 모든 점수가 같으면 중간값
            scores[book_id] = round(normalized, 4)

        logger.debug(
            "[cf_scorer] 점수 계산: user=%s candidates=%d matched=%d",
            user_id,
            len(candidate_book_ids),
            len(scores),
        )
        return scores

    def reload_model(self) -> None:
        """모델 파일 핫 리로드 (재학습 후 프로세스 재시작 없이 적용)."""
        logger.info("[cf_scorer] 모델 리로드 시작")
        self._user_factors = None
        self._item_factors = None
        self._user_map = {}
        self._item_map = {}
        self._loaded = False
        self._try_load()


# 싱글톤 인스턴스
cf_scorer = CFScorer()
