from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UniqueWord(Base):
    __tablename__ = "unique_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)


class ParagraphWord(Base):
    __tablename__ = "paragraph_words"
    __table_args__ = (
        UniqueConstraint("unique_word_id", "paragraph_id", name="uq_paragraph_words_unique_word_paragraph"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unique_word_id: Mapped[int] = mapped_column(ForeignKey("unique_words.id"), nullable=False, index=True)
    paragraph_id: Mapped[int] = mapped_column(ForeignKey("paragraphs.id"), nullable=False, index=True)
