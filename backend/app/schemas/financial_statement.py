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


# ── 8-B 업로드 ───────────────────────────────────────────────

class UploadSheetCandidate(BaseModel):
    sheet: str
    kind: str
    statement_type: str | None


class UploadRow(BaseModel):
    """파싱·추론된 행. `match` 는 대응 계정 id 또는 "new"(신규 생성)."""
    row_no: int
    raw_label: str
    label: str
    depth: int
    parent_row_no: int | None
    kind: str
    is_subtotal: bool
    rollup_sign: int
    section: str
    amounts: dict[str, Decimal | None]
    flags: list[str]
    errors: list[str]
    excluded: bool
    match: str | None


class UploadSubtotalDiff(BaseModel):
    row_no: int
    label: str
    fiscal_year: int
    expected: Decimal
    actual: Decimal
    diff: Decimal


class UploadConflict(BaseModel):
    fiscal_year: int
    statement_id: UUID
    status: str


class UploadValidationItem(BaseModel):
    rule: str
    raw_row_no: int | None   # 원본 행 — preview 에서는 계정 id 가 롤백되므로 이것으로 찾는다
    account_id: UUID | None  # commit 에서만
    account_name: str | None
    expected: Decimal | None
    actual: Decimal | None
    diff: Decimal | None


class UploadStatementResult(BaseModel):
    fiscal_year: int
    statement_id: UUID | None   # commit 에서만
    status: str                 # draft / final (preview 는 draft)
    finalize_candidate: bool    # 최신 연도(자동 확정 대상)
    finalized: bool
    ok: bool
    errors: list[UploadValidationItem]
    skipped: list[UploadValidationItem]
    checks_count: int
    suspense: list["SuspenseAbsorbed"] = []   # 이번에 임시계정으로 받은 소계 불일치


class UploadResponse(BaseModel):
    mode: str
    committed: bool
    can_commit: bool
    filename: str | None
    sheet: str | None
    kind: str | None
    statement_type: str | None
    basis: str | None
    unit: int | None
    unit_label: str | None       # 시트 표기(감지값)
    periods: list[int]           # 시트에 있는 연도
    fiscal_years: list[int]      # 이번에 저장할(한) 연도
    sheets: list[UploadSheetCandidate]
    errors: list[str]            # 업로드를 막는 오류(commit 422)
    warnings: list[str]
    master_empty: bool
    mapping_required: bool       # commit 409 — mapping 을 명시해야 한다
    suggested_mapping: dict[str, str]
    conflicts: list[UploadConflict]   # commit 409
    rows: list[UploadRow]
    subtotal_diffs: list[UploadSubtotalDiff]
    statements: list[UploadStatementResult]


# ── 8-B2 정산표 결합 ─────────────────────────────────────────

class AttachBridgeCandidate(BaseModel):
    column: str      # 매핑 열 글자
    values: int      # 열의 값 종류 수
    matched: int     # 공시 계정과 맞은 값 종류 수(category_map 적용 후)


class AttachRowOut(BaseModel):
    row_no: int
    raw_label: str
    name: str                     # 계정명(반복 이름은 "감가상각누계액_건물" 처럼 구분)
    bridge: str | None            # 매핑 열 원문
    source_path: list[str]        # 정산표 안의 상위 그룹(계정으로 만들지 않는다)
    target_account_id: UUID | None
    target_name: str | None       # 부모가 될 공시 계정
    existing_account_id: UUID | None   # 이미 붙어 있는 COA 계정(재결합)
    amounts: dict[str, Decimal | None]
    skip_reason: str | None


class AttachResponse(BaseModel):
    mode: str
    committed: bool
    can_commit: bool
    filename: str | None
    sheet: str | None
    statement_type: str | None
    basis: str | None
    unit: int | None
    bridge_column: str | None
    bridge_candidates: list[AttachBridgeCandidate]
    periods: list[int]
    fiscal_years: list[int]
    errors: list[str]
    warnings: list[str]
    conflicts: list[UploadConflict]    # final 재무제표 — commit 409(재오픈 후)
    unmatched: list[str]               # 공시 계정을 못 찾은 매핑 값 — category_map 필요
    rows: list[AttachRowOut]
    statements: list[UploadStatementResult]


# ── 8-C 템플릿 링크 ──────────────────────────────────────────

class TemplateLinkOut(BaseModel):
    id: UUID
    account_id: UUID
    template_account_id: UUID
    template_name: str | None
    template_code: str
    template_version: int
    basis: str               # exact / normalized / manual — 서버 판정
    confirmed_by_id: UUID
    confirmed_at: datetime
    note: str | None


class TemplateSuggestion(BaseModel):
    template_account_id: UUID
    template_name: str
    basis: str               # 제안 근거. 저장되지 않는다


class TemplateMatchRow(BaseModel):
    account_id: UUID
    name: str
    parent_name: str | None
    depth: int
    is_subtotal: bool
    link: TemplateLinkOut | None
    suggestion: TemplateSuggestion | None


class TemplateAccountOut(BaseModel):
    id: UUID
    name: str
    group_label: str | None
    sort_order: int
    linked_count: int


class TemplateMatchesResponse(BaseModel):
    template_code: str
    template_version: int
    statement_type: str
    accounts: list[TemplateMatchRow]
    template_accounts: list[TemplateAccountOut]
    counts: dict[str, int]


class TemplateLinkItem(BaseModel):
    account_id: UUID
    template_account_id: UUID
    note: str | None = Field(default=None, max_length=2000)


class TemplateLinkRequest(BaseModel):
    template_code: str | None = None      # 생략 시 기본 템플릿
    template_version: int | None = None   # 생략 시 최신 버전
    links: list[TemplateLinkItem] = Field(min_length=1, max_length=500)


class TemplateLinkResponse(BaseModel):
    links: list[TemplateLinkOut]
    warnings: list[str]


# ── 임시계정(원본 차이) ──────────────────────────────────────

class SuspenseAbsorbed(BaseModel):
    parent_account_id: UUID
    parent_name: str
    amount: Decimal


class SuspenseItem(BaseModel):
    amount_id: UUID
    account_id: UUID
    parent_account_id: UUID | None
    parent_name: str | None
    amount: Decimal | None
    source_amount: Decimal | None   # 흡수 당시 차액
    expected: str | None            # 흡수 당시 하위 합
    actual: str | None              # 흡수 당시 소계 금액(원본)
    resolved: dict | None           # {action, reason, by, at, amount, target_account_id?}
    is_deleted: bool                # fix_subtotal·reclass 로 해소되면 True(이력으로 남는다)


class SuspenseResolveRequest(BaseModel):
    action: str                       # fix_subtotal / reclass / accept
    reason: str = Field(max_length=2000)
    target_account_id: UUID | None = None   # reclass 에서만 — 같은 소계 아래 형제 계정


# SuspenseAbsorbed 가 UploadStatementResult 보다 뒤에 정의돼 전방 참조를 여기서 푼다
UploadStatementResult.model_rebuild()
