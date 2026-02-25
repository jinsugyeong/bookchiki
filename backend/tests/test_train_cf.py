"""train_cf.py 단위 테스트."""
import sys
from pathlib import Path

import pytest

# scripts 디렉토리를 sys.path에 추가
# Docker: .:/project 마운트 → /project/scripts
# 로컬: backend/../scripts
BACKEND_DIR = Path(__file__).resolve().parent.parent
for _candidate in [
    Path("/project/scripts"),       # Docker (.:/project 마운트)
    BACKEND_DIR / "scripts",        # 구 Docker (./scripts:/app/scripts 마운트)
    BACKEND_DIR.parent / "scripts", # 로컬 개발
]:
    if _candidate.exists():
        sys.path.insert(0, str(_candidate))
        break

from train_cf import (
    _normalize_title,
    build_real_interactions,
    build_sparse_matrix,
    build_synthetic_interactions,
)


class TestNormalizeTitle:
    """_normalize_title 단위 테스트."""

    def test_removes_whitespace(self) -> None:
        """공백 제거."""
        assert _normalize_title("자기앞의 생") == "자기앞의생"

    def test_removes_special_chars(self) -> None:
        """특수문자 제거."""
        assert _normalize_title("[책제목]") == "책제목"
        assert _normalize_title("책 : 제목") == "책제목"

    def test_lowercases(self) -> None:
        """소문자 변환."""
        assert _normalize_title("Harry Potter") == "harrypotter"

    def test_empty_string(self) -> None:
        """빈 문자열 처리."""
        assert _normalize_title("") == ""


class TestBuildSyntheticInteractions:
    """build_synthetic_interactions 단위 테스트."""

    def test_groups_by_post_num(self) -> None:
        """같은 post_num의 책들이 같은 synthetic user로 그룹핑."""
        reviews = [
            {"post_num": "1", "title": "책A"},
            {"post_num": "1", "title": "책B"},
            {"post_num": "2", "title": "책C"},
        ]
        title_map = {
            "책a": "book-001",
            "책b": "book-002",
            "책c": "book-003",
        }

        interactions, match_count, total = build_synthetic_interactions(reviews, title_map)

        user_keys = {i[0] for i in interactions}
        assert "syn_1" in user_keys
        assert "syn_2" in user_keys
        assert match_count == 3
        assert total == 3

    def test_confidence_is_1(self) -> None:
        """synthetic user의 confidence는 1.0 (binary implicit)."""
        reviews = [{"post_num": "1", "title": "책A"}]
        title_map = {"책a": "book-001"}

        interactions, _, _ = build_synthetic_interactions(reviews, title_map)

        assert interactions[0][2] == 1.0

    def test_unmatched_titles_excluded(self) -> None:
        """매핑 실패 제목은 상호작용에서 제외. title_map 키는 정규화된 형태."""
        reviews = [
            {"post_num": "1", "title": "없는 책"},   # 공백 포함 → 정규화 시 "없는책"
            {"post_num": "1", "title": "있는 책"},   # 공백 포함 → 정규화 시 "있는책"
        ]
        # title_map 키는 _normalize_title 적용 후 형태
        title_map = {"있는책": "book-001"}

        interactions, match_count, total = build_synthetic_interactions(reviews, title_map)

        assert len(interactions) == 1
        assert match_count == 1
        assert total == 2

    def test_empty_post_num_skipped(self) -> None:
        """빈 post_num은 스킵."""
        reviews = [{"post_num": "", "title": "책A"}]
        title_map = {"책a": "book-001"}

        interactions, _, total = build_synthetic_interactions(reviews, title_map)

        assert len(interactions) == 0
        assert total == 0


class TestBuildRealInteractions:
    """build_real_interactions 단위 테스트."""

    def test_rating_based_confidence(self) -> None:
        """평점 있으면 confidence = rating / 5.0."""
        db_rows = [{"user_id": "user-1", "book_id": "book-1", "rating": 5}]

        interactions = build_real_interactions(db_rows)

        assert interactions[0][2] == pytest.approx(1.0)

    def test_no_rating_confidence_half(self) -> None:
        """평점 없으면 confidence = 0.5."""
        db_rows = [{"user_id": "user-1", "book_id": "book-1", "rating": None}]

        interactions = build_real_interactions(db_rows)

        assert interactions[0][2] == 0.5

    def test_user_key_prefix(self) -> None:
        """real user key는 'real_' prefix."""
        db_rows = [{"user_id": "abc123", "book_id": "book-1", "rating": 3}]

        interactions = build_real_interactions(db_rows)

        assert interactions[0][0] == "real_abc123"

    def test_empty_input(self) -> None:
        """빈 입력 → 빈 결과."""
        assert build_real_interactions([]) == []


class TestBuildSparseMatrix:
    """build_sparse_matrix 단위 테스트."""

    def test_correct_shape(self) -> None:
        """행렬 shape: n_unique_users × n_unique_items."""
        interactions = [
            ("user-1", "book-1", 1.0),
            ("user-1", "book-2", 0.8),
            ("user-2", "book-1", 0.5),
        ]

        matrix, user_map, item_map = build_sparse_matrix(interactions)

        assert matrix.shape == (2, 2)
        assert len(user_map) == 2
        assert len(item_map) == 2

    def test_user_item_mapping(self) -> None:
        """user_map/item_map 인덱스 일관성."""
        interactions = [
            ("user-A", "item-X", 1.0),
            ("user-B", "item-Y", 0.5),
        ]

        matrix, user_map, item_map = build_sparse_matrix(interactions)

        # user_A의 item_X 위치에 값이 있어야 함
        u_idx = user_map["user-A"]
        i_idx = item_map["item-X"]
        assert matrix[u_idx, i_idx] == pytest.approx(1.0)

    def test_empty_input(self) -> None:
        """빈 입력 → shape (0, 0)."""
        matrix, user_map, item_map = build_sparse_matrix([])

        assert matrix.shape == (0, 0)
        assert user_map == {}
        assert item_map == {}

    def test_confidence_values_stored(self) -> None:
        """confidence 값이 행렬에 정확히 저장됨."""
        interactions = [("user-1", "book-1", 0.75)]

        matrix, user_map, item_map = build_sparse_matrix(interactions)

        u_idx = user_map["user-1"]
        i_idx = item_map["book-1"]
        assert matrix[u_idx, i_idx] == pytest.approx(0.75)
