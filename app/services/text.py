from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

_WORD_RE = re.compile(r"[a-zA-Z]+(?:'[a-zA-Z]+)?")


def normalize_word(word: str) -> str:
    """Normalize a word by stripping whitespace and converting to lowercase."""
    try:
        if not isinstance(word, str):
            raise TypeError(f"Expected string, got {type(word)}")
        return word.strip().lower()
    except Exception as e:
        raise RuntimeError(f"Error normalizing word '{word}': {e}") from e


def extract_words(text: str) -> list[str]:
    """Extract words from text using regex pattern."""
    try:
        if not isinstance(text, str):
            raise TypeError(f"Expected string, got {type(text)}")
        return [normalize_word(m.group(0)) for m in _WORD_RE.finditer(text)]
    except Exception as e:
        raise RuntimeError(f"Error extracting words from text: {e}") from e


def extract_word_counts(text: str) -> Counter[str]:
    """Extract words from text and return their counts directly."""
    try:
        if not isinstance(text, str):
            raise TypeError(f"Expected string, got {type(text)}")
        counter = Counter()
        for match in _WORD_RE.finditer(text):
            word = normalize_word(match.group(0))
            counter[word] += 1
        return counter
    except Exception as e:
        raise RuntimeError(f"Error extracting word counts from text: {e}") from e


def top_words(texts: Iterable[str], n: int = 10) -> list[tuple[str, int]]:
    """Get top N most common words from a collection of texts."""
    try:
        if not isinstance(n, int) or n < 1:
            raise ValueError(f"n must be a positive integer, got {n}")

        c: Counter[str] = Counter()
        for t in texts:
            if not isinstance(t, str):
                raise TypeError(f"Expected string in texts, got {type(t)}")
            c.update(extract_words(t))
        return c.most_common(n)
    except Exception as e:
        raise RuntimeError(f"Error calculating top words: {e}") from e

