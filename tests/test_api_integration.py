from __future__ import annotations

import importlib

import respx
from fastapi.testclient import TestClient
from httpx import Response


def _make_client(raise_server_exceptions: bool = True) -> TestClient:
    import app.main as main

    return TestClient(main.app, raise_server_exceptions=raise_server_exceptions)


@respx.mock
def test_fetch_stores_paragraph() -> None:
    # Initialize database
    from app.db import init_db
    init_db()
    
    # Clear database for this test
    from app.db import get_sessionmaker
    from app.models import Paragraph
    from sqlalchemy import delete
    
    sessionmaker = get_sessionmaker()
    with sessionmaker() as session:
        session.execute(delete(Paragraph))
        session.commit()
    
    respx.get("http://metaphorpsum.com/paragraphs/1/50").mock(
        return_value=Response(200, text="Alpha beta gamma.")
    )
    with _make_client() as client:
        r = client.post("/fetch")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == 1
        assert "Alpha beta gamma" in data["text"]


@respx.mock
def test_search_or_and_dictionary() -> None:
    # Initialize database
    from app.db import init_db
    init_db()
    
    # Clear database for this test
    from app.db import get_sessionmaker
    from app.models import Paragraph
    from sqlalchemy import delete
    
    sessionmaker = get_sessionmaker()
    with sessionmaker() as session:
        session.execute(delete(Paragraph))
        session.commit()
    
    respx.get("http://metaphorpsum.com/paragraphs/1/50").mock(
        side_effect=[
            Response(200, text="one two three"),
            Response(200, text="one four"),
        ]
    )
    # Dictionary definitions
    respx.get("https://api.dictionaryapi.dev/api/v2/entries/en/one").mock(
        return_value=Response(
            200,
            json=[{"meanings": [{"definitions": [{"definition": "the number 1"}]}]}],
        )
    )
    respx.get("https://api.dictionaryapi.dev/api/v2/entries/en/two").mock(
        return_value=Response(
            200,
            json=[{"meanings": [{"definitions": [{"definition": "the number 2"}]}]}],
        )
    )
    respx.get("https://api.dictionaryapi.dev/api/v2/entries/en/three").mock(
        return_value=Response(
            200,
            json=[{"meanings": [{"definitions": [{"definition": "the number 3"}]}]}],
        )
    )
    respx.get("https://api.dictionaryapi.dev/api/v2/entries/en/four").mock(
        return_value=Response(
            200,
            json=[{"meanings": [{"definitions": [{"definition": "the number 4"}]}]}],
        )
    )

    with _make_client() as client:
        assert client.post("/fetch").status_code == 200
        assert client.post("/fetch").status_code == 200

        r_or = client.get("/search", params=[("words", "two"), ("words", "four"), ("operator", "or")])
        assert r_or.status_code == 200
        assert r_or.json()["count"] == 2

        r_and = client.get("/search", params=[("words", "one"), ("words", "two"), ("operator", "and")])
        assert r_and.status_code == 200
        assert r_and.json()["count"] == 1

        rd = client.get("/dictionary")
        assert rd.status_code == 200
        payload = rd.json()
        assert len(payload["top"]) <= 10
        top_words = {e["word"]: e for e in payload["top"]}
        assert top_words["one"]["definition"] == "the number 1"


@respx.mock
def test_fetch_external_api_failure() -> None:
    """Fetch should return 500 when external API fails."""
    from app.db import init_db
    init_db()

    respx.get("http://metaphorpsum.com/paragraphs/1/50").mock(
        return_value=Response(500)
    )
    with _make_client(raise_server_exceptions=False) as client:
        r = client.post("/fetch")
        assert r.status_code == 500


@respx.mock
def test_search_no_paragraphs() -> None:
    """Search on empty database returns zero results."""
    from app.db import init_db
    init_db()

    with _make_client() as client:
        r = client.get("/search", params=[("words", "anything"), ("operator", "or")])
        assert r.status_code == 200
        assert r.json()["count"] == 0
        assert r.json()["results"] == []


def test_search_missing_words_param() -> None:
    """Search without words parameter should return an error status."""
    from app.db import init_db
    init_db()

    with _make_client(raise_server_exceptions=False) as client:
        r = client.get("/search", params=[("operator", "or")])
        assert r.status_code >= 400


@respx.mock
def test_search_case_insensitive() -> None:
    """Search should be case-insensitive."""
    from app.db import init_db
    init_db()

    respx.get("http://metaphorpsum.com/paragraphs/1/50").mock(
        return_value=Response(200, text="Hello World")
    )
    with _make_client() as client:
        client.post("/fetch")
        r = client.get("/search", params=[("words", "HELLO"), ("operator", "or")])
        assert r.status_code == 200
        assert r.json()["count"] == 1


@respx.mock
def test_fetch_response_shape() -> None:
    """Fetch response should have id, text, and created_at fields."""
    from app.db import init_db
    init_db()

    respx.get("http://metaphorpsum.com/paragraphs/1/50").mock(
        return_value=Response(200, text="Some paragraph text here.")
    )
    with _make_client() as client:
        r = client.post("/fetch")
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert "text" in data
        assert "created_at" in data
        assert data["text"] == "Some paragraph text here."


@respx.mock
def test_search_and_no_match() -> None:
    """AND search should return 0 when no paragraph has all words."""
    from app.db import init_db
    init_db()

    respx.get("http://metaphorpsum.com/paragraphs/1/50").mock(
        side_effect=[
            Response(200, text="alpha beta"),
            Response(200, text="gamma delta"),
        ]
    )
    with _make_client() as client:
        client.post("/fetch")
        client.post("/fetch")

        r = client.get("/search", params=[("words", "alpha"), ("words", "gamma"), ("operator", "and")])
        assert r.status_code == 200
        assert r.json()["count"] == 0


@respx.mock
def test_dictionary_empty_database() -> None:
    """Dictionary on empty database should return empty top list."""
    from app.db import init_db
    init_db()

    with _make_client() as client:
        r = client.get("/dictionary")
        assert r.status_code == 200
        assert r.json()["top"] == []


@respx.mock
def test_multiple_fetches_increment_ids() -> None:
    """Each fetch should create a new paragraph with incrementing IDs."""
    from app.db import init_db
    init_db()

    respx.get("http://metaphorpsum.com/paragraphs/1/50").mock(
        side_effect=[
            Response(200, text="first paragraph"),
            Response(200, text="second paragraph"),
        ]
    )
    with _make_client() as client:
        r1 = client.post("/fetch")
        r2 = client.post("/fetch")
        assert r1.json()["id"] < r2.json()["id"]

