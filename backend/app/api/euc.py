"""EUC (End User Computing) API — ADR-0033(정정), 5-1.

**EUC 화면은 파일 중심이다.** 파일 목록에 산출값(파일 중요성·위험 등급·통제 식별)과
참조 통제를 함께 낸다. 산출값은 저장하지 않고 조회마다 계산한다(`services/euc_risk.py`).

**권한은 명시적으로 정했다**(5-1 §2.5, `services/euc_iuc.py`) — `require_write` 로 기본 처리하면
external_auditor 만 막히고 누구나 쓰게 된다(13.9-35·13.9-41).
- 파일 생성: `icfr_manager` 만 (아직 참조하는 통제가 없으므로)
- 파일 수정·삭제: `icfr_manager` + 이 파일을 참조하는 통제 중 하나의 `control_owner`
- 조회: 전원
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import require_icfr_manager, tenant_roles
from app.models.euc import (
    CHANGE_FREQUENCY_LABELS,
    COMPLEXITY_LABELS,
    RISK_GRADES,
    RISK_LABELS,
    EucFile,
)
from app.models.iuc import (
    IMPORTANCE_LABELS,
    IMPORTANCE_VALUES,
    INFO_TYPE_LABELS,
    INFO_TYPES,
    InformationItem,
)
from app.models.role_assignment import ROLE_ICFR_MANAGER
from app.models.user import User
from app.schemas.euc import (
    CountBucket,
    EucControlRef,
    EucFileCreate,
    EucFileList,
    EucFileRead,
    EucFileUpdate,
    EucIucSummary,
    EucMeta,
    Option,
)
from app.services.euc_iuc import (
    FileView,
    alive_controls,
    can_edit_file,
    file_views,
    live_items,
)
from app.services.euc_risk import identification_threshold

router = APIRouter(prefix="/api/euc", tags=["euc"])

# 대시보드 드릴스루와 같은 센티널 — 미평가 칸. 빈 문자열이면 "필터 없음"과 구분되지 않는다
UNSET = "__none__"


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    return {
        "module": "euc",
        "name_kr": "EUC",
        "phase_1_status": "인벤토리(5-1) — 파일 목록·위험 산출",
        "next": ["EUC 통제 4종·평가 회차(5-2)"],
        "available_in_phase_1": True,
    }


def _options(labels: dict[str, str]) -> list[Option]:
    return [Option(value=k, label=v) for k, v in labels.items()]


@router.get("/meta", response_model=EucMeta)
def get_meta(user: CurrentUser = None, db: Session = Depends(get_db)) -> EucMeta:
    """화면 선택지. **서버가 준다** — 화면이 목록을 따로 들면 상수와 어긋난다(13.9-40)."""
    return EucMeta(
        complexity=_options(COMPLEXITY_LABELS),
        change_frequency=_options(CHANGE_FREQUENCY_LABELS),
        risk_grade=_options(RISK_LABELS),
        importance=_options(IMPORTANCE_LABELS),
        info_type=_options(INFO_TYPE_LABELS),
        identification_threshold=identification_threshold(db),
    )


def _to_read(db: Session, view: FileView, controls: dict, user_id: UUID) -> EucFileRead:
    row = EucFileRead.model_validate(view.file)
    row.importance = view.importance
    row.risk_grade = view.risk_grade
    row.identified = view.identified
    row.source_mismatch = view.source_mismatch
    row.controls = [
        EucControlRef(id=cid, code=controls[cid]["code"], name=controls[cid]["name"])
        for cid in view.control_ids if cid in controls
    ]
    row.can_edit = can_edit_file(db, user_id, view, controls)
    return row


def _view_or_404(db: Session, file_id: UUID, controls: dict) -> FileView:
    view = next((v for v in file_views(db, controls) if v.file.id == file_id), None)
    if view is None:
        raise HTTPException(status_code=404, detail="EUC 파일을 찾을 수 없습니다")
    return view


def _assert_name_free(db: Session, name: str, exclude_id: UUID | None = None) -> None:
    """살아 있는 이름 중복은 409 — DB 부분 유니크보다 먼저 봐서 읽을 수 있는 문구를 준다
    (DB 제약이 먼저 터지면 "데이터 무결성 제약 위반"이라 원인을 알 수 없다, 13.9-42)."""
    q = db.query(EucFile).filter(EucFile.name == name, EucFile.is_deleted == False)  # noqa: E712
    if exclude_id is not None:
        q = q.filter(EucFile.id != exclude_id)
    if q.first() is not None:
        raise HTTPException(status_code=409, detail=f"EUC 파일명 '{name}' 은 이미 사용 중입니다")


@router.get("/files", response_model=EucFileList)
def list_files(user: CurrentUser = None, db: Session = Depends(get_db)) -> EucFileList:
    controls = alive_controls(db)
    views = file_views(db, controls)
    items = [_to_read(db, v, controls, user.id) for v in views]
    return EucFileList(
        items=items, total=len(items),
        can_create=ROLE_ICFR_MANAGER in tenant_roles(db, user.id),
    )


@router.get("/files/{file_id}", response_model=EucFileRead)
def get_file(file_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> EucFileRead:
    controls = alive_controls(db)
    return _to_read(db, _view_or_404(db, file_id, controls), controls, user.id)


@router.post("/files", status_code=status.HTTP_201_CREATED, response_model=EucFileRead)
def create_file(body: EucFileCreate, user: User = Depends(require_icfr_manager),
                db: Session = Depends(get_db)) -> EucFileRead:
    """생성은 `icfr_manager` 만 — 새 파일은 아직 참조하는 통제가 없어 통제책임자가 정해지지 않는다."""
    _assert_name_free(db, body.name)
    obj = EucFile(**body.model_dump())
    db.add(obj)
    db.commit()
    controls = alive_controls(db)
    return _to_read(db, _view_or_404(db, obj.id, controls), controls, user.id)


@router.patch("/files/{file_id}", response_model=EucFileRead)
def update_file(file_id: UUID, body: EucFileUpdate, user: CurrentUser = None,
                db: Session = Depends(get_db)) -> EucFileRead:
    controls = alive_controls(db)
    view = _view_or_404(db, file_id, controls)
    if not can_edit_file(db, user.id, view, controls):
        raise HTTPException(
            status_code=403,
            detail="이 EUC 파일은 내부회계관리자 또는 참조 통제의 통제책임자만 수정할 수 있습니다",
        )
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise HTTPException(status_code=422, detail="파일명은 비울 수 없습니다")
    if changes.get("name"):
        _assert_name_free(db, changes["name"], exclude_id=file_id)
    for k, v in changes.items():
        setattr(view.file, k, v)
    db.commit()
    return _to_read(db, _view_or_404(db, file_id, controls), controls, user.id)


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    """삭제(soft). **정보 항목이 가리키고 있으면 거부한다.**

    제외된 통제의 항목도 센다 — 그 통제를 복원하면 항목이 지워진 파일을 가리키게 된다.
    """
    controls = alive_controls(db)
    view = _view_or_404(db, file_id, controls)
    if not can_edit_file(db, user.id, view, controls):
        raise HTTPException(
            status_code=403,
            detail="이 EUC 파일은 내부회계관리자 또는 참조 통제의 통제책임자만 삭제할 수 있습니다",
        )
    linked = db.query(InformationItem).filter(
        InformationItem.euc_file_id == file_id,
        InformationItem.is_deleted == False,  # noqa: E712
    ).count()
    if linked:
        raise HTTPException(
            status_code=409,
            detail=f"정보 항목 {linked}건이 이 파일을 참조하고 있어 삭제할 수 없습니다. 연결을 먼저 해제하세요",
        )
    view.file.is_deleted = True
    db.commit()


# ── 대시보드 ───────────────────────────────────────────────

@router.get("/summary", response_model=EucIucSummary)
def get_summary(user: CurrentUser = None, db: Session = Depends(get_db)) -> EucIucSummary:
    """EUC·IUC 집계. **0 건도 0 으로, 미평가는 따로** 센다.

    원천 8건이 전부 Low 로 적혀 있어도 우리 모델은 복잡도 없이 등급을 내지 않는다 —
    "식별 0건"만 보이면 평가해서 Low 인 것처럼 읽힌다. 그래서 미평가 칸을 따로 둔다.
    """
    controls = alive_controls(db)
    views = file_views(db, controls)
    items = live_items(db, controls)

    grade_counts = {g: 0 for g in RISK_GRADES}
    unevaluated = 0
    for v in views:
        if v.risk_grade is None:
            unevaluated += 1
        else:
            grade_counts[v.risk_grade] += 1
    risk_buckets = [CountBucket(value=g, label=RISK_LABELS[g], count=grade_counts[g]) for g in RISK_GRADES]
    risk_buckets.append(CountBucket(value=UNSET, label="미평가", count=unevaluated))

    imp_counts = {v: 0 for v in IMPORTANCE_VALUES}
    imp_unset = 0
    type_counts = {t: 0 for t in INFO_TYPES}
    for it in items:
        if it.importance in imp_counts:
            imp_counts[it.importance] += 1
        else:
            imp_unset += 1
        type_counts[it.info_type] = type_counts.get(it.info_type, 0) + 1
    imp_buckets = [CountBucket(value=v, label=IMPORTANCE_LABELS[v], count=imp_counts[v])
                   for v in IMPORTANCE_VALUES]
    imp_buckets.append(CountBucket(value=UNSET, label="미평가", count=imp_unset))

    return EucIucSummary(
        file_total=len(views),
        item_total=len(items),
        identified=sum(1 for v in views if v.identified),
        unevaluated=unevaluated,
        unreferenced_files=sum(1 for v in views if not v.control_ids),
        source_mismatch=sum(1 for v in views if v.source_mismatch),
        identification_threshold=identification_threshold(db),
        risk_grade=risk_buckets,
        importance=imp_buckets,
        info_type=[CountBucket(value=t, label=INFO_TYPE_LABELS.get(t, t), count=n)
                   for t, n in type_counts.items()],
    )
