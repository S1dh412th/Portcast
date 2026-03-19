from __future__ import annotations

import httpx
from httpx import HTTPError, TimeoutException

from app.config import settings


async def fetch_paragraph() -> str:
    """Fetch a paragraph from Metaphorpsum API with error handling."""
    try:
        async with httpx.AsyncClient(timeout=settings.external_api.metaphorpsum_timeout) as client:
            r = await client.get(settings.external_api.metaphorpsum_url)
            r.raise_for_status()
            text = r.text.strip()
            if not text:
                raise ValueError("Metaphorpsum API returned empty response")
            return text
    except TimeoutException as e:
        raise RuntimeError(f"Timeout fetching paragraph from Metaphorpsum API: {e}") from e
    except HTTPError as e:
        raise RuntimeError(f"HTTP error fetching paragraph from Metaphorpsum API: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error fetching paragraph from Metaphorpsum API: {e}") from e
 
