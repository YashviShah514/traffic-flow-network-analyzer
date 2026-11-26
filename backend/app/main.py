"""FastAPI application entry point.   Run:  uvicorn app.main:app --reload"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, database, migrations, models  # noqa: F401  (models import registers tables)
from .routers.api import router
from .services.repository import seed_demos

log = logging.getLogger("flowmatrix")


def init_db(engine=None, session_factory=None):
    engine = engine or database.engine
    for change in migrations.upgrade(engine):
        log.warning("database upgraded: %s", change)
    database.Base.metadata.create_all(engine)
    if os.getenv("SEED_DEMOS", "1") != "0":
        with (session_factory or database.SessionLocal)() as db:
            seed_demos(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="FlowMatrix API", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
