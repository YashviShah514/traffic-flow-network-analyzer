import warnings

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from . import config

warnings.filterwarnings("ignore", message=".*does \\*not\\* support Decimal.*")


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    url = url or config.database_url()
    if url.startswith("sqlite"):
        kw = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url:
            kw["poolclass"] = StaticPool
        return create_engine(url, **kw)
    return create_engine(url, pool_pre_ping=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
