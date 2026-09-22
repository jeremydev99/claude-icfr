"""6-1b 스코핑 보완 — 검토 확인·중요성 기준 회사 설정·기준 연도 (ADR-0034 정정)

Revision ID: b1c2d3e4f5a6
Revises: a9b0c1d2e3f4
Create Date: 2026-09-22

**칸 추가만 한다. 기존 값을 바꾸지 않는다.**

- `scoping_field_origins.confirmed_by_id`·`confirmed_at` — 검토 확인(`status='confirmed'`)의 누가·언제.
  감사 컬럼(`updated_by`)을 빌리지 않는다 — 시스템 전체에서 비어 있고(13.9-51) 수정 때 덮어써진다
- `scopings.base_fiscal_year`·`smt_guide_low/high`·`qual_threshold`·`qual_comparison` — 중요성 기준을
  **회계연도 스코핑에** 둔다(6-1b §3.2 B안). 테넌트 정책은 새 연도의 기본값으로만 쓴다
- `scoping_benchmarks.guide_low/high` — 비율 가이드 범위(회사 설정)
- `scoping_templates.default_criteria` — 템플릿의 기준 기본값(원천 Note 1·2, 매출액은 비움)

**기존 행 채우기 (마스터 규칙, 2026-09-22)**
- 템플릿: `default_criteria` 가 비어 있으면 원천 기본값으로 채운다(제품 콘텐츠, 테넌트 데이터 아님)
- 작성 중·검토 중 스코핑: 새 기준 칸을 **템플릿 기본값**으로 채우고 **템플릿 배지**(출처 행)를 붙인다.
  새 칸이라 사용자가 입력한 값을 덮어쓰지 않는다. 질적 기준은 그 테넌트 정책 값이 있으면 그것, 없으면 2 이상.
  기준 연도 = 회계연도 − 1
- **확정 스코핑은 채우지 않는다** — 확정 기록을 사후에 바꾸면 안 된다. 새 칸은 NULL 로 남고, 조회는
  기본값으로 대신 보여 주며 확정 판단은 확정 스냅샷이 보존한다. 건수를 출력한다.
  마이그레이션을 실패시키지 않는 이유: push = 운영 마이그레이션 실행이라, 여기서 멈추면 배포가
  깨지고 서비스가 내려간다. 확정 스코핑 존재 여부는 **push 전에 마스터가 조회로 확인**한다.

값은 이 파일에 적는다 — 마이그레이션이 앱 코드(`models/scoping.py` 상수)를 import 하면, 상수가
나중에 바뀔 때 과거 마이그레이션의 결과가 달라진다.
"""
import json
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a9b0c1d2e3f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 원천 Note 1·2 (models/scoping.py BENCHMARK_GUIDE_RANGES·SMT_RATE_GUIDE_RANGE 의 2026-09-22 값)
_BENCHMARK_GUIDES = {
    "adjusted_pbt": ["0.05", "0.10"],
    "revenue": None,                     # 원천 "0.0~5%" 불분명 — 비워 둔다
    "total_assets": ["0.01", "0.02"],
    "total_equity": [None, "0.03"],
    "total_expenses": ["0.03", "0.05"],
    "operating_cf": ["0.03", "0.05"],
}
_SMT_GUIDE = ["0.50", "0.75"]
_DEFAULT_CRITERIA = {"benchmark_guides": _BENCHMARK_GUIDES, "smt_guide": _SMT_GUIDE}
_QUAL_THRESHOLD_KEY = "scoping_qual_threshold"
_QUAL_COMPARISON_KEY = "scoping_qual_comparison"
_QUAL_COMPARISONS = ("ge", "gt")


def upgrade() -> None:
    op.add_column('scoping_templates', sa.Column('default_criteria', sa.JSON(), nullable=True))
    op.add_column('scopings', sa.Column('base_fiscal_year', sa.Integer(), nullable=True))
    op.add_column('scopings', sa.Column('smt_guide_low', sa.Numeric(7, 4), nullable=True))
    op.add_column('scopings', sa.Column('smt_guide_high', sa.Numeric(7, 4), nullable=True))
    op.add_column('scopings', sa.Column('qual_threshold', sa.Numeric(4, 2), nullable=True))
    op.add_column('scopings', sa.Column('qual_comparison', sa.String(10), nullable=True))
    op.add_column('scoping_benchmarks', sa.Column('guide_low', sa.Numeric(9, 6), nullable=True))
    op.add_column('scoping_benchmarks', sa.Column('guide_high', sa.Numeric(9, 6), nullable=True))
    op.add_column('scoping_field_origins', sa.Column('confirmed_by_id', PG_UUID(as_uuid=True),
                                                     sa.ForeignKey('users.id'), nullable=True))
    op.add_column('scoping_field_origins', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))

    bind = op.get_bind()

    # ── 템플릿 기본값 ──
    bind.execute(sa.text("UPDATE scoping_templates SET default_criteria = CAST(:c AS JSON) "
                         "WHERE default_criteria IS NULL"), {"c": json.dumps(_DEFAULT_CRITERIA)})

    # ── 기존 스코핑 ──
    rows = bind.execute(sa.text(
        "SELECT s.id, s.tenant_id, s.fiscal_year, s.status, s.template_version, t.default_criteria "
        "FROM scopings s LEFT JOIN scoping_templates t "
        "  ON t.code = s.template_code AND t.version = s.template_version AND NOT t.is_deleted "
        "WHERE NOT s.is_deleted")).fetchall()
    skipped = []
    for sid, tenant_id, fiscal_year, status, tver, crit in rows:
        if status == "confirmed":
            skipped.append(fiscal_year)
            continue
        crit = crit if isinstance(crit, dict) else (json.loads(crit) if crit else _DEFAULT_CRITERIA)
        smt = crit.get("smt_guide") or _SMT_GUIDE
        guides = crit.get("benchmark_guides") or _BENCHMARK_GUIDES
        pol = dict(bind.execute(sa.text(
            "SELECT policy_key, policy_value FROM tenant_policies "
            "WHERE tenant_id = :t AND NOT is_deleted AND policy_key IN (:k1, :k2)"),
            {"t": tenant_id, "k1": _QUAL_THRESHOLD_KEY, "k2": _QUAL_COMPARISON_KEY}).fetchall())
        threshold = pol.get(_QUAL_THRESHOLD_KEY) or "2"
        comparison = pol.get(_QUAL_COMPARISON_KEY) if pol.get(_QUAL_COMPARISON_KEY) in _QUAL_COMPARISONS else "ge"
        bind.execute(sa.text(
            "UPDATE scopings SET base_fiscal_year = :y, smt_guide_low = :lo, smt_guide_high = :hi, "
            "qual_threshold = :qt, qual_comparison = :qc WHERE id = :id"),
            {"y": fiscal_year - 1, "lo": smt[0], "hi": smt[1], "qt": threshold, "qc": comparison, "id": sid})

        def origin(target_type: str, target_id, field: str) -> None:
            bind.execute(sa.text(
                "INSERT INTO scoping_field_origins "
                "(id, tenant_id, scoping_id, target_type, target_id, field, status, template_version) "
                "VALUES (:id, :t, :s, :tt, :ti, :f, 'template', :v)"),
                {"id": uuid.uuid4(), "t": tenant_id, "s": sid, "tt": target_type, "ti": target_id,
                 "f": field, "v": tver})

        origin("scoping", sid, "smt_guide")
        origin("scoping", sid, "qual_threshold")
        origin("scoping", sid, "qual_comparison")
        for bid, kind in bind.execute(sa.text(
                "SELECT id, kind FROM scoping_benchmarks WHERE scoping_id = :s AND NOT is_deleted"),
                {"s": sid}).fetchall():
            g = guides.get(kind)
            if not g:
                continue   # 매출액 — 기본값이 비어 있으면 채울 것도 배지도 없다
            bind.execute(sa.text("UPDATE scoping_benchmarks SET guide_low = :lo, guide_high = :hi WHERE id = :id"),
                         {"lo": g[0], "hi": g[1], "id": bid})
            origin("benchmark", bid, "guide")
    print(f"  [6-1b] 기준 칸 채움: {len(rows) - len(skipped)}건 / 확정이라 건너뜀: {len(skipped)}건 {skipped}")


def downgrade() -> None:
    bind = op.get_bind()
    # 이 리비전이 붙인 출처 행만 지운다 — 6-1 의 필드명에는 없는 것들이다
    bind.execute(sa.text("DELETE FROM scoping_field_origins "
                         "WHERE field IN ('smt_guide', 'qual_threshold', 'qual_comparison', 'guide')"))
    # 확인 상태는 6-1 에 없던 값이다 — 되돌리면 템플릿 상태로 돌린다(동의 표시만 사라지고 값은 그대로)
    bind.execute(sa.text("UPDATE scoping_field_origins SET status = 'template' WHERE status = 'confirmed'"))
    op.drop_column('scoping_field_origins', 'confirmed_at')
    op.drop_column('scoping_field_origins', 'confirmed_by_id')
    op.drop_column('scoping_benchmarks', 'guide_high')
    op.drop_column('scoping_benchmarks', 'guide_low')
    op.drop_column('scopings', 'qual_comparison')
    op.drop_column('scopings', 'qual_threshold')
    op.drop_column('scopings', 'smt_guide_high')
    op.drop_column('scopings', 'smt_guide_low')
    op.drop_column('scopings', 'base_fiscal_year')
    op.drop_column('scoping_templates', 'default_criteria')
