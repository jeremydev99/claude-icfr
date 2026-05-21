from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_db
from app.models.user import User
from app.models.user_mgmt import UserRole
from app.schemas.user_mgmt import UserRead, UserRoleCreate, UserRoleUpdate, UserRoleRead

router = APIRouter(prefix="/api/users", tags=["user_mgmt"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    return {
        "module": "user_mgmt",
        "name_kr": "사용자/권한",
        "phase_0_status": "최소 CRUD 완료",
        "phase_1_features": ["사용자 CRUD", "단순 역할 (admin/user)", "비밀번호 변경"],
        "phase_1_excluded": ["SoD (직무 분리)", "위임", "HR 연동"],
        "available_in_phase_1": True,
    }


# ── Users (READ-only) ──────────────────────────────────────

@router.get("/")
def list_users(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(User).filter(User.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [UserRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> User:
    obj = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="User not found")
    return obj


# ── User Roles (CRUD) ──────────────────────────────────────

@router.get("/roles/list")
def list_roles(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(UserRole).filter(UserRole.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [UserRoleRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/roles", status_code=status.HTTP_201_CREATED, response_model=UserRoleRead)
def create_role(body: UserRoleCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> UserRole:
    obj = UserRole(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/roles/{role_id}", response_model=UserRoleRead)
def get_role(role_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> UserRole:
    obj = db.query(UserRole).filter(UserRole.id == role_id, UserRole.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="UserRole not found")
    return obj


@router.patch("/roles/{role_id}", response_model=UserRoleRead)
def update_role(role_id: UUID, body: UserRoleUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> UserRole:
    obj = db.query(UserRole).filter(UserRole.id == role_id, UserRole.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="UserRole not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, field, val)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(UserRole).filter(UserRole.id == role_id, UserRole.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="UserRole not found")
    obj.is_deleted = True
    db.commit()
