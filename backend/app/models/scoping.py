"""스코핑 — ADR-0034, 6-1.

**원천 실무 양식을 옮긴다. 회계기준을 새로 해석하지 않는다.** 계산식·판정 규칙·문구가
전부 `backend/seeds/4__내부회계관리제도_Scoping.xlsx` 에 있다(ADR-0034 §1.1).

두 계층이다.

- **템플릿(전역, `IdentityBase`)** — 제품 콘텐츠다. 테넌트에 속하지 않고 `(code, version)` 으로
  식별한다. ADR-0030 §2.4 의 산업별 템플릿과 같은 계층이다
- **스코핑(테넌트 소유, `AuditedBase`)** — 회계연도마다 1건. 생성 시 템플릿을 **복사**하고
  이후는 독립적으로 관리한다. 어느 템플릿·어느 버전에서 왔는지 기록한다

**계산 결론(양적·질적·유의성)은 저장하지 않고 조회할 때 산출한다**(ADR-0029 §2.2,
`services/scoping_calc.py`). **확정 시점의 결론만 스냅샷으로 남긴다** — 확정 뒤 정책 기준을
바꿔도 확정 당시 판단은 보존되어야 한다.

**금액은 원 단위 정수(BigInteger)다.** float 를 쓰지 않는다 — 원천 수식과 한 원도 다르면 안 된다.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditedBase, IdentityBase

# ── 값 상수 — 정의처는 여기 하나다(13.9-40) ────────────────────────
# 라벨은 화면에 필요하므로 코드값과 함께 둔다. dict 순서 = 표시 순서.

# 재무제표 종류 (ADR-0034 §2.4). 대상은 별도재무제표다(§2.1).
STATEMENT_BS = "BS"
STATEMENT_PL = "PL"
STATEMENT_NOTE = "NOTE"
STATEMENT_CF = "CF"
STATEMENT_LABELS = {
    STATEMENT_BS: "재무상태표",
    STATEMENT_PL: "손익계산서",
    STATEMENT_NOTE: "주석",
    STATEMENT_CF: "현금흐름",
}
STATEMENT_TYPES = tuple(STATEMENT_LABELS)
# **양적 판정은 BS·PL 에만 적용한다.** 원천 각주 그대로다 —
#   주석:   "주석의 경우 양적기준은 유의한 계정과목(BS/PL)에서 분석이 됨에 따라 질적 유의여부로 판단함"
#   현금흐름: "현금흐름표의 경우 간접법형식으로 작성되며 … 질적 유의여부로 판단함"
# 주석·현금흐름의 양적 판정은 "해당 없음"이며 **"미평가"와 다른 상태다** — 금액이 없어서
# 못 하는 것과 입력하지 않아서 못 하는 것은 다르다(6-1 §2.3).
QUANT_APPLICABLE_STATEMENTS = frozenset({STATEMENT_BS, STATEMENT_PL})

# 벤치마크 6종 (ADR-0034 §2.3)
BENCHMARK_ADJUSTED_PBT = "adjusted_pbt"
BENCHMARK_LABELS = {
    BENCHMARK_ADJUSTED_PBT: "조정세전순이익",
    "revenue": "매출액(영업수익)",
    "total_assets": "총자산",
    "total_equity": "총자본(순자산)",
    "total_expenses": "총비용",
    "operating_cf": "영업활동현금흐름",
}
BENCHMARKS = tuple(BENCHMARK_LABELS)

# 가이드 범위 (원천 Notes 시트 Note 1·2). (하한, 상한) — None 은 그 쪽 경계 없음.
# **벗어나면 경고하되 막지 않는다**(ADR-0034 §2.3).
# ⚠️ **매출액은 비워 둔다.** 원천이 "0.0 ~ 5 %" 로 적었는데 통상 0.5~1% 라 오기가 의심된다
# (원천이 실제로 매출액 벤치마크에 쓴 비율은 0.5% — G53=0.005 — 로 그 가설과 맞는다).
# **마스터 확인 전까지 경고 판정에 쓰지 않는다**(ADR-0034 §5).
BENCHMARK_GUIDE_RANGES: dict[str, tuple[str | None, str | None] | None] = {
    BENCHMARK_ADJUSTED_PBT: ("0.05", "0.10"),
    "revenue": None,
    "total_assets": ("0.01", "0.02"),
    "total_equity": (None, "0.03"),
    "total_expenses": ("0.03", "0.05"),
    "operating_cf": ("0.03", "0.05"),
}
SMT_RATE_GUIDE_RANGE = ("0.50", "0.75")   # Note 2 — 수행중요성 설정율
DEFAULT_SMT_RATE = "0.70"

# 질적 10요소 (원천 "설계운영 적용기법 질적요소 42" 문구 그대로)
QUAL_FACTOR_LABELS = {
    "q1": "계정과목 내 개별 거래의 규모, 복잡성, 동질성",
    "q2": "추정이나 판단이 개입되는 회계처리 및 평가",
    "q3": "회계처리 및 보고의 복잡성",
    "q4": "우발채무의 발생가능성",
    "q5": "특수관계자와 유의적 거래의 존재 여부",
    "q6": "계정과목 성격의 변화 및 당기 금액 변화 정도",
    "q7": "비경상적인 거래",
    "q8": "관련 회계처리 기준의 변경",
    "q9": "법규 및 감독당국의 강조 사항",
    "q10": "주요한 외부환경의 변화가 존재하는 계정",
}
QUAL_FACTORS = tuple(QUAL_FACTOR_LABELS)

# 평가값 H/M/L = 3/2/1 (원천 BS 시트 B12:C14)
RATING_LABELS = {"H": "High", "M": "Medium", "L": "Low"}
RATINGS = tuple(RATING_LABELS)
RATING_SCORES = {"H": 3, "M": 2, "L": 1}
# 원천 표기 → 코드 (템플릿 적재용)
RATING_ALIASES = {"high": "H", "medium": "M", "low": "L"}

# 질적 판정 정책 (ADR-0034 §2.4, 2026-09-22 결정) — **이상(≥) 2** 가 기본이다.
# 하드코딩하지 않는다. 감사인이 다른 기준을 요구하면 바로 바꿀 수 있어야 한다.
POLICY_SCOPING_QUAL_THRESHOLD = "scoping_qual_threshold"
POLICY_SCOPING_QUAL_COMPARISON = "scoping_qual_comparison"
DEFAULT_QUAL_THRESHOLD = "2"
QUAL_COMPARISON_GE = "ge"   # 이상
QUAL_COMPARISON_GT = "gt"   # 초과
QUAL_COMPARISONS = {QUAL_COMPARISON_GE: "이상", QUAL_COMPARISON_GT: "초과"}
DEFAULT_QUAL_COMPARISON = QUAL_COMPARISON_GE

# 스코핑 상태 (ADR-0034 §2.2)
STATUS_DRAFT = "draft"
STATUS_REVIEW = "review"
STATUS_CONFIRMED = "confirmed"
STATUS_LABELS = {STATUS_DRAFT: "작성 중", STATUS_REVIEW: "검토 중", STATUS_CONFIRMED: "확정"}
STATUSES = tuple(STATUS_LABELS)
# 허용 전이. 확정 → 작성 중 은 재오픈이며 icfr_manager + 사유가 필요하다
TRANSITIONS = {
    STATUS_DRAFT: {STATUS_REVIEW},
    STATUS_REVIEW: {STATUS_CONFIRMED, STATUS_DRAFT},
    STATUS_CONFIRMED: {STATUS_DRAFT},
}

# 필드 출처 상태 — **불리언이 아니라 값 목록이다.** ADR-0034 §5 의 "검토 확인" 상태가
# 나중에 붙는다. 불리언이면 그때 스키마를 또 바꿔야 한다.
ORIGIN_TEMPLATE = "template"   # 템플릿에서 온 그대로 — 배지
ORIGIN_EDITED = "edited"       # 사용자가 바꿈 — 배지 해제
ORIGIN_LABELS = {ORIGIN_TEMPLATE: "템플릿 문구", ORIGIN_EDITED: "직접 수정"}
ORIGIN_STATUSES = tuple(ORIGIN_LABELS)

# 출처 대상 종류 (다형 — FK 없음, 아래 ScopingFieldOrigin)
ORIGIN_TARGET_SCOPING = "scoping"
ORIGIN_TARGET_TEXT = "text"
ORIGIN_TARGET_ACCOUNT = "account"
ORIGIN_TARGET_BENCHMARK = "benchmark"
ORIGIN_TARGETS = (ORIGIN_TARGET_SCOPING, ORIGIN_TARGET_TEXT, ORIGIN_TARGET_ACCOUNT, ORIGIN_TARGET_BENCHMARK)

CONCLUSIONS = ("Y", "N")

DEFAULT_TEMPLATE_CODE = "ICFR_STD"


# ── 전역 템플릿 (IdentityBase — tenant_id 없음) ────────────────────

class ScopingTemplate(IdentityBase):
    """스코핑 템플릿 한 판. **개정은 새 version 행이다** — 이미 복사된 스코핑은 옛 버전 그대로다."""
    __tablename__ = "scoping_templates"
    __table_args__ = (
        Index("uq_scoping_templates_code_version", "code", "version", unique=True,
              sqlite_where=text("is_deleted = 0"), postgresql_where=text("NOT is_deleted")),
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # 템플릿 단위 기본값 (설정근거 문구 등은 텍스트 행)
    default_benchmark: Mapped[str] = mapped_column(String(30), nullable=False,
                                                   default=BENCHMARK_ADJUSTED_PBT)
    default_rates: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    default_smt_rate: Mapped[str] = mapped_column(String(10), nullable=False, default=DEFAULT_SMT_RATE)


class ScopingTemplateText(IdentityBase):
    """템플릿 문구 — 가이던스·질적 10요소 설명·판단 원칙·Notes·설정근거. 키로 식별한다."""
    __tablename__ = "scoping_template_texts"
    __table_args__ = (
        Index("uq_scoping_template_texts_key", "template_id", "key", unique=True,
              sqlite_where=text("is_deleted = 0"), postgresql_where=text("NOT is_deleted")),
    )
    template_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("scoping_templates.id"),
                                              nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ScopingTemplateAccount(IdentityBase):
    """템플릿 계정 한 줄 — 계정명·소속 구분·질적 10요소 평가값·판단 근거·수동 판정. **금액은 없다.**"""
    __tablename__ = "scoping_template_accounts"
    template_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("scoping_templates.id"),
                                              nullable=False, index=True)
    statement_type: Mapped[str] = mapped_column(String(10), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    group_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    ratings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    qual_basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_conclusion: Mapped[str | None] = mapped_column(String(1), nullable=True)
    manual_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


# ── 테넌트 스코핑 (AuditedBase) ────────────────────────────────────

def _scoping_fk(name: str) -> ForeignKeyConstraint:
    """하위 테이블 → scopings 복합 FK (ADR-0030 §2.3). 테넌트를 넘는 참조를 DB 가 막는다."""
    return ForeignKeyConstraint(["scoping_id", "tenant_id"], ["scopings.id", "scopings.tenant_id"],
                                name=name)


class Scoping(AuditedBase):
    """회계연도별 스코핑 1건 (ADR-0034 §2.1). 대상은 별도재무제표."""
    __tablename__ = "scopings"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_scopings_id_tenant"),
        # **처음부터 부분 유니크** — 13.9-35 ④·13.9-42 를 반복하지 않는다
        Index("uq_scopings_tenant_year", "tenant_id", "fiscal_year", unique=True,
              sqlite_where=text("is_deleted = 0"), postgresql_where=text("NOT is_deleted")),
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_DRAFT)
    template_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 양적 중요성 (§2.3)
    selected_benchmark: Mapped[str] = mapped_column(String(30), nullable=False,
                                                    default=BENCHMARK_ADJUSTED_PBT)
    smt_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False,
                                              default=lambda: Decimal(DEFAULT_SMT_RATE))
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)   # 설정근거 — 확정 전 필수
    # 확정 (§2.2)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    confirm_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirm_badge_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # **확정 스냅샷** — 결론은 평소 산출하지만 확정 당시 판단은 보존한다(ADR-0034 §3)
    confirmed_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 감사인 검토 기록 — 시스템 밖에서 이뤄진 검토를 icfr_manager 가 기록한다(§2.2)
    # 증빙은 **텍스트 참조**(문서명·보관 위치)다. 증빙 모듈이 통제×회차에만 붙어서 지금은 첨부할
    # 수 없다 — 파일 첨부는 증빙 모듈 확장 별건(ClaudeICFR.md 13.9-49)
    review_auditor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_opinion: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_evidence_ref: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScopingBenchmark(AuditedBase):
    """벤치마크 한 종 — 기준값(원)·비율. 산출액은 저장하지 않는다."""
    __tablename__ = "scoping_benchmarks"
    __table_args__ = (
        _scoping_fk("fk_scoping_benchmarks_scoping_tenant"),
        Index("uq_scoping_benchmarks_kind", "tenant_id", "scoping_id", "kind", unique=True,
              sqlite_where=text("is_deleted = 0"), postgresql_where=text("NOT is_deleted")),
    )
    scoping_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    # 조정세전순이익이면 **조정 전 세전이익**이다 — 조정은 ScopingAdjustment 합으로 더한다
    base_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)


class ScopingAdjustment(AuditedBase):
    """조정세전순이익의 비경상 조정 1건. **부호를 붙인 금액을 더한다**(감소 조정은 음수).

    원천은 FY2022 `=SUM(F43:F45)`(더함), FY2021 `=G43-SUM(G45:G45)`(뺌)로 연도마다 부호가
    달랐다. 부호를 금액에 싣고 항상 더하면 해석이 하나가 된다(6-1 STEP 0, 원천 불일치 1).
    """
    __tablename__ = "scoping_adjustments"
    __table_args__ = (_scoping_fk("fk_scoping_adjustments_scoping_tenant"),)
    scoping_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class ScopingText(AuditedBase):
    """복사된 문구 — 템플릿 문구 키 그대로. 사용자가 고칠 수 있고 그러면 배지가 떨어진다."""
    __tablename__ = "scoping_texts"
    __table_args__ = (
        _scoping_fk("fk_scoping_texts_scoping_tenant"),
        Index("uq_scoping_texts_key", "tenant_id", "scoping_id", "key", unique=True,
              sqlite_where=text("is_deleted = 0"), postgresql_where=text("NOT is_deleted")),
    )
    scoping_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ScopingAccount(AuditedBase):
    """계정 평가 1줄 (ADR-0034 §2.4). 금액은 원 단위 — 원천 주석 시트는 백만원이라 입력 시 환산한다."""
    __tablename__ = "scoping_accounts"
    __table_args__ = (_scoping_fk("fk_scoping_accounts_scoping_tenant"),)
    scoping_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    statement_type: Mapped[str] = mapped_column(String(10), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    group_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    current_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prior_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # 질적 10요소 {q1: "H", ...}. 키가 없거나 None 이면 미입력 — **0 으로 합산하지 않는다**
    ratings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    qual_basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 수동 판정 — 사유 필수. 계산 결론은 따로 산출되므로 **둘 다 보존**된다
    manual_conclusion: Mapped[str | None] = mapped_column(String(1), nullable=True)
    manual_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScopingStatusHistory(AuditedBase):
    """상태 전이 이력 — 검토 요청·확정·재오픈. 재오픈 사유가 여기 남는다."""
    __tablename__ = "scoping_status_history"
    __table_args__ = (_scoping_fk("fk_scoping_status_history_scoping_tenant"),)
    scoping_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    from_status: Mapped[str] = mapped_column(String(20), nullable=False)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    badge_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 확정 이력마다 그때의 결론 스냅샷을 남긴다 — 재오픈하면 scopings.confirmed_snapshot 은
    # 비워지지만 "그때 무엇을 확정했는지"는 여기 남는다
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ScopingFieldOrigin(AuditedBase):
    """필드 단위 출처 — **배지**(ADR-0034 §2.7).

    템플릿에서 복사된 필드에만 행이 생긴다. 사용자가 처음부터 입력한 필드는 행이 없다(배지 없음).
    사용자가 **값을 바꿔** 저장하면 `edited` 로 바뀐다. 같은 값 재저장은 수정이 아니다.

    **대상이 다형이라 FK 를 걸 수 없다.** `target_type`(scoping/text/account) + `target_id` 가
    서로 다른 테이블을 가리킨다. 존재 검증은 쓰는 쪽 핸들러가 한다(`api/scoping.py`) — 출처 행은
    핸들러가 대상과 같은 트랜잭션에서만 만들고 바꾼다. 스코핑 자신에 대한 복합 FK 는 건다.
    """
    __tablename__ = "scoping_field_origins"
    __table_args__ = (
        _scoping_fk("fk_scoping_field_origins_scoping_tenant"),
        Index("uq_scoping_field_origins_field", "tenant_id", "target_type", "target_id", "field",
              unique=True, sqlite_where=text("is_deleted = 0"), postgresql_where=text("NOT is_deleted")),
    )
    scoping_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    field: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ORIGIN_TEMPLATE)
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
