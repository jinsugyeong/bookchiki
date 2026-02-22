import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import auth, books, user_books, highlights, imports
from app.api.recommendations import router as recommendations_router, admin_router

# 기본 로깅 레벨을 INFO로 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB 스키마는 Alembic 마이그레이션으로 관리 (startup에서 create_all 하지 않음)
    logger.info("Bookchiki API starting up")

    # Ensure OpenSearch indexes exist
    try:
        from app.opensearch.index import ensure_knowledge_index
        ensure_knowledge_index()
        logger.info("OpenSearch rag_knowledge index ready")
    except Exception as e:
        logger.warning(f"OpenSearch not available — skipping index init: {e}")

    yield

    logger.info("Bookchiki API shutting down")


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

app.include_router(auth.router)
app.include_router(books.router)
app.include_router(user_books.router)
app.include_router(highlights.router)
app.include_router(imports.router)
app.include_router(recommendations_router)
app.include_router(admin_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
