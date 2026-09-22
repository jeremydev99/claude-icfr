"""스코핑 스키마 — ADR-0034, 6-1.

허용 값은 모델 상수에서 만든다(정규식을 따로 적으면 상수와 어긋나도 알 수 없다).
금액은 int(원), 비율은 문자열 Decimal 로 주고받는다 — JSON 숫자로 비율을 보내면 float 가 된다.
"""
import re
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.scoping import BENCHMARKS, CONCLUSIONS, STATUSES


def _one_of(values) -> str:
    return "^(" + "|".join(re.escape(v) for v in values) + ")$"


class Option(BaseModel):
    value: str
    label: str


class ScopingMeta(BaseModel):
    statement_types: list[Option]
    benchmarks: list[Option]
    qual_factors: list[Option]
    ratings: list[Option]
    statuses: list[Option]
    origin_statuses: list[Option]
    qual_comparisons: list[Option]
    benchmark_guide_ranges: dict[str, list[str | None] | None]
    smt_rate_guide_range: list[str]
    quant_applicable: list[str]


class TemplateRead(BaseModel):
    id: UUID
    code: str
    version: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class ScopingCreate(BaseModel):
    fiscal_year: int = Field(ge=2000, le=2100)
    template_code: str | None = None
    template_version: int | None = None


class ScopingUpdate(BaseModel):
    """PATCH — 보낸 필드만 바꾼다(exclude_unset). 감사인 검토 기록도 여기로 받는다."""
    selected_benchmark: str | None = Field(None, pattern=_one_of(BENCHMARKS))
    smt_rate: Decimal | None = Field(None, gt=0, le=1)
    rationale: str | None = None
    review_auditor: str | None = Field(None, max_length=200)
    review_date: date | None = None
    review_opinion: str | None = None
    # 증빙은 **텍스트 참조**(문서명·보관 위치). 파일 첨부는 증빙 모듈 확장 별건(13.9-49)
    review_evidence_ref: str | None = None


class BenchmarkUpdate(BaseModel):
    base_amount: int | None = None
    rate: Decimal | None = Field(None, ge=0, le=1)


class AdjustmentCreate(BaseModel):
    """조정 1건 — **부호를 붙인 금액**을 더한다(감소 조정은 음수)."""
    amount: int
    reason: str = Field(min_length=1)


class TextUpdate(BaseModel):
    body: str = Field(min_length=1)


class AccountUpdate(BaseModel):
    """계정 PATCH. `ratings` 는 **부분 갱신**이다 — 보낸 요소만 바꾸고 나머지는 둔다.
    요소 값을 null 로 보내면 그 요소를 미입력으로 되돌린다."""
    current_amount: int | None = None
    prior_amount: int | None = None
    ratings: dict[str, str | None] | None = None
    qual_basis: str | None = None
    manual_conclusion: str | None = Field(None, pattern=_one_of(CONCLUSIONS))
    manual_reason: str | None = None


class TransitionRequest(BaseModel):
    to_status: str = Field(pattern=_one_of(STATUSES))
    reason: str | None = None


# ── 응답 ───────────────────────────────────────────────────

class BenchmarkRow(BaseModel):
    kind: str
    label: str
    base_amount: int | None
    effective_base: int | None
    rate: str | None
    amount: int | None
    guide_range: list[str | None] | None
    out_of_range: bool
    badge: str | None = None


class AdjustmentRead(BaseModel):
    id: UUID
    amount: int
    reason: str
    model_config = ConfigDict(from_attributes=True)


class TextRead(BaseModel):
    id: UUID
    key: str
    title: str | None
    body: str
    badge: str | None = None


class AccountRead(BaseModel):
    id: UUID
    statement_type: str
    sort_order: int
    group_label: str | None
    name: str
    current_amount: int | None
    prior_amount: int | None
    ratings: dict[str, str]
    qual_basis: str | None
    manual_conclusion: str | None
    manual_reason: str | None
    # 산출 (저장하지 않는다)
    quant: str | None           # Y / N / na(해당 없음) / null(미평가)
    qual_average: str | None
    qual: str | None
    computed: str | None        # 계산 결론
    final: str | None           # 수동 판정이 있으면 그것
    snapshot_final: str | None = None   # 확정 스냅샷의 결론(확정 상태일 때)
    # 필드 단위 배지 {"ratings.q1": "template", "qual_basis": "edited", ...}
    badges: dict[str, str] = {}


class HistoryRead(BaseModel):
    id: UUID
    from_status: str
    to_status: str
    reason: str | None
    actor_id: UUID
    badge_count: int | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ScopingDetail(BaseModel):
    id: UUID
    fiscal_year: int
    status: str
    template_code: str | None
    template_version: int | None
    policy: dict
    benchmarks: list[BenchmarkRow]
    adjustments: list[AdjustmentRead]
    selected_benchmark: str
    overall_materiality: int | None
    smt: int | None
    smt_rate: str | None
    smt_out_of_range: bool
    rationale: str | None
    scoping_badges: dict[str, str]
    texts: list[TextRead]
    accounts: list[AccountRead]
    warnings: list[str]
    badge_count: int
    confirmed_at: datetime | None
    confirm_reason: str | None
    confirm_badge_count: int | None
    confirmed_snapshot: dict | None
    review_auditor: str | None
    review_date: date | None
    review_opinion: str | None
    review_evidence_ref: str | None
    history: list[HistoryRead]
    can_edit: bool


class ScopingListItem(BaseModel):
    id: UUID
    fiscal_year: int
    status: str
    template_code: str | None
    template_version: int | None
    confirmed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class ScopingSummary(BaseModel):
    """대시보드 카드 — 가장 최근 회계연도 스코핑. 없으면 exists=false."""
    exists: bool
    fiscal_year: int | None = None
    status: str | None = None
    overall_materiality: int | None = None
    smt: int | None = None
    badge_count: int = 0
    # 재무제표 종류별 {Y, N, unevaluated}
    by_statement: dict[str, dict[str, int]] = {}

