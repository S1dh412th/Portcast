from app.services.text import extract_words, extract_word_counts, top_words


def test_extract_words_basic() -> None:
    assert extract_words("Hello, world!") == ["hello", "world"]


def test_extract_words_apostrophes() -> None:
    assert extract_words("Don't stop") == ["don't", "stop"]


def test_extract_word_counts() -> None:
    from collections import Counter
    result = extract_word_counts("Hello world hello!")
    expected = Counter({"hello": 2, "world": 1})
    assert result == expected


def test_top_words_counts() -> None:
    texts = ["One two two.", "two three"]
    assert top_words(texts, n=2) == [("two", 3), ("one", 1)]

