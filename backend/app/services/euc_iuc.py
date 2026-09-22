"""EUC·IUC 공통 해석 — 살아 있는 정보 항목, 파일 산출값, 쓰기 권한 (ADR-0033, 5-1).

EUC 화면(파일 중심)·IUC 화면(정보 항목 중심)·대시보드 집계가 **같은 해석**을 봐야 한다.
각자 계산하면 "IUC 에는 8건인데 대시보드는 9건" 같은 어긋남이 생긴다 — 그래서 한 곳에 둔다.

**effective 제외(2026-09-22 정정)** — 통제가 overlay 로 exclude 되면 그 통제의 정보 항목을
물리적으로 건드리지 않고 계산에서만 뺀다. `resolve_controls` 는 cascade 까지 반영한
살아 있는 통제만 돌려주므로 **그 목록에 없는 통제의 항목은 제외**다. 복원하면 그대로 돌아온다.
ADR-0029 §2.4(통제 제외 시 어서션 연결도 함께 제외)와 같은 원칙이다.
"""
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.permissions import can_write, tenant_roles
from app.models.euc import EucFile
from app.models.iuc import InformationItem
from app.models.role_assignment import ROLE_ASSESSOR, ROLE_CONTROL_OWNER, ROLE_ICFR_MANAGER
from app.services.control_resolver import resolve_controls, resolve_processes
from app.services.euc_risk import (
    file_importance,
    identification_threshold,
    is_identified,
    risk_grade,
)
from app.services.role_resolver import _assignments_by_target, resolve_roles_for_control


def alive_controls(db: Session) -> dict[UUID, dict]:
    """살아 있는 통제 id → resolver 행. **정보 항목의 제외 판정 기준이다.**"""
    return {c["id"]: c for c in resolve_controls(db)}


def live_items(db: Session, controls: dict[UUID, dict]) -> list[InformationItem]:
    """살아 있는 통제에 딸린 정보 항목만. 제외된 통제의 항목은 여기서 빠진다(effective 제외)."""
    return [
        i for i in db.query(InformationItem).filter(
            InformationItem.is_deleted == False,  # noqa: E712
        ).all()
        if i.control_id in controls
    ]


@dataclass
class FileView:
    """EUC 파일 1건 + 산출값. 산출값은 저장하지 않는다(`services/euc_risk.py`)."""
    file: EucFile
    importance: str | None
    risk_grade: str | None
    identified: bool | None
    # 이 파일을 참조하는 **살아 있는** 통제. 전부 제외되면 빈 목록이 된다 —
    # 파일은 독립 대상이라 지우지 않고 "참조 통제 0건" 으로 보인다.
    control_ids: list[UUID] = field(default_factory=list)

    @property
    def source_mismatch(self) -> bool:
        """원천 참고값과 산출 등급이 **둘 다 있는데 다르면** 검토 신호다.

        한쪽이 없으면(미평가 포함) 비교하지 않는다 — 없는 것과 다른 것은 다른 상태다.
        """
        src = (self.file.source_risk_rating or "").strip().lower() or None
        return src is not None and self.risk_grade is not None and src != self.risk_grade


def file_views(db: Session, controls: dict[UUID, dict] | None = None) -> list[FileView]:
    """모든 EUC 파일의 산출값. 파일 중요성은 살아 있는 정보 항목만으로 계산한다."""
    controls = alive_controls(db) if controls is None else controls
    threshold = identification_threshold(db)
    items = live_items(db, controls)

    by_file: dict[UUID, list[InformationItem]] = {}
    for it in items:
        if it.euc_file_id is not None:
            by_file.setdefault(it.euc_file_id, []).append(it)

    views = []
    for f in db.query(EucFile).filter(EucFile.is_deleted == False).order_by(EucFile.name).all():  # noqa: E712
        linked = by_file.get(f.id, [])
        imp = file_importance([i.importance for i in linked])
        grade = risk_grade(f.complexity, imp)
        views.append(FileView(
            file=f, importance=imp, risk_grade=grade,
            identified=is_identified(grade, threshold),
            control_ids=sorted({i.control_id for i in linked}, key=str),
        ))
    return views


# ── 쓰기 권한 (5-1 §2.5) ───────────────────────────────────
# **`require_write` 로 기본 처리하지 않는다.** 그러면 external_auditor 만 막히고 누구나 쓴다 —
# 13.9-35·13.9-41 에서 두 번 반복된 결함이다. 누가 쓸 수 있는지를 여기서 명시한다.

def writable_control_ids(db: Session, user_id: UUID,
                         controls: dict[UUID, dict] | None = None) -> set[UUID]:
    """이 사용자가 정보 항목을 쓸 수 있는 통제.

    - `icfr_manager` → 전부
    - 그 외 → 그 통제의 `control_owner`·`assessor` 인 통제만 (통제 단위, 프로세스 기본값 포함)
    - `external_auditor` → 없음 (조회 전용, ADR-0031 §2.1)
    """
    roles = tenant_roles(db, user_id)
    if not can_write(roles):
        return set()
    controls = alive_controls(db) if controls is None else controls
    if ROLE_ICFR_MANAGER in roles:
        return set(controls)

    assignments = _assignments_by_target(db)
    process_id_by_code = {p["code"]: p["id"] for p in resolve_processes(db)}
    writable: set[UUID] = set()
    for cid, c in controls.items():
        resolved = resolve_roles_for_control(
            db, cid, process_id_by_code.get(c["process_code"]),
            assignments=assignments, primary_dept={}, user_names={},
        )
        if any(r["user_id"] == user_id and r["role_name"] in (ROLE_CONTROL_OWNER, ROLE_ASSESSOR)
               for r in resolved):
            writable.add(cid)
    return writable


def owner_control_ids(db: Session, user_id: UUID,
                      controls: dict[UUID, dict] | None = None) -> set[UUID]:
    """이 사용자가 `control_owner` 인 통제 — EUC 파일 쓰기 판정용.

    파일은 `control_owner` 만(assessor 제외) 고칠 수 있다. 파일은 도구 자체이고, 도구를 관리하는
    것은 그 도구로 통제를 수행하는 사람이다. assessor 는 평가자라 도구를 바꾸는 쪽이 아니다.
    """
    controls = alive_controls(db) if controls is None else controls
    assignments = _assignments_by_target(db)
    process_id_by_code = {p["code"]: p["id"] for p in resolve_processes(db)}
    owned: set[UUID] = set()
    for cid, c in controls.items():
        resolved = resolve_roles_for_control(
            db, cid, process_id_by_code.get(c["process_code"]),
            assignments=assignments, primary_dept={}, user_names={},
        )
        if any(r["user_id"] == user_id and r["role_name"] == ROLE_CONTROL_OWNER for r in resolved):
            owned.add(cid)
    return owned


def can_edit_file(db: Session, user_id: UUID, view: FileView,
                  controls: dict[UUID, dict] | None = None) -> bool:
    """EUC 파일 쓰기 — `icfr_manager`, 또는 **이 파일을 참조하는 통제 중 하나의** `control_owner`.

    아무 통제도 참조하지 않는 파일은 `icfr_manager` 만 고칠 수 있다.
    """
    roles = tenant_roles(db, user_id)
    if not can_write(roles):
        return False
    if ROLE_ICFR_MANAGER in roles:
        return True
    return bool(owner_control_ids(db, user_id, controls) & set(view.control_ids))
