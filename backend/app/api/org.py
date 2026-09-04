"""부서·소속 API — 3-1, ADR-0031 §2.8.

ADR-0020 준수 — 서비스 클래스 없이 직접 함수와 명시적 분기만 쓴다.
ADR-0025 준수 — **수동 tenant 필터를 걸지 않는다.** `AuditedBase` 자동 격리가 건다.

계약은 기존 RCM API 규약을 따른다(`docs/api/rcm-hierarchy-contract.md`) —
목록 봉투, 404 `{"detail": ...}`, 409 는 사용자에게 그대로 보여줄 수 있는 한국어.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import require_write
from app.models.org import Department, UserDepartment
from app.models.user import User
from app.schemas.org import (
    DepartmentCreate,
    DepartmentRead,
    DepartmentUpdate,
    UserDepartmentCreate,
    UserDepartmentRead,
    UserDepartmentUpdate,
)

router = APIRouter(prefix="/api/org", tags=["org"])


def _user_names(db: Session, ids: set[UUID]) -> dict[UUID, str]:
    """id → display_name. 표시용 파생값을 채우기 위한 메모리 lookup(조인 아님)."""
    if not ids:
        return {}
    return {
        u.id: u.display_name
        for u in db.query(User).filter(User.id.in_(ids)).all()
    }


def _to_department_read(obj: Department, names: dict[UUID, str]) -> DepartmentRead:
    row = DepartmentRead.model_validate(obj)
    row.manager_name = names.get(obj.manager_id) if obj.manager_id else None
    return row


def _assert_name_available(db: Session, name: str, exclude_id: UUID | None = None) -> None:
    """부서명 중복 검증. DB 제약이 있어도 여기서 먼저 본다 —
    IntegrityError 의 일반 문구 대신 의미 있는 메시지를 돌려주기 위해서다
    (통제 code 중복 검증과 같은 이유, 13.9-17)."""
    q = db.query(Department).filter(
        Department.name == name,
        Department.is_deleted == False,  # noqa: E712
    )
    if exclude_id is not None:
        q = q.filter(Department.id != exclude_id)
    if q.first() is not None:
        raise HTTPException(status_code=409, detail=f"부서명 '{name}' 은 이미 사용 중입니다")


def _get_department_or_404(db: Session, dept_id: UUID) -> Department:
    obj = db.query(Department).filter(
        Department.id == dept_id,
        Department.is_deleted == False,  # noqa: E712
    ).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return obj


# ── 부서 ──────────────────────────────────────────────────

@router.get("/departments")
def list_departments(skip: int = 0, limit: int = 100, user: CurrentUser = None,
                     db: Session = Depends(get_db)) -> dict:
    """목록 — 평면. 계층 조립을 하지 않는다(ADR-0031 §2.8, `parent_id` 는 초기 NULL)."""
    q = db.query(Department).filter(Department.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.order_by(Department.name).offset(skip).limit(limit).all()
    names = _user_names(db, {d.manager_id for d in items if d.manager_id})
    return {
        "items": [_to_department_read(d, names) for d in items],
        "total": total, "skip": skip, "limit": limit,
    }


@router.post("/departments", status_code=status.HTTP_201_CREATED, response_model=DepartmentRead)
def create_department(body: DepartmentCreate, user: User = Depends(require_write),
                      db: Session = Depends(get_db)) -> DepartmentRead:
    """생성. tenant_id 는 before_flush 자동 stamp (ADR-0025, 수동 지정 금지)."""
    _assert_name_available(db, body.name)
    obj = Department(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _to_department_read(obj, _user_names(db, {obj.manager_id} if obj.manager_id else set()))


@router.get("/departments/{dept_id}", response_model=DepartmentRead)
def get_department(dept_id: UUID, user: CurrentUser = None,
                   db: Session = Depends(get_db)) -> DepartmentRead:
    obj = _get_department_or_404(db, dept_id)
    return _to_department_read(obj, _user_names(db, {obj.manager_id} if obj.manager_id else set()))


@router.patch("/departments/{dept_id}", response_model=DepartmentRead)
def update_department(dept_id: UUID, body: DepartmentUpdate, user: User = Depends(require_write),
                      db: Session = Depends(get_db)) -> DepartmentRead:
    """수정. `exclude_unset` — None 도 유효한 값이라 미전송 여부로만 판별한다."""
    obj = _get_department_or_404(db, dept_id)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] != obj.name:
        _assert_name_available(db, changes["name"], exclude_id=dept_id)
    if changes.get("parent_id") == dept_id:
        raise HTTPException(status_code=409, detail="부서를 자기 자신의 상위로 지정할 수 없습니다")
    for f, v in changes.items():
        setattr(obj, f, v)
    db.commit()
    db.refresh(obj)
    return _to_department_read(obj, _user_names(db, {obj.manager_id} if obj.manager_id else set()))


@router.delete("/departments/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(dept_id: UUID, user: User = Depends(require_write),
                      db: Session = Depends(get_db)) -> None:
    """삭제(soft). 소속이 남아 있으면 거부한다 — 소속만 남으면 어느 부서인지 알 수 없다."""
    obj = _get_department_or_404(db, dept_id)
    linked = db.query(UserDepartment).filter(
        UserDepartment.department_id == dept_id,
        UserDepartment.is_deleted == False,  # noqa: E712
    ).count()
    if linked:
        raise HTTPException(
            status_code=409,
            detail=f"소속 인원 {linked}명이 남아 있어 삭제할 수 없습니다. 소속을 먼저 정리하세요",
        )
    obj.is_deleted = True
    db.commit()


# ── 소속 ──────────────────────────────────────────────────

def _to_membership_read(obj: UserDepartment, user_names: dict[UUID, str],
                        dept_names: dict[UUID, str]) -> UserDepartmentRead:
    row = UserDepartmentRead.model_validate(obj)
    row.user_name = user_names.get(obj.user_id)
    row.department_name = dept_names.get(obj.department_id)
    return row


def _clear_other_primaries(db: Session, user_id: UUID, keep_id: UUID | None) -> None:
    """주 소속을 하나로 유지한다. DB 부분 유니크가 최종 방어선이고 여기는 사용성 —
    "이미 주 소속이 있습니다" 로 거부하는 대신 옮겨준다(부서 이동이 정상 업무다)."""
    q = db.query(UserDepartment).filter(
        UserDepartment.user_id == user_id,
        UserDepartment.is_primary == True,  # noqa: E712
        UserDepartment.is_deleted == False,  # noqa: E712
    )
    if keep_id is not None:
        q = q.filter(UserDepartment.id != keep_id)
    for other in q.all():
        other.is_primary = False
    db.flush()


@router.get("/memberships")
def list_memberships(user_id: UUID | None = None, department_id: UUID | None = None,
                     skip: int = 0, limit: int = 100, user: CurrentUser = None,
                     db: Session = Depends(get_db)) -> dict:
    q = db.query(UserDepartment).filter(UserDepartment.is_deleted == False)  # noqa: E712
    if user_id:
        q = q.filter(UserDepartment.user_id == user_id)
    if department_id:
        q = q.filter(UserDepartment.department_id == department_id)
    total = q.count()
    items = q.order_by(UserDepartment.created_at).offset(skip).limit(limit).all()
    user_names = _user_names(db, {m.user_id for m in items})
    dept_names = {
        d.id: d.name for d in db.query(Department).filter(
            Department.id.in_({m.department_id for m in items} or {None})
        ).all()
    }
    return {
        "items": [_to_membership_read(m, user_names, dept_names) for m in items],
        "total": total, "skip": skip, "limit": limit,
    }


@router.post("/memberships", status_code=status.HTTP_201_CREATED, response_model=UserDepartmentRead)
def create_membership(body: UserDepartmentCreate, user: User = Depends(require_write),
                      db: Session = Depends(get_db)) -> UserDepartmentRead:
    """소속 추가. **한 사람이 여러 부서에 소속될 수 있다**(ADR-0031 §2.2 근거와 같은 실무).

    주 소속으로 지정하면 기존 주 소속은 해제된다 — 부서 이동이 정상 업무이므로
    "이미 있습니다" 로 막지 않는다. 사용자당 1건은 DB 부분 유니크가 최종 보장한다.
    """
    _get_department_or_404(db, body.department_id)
    if db.query(User).filter(User.id == body.user_id, User.is_deleted == False).first() is None:  # noqa: E712
        raise HTTPException(status_code=404, detail="User not found")

    dup = db.query(UserDepartment).filter(
        UserDepartment.user_id == body.user_id,
        UserDepartment.department_id == body.department_id,
        UserDepartment.is_deleted == False,  # noqa: E712
    ).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="이미 해당 부서에 소속되어 있습니다")

    if body.is_primary:
        _clear_other_primaries(db, body.user_id, keep_id=None)
    obj = UserDepartment(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    dept = db.query(Department).filter(Department.id == obj.department_id).first()
    return _to_membership_read(obj, _user_names(db, {obj.user_id}),
                               {dept.id: dept.name} if dept else {})


@router.patch("/memberships/{membership_id}", response_model=UserDepartmentRead)
def update_membership(membership_id: UUID, body: UserDepartmentUpdate,
                      user: User = Depends(require_write),
                      db: Session = Depends(get_db)) -> UserDepartmentRead:
    obj = db.query(UserDepartment).filter(
        UserDepartment.id == membership_id,
        UserDepartment.is_deleted == False,  # noqa: E712
    ).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("is_primary") is True:
        _clear_other_primaries(db, obj.user_id, keep_id=obj.id)
    for f, v in changes.items():
        setattr(obj, f, v)
    db.commit()
    db.refresh(obj)
    dept = db.query(Department).filter(Department.id == obj.department_id).first()
    return _to_membership_read(obj, _user_names(db, {obj.user_id}),
                               {dept.id: dept.name} if dept else {})


@router.delete("/memberships/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_membership(membership_id: UUID, user: User = Depends(require_write),
                      db: Session = Depends(get_db)) -> None:
    obj = db.query(UserDepartment).filter(
        UserDepartment.id == membership_id,
        UserDepartment.is_deleted == False,  # noqa: E712
    ).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    obj.is_deleted = True
    db.commit()
