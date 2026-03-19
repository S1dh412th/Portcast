from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings

Base = declarative_base()

_ENGINE: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None
_POST_COMMIT_HOOKS_KEY = "post_commit_hooks"


def add_post_commit_hook(session: Session, hook: Callable[[], None]) -> None:
    """Register a callback to run only after the surrounding transaction commits."""
    hooks = session.info.setdefault(_POST_COMMIT_HOOKS_KEY, [])
    hooks.append(hook)


def reset_db() -> None:
    """Reset database connections (mainly for testing)."""
    global _ENGINE, _SessionLocal
    if _ENGINE:
        _ENGINE.dispose()
    _ENGINE = None
    _SessionLocal = None


def get_engine() -> Engine:
    """Get or create the database engine."""
    global _ENGINE
    if _ENGINE is None:
        try:
            url = settings.database.url
            _ENGINE = create_engine(
                url,
                echo=settings.database.echo,
                connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create database engine: {e}") from e
    return _ENGINE


def get_sessionmaker() -> sessionmaker[Session]:
    """Get or create the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        try:
            _SessionLocal = sessionmaker(
                bind=get_engine(),
                autoflush=False,
                autocommit=False,
                class_=Session,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create session factory: {e}") from e
    return _SessionLocal


def init_db() -> None:
    """Initialize the database by creating all tables."""
    try:
        from app import models  # noqa: F401
        Base.metadata.create_all(bind=get_engine())
    except SQLAlchemyError as e:
        raise RuntimeError(f"Failed to initialize database: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error during database initialization: {e}") from e


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for database sessions with automatic commit/rollback."""
    session = None
    try:
        session = get_sessionmaker()()
        yield session
        session.commit()
        hooks = session.info.pop(_POST_COMMIT_HOOKS_KEY, [])
        for hook in hooks:
            try:
                hook()
            except Exception:
                pass
    except SQLAlchemyError as e:
        if session:
            session.info.pop(_POST_COMMIT_HOOKS_KEY, None)
            session.rollback()
        raise RuntimeError(f"Database session error: {e}") from e
    except Exception as e:
        if session:
            session.info.pop(_POST_COMMIT_HOOKS_KEY, None)
            session.rollback()
        raise RuntimeError(f"Unexpected error in database session: {e}") from e
    finally:
        if session:
            session.close()