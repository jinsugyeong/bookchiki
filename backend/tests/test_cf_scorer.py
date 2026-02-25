"""cf_scorer.py 단위 테스트."""
import json
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

import numpy as np
import pytest

from app.services.cf_scorer import CFScorer


@pytest.fixture
def model_dir(tmp_path: Path) -> Path:
    """임시 모델 디렉토리 픽스처."""
    return tmp_path / "models"


@pytest.fixture
def sample_user_id() -> UUID:
    """테스트용 유저 ID."""
    return UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_book_ids() -> list[str]:
    """테스트용 book_id 목록."""
    return [
        "10000000-0000-0000-0000-000000000001",
        "10000000-0000-0000-0000-000000000002",
        "10000000-0000-0000-0000-000000000003",
    ]


def _write_model_files(
    model_dir: Path,
    user_id: UUID,
    book_ids: list[str],
    factors: int = 4,
) -> tuple[Path, Path]:
    """테스트용 모델 파일 생성."""
    model_dir.mkdir(parents=True, exist_ok=True)

    n_users = 2
    n_items = len(book_ids)
    rng = np.random.default_rng(42)

    user_factors = rng.random((n_users, factors)).astype(np.float32)
    item_factors = rng.random((n_items, factors)).astype(np.float32)

    model_path = model_dir / "cf_model.npz"
    mapping_path = model_dir / "cf_mapping.json"

    np.savez(model_path, user_factors=user_factors, item_factors=item_factors)

    mapping = {
        "user_map": {str(user_id): 0},
        "item_map": {book_id: idx for idx, book_id in enumerate(book_ids)},
        "n_users": n_users,
        "n_items": n_items,
        "factors": factors,
    }
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f)

    return model_path, mapping_path


class TestCFScorerNoModel:
    """모델 파일 없을 때 동작 테스트."""

    def test_is_not_available(self, model_dir: Path) -> None:
        """모델 파일 없으면 is_available()은 False."""
        scorer = CFScorer.__new__(CFScorer)
        scorer._user_factors = None
        scorer._item_factors = None
        scorer._user_map = {}
        scorer._item_map = {}
        scorer._loaded = False

        assert scorer.is_available() is False

    def test_get_scores_returns_empty_when_not_loaded(self, sample_user_id: UUID, sample_book_ids: list[str]) -> None:
        """모델 미로드 시 get_scores()는 빈 dict 반환."""
        scorer = CFScorer.__new__(CFScorer)
        scorer._user_factors = None
        scorer._item_factors = None
        scorer._user_map = {}
        scorer._item_map = {}
        scorer._loaded = False

        result = scorer.get_scores(sample_user_id, sample_book_ids)

        assert result == {}


class TestCFScorerWithModel:
    """모델 파일 있을 때 동작 테스트."""

    def _make_scorer(
        self,
        model_dir: Path,
        user_id: UUID,
        book_ids: list[str],
    ) -> CFScorer:
        """모델 파일을 만들고 CFScorer를 초기화."""
        model_path, mapping_path = _write_model_files(model_dir, user_id, book_ids)

        # CFScorer를 임시 경로에서 로드하도록 패치
        scorer = CFScorer.__new__(CFScorer)
        scorer._user_factors = None
        scorer._item_factors = None
        scorer._user_map = {}
        scorer._item_map = {}
        scorer._loaded = False

        # 모델 파일 직접 로드
        data = np.load(model_path)
        scorer._user_factors = data["user_factors"]
        scorer._item_factors = data["item_factors"]

        with open(mapping_path, encoding="utf-8") as f:
            mapping = json.load(f)

        scorer._user_map = {str(k): int(v) for k, v in mapping["user_map"].items()}
        scorer._item_map = {str(k): int(v) for k, v in mapping["item_map"].items()}
        scorer._loaded = True

        return scorer

    def test_is_available_with_model(
        self,
        model_dir: Path,
        sample_user_id: UUID,
        sample_book_ids: list[str],
    ) -> None:
        """모델 파일 있으면 is_available()은 True."""
        scorer = self._make_scorer(model_dir, sample_user_id, sample_book_ids)
        assert scorer.is_available() is True

    def test_get_scores_returns_normalized_scores(
        self,
        model_dir: Path,
        sample_user_id: UUID,
        sample_book_ids: list[str],
    ) -> None:
        """get_scores() 반환값이 0.0~1.0 범위인지 확인."""
        scorer = self._make_scorer(model_dir, sample_user_id, sample_book_ids)
        scores = scorer.get_scores(sample_user_id, sample_book_ids)

        assert len(scores) == len(sample_book_ids)
        for book_id in sample_book_ids:
            assert book_id in scores
            assert 0.0 <= scores[book_id] <= 1.0

    def test_get_scores_unknown_user_returns_empty(
        self,
        model_dir: Path,
        sample_user_id: UUID,
        sample_book_ids: list[str],
    ) -> None:
        """매핑에 없는 user_id → 빈 dict 반환."""
        scorer = self._make_scorer(model_dir, sample_user_id, sample_book_ids)
        unknown_user = uuid4()

        result = scorer.get_scores(unknown_user, sample_book_ids)

        assert result == {}

    def test_get_scores_unknown_books_filtered(
        self,
        model_dir: Path,
        sample_user_id: UUID,
        sample_book_ids: list[str],
    ) -> None:
        """매핑에 없는 book_id는 결과에서 제외."""
        scorer = self._make_scorer(model_dir, sample_user_id, sample_book_ids)
        unknown_book = "ffffffff-ffff-ffff-ffff-ffffffffffff"

        result = scorer.get_scores(sample_user_id, [sample_book_ids[0], unknown_book])

        assert sample_book_ids[0] in result
        assert unknown_book not in result

    def test_get_scores_min_max_normalization(
        self,
        model_dir: Path,
        sample_user_id: UUID,
        sample_book_ids: list[str],
    ) -> None:
        """min-max 정규화: 최솟값=0.0, 최댓값=1.0."""
        scorer = self._make_scorer(model_dir, sample_user_id, sample_book_ids)
        scores = scorer.get_scores(sample_user_id, sample_book_ids)

        if len(scores) >= 2:
            values = list(scores.values())
            assert min(values) == pytest.approx(0.0, abs=1e-4)
            assert max(values) == pytest.approx(1.0, abs=1e-4)

    def test_reload_model_clears_state_when_file_missing(
        self,
        model_dir: Path,
        sample_user_id: UUID,
        sample_book_ids: list[str],
    ) -> None:
        """reload_model() 호출 후 파일이 없으면 _loaded=False로 초기화."""
        scorer = self._make_scorer(model_dir, sample_user_id, sample_book_ids)
        assert scorer.is_available() is True

        # 존재하지 않는 경로로 패치 후 reload_model() 실제 호출
        import app.services.cf_scorer as cf_module
        from unittest.mock import patch

        with (
            patch.object(cf_module, "CF_MODEL_PATH", model_dir / "nonexistent.npz"),
            patch.object(cf_module, "CF_MAPPING_PATH", model_dir / "nonexistent.json"),
        ):
            scorer.reload_model()

        assert scorer.is_available() is False

    def test_reload_model_restores_state_when_file_exists(
        self,
        model_dir: Path,
        sample_user_id: UUID,
        sample_book_ids: list[str],
    ) -> None:
        """reload_model() 후 파일이 있으면 _loaded=True로 복원."""
        model_path, mapping_path = _write_model_files(model_dir, sample_user_id, sample_book_ids)

        scorer = self._make_scorer(model_dir, sample_user_id, sample_book_ids)
        # 상태를 강제로 초기화 후 reload_model 호출
        scorer._loaded = False
        scorer._user_factors = None

        import app.services.cf_scorer as cf_module
        from unittest.mock import patch

        with (
            patch.object(cf_module, "CF_MODEL_PATH", model_path),
            patch.object(cf_module, "CF_MAPPING_PATH", mapping_path),
        ):
            scorer.reload_model()

        assert scorer.is_available() is True
