"""재무제표·계정 트리 스키마 — ADR-0037, 8-A.

**금액·허용 오차·차액은 문자열 Decimal 로 내보낸다** — JSON 숫자로 보내면 float 가 된다.
pydantic v2 는 `Decimal` 을 JSON 에서 문자열로 직렬화한다.
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Option(BaseModel):
    value: str
    label: str


class FsMeta(BaseModel):
    statement_types: list[Option]
    bases: list[Option]
    sections: list[Option]
    sections_by_statement: dict[str, list[str]]
    units: list[Option]
    statuses: list[Option]
    source_kinds: list[Option]


class AccountNode(BaseModel):
    id: UUID
    code: str | None
    name: str
    statement_type: str
    section: str
    is_subtotal: bool
    rollup_sign: int
    sort_order: int
    depth: int
    valid_from_year: int | None
    valid_to_year: int | None
    children: list["AccountNode"] = []


class AmountNode(AccountNode):
    """재무제표 상세의 트리 노드. 금액 행이 없는 조상(제목)은 `has_row=False`."""
    has_row: bool
    amount: Decimal | None = None
    raw_row_no: int | None = None
    raw_label: str | None = None
    raw_indent: int | None = None
    raw_value: str | None = None
    raw_meta: dict | None = None
    children: list["AmountNode"] = []


class StatementListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    fiscal_year: int
    statement_type: str
    basis: str
    unit: int
    currency: str
    tolerance: Decimal
    status: str
    finalized_at: datetime | None
    finalized_by_id: UUID | None
    source_kind: str | None
    source_filename: str | None
    source_sheet: str | None


class StatusEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    from_status: str
    to_status: str
    reason: str | None
    actor_id: UUID
    occurred_at: datetime
    tolerance: Decimal | None
    skipped_count: int | None
    tolerance_diffs: list | None


class ValidationItem(BaseModel):
    rule: str
    account_id: UUID | None
    account_code: str | None
    account_name: str | None   # 표시용. 판정에는 쓰지 않는다
    expected: Decimal | None
    actual: Decimal | None
    diff: Decimal | None


class ValidationResult(BaseModel):
    statement_id: UUID
    ok: bool
    unit: int
    currency: str
    tolerance: Decimal
    errors: list[ValidationItem]
    skipped: list[ValidationItem]   # Q6(b) — 확정을 막지 않는다
    checks: list[ValidationItem]


class StatementDetail(StatementListItem):
    tree: list[AmountNode]
    events: list[StatusEventRead]
    validation: ValidationResult


class FinalizeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class ReopenRequest(BaseModel):
    reason: str = Field(max_length=2000)
