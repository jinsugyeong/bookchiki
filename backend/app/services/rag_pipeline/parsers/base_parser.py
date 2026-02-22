"""
기본 Parser 인터페이스 및 Chunk 데이터 모델.

이 모듈은 모든 파서가 구현해야 하는 추상 인터페이스를 정의합니다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class Chunk:
    """RAG 파이프라인에서 사용하는 기본 청크 데이터 모델."""

    text: str
    """청크의 실제 텍스트 내용"""

    source: str
    """데이터 소스 (recommend, reviews, monthly_closing, thread_reviews)"""

    metadata: Dict[str, Any]
    """소스별 메타데이터 (book_title, category, author 등)"""

    created_at: Optional[datetime] = None
    """청크 생성 시간"""

    chunk_id: Optional[str] = None
    """내용 기반 SHA256 해시 (OpenSearch 중복 제거용)"""


class BaseParser(ABC):
    """
    모든 파서의 추상 기본 클래스.

    각 데이터 소스별 파서는 이 클래스를 상속하고
    parse() 메서드를 구현해야 합니다.
    """

    def __init__(self, source_name: str):
        """
        파서 초기화.

        Args:
            source_name: 데이터 소스 이름 (recommend, reviews 등)
        """
        self.source_name = source_name
        self.parse_stats = {
            "total_items": 0,
            "successful_chunks": 0,
            "failed_items": 0,
            "skipped_items": 0,
        }

    @abstractmethod
    def parse(self, data: Any) -> List[Chunk]:
        """
        원본 데이터를 청크 리스트로 변환합니다.

        Args:
            data: 파서에 따라 다른 입력 형식
                  (파일 경로, 파일 내용, JSON 객체 등)

        Returns:
            Chunk 객체의 리스트

        Raises:
            ValueError: 데이터 형식 오류 시
        """
        pass

    @abstractmethod
    def validate(self, data: Any) -> bool:
        """
        입력 데이터의 유효성을 확인합니다.

        Args:
            data: 검증할 데이터

        Returns:
            유효성 여부
        """
        pass

    def get_stats(self) -> Dict[str, int]:
        """파싱 통계를 반환합니다."""
        return self.parse_stats.copy()

    def reset_stats(self):
        """파싱 통계를 초기화합니다."""
        self.parse_stats = {
            "total_items": 0,
            "successful_chunks": 0,
            "failed_items": 0,
            "skipped_items": 0,
        }
