import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from src.api.api import api_router
from src.rag.vector_store import refresh_periodically

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Keep the in-memory knowledge base fresh while the API is up."""
    refresher = asyncio.create_task(refresh_periodically())
    try:
        yield
    finally:
        refresher.cancel()


app = FastAPI(lifespan=lifespan)

app.include_router(api_router, prefix="/api")
