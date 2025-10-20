import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/scheduler.db")

if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "", 1)
    directory = os.path.dirname(db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


engine = create_engine(DATABASE_URL, future=True, echo=False)

SessionLocal = scoped_session(
    sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )
)


def init_db() -> None:
    """Create database tables if they do not exist."""
    import src.storage.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session() -> Generator:
    """Provide a transactional scope for DB operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
