"""Test fixtures.

By default each test gets a fresh SQLite file. Set TEST_DATABASE_URL to run the very same
tests against PostgreSQL, e.g.
    TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/traffic pytest
(all tables in that database are dropped and recreated for every test)."""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import config, main
from app.database import Base, get_db, make_engine


@pytest.fixture()
def client(tmp_path):
    url = os.getenv("TEST_DATABASE_URL")
    if url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1) if url.startswith("postgresql://") else url
        engine = make_engine(url)
        Base.metadata.drop_all(engine)
    else:
        engine = make_engine(f"sqlite:///{tmp_path / 't.db'}")
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    main.init_db(engine, Session)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override
    c = TestClient(main.app)  # no lifespan: tests use the test DB only
    c.session_factory = Session
    c.dialect = engine.dialect.name
    yield c
    main.app.dependency_overrides.clear()
    engine.dispose()
