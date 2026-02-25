import json
import logging
from typing import List, Any, Dict, Optional
from .base_parser import BaseParser, Chunk

logger = logging.getLogger(__name__)


class ThreadReviewsParser(BaseParser):
    """
    후기 댓글 파서.

    thread_review.json의 각 레코드에서 title, author, text 필드를 직접 사용하여
    "책: {title}\n후기: {text}" 형태의 청크를 생성합니다.
    """

    def __init__(self):
        """후기 파서 초기화."""
        super().__init__(source_name="thread_reviews")

    def parse(self, data: Any) -> List[Chunk]:
        """
        JSON 파일을 청크 리스트로 파싱합니다.

        Args:
            data: 파일 경로 (str) 또는 JSON 데이터 (list/dict)

        Returns:
            Chunk 객체의 리스트
        """
        self.reset_stats()
        chunks = []

        try:
            if isinstance(data, str) and data.endswith(".json"):
                with open(data, "r", encoding="utf-8") as f:
                    json_data = json.load(f)
            else:
                json_data = data

            # 배열 형태: [{cmt_id, post_num, title, author, text, page, created_at}, ...]
            if isinstance(json_data, list):
                for item in json_data:
                    if isinstance(item, dict):
                        chunk = self._parse_record(item)
                        self.parse_stats["total_items"] += 1
                        if chunk:
                            chunks.append(chunk)
                            self.parse_stats["successful_chunks"] += 1
                        else:
                            self.parse_stats["skipped_items"] += 1
            # 딕셔너리 형태: {post_num: [{...}], ...}
            elif isinstance(json_data, dict):
                for post_num, comments in json_data.items():
                    if isinstance(comments, list):
                        for comment in comments:
                            if isinstance(comment, dict):
                                # post_num을 레코드에 주입
                                record = {**comment, "post_num": comment.get("post_num", post_num)}
                                chunk = self._parse_record(record)
                                self.parse_stats["total_items"] += 1
                                if chunk:
                                    chunks.append(chunk)
                                    self.parse_stats["successful_chunks"] += 1
                                else:
                                    self.parse_stats["skipped_items"] += 1

        except json.JSONDecodeError as e:
            logger.error("JSON decode error: %s", e)
            self.parse_stats["failed_items"] += 1
        except Exception as e:
            logger.error("Failed to parse thread_review.json: %s", e)
            self.parse_stats["failed_items"] += 1

        logger.info(
            "ThreadReviews parser: %d chunks / %d items / %d skipped / %d errors",
            self.parse_stats["successful_chunks"],
            self.parse_stats["total_items"],
            self.parse_stats["skipped_items"],
            self.parse_stats["failed_items"],
        )
        return chunks

    def _parse_record(self, record: Dict[str, Any]) -> Optional[Chunk]:
        """
        개별 레코드를 Chunk로 변환합니다.

        Args:
            record: {cmt_id, post_num, title, author, text, page, created_at} 딕셔너리

        Returns:
            Chunk 객체 (title 또는 text가 없으면 None)
        """
        try:
            title = (record.get("title") or "").strip()
            text = (record.get("text") or "").strip()
            author = (record.get("author") or "").strip()
            cmt_id = record.get("cmt_id", "")
            post_num = record.get("post_num", "")
            created_at = record.get("created_at", "")

            if not title or not text:
                return None

            chunk_text = f"책: {title}\n후기: {text}"

            return Chunk(
                text=chunk_text,
                source=self.source_name,
                metadata={
                    "book_title": title,
                    "author": author,
                    "post_num": str(post_num),
                    "cmt_id": str(cmt_id),
                    "created_at": str(created_at),
                },
            )
        except Exception as e:
            logger.debug("Error parsing record: %s", e)
            return None
