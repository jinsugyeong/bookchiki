"""Reset database: drop all tables and recreate them. Also reset OpenSearch index."""
import asyncio

from app.core.database import engine, Base
from app.models import *  # noqa: F401,F403 — ensure all models are imported
from app.opensearch.client import os_client
from app.opensearch.index import INDEX_NAME, ensure_index


def reset_opensearch():
    try:
        if os_client.indices.exists(index=INDEX_NAME):
            os_client.indices.delete(index=INDEX_NAME)
            print(f"Deleted OpenSearch index '{INDEX_NAME}'.")
        ensure_index()
        print(f"Recreated OpenSearch index '{INDEX_NAME}'.")
    except Exception as e:
        print(f"OpenSearch reset failed (may not be running): {e}")


async def reset():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        print("Dropped all tables.")
        await conn.run_sync(Base.metadata.create_all)
        print("Recreated all tables.")
    await engine.dispose()

    reset_opensearch()


if __name__ == "__main__":
    asyncio.run(reset())
