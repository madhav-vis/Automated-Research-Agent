"""Data models for papers, search queries, and validation results."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Paper(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str = ""
    citation_count: int | None = None
    journal: str | None = ""
    source: str  # "openalex" | "arxiv"
    relevance_score: float | None = None


class SearchQuery(BaseModel):
    keywords: str
    year_range: tuple[int, int] | None = None
    field_filter: str | None = None


class SearchIntentProfile(BaseModel):
    """Structured search intent derived from the narrowing dialogue."""
    original_query: str
    identified_topic: str = ""
    domain: str = ""
    application: str = ""
    methods: list[str] = Field(default_factory=list)
    recency: str = "5y"
    year_from: int | None = None


