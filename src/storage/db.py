from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import DATABASE_URL
from src.storage.models import Base

# check_same_thread only matters for SQLite; harmless to pass otherwise.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def init_db() -> None:
    """Create all tables. Safe to call repeatedly - no-op if they exist."""
    Base.metadata.create_all(engine)

@contextmanager
def get_session():
    """Usage: with get_session() as session: session.add(obj)"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()