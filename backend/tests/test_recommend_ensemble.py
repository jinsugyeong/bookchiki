"""recommend.py CF 앙상블 로직 단위 테스트."""
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.services.recommend import _compute_ensemble_alpha, _apply_cf_ensemble


class TestComputeEnsembleAlpha:
    """_compute_ensemble_alpha 단위 테스트."""

    def test_alpha_under_10_books(self) -> None:
        """서재 < 10권 → α=0.9."""
        assert _compute_ensemble_alpha(0) == 0.9
        assert _compute_ensemble_alpha(5) == 0.9
        assert _compute_ensemble_alpha(9) == 0.9

    def test_alpha_10_to_29_books(self) -> None:
        """서재 10-29권 → α=0.7."""
        assert _compute_ensemble_alpha(10) == 0.7
        assert _compute_ensemble_alpha(20) == 0.7
        assert _compute_ensemble_alpha(29) == 0.7

    def test_alpha_30_or_more_books(self) -> None:
        """서재 >= 30권 → α=0.5."""
        assert _compute_ensemble_alpha(30) == 0.5
        assert _compute_ensemble_alpha(100) == 0.5


class TestApplyCFEnsemble:
    """_apply_cf_ensemble 단위 테스트."""

    @pytest.fixture
    def user_id(self) -> UUID:
        """테스트용 유저 ID."""
        return UUID("00000000-0000-0000-0000-000000000001")

    @pytest.fixture
    def candidates(self) -> list[dict]:
        """테스트용 후보 목록."""
        return [
            {"book_id": "book-001", "title": "책A", "score": 0.9},
            {"book_id": "book-002", "title": "책B", "score": 0.8},
            {"book_id": "book-003", "title": "책C", "score": 0.7},
        ]

    def test_ensemble_without_cf_model_preserves_original(
        self,
        user_id: UUID,
        candidates: list[dict],
    ) -> None:
        """CF 모델 없으면 원본 candidates 순서/점수 그대로."""
        with patch("app.services.recommend.cf_scorer") as mock_scorer:
            mock_scorer.is_available.return_value = False

            result = _apply_cf_ensemble(candidates, user_id, book_count=5)

        assert result == candidates

    def test_ensemble_without_user_mapping_preserves_original(
        self,
        user_id: UUID,
        candidates: list[dict],
    ) -> None:
        """CF 모델 있지만 유저 매핑 없으면 원본 candidates 그대로."""
        with patch("app.services.recommend.cf_scorer") as mock_scorer:
            mock_scorer.is_available.return_value = True
            mock_scorer.get_scores.return_value = {}  # 유저 매핑 없음

            result = _apply_cf_ensemble(candidates, user_id, book_count=5)

        assert result == candidates

    def test_ensemble_reranks_candidates(
        self,
        user_id: UUID,
        candidates: list[dict],
    ) -> None:
        """CF 점수 적용 후 재정렬 확인."""
        # book-003에 높은 CF 점수 → 최종 순위에서 올라와야 함
        cf_scores = {
            "book-001": 0.1,
            "book-002": 0.5,
            "book-003": 1.0,  # CF 점수가 높음
        }
        with patch("app.services.recommend.cf_scorer") as mock_scorer:
            mock_scorer.is_available.return_value = True
            mock_scorer.get_scores.return_value = cf_scores

            # 서재 < 10권 → alpha=0.9 (OpenSearch 점수 위주)
            result = _apply_cf_ensemble(candidates, user_id, book_count=5)

        # alpha=0.9: 0.9*os + 0.1*cf
        # book-001: 0.9*0.9 + 0.1*0.1 = 0.81 + 0.01 = 0.82
        # book-002: 0.9*0.8 + 0.1*0.5 = 0.72 + 0.05 = 0.77
        # book-003: 0.9*0.7 + 0.1*1.0 = 0.63 + 0.10 = 0.73
        assert result[0]["book_id"] == "book-001"
        assert result[1]["book_id"] == "book-002"
        assert result[2]["book_id"] == "book-003"

    def test_ensemble_score_formula(
        self,
        user_id: UUID,
    ) -> None:
        """final_score = alpha * os_score + (1-alpha) * cf_score 공식 검증."""
        candidates = [{"book_id": "book-001", "title": "책A", "score": 0.8}]
        cf_scores = {"book-001": 0.4}

        with patch("app.services.recommend.cf_scorer") as mock_scorer:
            mock_scorer.is_available.return_value = True
            mock_scorer.get_scores.return_value = cf_scores

            # 서재 30권+ → alpha=0.5
            result = _apply_cf_ensemble(candidates, user_id, book_count=30)

        # 0.5 * 0.8 + 0.5 * 0.4 = 0.4 + 0.2 = 0.6
        assert result[0]["score"] == pytest.approx(0.6, abs=1e-4)

    def test_ensemble_partial_cf_coverage(
        self,
        user_id: UUID,
        candidates: list[dict],
    ) -> None:
        """CF 점수가 일부 book만 커버해도 정상 동작."""
        # book-003만 CF 점수 없음 → cf_score=0.0으로 처리
        cf_scores = {
            "book-001": 0.8,
            "book-002": 0.6,
            # book-003 없음
        }
        with patch("app.services.recommend.cf_scorer") as mock_scorer:
            mock_scorer.is_available.return_value = True
            mock_scorer.get_scores.return_value = cf_scores

            result = _apply_cf_ensemble(candidates, user_id, book_count=5)

        # 결과가 3개 모두 포함되어야 함
        result_ids = [r["book_id"] for r in result]
        assert "book-001" in result_ids
        assert "book-002" in result_ids
        assert "book-003" in result_ids

    def test_ensemble_preserves_non_score_fields(
        self,
        user_id: UUID,
    ) -> None:
        """앙상블 후에도 title, author 등 원본 필드 보존."""
        candidates = [
            {"book_id": "book-001", "title": "책A", "author": "저자A", "score": 0.8}
        ]
        cf_scores = {"book-001": 0.5}

        with patch("app.services.recommend.cf_scorer") as mock_scorer:
            mock_scorer.is_available.return_value = True
            mock_scorer.get_scores.return_value = cf_scores

            result = _apply_cf_ensemble(candidates, user_id, book_count=5)

        assert result[0]["title"] == "책A"
        assert result[0]["author"] == "저자A"
