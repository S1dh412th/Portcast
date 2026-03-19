from __future__ import annotations

import httpx
from httpx import HTTPError, TimeoutException

from app.config import settings
from app.services.cache import cache


async def fetch_definition(word: str) -> str | None:
    """Fetch definition for a word from cache or Dictionary API with error handling."""
    # Try cache first
    cached_definition = cache.get_word_definition(word)
    if cached_definition:
        return cached_definition

    # Fetch from API if not cached
    try:
        url = f"{settings.external_api.dictionary_base_url}/{word}"
        async with httpx.AsyncClient(timeout=settings.external_api.dictionary_timeout) as client:
            r = await client.get(url)
            r.raise_for_status()

            data = r.json()
            if not isinstance(data, list) or not data:
                return None

            entry0 = data[0]
            meanings = entry0.get("meanings") if isinstance(entry0, dict) else None
            if not isinstance(meanings, list) or not meanings:
                return None

            defs = meanings[0].get("definitions") if isinstance(meanings[0], dict) else None
            if not isinstance(defs, list) or not defs:
                return None

            definition = defs[0].get("definition") if isinstance(defs[0], dict) else None
            if isinstance(definition, str) and definition.strip():
                definition = definition.strip()
                # Cache the successful result
                cache.set_word_definition(word, definition)
                return definition
            return None

    except TimeoutException:
        # Return None for timeouts - word might not have definition
        return None
    except HTTPError:
        # Return None for HTTP errors - word might not exist
        return None
    except Exception:
        # Return None for any other errors (JSON parsing, etc.)
        return None
 
