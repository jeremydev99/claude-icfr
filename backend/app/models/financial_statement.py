"""재무제표·계정 트리 — ADR-0037, 8-A.

**재무제표가 계정 행을 정하고, 템플릿은 매칭으로 기본값만 공급한다**(ADR-0037 §1). 8-A 는 데이터
구조와 검증만 만든다. 업로드(8-B)·템플릿 매칭(8-C)·화면(8-D)·스코핑 연결(8-E)은 후속이다.

**기존 스코핑과 병행 신규 구축이다.** `scoping_accounts`·`scoping_template_accounts` 와 이름이
겹치지 않게 `fs_` 접두를 쓰고, 상수도 `models/scoping.py` 의 `STATEMENT_*` 를 import 하지 않고
`FS_` 접두로 따로 둔다(13.9-40 — 축이 다르면 상수를 나눈다). 코드값(BS/PL/CF)은 8-E 매칭을
쉽게 하려고 스코핑과 같게 맞췄다.

세 테이블 + 상태 이력 하나다.

- **계정 마스터(`fs_accounts`)** — 회사 단위 하나. 재무제표마다 복제하지 않는다(§2.1). 트리는
  `parent_id` + `sort_order`(adjacency list), 조회는 재귀 CTE(`services/financial_statement.py`)
- **재무제표 헤더(`fs_statements`)** — 회계연도 × 종류 × 연결/별도. 단위·통화·허용 오차를 여기 둔다
- **금액 행(`fs_amounts`)** — 헤더 × 계정. 금액은 **공시 표시 그대로**(괄호는 음수, 비용은 양수),
  합산 부호는 계정의 `rollup_sign` 이다(§2.4). 원본 보존 컬럼(`raw_*`)을 둔다
- **상태 이력(`fs_statement_status_events`)** — 확정·재오픈마다 1행

**판별은 구조로 한다**(§2.3). 자산·부채를 계정명으로 판정하지 않는다 — `section` 과 `is_subtotal`
로만 한다. 검증 로직에 계정명 문자열 비교를 넣지 않는다.
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditedBase

# ── 값 상수 — 정의처는 여기 하나다(13.9-40) ────────────────────────
# 라벨은 화면에 필요하므로 코드값과 함께 둔다. dict 순서 = 표시 순서.

# 재무제표 종류 (ADR-0037 §2.5). 주석(NOTE)은 트리형 재무제표가 아니라 넣지 않는다(8-E 소관)
FS_STATEMENT_BS = "BS"
FS_STATEMENT_PL = "PL"
FS_STATEMENT_CF = "CF"
FS_STATEMENT_SCE = "SCE"
FS_STATEMENT_LABELS = {
    FS_STATEMENT_BS: "재무상태표",
    FS_STATEMENT_PL: "손익계산서",
    FS_STATEMENT_CF: "현금흐름표",
    FS_STATEMENT_SCE: "자본변동표",
}
FS_STATEMENT_TYPES = tuple(FS_STATEMENT_LABELS)

# 연결·별도 (§2.6). 회사는 지금 별도만 쓰지만 나중에 넣으면 마이그레이션이 한 번 더 필요하다
FS_BASIS_SEPARATE = "separate"
FS_BASIS_CONSOLIDATED = "consolidated"
FS_BASIS_LABELS = {FS_BASIS_SEPARATE: "별도", FS_BASIS_CONSOLIDATED: "연결"}
FS_BASES = tuple(FS_BASIS_LABELS)

# 섹션 — **판별은 이 값으로 한다**(§2.3). 재무제표 종류마다 허용 값이 다르다
FS_SECTION_ASSET = "asset"
FS_SECTION_LIABILITY = "liability"
FS_SECTION_EQUITY = "equity"
FS_SECTION_LIABILITY_EQUITY = "liability_equity"   # 부채와자본총계 — 자산=부채+자본 판정에서 제외
FS_SECTION_LABELS = {
    FS_SECTION_ASSET: "자산",
    FS_SECTION_LIABILITY: "부채",
    FS_SECTION_EQUITY: "자본",
    FS_SECTION_LIABILITY_EQUITY: "부채와자본",
    "revenue": "수익",
    "expense": "비용",
    "profit": "손익(이익 소계)",
    "operating": "영업활동",
    "investing": "투자활동",
    "financing": "재무활동",
    "cf_other": "현금흐름 기타",
    "equity_change": "자본변동",
}
FS_SECTIONS = tuple(FS_SECTION_LABELS)
FS_SECTIONS_BY_STATEMENT = {
    FS_STATEMENT_BS: (FS_SECTION_ASSET, FS_SECTION_LIABILITY, FS_SECTION_EQUITY,
                      FS_SECTION_LIABILITY_EQUITY),
    FS_STATEMENT_PL: ("revenue", "expense", "profit"),
    FS_STATEMENT_CF: ("operating", "investing", "financing", "cf_other"),
    FS_STATEMENT_SCE: ("equity_change",),
}

# 합산 부호 (§2.4) — 부모 소계에 더할 때 곱한다. 비용은 양수로 표시되므로 이익 소계 아래에서 -1
FS_ROLLUP_SIGNS = (1, -1)

# 단위 (§2.7) — 원 기준 배수. **검증은 재무제표 단위 그대로 한다**(원으로 환산하지 않는다)
FS_UNIT_LABELS = {1: "원", 1000: "천원", 1000000: "백만원"}
FS_UNITS = tuple(FS_UNIT_LABELS)
FS_DEFAULT_CURRENCY = "KRW"

# 상태 (§2.9). 가로 연도형에서 최신 연도를 자동 final 로 두는 규칙은 8-B 파서가 적용한다
FS_STATUS_DRAFT = "draft"
FS_STATUS_FINAL = "final"
FS_STATUS_LABELS = {FS_STATUS_DRAFT: "작성 중", FS_STATUS_FINAL: "확정"}
FS_STATUSES = tuple(FS_STATUS_LABELS)

# 원천 형태 (8-B 가 채운다). 8-A 에서는 값 목록만 둔다
FS_SOURCE_KIND_LABELS = {
    "horizontal_years": "가로 연도형",
    "disclosure_form": "공시양식형",
    "manual": "직접 입력",
}
FS_SOURCE_KINDS = tuple(FS_SOURCE_KIND_LABELS)

# 금액 정밀도 (§2.7, 마스터 확정 Q1) — Numeric(20, 2). (20, 0)은 소수 입력 시 조용히 반올림한다
FS_AMOUNT_PRECISION = 20
FS_AMOUNT_SCALE = 2


def _amount(nullable: bool = True, **kw):
    return mapped_column(Numeric(FS_AMOUNT_PRECISION, FS_AMOUNT_SCALE), nullable=nullable, **kw)


# ── 계정 마스터 ─────────────────────────────────────────────────────

class FsAccount(AuditedBase):
    """회사 계정 1개 (§2.1~2.3).

    **폐지는 행을 지우지 않는다**(§2.10) — `valid_to_year` 로 표현한다. 과거 연도 금액은 그대로
    이 행을 참조한다. `name` 은 사람이 읽는 표준 계정명이며 **검증 로직은 이 값을 보지 않는다.**

    순환(자기 자신·자기 자손을 부모로)은 DB 가 `parent_id <> id` 만 막고, 나머지는 서비스가
    재귀 CTE 로 막는다 — 자손 판정은 CHECK 로 표현할 수 없다.
    """
    __tablename__ = "fs_accounts"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_fs_accounts_id_tenant"),
        # 부모 → 같은 테넌트 계정만 (ADR-0030 §2.3). parent_id 가 NULL 이면 검사하지 않는다(MATCH SIMPLE)
        ForeignKeyConstraint(["parent_id", "tenant_id"], ["fs_accounts.id", "fs_accounts.tenant_id"],
                             name="fk_fs_accounts_parent_tenant"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_fs_accounts_not_self_parent"),
        CheckConstraint("rollup_sign IN (1, -1)", name="ck_fs_accounts_rollup_sign"),
        CheckConstraint("valid_from_year IS NULL OR valid_to_year IS NULL OR valid_from_year <= valid_to_year",
                        name="ck_fs_accounts_valid_range"),
        Index("uq_fs_accounts_code", "tenant_id", "code", unique=True,
              sqlite_where=text("is_deleted = 0 AND code IS NOT NULL"),
              postgresql_where=text("NOT is_deleted AND code IS NOT NULL")),
    )
    statement_type: Mapped[str] = mapped_column(String(10), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    section: Mapped[str] = mapped_column(String(30), nullable=False)
    is_subtotal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rollup_sign: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    # 유효 회계연도 범위 — NULL 은 그 쪽 경계 없음
    valid_from_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_to_year: Mapped[int | None] = mapped_column(Integer, nullable=True)


# ── 재무제표 헤더 ───────────────────────────────────────────────────

class FsStatement(AuditedBase):
    """재무제표 1건 = 회계연도 × 종류 × 연결/별도 (§2.5·2.6).

    **단위·통화를 여기 저장한다**(§2.7) — 단위를 잘못 읽으면 검증이 엉뚱한 곳에서 깨진다.
    금액·허용 오차·검증 차액은 전부 이 단위 기준이다.
    """
    __tablename__ = "fs_statements"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_fs_statements_id_tenant"),
        # **처음부터 부분 유니크** — 13.9-35 ④·13.9-42 를 반복하지 않는다
        Index("uq_fs_statements_year_type_basis", "tenant_id", "fiscal_year", "statement_type", "basis",
              unique=True, sqlite_where=text("is_deleted = 0"), postgresql_where=text("NOT is_deleted")),
        CheckConstraint("tolerance >= 0", name="ck_fs_statements_tolerance"),
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    statement_type: Mapped[str] = mapped_column(String(10), nullable=False)
    basis: Mapped[str] = mapped_column(String(20), nullable=False, default=FS_BASIS_SEPARATE)
    unit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default=FS_DEFAULT_CURRENCY)
    # 허용 오차 (마스터 확정 Q3) — |차액| <= tolerance 면 통과. 기본 0(엄격). 단위는 재무제표 단위
    tolerance: Mapped[Decimal] = _amount(nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=FS_STATUS_DRAFT)
    # 현재 확정 정보 — 재오픈하면 비운다. 이력은 fs_statement_status_events 에 남는다
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"),
                                                         nullable=True)
    # 원천 (8-B 가 채운다)
    source_kind: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source_sheet: Mapped[str | None] = mapped_column(String(200), nullable=True)


# ── 금액 행 ─────────────────────────────────────────────────────────

class FsAmount(AuditedBase):
    """재무제표 × 계정 금액 1행 (§2.4·2.8).

    `amount` 는 **공시 표시 그대로**다 — 괄호 표기는 음수, 비용은 양수. 합산은 계정의
    `rollup_sign` 으로 한다. 파일별 표기 차이는 8-B preview 에서 뒤집는다.
    `amount` NULL 은 금액 칸이 비어 있는 행(제목 행 등)이다 — 0 과 다르다.

    **원본 보존 컬럼**(`raw_*`) — 8-B 파서가 무엇을 읽든 담을 수 있게 둔다. 파서를 만들 때
    구조를 고치지 않기 위해서다. 정해진 칸에 없는 것은 `raw_meta`(JSON)에 둔다.
    """
    __tablename__ = "fs_amounts"
    __table_args__ = (
        ForeignKeyConstraint(["statement_id", "tenant_id"], ["fs_statements.id", "fs_statements.tenant_id"],
                             name="fk_fs_amounts_statement_tenant"),
        ForeignKeyConstraint(["account_id", "tenant_id"], ["fs_accounts.id", "fs_accounts.tenant_id"],
                             name="fk_fs_amounts_account_tenant"),
        Index("uq_fs_amounts_statement_account", "tenant_id", "statement_id", "account_id", unique=True,
              sqlite_where=text("is_deleted = 0"), postgresql_where=text("NOT is_deleted")),
    )
    statement_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    amount: Mapped[Decimal | None] = _amount()
    raw_row_no: Mapped[int | None] = mapped_column(Integer, nullable=True)      # 원본 행번호
    raw_label: Mapped[str | None] = mapped_column(String(300), nullable=True)   # 원본 표기 계정명
    raw_indent: Mapped[int | None] = mapped_column(Integer, nullable=True)      # 원본 들여쓰기 수준
    raw_value: Mapped[str | None] = mapped_column(String(100), nullable=True)   # 원본 셀 텍스트 "(1,234)"
    raw_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)          # 주석번호 등 나머지


# ── 상태 이력 ───────────────────────────────────────────────────────

class FsStatementStatusEvent(AuditedBase):
    """확정·재오픈 1건 (마스터 확정 Q4). **금액 스냅샷은 만들지 않는다.**

    확정 행에는 그때의 허용 오차와 건너뛴(skipped) 소계 건수를 남긴다. 허용 오차가 0 이 아닌
    상태로 확정했으면 규칙별 실제 차액(`tolerance_diffs`)도 남긴다 — 오차를 허용해 확정했다는
    사실과 그 크기를 나중에 설명할 수 있어야 한다.
    """
    __tablename__ = "fs_statement_status_events"
    __table_args__ = (
        ForeignKeyConstraint(["statement_id", "tenant_id"], ["fs_statements.id", "fs_statements.tenant_id"],
                             name="fk_fs_statement_status_events_statement_tenant"),
    )
    statement_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    from_status: Mapped[str] = mapped_column(String(10), nullable=False)
    to_status: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tolerance: Mapped[Decimal | None] = _amount()
    skipped_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tolerance_diffs: Mapped[list | None] = mapped_column(JSON, nullable=True)


# ── 템플릿 링크 (8-C) ───────────────────────────────────────────────

# 매칭 근거 (ADR-0037 §4) — **서버가 이름 규칙으로 판정한다**(클라이언트가 보내지 않는다)
FS_LINK_EXACT = "exact"             # 공백 제거 후 동일
FS_LINK_NORMALIZED = "normalized"   # 접두 번호·괄호/밑줄 접미를 뗀 뒤 동일
FS_LINK_MANUAL = "manual"           # 이름 규칙으로 설명되지 않는 사람의 대응
FS_LINK_BASIS_LABELS = {FS_LINK_EXACT: "정확일치", FS_LINK_NORMALIZED: "정규화일치", FS_LINK_MANUAL: "수동"}
FS_LINK_BASES = tuple(FS_LINK_BASIS_LABELS)


class FsTemplateLink(AuditedBase):
    """회사 계정 ↔ 스코핑 템플릿 계정 링크 1건 (8-C, ADR-0037 §4).

    **사람이 확인한 링크만 저장한다.** 자동 제안은 저장하지 않는다. 확정된 링크만 8-E 에서 스코핑 기본값
    (질적 평가값·판단 근거 등) 공급에 쓴다.

    템플릿 계정은 전역(`scoping_template_accounts`)이고 버전마다 행이 따로 있다 — 링크는 그 행 id 를
    참조하고, 조회 편의로 `template_code`·`template_version` 을 함께 둔다. 템플릿이 개정되면 옛 버전 링크는
    그대로 두고 새 버전 링크를 따로 만든다. **회사 계정 1개 × 템플릿 버전 1개당 활성 링크는 1개**(부분 유니크).
    템플릿 계정 하나에 회사 계정 여럿이 걸리는 것은 허용한다(리스부채 유동·비유동 등, 경고만).
    """
    __tablename__ = "fs_template_links"
    __table_args__ = (
        ForeignKeyConstraint(["account_id", "tenant_id"], ["fs_accounts.id", "fs_accounts.tenant_id"],
                             name="fk_fs_template_links_account_tenant"),
        CheckConstraint("basis IN ('exact', 'normalized', 'manual')", name="ck_fs_template_links_basis"),
        Index("uq_fs_template_links_account_version", "tenant_id", "account_id", "template_code",
              "template_version", unique=True,
              sqlite_where=text("is_deleted = 0"), postgresql_where=text("NOT is_deleted")),
    )
    account_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    template_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("scoping_template_accounts.id"), nullable=False, index=True)
    template_code: Mapped[str] = mapped_column(String(50), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # 서버가 항상 판정해 넣는다. 기본값은 가장 보수적인 "수동"(이름 규칙으로 설명되지 않음)
    basis: Mapped[str] = mapped_column(String(20), nullable=False, default=FS_LINK_MANUAL)
    confirmed_by_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
