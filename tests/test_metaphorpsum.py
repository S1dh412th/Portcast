from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.services.metaphorpsum import fetch_paragraph


@respx.mock
@pytest.mark.asyncio
async def test_fetch_paragraph_success() -> None:
    respx.get("http://metaphorpsum.com/paragraphs/1/50").mock(
        return_value=Response(200, text="A nice paragraph about life.")
    )
    result = await fetch_paragraph()
    assert result == "A nice paragraph about life."


@respx.mock
@pytest.mark.asyncio
async def test_fetch_paragraph_strips_whitespace() -> None:
    respx.get("http://metaphorpsum.com/paragraphs/1/50").mock(
        return_value=Response(200, text="  padded text  \n")
    )
    result = await fetch_paragraph()
    assert result == "padded text"


@respx.mock
@pytest.mark.asyncio
async def test_fetch_paragraph_empty_response() -> None:
    respx.get("http://metaphorpsum.com/paragraphs/1/50").mock(
        return_value=Response(200, text="   ")
    )
    with pytest.raises(RuntimeError, match="empty response"):
        await fetch_paragraph()


@respx.mock
@pytest.mark.asyncio
async def test_fetch_paragraph_http_500() -> None:
    respx.get("http://metaphorpsum.com/paragraphs/1/50").mock(
        return_value=Response(500)
    )
    with pytest.raises(RuntimeError, match="HTTP error"):
        await fetch_paragraph()


@respx.mock
@pytest.mark.asyncio
async def test_fetch_paragraph_http_404() -> None:
    respx.get("http://metaphorpsum.com/paragraphs/1/50").mock(
        return_value=Response(404)
    )
    with pytest.raises(RuntimeError, match="HTTP error"):
        await fetch_paragraph()
