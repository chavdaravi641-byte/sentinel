"""Shared/common response schemas."""

import time
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    detail: Any = None


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "Paginated[T]":
        pages = (total + page_size - 1) // page_size if page_size else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


class HealthResponse(BaseModel):
    status: str = Field(description="overall status; ok or degraded")
    version: str
    components: dict[str, dict[str, Any]]
    timestamp: float = Field(default_factory=time.time)