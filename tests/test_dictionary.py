from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.services.dictionary import fetch_definition


@respx.mock
@pytest.mark.asyncio
async def test_fetch_definition_success() -> None:
    respx.get("https://api.dictionaryapi.dev/api/v2/entries/en/hello").mock(
        return_value=Response(
            200,
            json=[{"meanings": [{"definitions": [{"definition": "a greeting"}]}]}],
        )
    )
    result = await fetch_definition("hello")
    assert result == "a greeting"


@respx.mock
@pytest.mark.asyncio
async def test_fetch_definition_strips_whitespace() -> None:
    respx.get("https://api.dictionaryapi.dev/api/v2/entries/en/test").mock(
        return_value=Response(
            200,
            json=[{"meanings": [{"definitions": [{"definition": "  a trial  "}]}]}],
        )
    )
    result = await fetch_definition("test")
    assert result == "a trial"


@respx.mock
@pytest.mark.asyncio
async def test_fetch_definition_empty_list_response() -> None:
    respx.get("https://api.dictionaryapi.dev/api/v2/entries/en/xyz").mock(
        return_value=Response(200, json=[])
    )
    result = await fetch_definition("xyz")
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_fetch_definition_no_meanings() -> None:
    respx.get("https://api.dictionaryapi.dev/api/v2/entries/en/xyz").mock(
        return_value=Response(200, json=[{"meanings": []}])
    )
    result = await fetch_definition("xyz")
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_fetch_definition_no_definitions() -> None:
    respx.get("https://api.dictionaryapi.dev/api/v2/entries/en/xyz").mock(
        return_value=Response(200, json=[{"meanings": [{"definitions": []}]}])
    )
    result = await fetch_definition("xyz")
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_fetch_definition_empty_definition_string() -> None:
    respx.get("https://api.dictionaryapi.dev/api/v2/entries/en/xyz").mock(
        return_value=Response(200, json=[{"meanings": [{"definitions": [{"definition": "   "}]}]}])
    )
    result = await fetch_definition("xyz")
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_fetch_definition_http_404() -> None:
    respx.get("https://api.dictionaryapi.dev/api/v2/entries/en/zzz").mock(
        return_value=Response(404)
    )
    result = await fetch_definition("zzz")
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_fetch_definition_http_500() -> None:
    respx.get("https://api.dictionaryapi.dev/api/v2/entries/en/fail").mock(
        return_value=Response(500)
    )
    result = await fetch_definition("fail")
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_fetch_definition_malformed_json() -> None:
    respx.get("https://api.dictionaryapi.dev/api/v2/entries/en/bad").mock(
        return_value=Response(200, json="not a list")
    )
    result = await fetch_definition("bad")
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_fetch_definition_non_dict_entry() -> None:
    respx.get("https://api.dictionaryapi.dev/api/v2/entries/en/odd").mock(
        return_value=Response(200, json=["a string instead of dict"])
    )
    result = await fetch_definition("odd")
    assert result is None
