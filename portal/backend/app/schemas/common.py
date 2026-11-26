"""Schema dùng chung: phân trang (openapi: PageMeta, tham số page/page_size)."""

from __future__ import annotations

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class PageParams:
    def __init__(self, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)) -> None:
        self.page, self.page_size = page, page_size

    def apply(self, db: Session, stmt: Select) -> tuple[list, int]:
        total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        rows = db.execute(stmt.limit(self.page_size).offset((self.page - 1) * self.page_size)).scalars().all()
        return list(rows), total
