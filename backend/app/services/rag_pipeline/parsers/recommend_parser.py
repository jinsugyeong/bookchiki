"""
추천리스트 마크다운 파서.

/output/recommend.md 파일을 파싱하여 카테고리별 책 추천을 청크로 변환합니다.
"""

import logging
import re
from pathlib import Path
from typing import List, Any
from .base_parser import BaseParser, Chunk

logger = logging.getLogger(__name__)


class RecommendParser(BaseParser):
    """
    추천리스트 마크다운 파서.

    마크다운 헤더(카테고리)와 테이블(책제목 | 추천사) 형식을 파싱합니다.
    """

    def __init__(self):
        """추천리스트 파서 초기화."""
        super().__init__(source_name="recommend")

    def validate(self, data: Any) -> bool:
        """
        입력 데이터의 유효성을 확인합니다.

        Args:
            data: 파일 경로 (str) 또는 파일 내용 (str)

        Returns:
            유효성 여부
        """
        if isinstance(data, str):
            # 파일 경로인 경우
            if data.endswith(".md"):
                return Path(data).exists()
            # 파일 내용인 경우
            return "##" in data or "|" in data
        return False

    def parse(self, data: Any) -> List[Chunk]:
        """
        마크다운 파일을 청크로 파싱합니다.

        Args:
            data: 파일 경로 (str) 또는 파일 내용 (str)

        Returns:
            Chunk 객체의 리스트
        """
        self.reset_stats()
        chunks = []

        try:
            # 파일 경로인 경우 읽기
            if isinstance(data, str) and data.endswith(".md"):
                with open(data, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                content = data

            # 카테고리별 섹션 분리
            sections = self._split_by_category(content)

            for category, section_content in sections:
                # 테이블에서 책과 추천사 추출
                rows = self._parse_table(section_content)

                for book_title, recommendation, count in rows:
                    if book_title and recommendation:
                        chunk_text = self._create_chunk_text(
                            category, book_title, recommendation
                        )

                        chunk = Chunk(
                            text=chunk_text,
                            source=self.source_name,
                            metadata={
                                "category": category,
                                "book_title": book_title,
                                "recommendation_count": count,
                            },
                        )
                        chunks.append(chunk)
                        self.parse_stats["successful_chunks"] += 1
                    else:
                        self.parse_stats["skipped_items"] += 1

                self.parse_stats["total_items"] += len(rows)

        except Exception as e:
            logger.error(f"Failed to parse recommend.md: {e}")
            self.parse_stats["failed_items"] += 1

        logger.info(
            f"Recommend parser: {self.parse_stats['successful_chunks']} chunks "
            f"({self.parse_stats['total_items']} items, "
            f"{self.parse_stats['failed_items']} errors)"
        )

        return chunks

    def _split_by_category(self, content: str) -> List[tuple]:
        """
        마크다운 콘텐츠를 카테고리별로 분리합니다.

        Args:
            content: 파일 내용

        Returns:
            (category, section_content) 튜플의 리스트
        """
        sections = []
        # ## 헤더 기준으로 분리
        pattern = r"^## (.+?)$"
        matches = list(re.finditer(pattern, content, re.MULTILINE))

        for i, match in enumerate(matches):
            category = match.group(1).strip()
            start_pos = match.end()

            # 다음 카테고리 위치 또는 파일 끝
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start_pos:end_pos]

            sections.append((category, section_content))

        return sections

    def _parse_table(self, section_content: str) -> List[tuple]:
        """
        마크다운 테이블을 파싱하여 (책제목, 추천사, 횟수) 추출합니다.

        Args:
            section_content: 섹션 내용

        Returns:
            (book_title, recommendation, count) 튜플의 리스트
        """
        rows = []
        lines = section_content.split("\n")

        # 테이블 시작 찾기
        table_start = -1
        for i, line in enumerate(lines):
            if line.startswith("|") and "책 제목" in line:
                table_start = i + 2  # 헤더 + 구분선 건너뛰기
                break

        if table_start < 0:
            return rows

        # 테이블 행 파싱
        for i in range(table_start, len(lines)):
            line = lines[i].strip()
            if not line.startswith("|") or line == "":
                break

            # 파이프로 분리
            cells = [cell.strip() for cell in line.split("|")[1:-1]]

            if len(cells) >= 2:
                # 첫 번째 셀: "책 제목 (숫자)"
                title_cell = cells[0]
                match = re.match(r"^(.+?)\s*\((\d+)\)\s*$", title_cell)

                if match:
                    book_title = match.group(1).strip()
                    count = int(match.group(2))
                else:
                    book_title = title_cell
                    count = 1

                recommendation = cells[1]
                rows.append((book_title, recommendation, count))

        return rows

    def _create_chunk_text(
        self, category: str, book_title: str, recommendation: str
    ) -> str:
        """
        청크 텍스트를 생성합니다.

        Args:
            category: 카테고리
            book_title: 책 제목
            recommendation: 추천사

        Returns:
            청크 텍스트
        """
        return f"카테고리: {category}\n책 제목: {book_title}\n추천사: {recommendation}"
