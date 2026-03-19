from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ParagraphOut(BaseModel):
    id: int
    text: str
    created_at: datetime


class SearchRequest(BaseModel):
    words: list[str] = Field(default_factory=list, min_length=1)
    operator: Literal["and", "or"] = "or"


class SearchResponse(BaseModel):
    count: int
    results: list[ParagraphOut]


class DictionaryEntry(BaseModel):
    word: str
    definition: str | None = None
    source: str = "dictionaryapi.dev"


class DictionaryResponse(BaseModel):
    top: list[DictionaryEntry]