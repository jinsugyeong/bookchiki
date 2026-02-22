"""
월말결산 마크다운 파서.

/output/monthly_closing_best.md 파일을 파싱하여 월별 순위를 청크로 변환합니다.

실제 파일 포맷:
    # 2025-11
    2025-11          ← 헤더 반복 라인 (무시)
    3 연매장          ← 횟수 책제목
    2 제노사이드
    1 개구리
"""

import logging
import re
from pathlib import Path
from typing import List, Any, Tuple
from .base_parser import BaseParser, Chunk

logger = logging.getLogger(__name__)


class MonthlyClosingParser(BaseParser):
    """
    월말결산 마크다운 파서.

    월별 책 순위와 언급 횟수 데이터를 파싱합니다.
    실제 포맷: # YYYY-MM 헤더 + "횟수 책제목" 라인
    """

    def __init__(self):
        """월말결산 파서 초기화."""
        super().__init__(source_name="monthly_closing")

    def validate(self, data: Any) -> bool:
        """
        입력 데이터의 유효성을 확인합니다.

        Args:
            data: 파일 경로 (str) 또는 파일 내용 (str)

        Returns:
            유효성 여부
        """
        if isinstance(data, str):
            if data.endswith(".md"):
                return Path(data).exists()
            return "##" in data or "#" in data
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
            if isinstance(data, str) and data.endswith(".md"):
                with open(data, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                content = data

            sections = self._split_by_month(content)

            for month, entries in sections:
                if month and entries:
                    chunk_text = self._create_chunk_text(month, entries)
                    chunk = Chunk(
                        text=chunk_text,
                        source=self.source_name,
                        metadata={
                            "month": month,
                            "entry_count": len(entries),
                        },
                    )
                    chunks.append(chunk)
                    self.parse_stats["successful_chunks"] += 1

                self.parse_stats["total_items"] += len(entries)

        except Exception as e:
            logger.error("Failed to parse monthly_closing_best.md: %s", e)
            self.parse_stats["failed_items"] += 1

        logger.info(
            "MonthlyClosed parser: %d chunks (%d items)",
            self.parse_stats["successful_chunks"],
            self.parse_stats["total_items"],
        )

        return chunks

    def _split_by_month(self, content: str) -> List[Tuple[str, List[tuple]]]:
        """
        마크다운 콘텐츠를 월별로 분리합니다.

        실제 포맷: # YYYY-MM 또는 # YYYY년 MM월 헤더

        Args:
            content: 파일 내용

        Returns:
            (month, entries) 튜플의 리스트
        """
        sections = []
        # # 2025-11, # 2025년 1월, # 1월 형식 모두 지원
        pattern = r"^#\s+(\d{4}년\s+\d{1,2}월|[0-9]{4}-[0-9]{2}|[0-9]{1,2}월)\s*$"
        matches = list(re.finditer(pattern, content, re.MULTILINE))

        for i, match in enumerate(matches):
            month = match.group(1).strip()
            start_pos = match.end()

            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start_pos:end_pos]

            entries = self._parse_month_entries(section_content, month)
            sections.append((month, entries))

        return sections

    def _parse_month_entries(self, section_content: str, month: str) -> List[tuple]:
        """
        월 섹션에서 책 항목(횟수 + 제목)을 추출합니다.

        실제 포맷: "횟수 책제목" (예: "3 연매장", "1 개구리")
        헤더 반복 라인(월 문자열만 있는 라인)은 무시합니다.

        Args:
            section_content: 월 섹션 내용
            month: 현재 월 (헤더 반복 라인 제외용)

        Returns:
            (count, book_title) 튜플의 리스트
        """
        entries = []
        lines = section_content.split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 헤더 반복 라인 제외 (예: "2025-11")
            if line == month:
                continue

            # "횟수 책제목" 형식 매칭 (횟수는 1~3자리 숫자)
            match = re.match(r"^(\d{1,3})\s+(.+)$", line)
            if match:
                count = int(match.group(1))
                book_title = match.group(2).strip()
                if book_title:
                    entries.append((count, book_title))
            else:
                # 횟수 없이 제목만 있는 경우 (count=1 기본값)
                if line and not line.isdigit():
                    entries.append((1, line))

        return entries

    def _create_chunk_text(self, month: str, entries: List[tuple]) -> str:
        """
        청크 텍스트를 생성합니다.

        Args:
            month: 월 정보 (예: "2025-11")
            entries: (count, book_title) 튜플의 리스트

        Returns:
            청크 텍스트
        """
        lines = [f"{month} 월말결산 베스트 책:"]

        # 횟수 내림차순 정렬 후 상위 10개
        sorted_entries = sorted(entries, key=lambda x: x[0], reverse=True)
        for rank, (count, book_title) in enumerate(sorted_entries[:10], 1):
            lines.append(f"{rank}. {book_title} ({count}회 언급)")

        return "\n".join(lines)
