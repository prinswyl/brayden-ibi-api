from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

from app.shared.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

T = TypeVar("T")


class PaginationParams:
    """FastAPI dependency for standardised pagination query parameters."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-based)"),
        page_size: int = Query(
            DEFAULT_PAGE_SIZE,
            ge=1,
            le=MAX_PAGE_SIZE,
            description=f"Results per page (max {MAX_PAGE_SIZE})",
        ),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int = Field(0)

    def model_post_init(self, __context: object) -> None:
        self.total_pages = (
            (self.total + self.page_size - 1) // self.page_size if self.page_size else 0
        )


class PagedResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: PageMeta

    @classmethod
    def build(
        cls,
        items: list[T],
        total: int,
        pagination: PaginationParams,
    ) -> "PagedResponse[T]":
        return cls(
            data=items,
            meta=PageMeta(
                page=pagination.page,
                page_size=pagination.page_size,
                total=total,
            ),
        )
