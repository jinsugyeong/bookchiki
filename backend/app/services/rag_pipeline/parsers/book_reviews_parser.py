"""
책 후기 JSON 파서.

/output/book_reviews.json 파일을 파싱하여 책별 리뷰를 청크로 변환합니다.
"""

import json
import logging
from pathlib import Path
from typing import List, Any, Dict
from .base_parser import BaseParser, Chunk

logger = logging.getLogger(__name__)


class BookReviewsParser(BaseParser):
    """
    책 후기 JSON 파서.

    JSON 형식의 책별 리뷰 데이터를 파싱하여 청크로 변환합니다.
    """

    def __init__(self):
        """책 후기 파서 초기화."""
        super().__init__(source_name="reviews")
        self.review_batch_size = 1  # 한 리뷰당 1개 청크, 필요시 2-3개 배치 가능

    def validate(self, data: Any) -> bool:
        """
        입력 데이터의 유효성을 확인합니다.

        Args:
            data: 파일 경로 (str) 또는 JSON 객체 (list/dict)

        Returns:
            유효성 여부
        """
        if isinstance(data, str):
            # 파일 경로인 경우
            if data.endswith(".json"):
                return Path(data).exists()
            return False
        elif isinstance(data, (list, dict)):
            return True
        return False

    def parse(self, data: Any) -> List[Chunk]:
        """
        JSON 파일을 청크로 파싱합니다.

        Args:
            data: 파일 경로 (str) 또는 JSON 데이터 (list/dict)

        Returns:
            Chunk 객체의 리스트
        """
        self.reset_stats()
        chunks = []

        try:
            # 파일 경로인 경우 읽기
            if isinstance(data, str) and data.endswith(".json"):
                with open(data, "r", encoding="utf-8") as f:
                    json_data = json.load(f)
            else:
                json_data = data

            # JSON 배열인 경우 처리
            if isinstance(json_data, list):
                for item in json_data:
                    book_chunks = self._parse_book_item(item)
                    chunks.extend(book_chunks)
            else:
                logger.warning("Expected JSON array, got object")
                self.parse_stats["failed_items"] += 1

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            self.parse_stats["failed_items"] += 1
        except Exception as e:
            logger.error(f"Failed to parse book_reviews.json: {e}")
            self.parse_stats["failed_items"] += 1

        logger.info(
            f"BookReviews parser: {self.parse_stats['successful_chunks']} chunks "
            f"({self.parse_stats['total_items']} items, "
            f"{self.parse_stats['failed_items']} errors)"
        )

        return chunks

    def _parse_book_item(self, item: Dict[str, Any]) -> List[Chunk]:
        """
        개별 책 항목의 리뷰들을 파싱합니다.

        Args:
            item: 책 항목 (title, author, reviews 등)

        Returns:
            Chunk 객체의 리스트
        """
        chunks = []

        try:
            book_title = item.get("title", "Unknown")
            author = item.get("author", "Unknown")
            reviews = item.get("reviews", [])

            self.parse_stats["total_items"] += 1

            # 리뷰가 없으면 스킵
            if not reviews or not isinstance(reviews, list):
                self.parse_stats["skipped_items"] += 1
                return chunks
            

            # 각 리뷰를 개별 청크로 생성
            for review in reviews:
                if isinstance(review, dict):
                    review_text = review.get("text", "")
                    rating = review.get("rating", None)

                    if review_text:
                        chunk_text = self._create_chunk_text(
                            book_title, author, review_text, rating
                        )

                        chunk = Chunk(
                            text=chunk_text,
                            source=self.source_name,
                            metadata={
                                "book_title": book_title,
                                "author": author,
                                "rating": rating,
                                "review_count": len(reviews),
                            },
                        )
                        chunks.append(chunk)
                        self.parse_stats["successful_chunks"] += 1

        except Exception as e:
            logger.debug(f"Error parsing review item: {e}")
            self.parse_stats["failed_items"] += 1

        return chunks

    def _create_chunk_text(
        self, book_title: str, author: str, review_text: str, rating: Any
    ) -> str:
        """
        청크 텍스트를 생성합니다.

        Args:
            book_title: 책 제목
            author: 저자
            review_text: 리뷰 텍스트
            rating: 평점

        Returns:
            청크 텍스트
        """
        rating_str = f" ({rating}점)" if rating else ""
        return f"책: {book_title} by {author}{rating_str}\n리뷰: {review_text}"
