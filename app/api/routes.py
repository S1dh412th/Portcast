from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas import DictionaryResponse, ParagraphOut, SearchResponse
from app.services.paragraph import fetch_and_store_paragraph, get_dictionary_data, search_paragraphs

router = APIRouter()


@router.post("/fetch", response_model=ParagraphOut)
async def fetch_and_store(db: Session = Depends(get_db)) -> ParagraphOut:
    """Fetch and store a new paragraph."""
    try:
        return await fetch_and_store_paragraph(db)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@router.get("/search", response_model=SearchResponse)
def search(
    words: Annotated[list[str], Query(min_length=1)],
    operator: Literal["and", "or"] = "or",
    db: Session = Depends(get_db),
) -> SearchResponse:
    """Search paragraphs by words."""
    try:
        return search_paragraphs(words, operator, db)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@router.get("/dictionary", response_model=DictionaryResponse)
async def dictionary(db: Session = Depends(get_db)) -> DictionaryResponse:
    """Get dictionary data for top words."""
    try:
        return await get_dictionary_data(db)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")