"""정보 항목(IUC) — ADR-0033 §1.2·§2.1(정정)·§2.2(정정)·§2.7, 5-1.

**정보 항목은 RCM 통제에 딸린다.** 통제가 쓰는 정보를 기술한다(IUC 관점). 정보 Type 이
EUC 인 항목은 EUC 파일을 참조하고, 여러 정보 항목(= 여러 통제)이 같은 파일을 가리킬 수 있다.

**중요성은 여기에 입력한다**(§2.2 정정). 같은 파일도 쓰는 통제에 따라 재무보고 영향이 다르다.
파일 단위 중요성은 연결된 정보 항목 중 최고값으로 산출하며 저장하지 않는다.

**통제 FK 는 걸지 않는다.** 통제 id 는 baseline/instance 두 테이블에 걸친 정체성 id 라
한쪽 테이블만 가리키는 FK 가 성립하지 않는다 — 걸면 회사가 추가한(add) 통제에는 정보 항목을
붙일 수 없다. `role_assignments.target_id`·`cycle_targets.control_id` 와 같은 처리이며,
**존재 검증은 핸들러가 `resolve_controls` 로 한다.**

⚠️ **위험 승계(13.9-27)** — FK 가 없으므로 `seed_baseline --reset` 으로 통제 id 가 바뀌면
정보 항목의 연결이 **조용히 끊어진다.** 정보 항목이 생긴 뒤에는 재시딩하지 말 것.

**통제 제외 시 물리적으로 건드리지 않는다**(2026-09-22 정정). 통제가 overlay 로 exclude 되면
그 통제의 정보 항목은 effective 제외로 계산한다 — `resolve_controls` 에 없는 통제의 항목은
IUC 목록·집계·파일 중요성 계산에서 빠지고, 복원하면 그대로 돌아온다. ADR-0029 §2.4
(통제 제외 시 어서션 연결도 함께 제외)와 같은 원칙이다.
"""
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditedBase

# ── 값 상수 — 정의처는 여기 하나다(13.9-40 교훈) ─────────────────────

# 정보 Type (§2.7). **지금은 EUC 하나만 지원하되 확장 가능하게 둔다** — 원천 양식에는
# `EUC information` 만 나타난다. ERP 리포트(`system_generated`) 등이 나중에 여기 추가된다.
INFO_TYPE_EUC = "euc"
INFO_TYPE_LABELS = {INFO_TYPE_EUC: "EUC information"}
INFO_TYPES = tuple(INFO_TYPE_LABELS)
# 원천 표기 → 코드값 (시드용)
INFO_TYPE_ALIASES = {"euc information": INFO_TYPE_EUC}

# 중요성 — 원천 IUC 양식 값(H/M/L) 그대로. 순서가 곧 서열이다(파일 중요성 = 최고값).
IMPORTANCE_LABELS = {"H": "높음", "M": "보통", "L": "낮음"}
IMPORTANCE_VALUES = tuple(IMPORTANCE_LABELS)


class InformationItem(AuditedBase):
    """통제에 쓰이는 정보 1건 (IPE — Information Produced by Entity)."""
    __tablename__ = "information_items"
    __table_args__ = (
        # 파일 참조는 테넌트를 넘지 못한다 (ADR-0030 §2.3 복합 FK)
        ForeignKeyConstraint(
            ["euc_file_id", "tenant_id"], ["euc_files.id", "euc_files.tenant_id"],
            name="fk_information_items_euc_file_tenant",
        ),
        # 같은 통제에 같은 이름의 정보가 두 번 붙지 않는다. **처음부터 부분 유니크.**
        Index(
            "uq_information_items_control_name", "tenant_id", "control_id", "name",
            unique=True, sqlite_where=text("is_deleted = 0"),
            postgresql_where=text("NOT is_deleted"),
        ),
    )

    # 통제 정체성 id (baseline id 또는 add instance id). FK 없음 — 위 docstring
    control_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    info_type: Mapped[str] = mapped_column(String(30), nullable=False, default=INFO_TYPE_EUC)
    # NULL = 미평가. 입력처는 여기 하나다(§2.2 — 두 곳에서 받지 않는다)
    importance: Mapped[str | None] = mapped_column(String(1), nullable=True)
    euc_file_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True  # FK 는 위 복합 FK
    )
    # IUC 관점 필드 (원천 IPE Template 열)
    system_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    itgc_in_scope: Mapped[str | None] = mapped_column(String(10), nullable=True)
    source_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_logic: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_parameter: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_data_review: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_logic_control: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_parameter_review: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ADR-0032 설계평가 회차와의 관계는 미결(§5) — 지금은 원천 서술을 그대로 담는다
    design_assessment_result: Mapped[str | None] = mapped_column(Text, nullable=True)
