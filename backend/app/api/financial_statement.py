"""재무제표·계정 트리 API — ADR-0037, 8-A.

**조회·확정만 있다.** 계정·금액 쓰기 API 는 두지 않는다 — 데이터는 8-B 업로드가 서비스 함수로
넣는다(마스터 확정 Q5).

**권한**: 조회는 전원(`external_auditor` 포함). 확정·재오픈은 `icfr_manager`. 스코핑과 같은 기준이다
(ADR-0034 §2.10 — `require_write` 로 처리하면 일반 사용자가 확정할 수 있게 된다).

**확정은 검증 관문이다** — 검증에 실패하면 422 와 함께 어긋난 계정·차액을 항목별로 돌려준다.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import require_icfr_manager
from app.models.financial_statement import (
    FS_BASES,
    FS_BASIS_LABELS,
    FS_SECTION_LABELS,
    FS_SECTIONS_BY_STATEMENT,
    FS_SOURCE_KIND_LABELS,
    FS_STATEMENT_LABELS,
    FS_STATEMENT_TYPES,
    FS_STATUS_LABELS,
    FS_UNIT_LABELS,
    FsStatement,
)
from app.models.user import User
from app.schemas.financial_statement import (
    AccountNode,
    AmountNode,
    FinalizeRequest,
    FsMeta,
    Option,
    ReopenRequest,
    StatementDetail,
    StatementListItem,
    StatusEventRead,
    ValidationResult,
)
from app.services import financial_statement as svc

router = APIRouter(prefix="/api/fs", tags=["financial-statements"])


def _opts(labels: dict) -> list[Option]:
    return [Option(value=str(k), label=v) for k, v in labels.items()]


def _get(db: Session, statement_id: UUID) -> FsStatement:
    try:
        return svc.get_statement(db, statement_id)
    except svc.FsNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


def _check_statement_type(statement_type: str) -> None:
    if statement_type not in FS_STATEMENT_TYPES:
        raise HTTPException(status_code=422, detail=f"재무제표 종류가 올바르지 않습니다: {statement_type}")


def _account_payload(a, d) -> dict:
    return {"id": a.id, "code": a.code, "name": a.name, "statement_type": a.statement_type,
            "section": a.section, "is_subtotal": a.is_subtotal, "rollup_sign": a.rollup_sign,
            "sort_order": a.sort_order, "depth": d, "valid_from_year": a.valid_from_year,
            "valid_to_year": a.valid_to_year}


def _amount_tree(db: Session, s: FsStatement) -> list[dict]:
    """금액 행이 있는 계정 + 그 조상만 남긴 트리. 조상(제목)은 `has_row=False`."""
    rows_by_acc = {a.id: r for r, a in svc.statement_rows(db, s)}
    tree_rows = svc.account_tree_rows(db, s.statement_type, s.fiscal_year)

    def payload(a, d):
        node = _account_payload(a, d)
        r = rows_by_acc.get(a.id)
        node["has_row"] = r is not None
        if r is not None:
            node.update(amount=r.amount, raw_row_no=r.raw_row_no, raw_label=r.raw_label,
                        raw_indent=r.raw_indent, raw_value=r.raw_value, raw_meta=r.raw_meta)
        return node

    def prune(nodes: list[dict]) -> list[dict]:
        out = []
        for n in nodes:
            n["children"] = prune(n["children"])
            if n["has_row"] or n["children"]:
                out.append(n)
        return out
    return prune(svc.build_tree(tree_rows, payload))


def _validation(result: dict) -> ValidationResult:
    return ValidationResult.model_validate(result)


def _detail(db: Session, s: FsStatement) -> StatementDetail:
    base = StatementListItem.model_validate(s).model_dump()
    return StatementDetail(
        **base,
        tree=[AmountNode.model_validate(n) for n in _amount_tree(db, s)],
        events=[StatusEventRead.model_validate(e) for e in svc.status_events(db, s.id)],
        validation=_validation(svc.validate(db, s)),
    )


@router.get("/meta", response_model=FsMeta)
def get_meta(user: CurrentUser) -> FsMeta:
    return FsMeta(
        statement_types=_opts(FS_STATEMENT_LABELS), bases=_opts(FS_BASIS_LABELS),
        sections=_opts(FS_SECTION_LABELS),
        sections_by_statement={k: list(v) for k, v in FS_SECTIONS_BY_STATEMENT.items()},
        units=_opts(FS_UNIT_LABELS), statuses=_opts(FS_STATUS_LABELS),
        source_kinds=_opts(FS_SOURCE_KIND_LABELS),
    )


@router.get("/accounts", response_model=list[AccountNode])
def get_account_tree(user: CurrentUser, statement_type: str = Query(...),
                     fiscal_year: int | None = Query(default=None),
                     db: Session = Depends(get_db)) -> list[AccountNode]:
    """계정 트리 (재귀 CTE). `fiscal_year` 를 주면 그 연도에 유효한 계정만."""
    _check_statement_type(statement_type)
    rows = svc.account_tree_rows(db, statement_type, fiscal_year)
    return [AccountNode.model_validate(n) for n in svc.build_tree(rows, _account_payload)]


@router.get("/statements", response_model=list[StatementListItem])
def list_statements(user: CurrentUser, fiscal_year: int | None = None, basis: str | None = None,
                    statement_type: str | None = None, db: Session = Depends(get_db)) -> list[StatementListItem]:
    if basis is not None and basis not in FS_BASES:
        raise HTTPException(status_code=422, detail=f"연결·별도 구분이 올바르지 않습니다: {basis}")
    if statement_type is not None:
        _check_statement_type(statement_type)
    q = select(FsStatement).where(FsStatement.is_deleted == False)  # noqa: E712
    if fiscal_year is not None:
        q = q.where(FsStatement.fiscal_year == fiscal_year)
    if basis is not None:
        q = q.where(FsStatement.basis == basis)
    if statement_type is not None:
        q = q.where(FsStatement.statement_type == statement_type)
    order = {t: i for i, t in enumerate(FS_STATEMENT_TYPES)}
    items = sorted(db.scalars(q).all(),
                   key=lambda s: (-s.fiscal_year, s.basis, order.get(s.statement_type, 99)))
    return [StatementListItem.model_validate(s) for s in items]


@router.get("/statements/{statement_id}", response_model=StatementDetail)
def get_statement(statement_id: UUID, user: CurrentUser, db: Session = Depends(get_db)) -> StatementDetail:
    """상세 — 트리 형태 금액 + 상태 이력 + 현재 검증 결과."""
    return _detail(db, _get(db, statement_id))


@router.get("/statements/{statement_id}/validation", response_model=ValidationResult)
def get_validation(statement_id: UUID, user: CurrentUser, db: Session = Depends(get_db)) -> ValidationResult:
    return _validation(svc.validate(db, _get(db, statement_id)))


@router.post("/statements/{statement_id}/finalize", response_model=StatementDetail)
def finalize(statement_id: UUID, body: FinalizeRequest | None = None,
             user: User = Depends(require_icfr_manager), db: Session = Depends(get_db)) -> StatementDetail:
    """draft → final. **검증 실패면 422** — `detail.validation` 에 어긋난 계정·차액이 항목별로 있다."""
    s = _get(db, statement_id)
    try:
        svc.finalize(db, s, user.id, body.reason if body else None)
    except svc.FsConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    except svc.FsValidationError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={
            "message": str(e),
            "validation": _validation(e.result).model_dump(mode="json"),
        }) from None
    db.commit()
    return _detail(db, s)


@router.post("/statements/{statement_id}/reopen", response_model=StatementDetail)
def reopen(statement_id: UUID, body: ReopenRequest, user: User = Depends(require_icfr_manager),
           db: Session = Depends(get_db)) -> StatementDetail:
    """final → draft. **사유 필수**(422). 확정 상태가 아니면 409."""
    s = _get(db, statement_id)
    try:
        svc.reopen(db, s, user.id, body.reason)
    except svc.FsConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    except svc.FsError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    db.commit()
    return _detail(db, s)
