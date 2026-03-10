
import asyncio
import logging
import sys
import os

# Add the backend directory to sys.path to import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import select, or_
from app.core.database import async_session
from app.models.book import Book
from app.services.aladin import get_book_details, search_books

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def enrich_books():
    async with async_session() as db:
        # Find books with:
        # 1. Corrupted title or author (contains )
        # 2. Missing core info (cover, description, publisher, published_at)
        # AND have an ISBN
        stmt = select(Book).where(
            or_(
                Book.title.like("%%"),
                Book.author.like("%%"),
                Book.cover_image_url == None,
                Book.cover_image_url == "",
                Book.description == None,
                Book.description == "",
                Book.publisher == None,
                Book.publisher == "",
                Book.published_at == None
            )
        ).where(Book.isbn != None).where(Book.isbn != "")
        
        result = await db.execute(stmt)
        books = result.scalars().all()
        
        logger.info(f"Found {len(books)} books to fix/enrich.")
        
        updated_count = 0
        for book in books:
            logger.info(f"Processing: {book.title} (ISBN: {book.isbn})")
            
            # Use ISBN to get clean data (ItemLookUp)
            details = await get_book_details(book.isbn)
            
            # Fallback to search if lookup fails or title still corrupted
            if not details or (not details.title or "" in details.title):
                logger.info(f"  ItemLookUp failed or returned corrupted for {book.isbn}, trying ItemSearch...")
                search_results = await search_books(book.isbn, max_results=1)
                if search_results:
                    details = search_results[0]
            
            if details:
                modified = False
                
                # 1. Fix corrupted title
                if ("" in book.title or not book.title) and details.title and "" not in details.title:
                    logger.info(f"  Fixing title: {book.title} -> {details.title}")
                    book.title = details.title
                    modified = True
                
                # 2. Fix corrupted author
                if ("" in book.author or book.author == "Unknown") and details.author and "" not in details.author:
                    logger.info(f"  Fixing author: {book.author} -> {details.author}")
                    book.author = details.author
                    modified = True
                
                # 3. Fix missing/corrupted cover
                if (not book.cover_image_url or "" in book.cover_image_url) and details.cover_image_url:
                    book.cover_image_url = details.cover_image_url
                    modified = True
                
                # 4. Fix missing/corrupted description
                if (not book.description or "" in book.description) and details.description:
                    book.description = details.description
                    modified = True
                
                # 5. Fix missing/corrupted publisher
                if (not book.publisher or "" in book.publisher) and details.publisher:
                    book.publisher = details.publisher
                    modified = True
                
                # 6. Fix missing published_at
                if not book.published_at and details.published_at:
                    book.published_at = details.published_at
                    modified = True
                
                # 7. Update genre if missing
                if not book.genre and details.genre:
                    book.genre = details.genre
                    modified = True

                if modified:
                    db.add(book)
                    updated_count += 1
                    logger.info(f"  Successfully updated: {book.title}")
                else:
                    logger.info(f"  No better info found for: {book.title}")
            else:
                logger.warning(f"  Could not find any info for: {book.title} (ISBN: {book.isbn})")
            
            # Rate limiting: Aladin API has rate limits
            await asyncio.sleep(0.1)
            
            # Partial commit every 20 records
            if updated_count % 20 == 0 and updated_count > 0:
                await db.commit()
                logger.info(f"--- Committed {updated_count} updates ---")
        
        await db.commit()
        logger.info(f"Enrichment completed. Total updated: {updated_count}")

if __name__ == "__main__":
    asyncio.run(enrich_books())
