from dataclasses import dataclass, field as dc_field
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from openpyxl import load_workbook
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.rcm import (
    Control, ControlAssertion, Process, Risk, RiskCategory, SubProcess,
)
from app.schemas.rcm import (
    BulkDeleteRequest, BulkUpdateRequest, ClearAllRequest,
    ControlAssertionCreate, ControlAssertionRead,
    ControlCreate, ControlRead, ControlUpdate,
    ProcessCreate, ProcessRead, ProcessUpdate,
    RiskCategoryCreate, RiskCategoryRead, RiskCategoryUpdate,
    RiskCreate, RiskRead, RiskUpdate,
    SubProcessCreate, SubProcessRead, SubProcessUpdate,
)

router = APIRouter(prefix="/api/rcm", tags=["rcm"])


# ── 모듈 정보 ─────────────────────────────────────────────

@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    return {
        "module": "rcm",
        "name_kr": "RCM 관리",
        "phase_0_status": "Phase 1 풀 확장 완료",
        "phase_1_features": [
            "SubProcess·Risk·Control CRUD",
            "Excel 업로드 (사이냅소프트 양식)",
            "풀 검색·필터",
            "위험 매트릭스",
            "벌크 삭제·수정",
        ],
        "phase_1_excluded": ["버전 관리 스냅샷·Diff", "변경 승인 워크플로"],
        "available_in_phase_1": True,
    }


# ── Processes ─────────────────────────────────────────────

@router.get("/processes")
def list_processes(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(Process).filter(Process.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [ProcessRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/processes", status_code=status.HTTP_201_CREATED, response_model=ProcessRead)
def create_process(body: ProcessCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> Process:
    obj = Process(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/processes/{process_id}", response_model=ProcessRead)
def get_process(process_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> Process:
    obj = db.query(Process).filter(Process.id == process_id, Process.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Process not found")
    return obj


@router.patch("/processes/{process_id}", response_model=ProcessRead)
def update_process(process_id: UUID, body: ProcessUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> Process:
    obj = db.query(Process).filter(Process.id == process_id, Process.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Process not found")
    for f, v in body.model_dump(exclude_none=True).items():
        setattr(obj, f, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/processes/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_process(process_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(Process).filter(Process.id == process_id, Process.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Process not found")
    obj.is_deleted = True
    db.commit()


# ── SubProcesses ──────────────────────────────────────────

@router.get("/sub-processes")
def list_sub_processes(process_id: UUID | None = None, skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(SubProcess).filter(SubProcess.is_deleted == False)  # noqa: E712
    if process_id:
        q = q.filter(SubProcess.process_id == process_id)
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [SubProcessRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/sub-processes", status_code=status.HTTP_201_CREATED, response_model=SubProcessRead)
def create_sub_process(body: SubProcessCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> SubProcess:
    obj = SubProcess(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/sub-processes/{sp_id}", response_model=SubProcessRead)
def get_sub_process(sp_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> SubProcess:
    obj = db.query(SubProcess).filter(SubProcess.id == sp_id, SubProcess.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="SubProcess not found")
    return obj


@router.patch("/sub-processes/{sp_id}", response_model=SubProcessRead)
def update_sub_process(sp_id: UUID, body: SubProcessUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> SubProcess:
    obj = db.query(SubProcess).filter(SubProcess.id == sp_id, SubProcess.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="SubProcess not found")
    for f, v in body.model_dump(exclude_none=True).items():
        setattr(obj, f, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/sub-processes/{sp_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sub_process(sp_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(SubProcess).filter(SubProcess.id == sp_id, SubProcess.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="SubProcess not found")
    obj.is_deleted = True
    db.commit()


# ── Risks ─────────────────────────────────────────────────

@router.get("/risks")
def list_risks(sub_process_id: UUID | None = None, skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(Risk).filter(Risk.is_deleted == False)  # noqa: E712
    if sub_process_id:
        q = q.filter(Risk.sub_process_id == sub_process_id)
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [RiskRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/risks", status_code=status.HTTP_201_CREATED, response_model=RiskRead)
def create_risk(body: RiskCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> Risk:
    obj = Risk(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/risks/{risk_id}", response_model=RiskRead)
def get_risk(risk_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> Risk:
    obj = db.query(Risk).filter(Risk.id == risk_id, Risk.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Risk not found")
    return obj


@router.patch("/risks/{risk_id}", response_model=RiskRead)
def update_risk(risk_id: UUID, body: RiskUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> Risk:
    obj = db.query(Risk).filter(Risk.id == risk_id, Risk.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Risk not found")
    for f, v in body.model_dump(exclude_none=True).items():
        setattr(obj, f, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/risks/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_risk(risk_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(Risk).filter(Risk.id == risk_id, Risk.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Risk not found")
    obj.is_deleted = True
    db.commit()


# ── Risk Categories ───────────────────────────────────────

@router.get("/risk-categories")
def list_risk_categories(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(RiskCategory).filter(RiskCategory.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [RiskCategoryRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/risk-categories", status_code=status.HTTP_201_CREATED, response_model=RiskCategoryRead)
def create_risk_category(body: RiskCategoryCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> RiskCategory:
    obj = RiskCategory(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/risk-categories/{rc_id}", response_model=RiskCategoryRead)
def get_risk_category(rc_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> RiskCategory:
    obj = db.query(RiskCategory).filter(RiskCategory.id == rc_id, RiskCategory.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="RiskCategory not found")
    return obj


@router.patch("/risk-categories/{rc_id}", response_model=RiskCategoryRead)
def update_risk_category(rc_id: UUID, body: RiskCategoryUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> RiskCategory:
    obj = db.query(RiskCategory).filter(RiskCategory.id == rc_id, RiskCategory.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="RiskCategory not found")
    for f, v in body.model_dump(exclude_none=True).items():
        setattr(obj, f, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/risk-categories/{rc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_risk_category(rc_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(RiskCategory).filter(RiskCategory.id == rc_id, RiskCategory.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="RiskCategory not found")
    obj.is_deleted = True
    db.commit()


# ── Controls — 정적 경로 먼저 (파라미터 경로보다 앞에 위치해야 함) ──

@router.get("/controls/search")
def search_controls(
    q: str | None = None,
    process_code: str | None = None,
    sub_process_code: str | None = None,
    risk_level: str | None = None,
    frequency: str | None = None,
    is_key_control: bool | None = None,
    auto_manual: str | None = None,
    preventive_detective: str | None = None,
    assertion: str | None = None,
    owner: str | None = None,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "code",
    sort_order: str = "asc",
    user: CurrentUser = None,
    db: Session = Depends(get_db),
) -> dict:
    """풀 검색·필터 — 단일 함수, 추상화 없음 (ADR-0020 원칙)."""
    query = db.query(Control).filter(Control.is_deleted == False)  # noqa: E712

    if q:
        query = query.filter(
            or_(
                Control.code.ilike(f"%{q}%"),
                Control.name.ilike(f"%{q}%"),
                Control.description.ilike(f"%{q}%"),
            )
        )
    if owner:
        query = query.filter(Control.owner_name.ilike(f"%{owner}%"))
    if frequency:
        query = query.filter(Control.frequency == frequency)
    if is_key_control is not None:
        query = query.filter(Control.is_key_control == is_key_control)
    if auto_manual:
        query = query.filter(Control.auto_manual == auto_manual)
    if preventive_detective:
        query = query.filter(Control.preventive_detective == preventive_detective)

    if risk_level or sub_process_code or process_code:
        query = query.join(Risk, Control.risk_id == Risk.id).filter(Risk.is_deleted == False)  # noqa: E712
        if risk_level:
            query = query.filter(Risk.assessment_level == risk_level)
        if sub_process_code or process_code:
            query = query.join(SubProcess, Risk.sub_process_id == SubProcess.id).filter(SubProcess.is_deleted == False)  # noqa: E712
            if sub_process_code:
                query = query.filter(SubProcess.code == sub_process_code)
            if process_code:
                query = query.join(Process, SubProcess.process_id == Process.id).filter(
                    Process.is_deleted == False, Process.code == process_code  # noqa: E712
                )

    if assertion:
        rc = db.query(RiskCategory).filter(RiskCategory.code == assertion, RiskCategory.is_deleted == False).first()  # noqa: E712
        if rc:
            assertion_ids = db.query(ControlAssertion.control_id).filter(
                ControlAssertion.risk_category_id == rc.id,
                ControlAssertion.is_deleted == False,  # noqa: E712
            )
            query = query.filter(Control.id.in_(assertion_ids))

    valid_sort = {"code", "name", "frequency", "created_at"}
    sort_col = getattr(Control, sort_by if sort_by in valid_sort else "code")
    query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())

    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return {
        "items": [ControlRead.model_validate(i) for i in items],
        "total": total,
        "skip": skip,
        "limit": limit,
        "sort": f"{sort_by}:{sort_order}",
    }


@router.post("/controls/bulk-delete")
def bulk_delete_controls(body: BulkDeleteRequest, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    count = 0
    for cid in body.control_ids:
        obj = db.query(Control).filter(Control.id == cid, Control.is_deleted == False).first()  # noqa: E712
        if obj:
            obj.is_deleted = True
            count += 1
    db.commit()
    return {"deleted_count": count}


@router.post("/controls/bulk-update")
def bulk_update_controls(body: BulkUpdateRequest, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    updates = body.updates.model_dump(exclude_none=True)
    count = 0
    for cid in body.control_ids:
        obj = db.query(Control).filter(Control.id == cid, Control.is_deleted == False).first()  # noqa: E712
        if obj:
            for f, v in updates.items():
                setattr(obj, f, v)
            count += 1
    db.commit()
    return {"updated_count": count}


@router.post("/controls/clear-all")
def clear_all_rcm(body: ClearAllRequest, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    """전체 RCM 데이터 하드 삭제 — Excel 재업로드용. Phase 0 한정 허용."""
    if body.confirm != "DELETE_ALL_RCM_DATA":
        raise HTTPException(status_code=400, detail="confirm 값이 올바르지 않습니다")
    ca_count = db.query(ControlAssertion).delete(synchronize_session=False)
    c_count = db.query(Control).delete(synchronize_session=False)
    r_count = db.query(Risk).delete(synchronize_session=False)
    sp_count = db.query(SubProcess).delete(synchronize_session=False)
    p_count = db.query(Process).delete(synchronize_session=False)
    db.commit()
    return {
        "deleted": {
            "assertions": ca_count,
            "controls": c_count,
            "risks": r_count,
            "sub_processes": sp_count,
            "processes": p_count,
        }
    }


@router.get("/controls")
def list_controls(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(Control).filter(Control.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [ControlRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/controls", status_code=status.HTTP_201_CREATED, response_model=ControlRead)
def create_control(body: ControlCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> Control:
    obj = Control(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/controls/{control_id}", response_model=ControlRead)
def get_control(control_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> Control:
    obj = db.query(Control).filter(Control.id == control_id, Control.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Control not found")
    return obj


@router.patch("/controls/{control_id}", response_model=ControlRead)
def update_control(control_id: UUID, body: ControlUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> Control:
    obj = db.query(Control).filter(Control.id == control_id, Control.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Control not found")
    for f, v in body.model_dump(exclude_none=True).items():
        setattr(obj, f, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/controls/{control_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_control(control_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(Control).filter(Control.id == control_id, Control.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Control not found")
    obj.is_deleted = True
    db.commit()


# ── Control Assertions ────────────────────────────────────

@router.get("/control-assertions")
def list_control_assertions(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(ControlAssertion).filter(ControlAssertion.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [ControlAssertionRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/control-assertions", status_code=status.HTTP_201_CREATED, response_model=ControlAssertionRead)
def create_control_assertion(body: ControlAssertionCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> ControlAssertion:
    obj = ControlAssertion(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/control-assertions/{ca_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_control_assertion(ca_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(ControlAssertion).filter(ControlAssertion.id == ca_id, ControlAssertion.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="ControlAssertion not found")
    obj.is_deleted = True
    db.commit()


# ── Excel 업로드 ──────────────────────────────────────────

@dataclass
class _ParsedRCM:
    processes: dict
    sub_processes: dict
    risks: dict
    controls: list
    errors: list
    warnings: list = dc_field(default_factory=list)


def _parse_rcm_excel(file_bytes: bytes) -> _ParsedRCM:
    """사이냅소프트 RCM 양식 파싱. 헤더 7행, 데이터 8행~."""
    VALID_LEVELS = {"LR", "MR", "HR", "SR"}
    VALID_FREQ = {"O", "D", "W", "M", "Q", "A"}
    VALID_PD = {"P", "D"}
    VALID_AM = {"A", "M", "IT"}
    VALID_IPE = {"Y", "N", "N/A"}

    wb = load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
    if "RCM" not in wb.sheetnames:
        raise ValueError("'RCM' 시트가 없습니다")
    ws = wb["RCM"]

    processes: dict = {}
    sub_processes: dict = {}
    risks: dict = {}
    controls: list = []
    errors: list = []
    warnings: list = []

    for row_idx, row in enumerate(ws.iter_rows(min_row=8, values_only=True), start=8):
        if not row or row[1] is None:
            break
        try:
            p_code = str(row[1]).strip()
            p_name = str(row[2] or "").strip()
            sp_code = str(row[3] or "").strip()
            sp_name = str(row[4] or "").strip()
            r_code = str(row[5] or "").strip()
            c_code = str(row[6] or "").strip()

            if not c_code:
                errors.append(f"Row {row_idx}: 통제활동번호(G) 누락")
                continue
            if not r_code:
                errors.append(f"Row {row_idx}: 위험번호(F) 누락")
                continue

            processes[p_code] = p_name
            sub_processes[sp_code] = {"name": sp_name, "process_code": p_code}

            level = str(row[14] or "LR").strip().upper()
            if level not in VALID_LEVELS:
                warnings.append(f"Row {row_idx}: 위험평가 '{level}' 무효 → LR 사용")
                level = "LR"
            risks[r_code] = {
                "description": str(row[8] or r_code).strip(),
                "assessment_level": level,
                "sub_process_code": sp_code,
            }

            c_name = str(row[16] or "").strip()
            if not c_name:
                errors.append(f"Row {row_idx}: 통제활동이름(Q) 누락")
                continue

            pd_val = str(row[25] or "P").strip().upper()
            if pd_val not in VALID_PD:
                warnings.append(f"Row {row_idx}: P/D 값 '{pd_val}' 무효 → P 사용")
                pd_val = "P"

            am_val = str(row[26] or "M").strip().upper()
            if am_val not in VALID_AM:
                warnings.append(f"Row {row_idx}: Auto/Manual '{am_val}' 무효 → M 사용")
                am_val = "M"

            freq_val = str(row[35] or "A").strip().upper()
            if freq_val not in VALID_FREQ:
                warnings.append(f"Row {row_idx}: 통제주기 '{freq_val}' 무효 → A 사용")
                freq_val = "A"

            ipe_val = str(row[36] or "N/A").strip()
            if ipe_val not in VALID_IPE:
                warnings.append(f"Row {row_idx}: IPE '{ipe_val}' 무효 → N/A 사용")
                ipe_val = "N/A"

            assertion_map = [
                ("E", 27), ("C", 28), ("R", 29), ("V", 30),
                ("P", 31), ("O", 32), ("M", 33),
            ]
            assertions = [
                code for code, idx in assertion_map
                if len(row) > idx and row[idx] == "O"
            ]

            controls.append({
                "code": c_code,
                "name": c_name,
                "description": str(row[17] or "").strip() or None,
                "objective": str(row[15] or "").strip() or None,
                "owner_name": str(row[7] or "").strip() or None,
                "risk_code": r_code,
                "is_key_control": (row[18] == "Yes") if len(row) > 18 else True,
                "preventive_detective": pd_val,
                "auto_manual": am_val,
                "activity_approval": len(row) > 19 and row[19] == "O",
                "activity_verification": len(row) > 20 and row[20] == "O",
                "activity_physical": len(row) > 21 and row[21] == "O",
                "activity_master_data": len(row) > 22 and row[22] == "O",
                "activity_reconciliation": len(row) > 23 and row[23] == "O",
                "activity_supervision": len(row) > 24 and row[24] == "O",
                "assertions": assertions,
                "related_accounts": str(row[34] or "").strip() or None,
                "frequency": freq_val,
                "ipe_relevant": ipe_val,
                "related_systems": str(row[37] or "").strip() or None,
                "euc_description": str(row[38] or "").strip() or None,
            })
        except Exception as e:
            errors.append(f"Row {row_idx}: {e}")

    wb.close()
    return _ParsedRCM(
        processes=processes,
        sub_processes=sub_processes,
        risks=risks,
        controls=controls,
        errors=errors,
        warnings=warnings,
    )


@router.post("/upload-excel")
async def upload_excel(
    file: UploadFile = File(...),
    mode: str = Form(default="preview"),
    user: CurrentUser = None,
    db: Session = Depends(get_db),
) -> dict:
    """사이냅소프트 RCM Excel 업로드. mode=preview: 파싱 결과 반환. mode=commit: DB 저장."""
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail=".xlsx 파일만 허용됩니다")
    if mode not in ("preview", "commit"):
        raise HTTPException(status_code=400, detail="mode는 'preview' 또는 'commit'이어야 합니다")

    contents = await file.read()
    try:
        parsed = _parse_rcm_excel(contents)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel 파싱 오류: {e}")

    summary = {
        "total_rows": len(parsed.controls) + len(parsed.errors),
        "valid_rows": len(parsed.controls),
        "errors": parsed.errors,
        "warnings": parsed.warnings,
    }

    if mode == "preview":
        return {
            "summary": summary,
            "preview": parsed.controls[:20],
        }

    # mode == "commit"
    process_id_map: dict = {}
    sp_id_map: dict = {}
    risk_id_map: dict = {}

    for p_code, p_name in parsed.processes.items():
        existing = db.query(Process).filter(Process.code == p_code).first()
        if existing:
            process_id_map[p_code] = existing.id
        else:
            obj = Process(code=p_code, name=p_name or p_code)
            db.add(obj)
            db.flush()
            process_id_map[p_code] = obj.id

    for sp_code, sp_info in parsed.sub_processes.items():
        p_id = process_id_map.get(sp_info["process_code"])
        if not p_id:
            continue
        existing = db.query(SubProcess).filter(SubProcess.code == sp_code).first()
        if existing:
            sp_id_map[sp_code] = existing.id
        else:
            obj = SubProcess(code=sp_code, name=sp_info["name"] or sp_code, process_id=p_id)
            db.add(obj)
            db.flush()
            sp_id_map[sp_code] = obj.id

    for r_code, r_info in parsed.risks.items():
        sp_id = sp_id_map.get(r_info["sub_process_code"])
        if not sp_id:
            continue
        existing = db.query(Risk).filter(Risk.code == r_code).first()
        if existing:
            risk_id_map[r_code] = existing.id
        else:
            obj = Risk(
                code=r_code,
                description=r_info["description"],
                assessment_level=r_info["assessment_level"],
                sub_process_id=sp_id,
            )
            db.add(obj)
            db.flush()
            risk_id_map[r_code] = obj.id

    # 7가지 assertion 코드 캐시
    rc_cache: dict = {}
    for code, name in [("E", "Existence"), ("C", "Completeness"), ("R", "Rights & Obligations"),
                        ("V", "Valuation"), ("P", "Presentation"), ("O", "Occurrence"), ("M", "Measurement")]:
        rc = db.query(RiskCategory).filter(RiskCategory.code == code).first()
        if not rc:
            rc = RiskCategory(code=code, name=name)
            db.add(rc)
            db.flush()
        rc_cache[code] = rc.id

    created = {"processes": 0, "sub_processes": 0, "risks": 0, "controls": 0, "assertions": 0}
    created["processes"] = len([v for v in process_id_map.values()])
    created["sub_processes"] = len([v for v in sp_id_map.values()])
    created["risks"] = len([v for v in risk_id_map.values()])

    for c_data in parsed.controls:
        r_id = risk_id_map.get(c_data["risk_code"])
        if not r_id:
            continue
        existing = db.query(Control).filter(Control.code == c_data["code"]).first()
        if existing:
            continue
        ctrl = Control(
            code=c_data["code"],
            name=c_data["name"],
            description=c_data.get("description"),
            objective=c_data.get("objective"),
            owner_name=c_data.get("owner_name"),
            risk_id=r_id,
            is_key_control=c_data.get("is_key_control", True),
            preventive_detective=c_data.get("preventive_detective", "P"),
            auto_manual=c_data.get("auto_manual", "M"),
            activity_approval=c_data.get("activity_approval", False),
            activity_verification=c_data.get("activity_verification", False),
            activity_physical=c_data.get("activity_physical", False),
            activity_master_data=c_data.get("activity_master_data", False),
            activity_reconciliation=c_data.get("activity_reconciliation", False),
            activity_supervision=c_data.get("activity_supervision", False),
            related_accounts=c_data.get("related_accounts"),
            frequency=c_data.get("frequency", "A"),
            ipe_relevant=c_data.get("ipe_relevant", "N/A"),
            related_systems=c_data.get("related_systems"),
            euc_description=c_data.get("euc_description"),
        )
        db.add(ctrl)
        db.flush()
        created["controls"] += 1

        for a_code in c_data.get("assertions", []):
            rc_id = rc_cache.get(a_code)
            if rc_id:
                db.add(ControlAssertion(control_id=ctrl.id, risk_category_id=rc_id))
                created["assertions"] += 1

    db.commit()
    return {"summary": summary, "created": created}


# ── 위험 매트릭스 ──────────────────────────────────────────

@router.get("/matrix")
def get_matrix(process_code: str | None = None, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    """Process → SubProcess → Risk → Control 중첩 구조. 별도 서비스 클래스 없음 (ADR-0020)."""
    q = db.query(Process).filter(Process.is_deleted == False)  # noqa: E712
    if process_code:
        q = q.filter(Process.code == process_code)
    processes = q.order_by(Process.code).all()

    matrix = []
    total_sp = total_risk = total_ctrl = 0
    level_dist: dict = {"LR": 0, "MR": 0, "HR": 0, "SR": 0}
    freq_dist: dict = {"O": 0, "D": 0, "W": 0, "M": 0, "Q": 0, "A": 0}

    for p in processes:
        sps = db.query(SubProcess).filter(
            SubProcess.process_id == p.id, SubProcess.is_deleted == False  # noqa: E712
        ).order_by(SubProcess.code).all()
        total_sp += len(sps)

        sp_list = []
        for sp in sps:
            risks = db.query(Risk).filter(
                Risk.sub_process_id == sp.id, Risk.is_deleted == False  # noqa: E712
            ).order_by(Risk.code).all()
            total_risk += len(risks)

            risk_list = []
            for r in risks:
                level_dist[r.assessment_level] = level_dist.get(r.assessment_level, 0) + 1
                ctrls = db.query(Control).filter(
                    Control.risk_id == r.id, Control.is_deleted == False  # noqa: E712
                ).order_by(Control.code).all()
                total_ctrl += len(ctrls)

                ctrl_list = []
                for c in ctrls:
                    freq_dist[c.frequency] = freq_dist.get(c.frequency, 0) + 1
                    assertion_codes = [
                        ca.risk_category.code
                        for ca in db.query(ControlAssertion).filter(
                            ControlAssertion.control_id == c.id,
                            ControlAssertion.is_deleted == False,  # noqa: E712
                        ).all()
                        if ca.risk_category
                    ]
                    ctrl_list.append({
                        "code": c.code,
                        "name": c.name,
                        "frequency": c.frequency,
                        "is_key_control": c.is_key_control,
                        "assertions": assertion_codes,
                    })
                risk_list.append({
                    "code": r.code,
                    "description": r.description,
                    "level": r.assessment_level,
                    "controls": ctrl_list,
                })
            sp_list.append({"code": sp.code, "name": sp.name, "risks": risk_list})
        matrix.append({"process": {"code": p.code, "name": p.name}, "sub_processes": sp_list})

    return {
        "matrix": matrix,
        "summary": {
            "process_count": len(processes),
            "sub_process_count": total_sp,
            "risk_count": total_risk,
            "control_count": total_ctrl,
            "risk_level_distribution": level_dist,
            "frequency_distribution": freq_dist,
        },
    }
