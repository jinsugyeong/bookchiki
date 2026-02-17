from datetime import date

import httpx

from app.core.config import settings
from app.schemas.book import BookSearchResult

ALADIN_SEARCH_URL = "http://www.aladin.co.kr/ttb/api/ItemSearch.aspx"


async def search_books(query: str, max_results: int = 20) -> list[BookSearchResult]:
    """Search books via Aladin ItemSearch API."""
    params = {
        "ttbkey": settings.ALADIN_API_KEY,
        "Query": query,
        "QueryType": "Keyword",
        "MaxResults": max_results,
        "start": 1,
        "SearchTarget": "Book",
        "output": "js",
        "Version": "20131101",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(ALADIN_SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    results: list[BookSearchResult] = []
    for item in data.get("item", []):
        published_at = None
        pub_date = item.get("pubDate", "")
        if pub_date:
            try:
                published_at = date.fromisoformat(pub_date)
            except ValueError:
                pass

        isbn = item.get("isbn13") or item.get("isbn") or None

        results.append(
            BookSearchResult(
                title=item.get("title", ""),
                author=item.get("author", ""),
                isbn=isbn,
                description=item.get("description", ""),
                cover_image_url=item.get("cover", ""),
                genre=item.get("categoryName", ""),
                publisher=item.get("publisher", ""),
                published_at=published_at,
            )
        )

    return results
