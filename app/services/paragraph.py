from __future__ import annotations

import asyncio
from collections import Counter
from typing import Literal

from sqlalchemy import distinct, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import add_post_commit_hook
from app.models import Paragraph, ParagraphWord, UniqueWord
from app.schemas import DictionaryEntry, DictionaryResponse, ParagraphOut, SearchResponse
from app.services.cache import cache
from app.services.dictionary import fetch_definition
from app.services.metaphorpsum import fetch_paragraph
from app.services.text import extract_words, extract_word_counts, normalize_word


_BACKGROUND_TASK_SEMAPHORE = asyncio.Semaphore(8)


def _get_or_create_unique_word_id(db: Session, word: str) -> int:
    """Get an existing unique-word id or create it safely under concurrent inserts."""
    existing_id = db.execute(select(UniqueWord.id).where(UniqueWord.word == word)).scalar_one_or_none()
    if existing_id is not None:
        return existing_id

    candidate = UniqueWord(word=word)
    try:
        with db.begin_nested():
            db.add(candidate)
            db.flush()
            return candidate.id
    except IntegrityError:
        # Another transaction inserted the same word first.
        pass

    # Handle race condition
    existing_id = db.execute(select(UniqueWord.id).where(UniqueWord.word == word)).scalar_one_or_none()
    if existing_id is None:
        raise RuntimeError(f"Failed to resolve unique word id for '{word}'")
    return existing_id


def _index_paragraph_words(db: Session, paragraph_id: int, text: str) -> None:
    """Populate the inverted index tables for a paragraph."""
    unique_words = {normalize_word(word) for word in extract_words(text)}
    unique_words.discard("")
    if not unique_words:
        return

    word_ids = [_get_or_create_unique_word_id(db, word) for word in unique_words]
    existing_links = set(
        db.execute(
            select(ParagraphWord.unique_word_id)
            .where(ParagraphWord.paragraph_id == paragraph_id)
            .where(ParagraphWord.unique_word_id.in_(word_ids))
        ).scalars()
    )

    new_links = [
        ParagraphWord(unique_word_id=word_id, paragraph_id=paragraph_id)
        for word_id in word_ids
        if word_id not in existing_links
    ]
    if new_links:
        db.add_all(new_links)


async def _process_paragraph_background(text: str) -> None:
    """Process paragraph in background: count words, update cache, fetch definitions."""
    async with _BACKGROUND_TASK_SEMAPHORE:
        try:
            # Extract words from new paragraph and count them directly
            new_word_counts = extract_word_counts(text)

            # Update word counts in Redis
            cache.update_word_counts(new_word_counts)

            # Get updated top 10 words
            top10_words = cache.get_top_words(10)

            # Ensure definitions are cached for top 10 words
            for word in top10_words:
                await cache.get_or_fetch_definition(word)
        except Exception:
            # Silently fail background processing - don't affect main response
            pass


async def fetch_and_store_paragraph(db: Session) -> ParagraphOut:
    """Fetch a paragraph from external API and store it in the database."""
    try:
        loop = asyncio.get_running_loop()
        text = await fetch_paragraph()

        p = Paragraph(text=text)
        db.add(p)
        db.flush()  # assign id/created_at
        _index_paragraph_words(db, p.id, p.text)

        # Start background processing only after the transaction commits.
        add_post_commit_hook(
            db,
            lambda paragraph_text=text, event_loop=loop: event_loop.call_soon_threadsafe(
                lambda: event_loop.create_task(_process_paragraph_background(paragraph_text))
            ),
        )

        return ParagraphOut(id=p.id, text=p.text, created_at=p.created_at)
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Database error while storing paragraph: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Error fetching and storing paragraph: {e}") from e


def search_paragraphs(
    words: list[str],
    operator: Literal["and", "or"],
    db: Session,
) -> SearchResponse:
    """Search paragraphs containing the specified words."""
    try:
        normalized = sorted({nw for w in words if (nw := normalize_word(w))})
        if not normalized:
            return SearchResponse(count=0, results=[])

        base_stmt = (
            select(Paragraph)
            .join(ParagraphWord, ParagraphWord.paragraph_id == Paragraph.id)
            .join(UniqueWord, UniqueWord.id == ParagraphWord.unique_word_id)
            .where(UniqueWord.word.in_(normalized))
            .group_by(Paragraph.id)
            .order_by(Paragraph.id.desc())
        )
        if operator == "and":
            base_stmt = base_stmt.having(func.count(distinct(UniqueWord.id)) == len(normalized))

        paragraphs = list(db.execute(base_stmt).scalars().all())
        results = [ParagraphOut(id=p.id, text=p.text, created_at=p.created_at) for p in paragraphs]

        return SearchResponse(count=len(results), results=results)
    except SQLAlchemyError as e:
        raise RuntimeError(f"Database error during paragraph search: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Error searching paragraphs: {e}") from e


async def get_dictionary_data(db: Session) -> DictionaryResponse:
    """Get dictionary data with top words and their definitions."""
    try:
        # Try to get top 10 words directly from cache (efficient)
        top10_words = cache.get_top_words(10)
        
        if top10_words:
            # Get definitions only for the top 10 words (fetches missing ones)
            definitions = await cache.get_definitions_for_words(top10_words)

            # Create entries with cached data
            entries = [DictionaryEntry(word=word, definition=definitions.get(word.lower()))
                      for word in top10_words]
        else:
            # Fallback: stream word counts directly into Redis paragraph by paragraph
            if cache.enabled:
                cache.clear_cache()  # Start fresh to avoid stale counts
                for paragraph_text in db.execute(select(Paragraph.text)).scalars():
                    cache.update_word_counts(extract_word_counts(paragraph_text))
                top10_words = cache.get_top_words(10)
            else:
                all_word_counts: Counter[str] = Counter()
                for paragraph_text in db.execute(select(Paragraph.text)).scalars():
                    all_word_counts.update(extract_word_counts(paragraph_text))
                top10_words = [word for word, _ in all_word_counts.most_common(10)]

            # Cache definitions
            definitions_dict = {}
            for word in top10_words:
                try:
                    definition = await fetch_definition(word)
                    cache.set_definition(word, definition)
                    definitions_dict[word] = definition
                except Exception:
                    definitions_dict[word] = None

            entries = [DictionaryEntry(word=w, definition=definitions_dict.get(w))
                      for w in top10_words]

        return DictionaryResponse(top=entries)
    except SQLAlchemyError as e:
        raise RuntimeError(f"Database error getting dictionary data: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Error getting dictionary data: {e}") from e