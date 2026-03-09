"""Pydantic request / response models for the chat API."""

from typing import Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Incoming chat request body."""

    question: str
    session_id: Optional[str] = None


class Citation(BaseModel):
    """A single citation reference with structured metadata."""

    source: str
    title: str = ""
    section: str = ""
    page: str = ""
    url: str = ""
    chunk_id: str = ""


class CitationsPayload(BaseModel):
    """Wrapper for the SSE ``citations`` named event."""

    citations: list[Citation]
