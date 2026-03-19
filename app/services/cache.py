from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import redis

from app.config import settings


class RedisCache:
    """Redis cache for word definitions and frequency data."""

    _definition_lock_ttl = 30

    def __init__(self):
        self.enabled = settings.redis.enabled
        self.ttl = settings.redis.ttl
        self._client: Optional[redis.Redis] = None

    def _get_client(self) -> redis.Redis:
        """Get or create Redis client with lazy reconnection."""
        if not self.enabled:
            raise RuntimeError("Redis caching is disabled")

        if self._client is None:
            try:
                self._client = redis.from_url(
                    settings.redis.url,
                    socket_connect_timeout=2,
                    retry_on_timeout=True,
                )
            except Exception as e:
                raise RuntimeError(f"Failed to connect to Redis: {e}") from e

        return self._client

    def get_word_definition(self, word: str) -> Optional[str]:
        """Get cached word definition."""
        if not self.enabled:
            return None

        try:
            client = self._get_client()
            result = client.execute_command('JSON.GET', 'definitions', f'$.{word.lower()}')
            if result:
                parsed = json.loads(result)
                return parsed[0] if parsed else None
            return None
        except Exception:
            return None

    def set_word_definition(self, word: str, definition: Optional[str]) -> None:
        """Cache word definition."""
        self.set_definition(word, definition)

    def get_all_word_counts(self) -> dict[str, int]:
        """Get all cached word counts from Redis sorted set."""
        if not self.enabled:
            return {}

        try:
            client = self._get_client()
            # Get all members with scores from sorted set
            result = client.zrange('word_counts', 0, -1, withscores=True)
            return {word.decode('utf-8'): int(score) for word, score in result}
        except Exception:
            return {}
    def set_all_word_counts(self, word_counts: dict[str, int]) -> None:
        """Store all word counts in Redis sorted set."""
        if not self.enabled:
            return

        try:
            client = self._get_client()
            # Clear existing set and add all counts
            client.delete('word_counts')
            if word_counts:
                # Add all word-count pairs to sorted set
                client.zadd('word_counts', word_counts)
            # Set expiration
            client.expire('word_counts', self.ttl)
        except Exception:
            # Silently fail on cache write errors
            pass

    def update_word_counts(self, updates: dict[str, int]) -> None:
        """Update specific word counts in Redis sorted set using a pipeline."""
        if not self.enabled:
            return

        try:
            client = self._get_client()
            pipe = client.pipeline()
            for word, count in updates.items():
                # Increment each word's score so the sorted set always reflects global frequency.
                pipe.zincrby('word_counts', count, word)
            pipe.expire('word_counts', self.ttl)
            pipe.execute()
        except Exception:
            pass

    def get_top_words(self, n: int = 10) -> list[str]:
        """Get top N words from Redis sorted set without loading all data."""
        if not self.enabled:
            return []

        try:
            client = self._get_client()
            # Use ZREVRANGE to get top N words by frequency
            result = client.zrevrange('word_counts', 0, n-1)
            return [word.decode('utf-8') for word in result]
        except Exception:
            return []

    def set_definition(self, word: str, definition: Optional[str]) -> None:
        """Store a word definition in Redis JSON."""
        if not self.enabled or definition is None:
            return

        try:
            client = self._get_client()
            normalized = word.lower()
            client.execute_command('JSON.SET', 'definitions', '$', '{}', 'NX')
            client.execute_command('JSON.SET', 'definitions', f'$.{normalized}', json.dumps(definition))
            client.expire('definitions', self.ttl)
        except Exception:
            pass

    def acquire_definition_lock(self, word: str) -> bool:
        """Acquire a short-lived lock to avoid duplicate definition fetches."""
        if not self.enabled:
            return False

        try:
            client = self._get_client()
            return bool(
                client.set(
                    f"word_def_lock:{word.lower()}",
                    "1",
                    ex=self._definition_lock_ttl,
                    nx=True,
                )
            )
        except Exception:
            return False

    def release_definition_lock(self, word: str) -> None:
        """Release the lock guarding a definition fetch."""
        if not self.enabled:
            return

        try:
            client = self._get_client()
            client.delete(f"word_def_lock:{word.lower()}")
        except Exception:
            pass

    async def get_or_fetch_definition(self, word: str) -> Optional[str]:
        """Get a cached definition or fetch it once across concurrent workers."""
        from app.services.dictionary import fetch_definition

        if not self.enabled:
            return None

        normalized_word = word.lower()
        definition = self.get_word_definition(normalized_word)
        if definition is not None:
            return definition

        if not self.acquire_definition_lock(normalized_word):
            for _ in range(3):
                await asyncio.sleep(0.1)
                definition = self.get_word_definition(normalized_word)
                if definition is not None:
                    return definition
            return None

        try:
            definition = self.get_word_definition(normalized_word)
            if definition is not None:
                return definition

            fetched_definition = await fetch_definition(normalized_word)
            self.set_definition(normalized_word, fetched_definition)
            return fetched_definition
        except Exception:
            return None
        finally:
            self.release_definition_lock(normalized_word)

    async def get_definitions_for_words(self, words: list[str]) -> dict[str, Optional[str]]:
        """Get cached definitions for specific words, fetching missing ones concurrently."""
        if not self.enabled:
            return {}

        try:
            definitions = await asyncio.gather(
                *(self.get_or_fetch_definition(word) for word in words),
                return_exceptions=True,
            )
            return {
                word.lower(): defn if not isinstance(defn, BaseException) else None
                for word, defn in zip(words, definitions)
            }
        except Exception:
            return {}

    def clear_cache(self) -> None:
        """Clear all cached data."""
        if not self.enabled:
            return

        try:
            client = self._get_client()
            client.delete('word_counts')  # Delete sorted set
            client.delete('definitions')   # O(1) single-key deletion
        except Exception:
            pass

    def invalidate_top_words(self) -> None:
        """Invalidate cached word counts and definitions."""
        if not self.enabled:
            return

        self.clear_cache()


# Global cache instance
cache = RedisCache()