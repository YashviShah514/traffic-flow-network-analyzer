"""FastAPI application entry point.   Run:  uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, database, models  # noqa: F401  (models import registers tables)
from .routers.api import router
from .services.repository import seed_demos


def init_db(engine=None, session_factory=None):
    engine = engine or database.engine
    database.Base.metadata.create_all(engine)
    with (session_factory or database.SessionLocal)() as db:
        seed_demos(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Traffic Flow Network Analyzer API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
