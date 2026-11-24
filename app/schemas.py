"""Request bodies accepted by the API."""

from pydantic import BaseModel, Field


class UrlRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


class ClipUpdate(BaseModel):
    start: float
    end: float
