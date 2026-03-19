from __future__ import annotations

import respx
from httpx import Response

from app.db import get_sessionmaker, init_db
from app.models import Paragraph, ParagraphWord, UniqueWord
from app.schemas import SearchResponse
from app.services.paragraph import (
    _get_or_create_unique_word_id,
    _index_paragraph_words,
    search_paragraphs,
)


def _setup_db():
    init_db()
    return get_sessionmaker()


def test_get_or_create_unique_word_creates_new() -> None:
    sm = _setup_db()
    with sm() as session:
        word_id = _get_or_create_unique_word_id(session, "testword")
        session.commit()
        assert isinstance(word_id, int)
        assert word_id > 0


def test_get_or_create_unique_word_returns_existing() -> None:
    sm = _setup_db()
    with sm() as session:
        id1 = _get_or_create_unique_word_id(session, "duplicate")
        session.commit()
    with sm() as session:
        id2 = _get_or_create_unique_word_id(session, "duplicate")
        session.commit()
        assert id1 == id2


def test_index_paragraph_words_creates_mappings() -> None:
    sm = _setup_db()
    with sm() as session:
        p = Paragraph(text="alpha beta gamma")
        session.add(p)
        session.flush()
        _index_paragraph_words(session, p.id, p.text)
        session.commit()

        # Verify unique words were created
        from sqlalchemy import select
        words = set(session.execute(select(UniqueWord.word)).scalars())
        assert "alpha" in words
        assert "beta" in words
        assert "gamma" in words

        # Verify paragraph-word links exist
        links = list(
            session.execute(
                select(ParagraphWord).where(ParagraphWord.paragraph_id == p.id)
            ).scalars()
        )
        assert len(links) == 3


def test_index_paragraph_words_empty_text() -> None:
    sm = _setup_db()
    with sm() as session:
        p = Paragraph(text="123 456")  # no alpha words
        session.add(p)
        session.flush()
        _index_paragraph_words(session, p.id, p.text)
        session.commit()

        from sqlalchemy import select
        links = list(
            session.execute(
                select(ParagraphWord).where(ParagraphWord.paragraph_id == p.id)
            ).scalars()
        )
        assert len(links) == 0


def test_index_paragraph_words_no_duplicate_links() -> None:
    sm = _setup_db()
    with sm() as session:
        p = Paragraph(text="word word word")
        session.add(p)
        session.flush()
        _index_paragraph_words(session, p.id, p.text)
        session.commit()

        from sqlalchemy import select
        links = list(
            session.execute(
                select(ParagraphWord).where(ParagraphWord.paragraph_id == p.id)
            ).scalars()
        )
        # "word" appears 3 times but should only create 1 link
        assert len(links) == 1


def test_search_paragraphs_or() -> None:
    sm = _setup_db()
    with sm() as session:
        p1 = Paragraph(text="cat dog")
        p2 = Paragraph(text="cat fish")
        p3 = Paragraph(text="bird fish")
        session.add_all([p1, p2, p3])
        session.flush()
        _index_paragraph_words(session, p1.id, p1.text)
        _index_paragraph_words(session, p2.id, p2.text)
        _index_paragraph_words(session, p3.id, p3.text)
        session.commit()

        result = search_paragraphs(["dog", "fish"], "or", session)
        assert result.count == 3  # p1 has dog, p2 has fish+cat, p3 has fish


def test_search_paragraphs_and() -> None:
    sm = _setup_db()
    with sm() as session:
        p1 = Paragraph(text="cat dog")
        p2 = Paragraph(text="cat fish")
        p3 = Paragraph(text="bird fish")
        session.add_all([p1, p2, p3])
        session.flush()
        _index_paragraph_words(session, p1.id, p1.text)
        _index_paragraph_words(session, p2.id, p2.text)
        _index_paragraph_words(session, p3.id, p3.text)
        session.commit()

        result = search_paragraphs(["cat", "fish"], "and", session)
        assert result.count == 1  # only p2 has both
        assert "cat fish" in result.results[0].text


def test_search_paragraphs_empty_words() -> None:
    sm = _setup_db()
    with sm() as session:
        result = search_paragraphs([], "or", session)
        assert result.count == 0
        assert result.results == []


def test_search_paragraphs_no_results() -> None:
    sm = _setup_db()
    with sm() as session:
        p = Paragraph(text="hello world")
        session.add(p)
        session.flush()
        _index_paragraph_words(session, p.id, p.text)
        session.commit()

        result = search_paragraphs(["nonexistent"], "or", session)
        assert result.count == 0


def test_search_paragraphs_case_insensitive() -> None:
    sm = _setup_db()
    with sm() as session:
        p = Paragraph(text="Hello World")
        session.add(p)
        session.flush()
        _index_paragraph_words(session, p.id, p.text)
        session.commit()

        result = search_paragraphs(["HELLO"], "or", session)
        assert result.count == 1


def test_search_paragraphs_order_desc() -> None:
    sm = _setup_db()
    with sm() as session:
        p1 = Paragraph(text="shared word")
        p2 = Paragraph(text="shared phrase")
        session.add_all([p1, p2])
        session.flush()
        _index_paragraph_words(session, p1.id, p1.text)
        _index_paragraph_words(session, p2.id, p2.text)
        session.commit()

        result = search_paragraphs(["shared"], "or", session)
        assert result.count == 2
        # Results should be in descending id order (newest first)
        assert result.results[0].id > result.results[1].id
