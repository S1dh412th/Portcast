from typing import Iterator

from sqlalchemy.orm import Session

from app.db import session_scope


def get_db() -> Iterator[Session]:
    with session_scope() as db:
        yield db