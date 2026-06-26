from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_db, require_admin
from app.core.security import hash_password
from app.models.user import User
from app.models.user_mgmt import UserRole
from app.schemas.user import UserCreate, UserUpdate, PasswordResetRequest
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


# ── Users (CRUD, 관리자 전용) ──────────────────────────────
# 감사 대상 시스템이므로 사용자 생성/수정/삭제·비번 리셋은 관리자만 가능.

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=UserRead)
def create_user(body: UserCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> User:
    existing = db.query(User).filter(User.email == body.email, User.is_deleted == False).first()  # noqa: E712
    if existing:
        raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다")
    obj = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name,  # 실명
        role=body.role,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: UUID, body: UserUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> User:
    obj = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="User not found")
    # password·email은 이 엔드포인트에서 변경하지 않음 (비번은 reset-password, email은 식별자)
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, field, val)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> None:
    obj = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="User not found")
    if obj.id == admin.id:
        raise HTTPException(status_code=409, detail="본인 계정은 삭제할 수 없습니다")
    if obj.role == "admin":
        admin_count = db.query(User).filter(
            User.role == "admin", User.is_deleted == False  # noqa: E712
        ).count()
        if admin_count <= 1:
            raise HTTPException(status_code=409, detail="마지막 관리자 계정은 삭제할 수 없습니다")
    obj.is_deleted = True
    db.commit()


@router.post("/{user_id}/reset-password", status_code=status.HTTP_200_OK)
def reset_password(user_id: UUID, body: PasswordResetRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    """관리자 비밀번호 리셋 — old 검증 없이 재설정 (관리자 전용)."""
    obj = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="User not found")
    obj.hashed_password = hash_password(body.new_password)
    db.commit()
    return {"detail": "비밀번호가 재설정되었습니다"}


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
