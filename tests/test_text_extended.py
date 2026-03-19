from __future__ import annotations

from collections import Counter

from app.services.text import extract_words, extract_word_counts, normalize_word, top_words


# --- normalize_word ---

def test_normalize_word_lowercase() -> None:
    assert normalize_word("Hello") == "hello"


def test_normalize_word_strips_whitespace() -> None:
    assert normalize_word("  world  ") == "world"


def test_normalize_word_empty() -> None:
    assert normalize_word("") == ""


def test_normalize_word_already_lower() -> None:
    assert normalize_word("test") == "test"


# --- extract_words ---

def test_extract_words_basic() -> None:
    assert extract_words("Hello, world!") == ["hello", "world"]


def test_extract_words_apostrophes() -> None:
    assert extract_words("Don't stop") == ["don't", "stop"]


def test_extract_words_numbers_ignored() -> None:
    assert extract_words("test 123 hello") == ["test", "hello"]


def test_extract_words_empty_string() -> None:
    assert extract_words("") == []


def test_extract_words_only_punctuation() -> None:
    assert extract_words("!@#$%^&*()") == []


def test_extract_words_mixed_case() -> None:
    assert extract_words("Hello WORLD hElLo") == ["hello", "world", "hello"]


def test_extract_words_hyphenated() -> None:
    # Hyphens split words with this regex
    result = extract_words("well-known fact")
    assert "well" in result
    assert "known" in result
    assert "fact" in result


# --- extract_word_counts ---

def test_word_counts() -> None:
    result = extract_word_counts("Hello world hello!")
    expected = Counter({"hello": 2, "world": 1})
    assert result == expected


def test_word_counts_empty() -> None:
    result = extract_word_counts("")
    assert result == Counter()


def test_word_counts_single_word() -> None:
    result = extract_word_counts("unique")
    assert result == Counter({"unique": 1})


def test_word_counts_repeated() -> None:
    result = extract_word_counts("go go go")
    assert result == Counter({"go": 3})


# --- top_words ---

def test_top_words_counts() -> None:
    texts = ["One two two.", "two three"]
    assert top_words(texts, n=2) == [("two", 3), ("one", 1)]


def test_top_words_empty_texts() -> None:
    assert top_words([], n=5) == []


def test_top_words_single_text() -> None:
    result = top_words(["apple banana apple"], n=1)
    assert result == [("apple", 2)]


def test_top_words_n_larger_than_vocab() -> None:
    result = top_words(["cat dog"], n=100)
    assert len(result) == 2
