import math
from dataclasses import dataclass

from fastapi import Query


@dataclass
class PaginationParams:
    page: int = 1
    page_size: int = 25

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def get_pagination(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


def build_pagination_meta(
    total_count: int,
    pagination: PaginationParams,
) -> dict:
    return {
        "page": pagination.page,
        "page_size": pagination.page_size,
        "total_count": total_count,
        "total_pages": math.ceil(total_count / pagination.page_size) if total_count > 0 else 0,
    }
