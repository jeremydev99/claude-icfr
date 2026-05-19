from pydantic import BaseModel


class PaginationMeta(BaseModel):
    page: int
    size: int
    total: int


class ErrorResponse(BaseModel):
    detail: str
