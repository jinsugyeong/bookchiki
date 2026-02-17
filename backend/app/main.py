import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, books, user_books, highlights, imports
from app.api.recommendations import router as recommendations_router, search_router, admin_router

# 기본 로깅 레벨을 INFO로 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (dev only; use Alembic migrations in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure OpenSearch index exists
    try:
        from app.opensearch.index import ensure_index
        ensure_index()
    except Exception:
        import logging
        logging.getLogger(__name__).warning("OpenSearch not available — skipping index init")

    yield


app = FastAPI(
    title="Bookchiki API",
    description="독서 기록 + AI 책 추천 서비스",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(books.router, prefix="/api")
app.include_router(user_books.router, prefix="/api")
app.include_router(highlights.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(recommendations_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
