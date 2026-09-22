"""IUC (Information Used in Controls) API — ADR-0033(정정), 5-1.

**IUC 화면은 정보 항목(통제) 중심이다.** 통제에 딸린 정보 항목을 다룬다.

**effective 제외** — 통제가 overlay 로 exclude 되면 그 통제의 항목은 목록에서 빠지고 404 가
된다. 물리적으로 건드리지 않으므로 통제를 복원하면 그대로 돌아온다(`services/euc_iuc.py`).

**권한은 통제 단위다**(5-1 §2.5): `icfr_manager` + 그 통제의 `control_owner`·`assessor`.
통제 A 의 책임자는 통제 B 의 정보 항목을 고칠 수 없다. `external_auditor` 는 조회 전용.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.euc import EucFile
from app.models.iuc import InformationItem
from app.schemas.euc import InfoItemCreate, InfoItemList, InfoItemRead, InfoItemUpdate
from app.services.euc_iuc import alive_controls, live_items, writable_control_ids

router = APIRouter(prefix="/api/iuc", tags=["iuc"])

_FORBIDDEN = "이 통제의 정보 항목은 내부회계관리자 또는 그 통제의 통제책임자·평가자만 수정할 수 있습니다"


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    return {
        "module": "iuc",
        "name_kr": "IUC",
        "phase_1_status": "인벤토리(5-1) — 통제별 정보 항목",
        "available_in_phase_1": True,
    }


def _file_names(db: Session) -> dict[UUID, str]:
    return {
        f.id: f.name
        for f in db.query(EucFile).filter(EucFile.is_deleted == False).all()  # noqa: E712
    }


def _to_read(item: InformationItem, controls: dict, file_names: dict[UUID, str],
             writable: set[UUID]) -> InfoItemRead:
    row = InfoItemRead.model_validate(item)
    c = controls.get(item.control_id)
    if c is not None:
        row.control_code = c["code"]
        row.control_name = c["name"]
        row.process_code = c["process_code"]
    row.euc_file_name = file_names.get(item.euc_file_id) if item.euc_file_id else None
    row.can_edit = item.control_id in writable
    return row


def _assert_file_exists(db: Session, file_id: UUID | None) -> None:
    """참조할 파일이 살아 있어야 한다. 복합 FK 는 테넌트 격리만 보장하고 소프트 삭제는 모른다."""
    if file_id is None:
        return
    if db.query(EucFile).filter(EucFile.id == file_id, EucFile.is_deleted == False).first() is None:  # noqa: E712
        raise HTTPException(status_code=404, detail="EUC 파일을 찾을 수 없습니다")


def _assert_name_free(db: Session, control_id: UUID, name: str, exclude_id: UUID | None = None) -> None:
    """같은 통제에 같은 이름의 정보가 살아 있으면 409 — DB 제약보다 먼저 읽을 수 있는 문구로."""
    q = db.query(InformationItem).filter(
        InformationItem.control_id == control_id,
        InformationItem.name == name,
        InformationItem.is_deleted == False,  # noqa: E712
    )
    if exclude_id is not None:
        q = q.filter(InformationItem.id != exclude_id)
    if q.first() is not None:
        raise HTTPException(status_code=409, detail=f"이 통제에 '{name}' 정보 항목이 이미 있습니다")


def _live_item_or_404(db: Session, item_id: UUID, controls: dict) -> InformationItem:
    item = db.query(InformationItem).filter(
        InformationItem.id == item_id, InformationItem.is_deleted == False,  # noqa: E712
    ).first()
    # 통제가 제외되면 항목도 보이지 않는다(effective 제외) — 404 로 같게 취급한다
    if item is None or item.control_id not in controls:
        raise HTTPException(status_code=404, detail="정보 항목을 찾을 수 없습니다")
    return item


@router.get("/items", response_model=InfoItemList)
def list_items(control_id: UUID | None = None, user: CurrentUser = None,
               db: Session = Depends(get_db)) -> InfoItemList:
    controls = alive_controls(db)
    writable = writable_control_ids(db, user.id, controls)
    names = _file_names(db)
    items = live_items(db, controls)
    if control_id is not None:
        items = [i for i in items if i.control_id == control_id]
    items.sort(key=lambda i: (controls[i.control_id]["code"] or "", i.name))
    return InfoItemList(
        items=[_to_read(i, controls, names, writable) for i in items],
        total=len(items),
        writable_control_ids=sorted(writable, key=lambda cid: controls[cid]["code"] or ""),
    )


@router.post("/items", status_code=status.HTTP_201_CREATED, response_model=InfoItemRead)
def create_item(body: InfoItemCreate, user: CurrentUser = None,
                db: Session = Depends(get_db)) -> InfoItemRead:
    controls = alive_controls(db)
    # 통제 존재 검증 — FK 가 없으므로 여기서 한다(models/iuc.py). 제외된 통제에도 붙이지 않는다
    if body.control_id not in controls:
        raise HTTPException(status_code=404, detail="통제를 찾을 수 없습니다")
    writable = writable_control_ids(db, user.id, controls)
    if body.control_id not in writable:
        raise HTTPException(status_code=403, detail=_FORBIDDEN)
    _assert_file_exists(db, body.euc_file_id)
    _assert_name_free(db, body.control_id, body.name)
    obj = InformationItem(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _to_read(obj, controls, _file_names(db), writable)


@router.patch("/items/{item_id}", response_model=InfoItemRead)
def update_item(item_id: UUID, body: InfoItemUpdate, user: CurrentUser = None,
                db: Session = Depends(get_db)) -> InfoItemRead:
    controls = alive_controls(db)
    item = _live_item_or_404(db, item_id, controls)
    writable = writable_control_ids(db, user.id, controls)
    if item.control_id not in writable:
        raise HTTPException(status_code=403, detail=_FORBIDDEN)
    changes = body.model_dump(exclude_unset=True)
    for key in ("name", "info_type"):
        if key in changes and changes[key] is None:
            raise HTTPException(status_code=422, detail=f"{key} 는 비울 수 없습니다")
    if "euc_file_id" in changes:
        _assert_file_exists(db, changes["euc_file_id"])
    if changes.get("name"):
        _assert_name_free(db, item.control_id, changes["name"], exclude_id=item.id)
    for k, v in changes.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return _to_read(item, controls, _file_names(db), writable)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    controls = alive_controls(db)
    item = _live_item_or_404(db, item_id, controls)
    if item.control_id not in writable_control_ids(db, user.id, controls):
        raise HTTPException(status_code=403, detail=_FORBIDDEN)
    item.is_deleted = True
    db.commit()
