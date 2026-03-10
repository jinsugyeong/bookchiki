from datetime import date
import httpx
import logging

from app.core.config import settings
from app.schemas.book import BookSearchResult

logger = logging.getLogger(__name__)

ALADIN_SEARCH_URL = "http://www.aladin.co.kr/ttb/api/ItemSearch.aspx"
ALADIN_LOOKUP_URL = "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"


async def search_books(query: str, max_results: int = 20) -> list[BookSearchResult]:
    """Search books via Aladin ItemSearch API."""
    params = {
        "ttbkey": settings.ALADIN_API_KEY,
        "Query": query,
        "QueryType": "Keyword",
        "MaxResults": max_results,
        "start": 1,
        "SearchTarget": "All",
        "output": "js",
        "Version": "20131101",
        "Cover": "Big",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(ALADIN_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("Aladin ItemSearch failed for query '%s': %s", query, e)
            return []

    _ALLOWED_MALL_TYPES = {"BOOK", "EBOOK"}

    results: list[BookSearchResult] = []
    for item in data.get("item", []):
        if item.get("mallType") not in _ALLOWED_MALL_TYPES:
            continue
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


async def get_book_details(isbn: str) -> BookSearchResult | None:
    """Fetch book details via Aladin ItemLookUp API using ISBN."""
    params = {
        "ttbkey": settings.ALADIN_API_KEY,
        "ItemId": isbn,
        "ItemIdType": "ISBN13",
        "output": "js",
        "Version": "20131101",
        "Cover": "Big",
        "OptResult": "description,fullSentence,story,ratingInfo,bestSeller",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(ALADIN_LOOKUP_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("Aladin ItemLookUp failed for ISBN %s: %s", isbn, e)
            return None

    items = data.get("item", [])
    if not items:
        # Try ISBN10 if ISBN13 failed
        params["ItemIdType"] = "ISBN"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(ALADIN_LOOKUP_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
                items = data.get("item", [])
            except Exception:
                return None

    if not items:
        return None

    item = items[0]
    published_at = None
    pub_date = item.get("pubDate", "")
    if pub_date:
        try:
            published_at = date.fromisoformat(pub_date)
        except ValueError:
            pass

    return BookSearchResult(
        title=item.get("title", ""),
        author=item.get("author", ""),
        isbn=item.get("isbn13") or item.get("isbn") or isbn,
        description=item.get("description", ""),
        cover_image_url=item.get("cover", ""),
        genre=item.get("categoryName", ""),
        publisher=item.get("publisher", ""),
        published_at=published_at,
    )
