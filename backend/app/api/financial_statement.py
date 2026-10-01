"""재무제표·계정 트리 API — ADR-0037, 8-A·8-B.

**계정·금액을 직접 쓰는 API 는 없다**(마스터 확정 Q5). 데이터는 8-B 엑셀 업로드
(`POST /upload`, preview/commit)만 넣고, 업로드는 8-A 서비스 함수를 부른다.

**권한**: 조회는 전원(`external_auditor` 포함). 확정·재오픈은 `icfr_manager`. 스코핑과 같은 기준이다
(ADR-0034 §2.10 — `require_write` 로 처리하면 일반 사용자가 확정할 수 있게 된다).

**확정은 검증 관문이다** — 검증에 실패하면 422 와 함께 어긋난 계정·차액을 항목별로 돌려준다.
"""
import json
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
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
    AttachResponse,
    FinalizeRequest,
    FsMeta,
    Option,
    ReopenRequest,
    StatementDetail,
    StatementListItem,
    StatementUpdate,
    StatusEventRead,
    SuspenseItem,
    SuspenseResolveRequest,
    TemplateLinkOut,
    TemplateLinkRequest,
    TemplateLinkResponse,
    TemplateMatchesResponse,
    UploadResponse,
    ValidationResult,
)
from app.services import financial_statement as svc
from app.services import fs_suspense, fs_upload
from app.services import fs_template_match as match_svc
from app.services.fs_upload import attach, importer
from app.services.fs_upload.parsed import KIND_DISCLOSURE, KIND_HORIZONTAL, ParsedRow, ParsedSheet

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


# ── 8-B 엑셀 업로드 ─────────────────────────────────────────

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UPLOAD_KINDS = ("auto", KIND_DISCLOSURE, KIND_HORIZONTAL)


def _depth(r: ParsedRow) -> int:
    d, cur = 0, r.parent
    while cur is not None:
        d, cur = d + 1, cur.parent
    return d


def _rows_payload(sheet: ParsedSheet, mapping: dict[str, str]) -> list[dict]:
    return [{"row_no": r.row_no, "raw_label": r.raw_label, "label": r.label, "depth": _depth(r),
             "parent_row_no": r.parent.row_no if r.parent else None, "kind": r.kind,
             "is_subtotal": r.is_subtotal, "rollup_sign": r.sign, "section": r.section,
             "amounts": {str(y): r.amounts.get(y) for y in sheet.periods}, "flags": r.flags,
             "errors": r.errors, "excluded": r.excluded,
             "match": mapping.get(str(r.row_no)) if r.is_account else None}
            for r in sheet.rows]


def _statement_results(applied: dict, *, committed: bool, finalize: bool) -> list[dict]:
    row_of = {a.id: int(k) for k, a in applied["accounts"].items()}

    def items(lst: list[dict]) -> list[dict]:
        return [{"rule": e["rule"], "raw_row_no": row_of.get(e["account_id"]),
                 "account_id": e["account_id"] if committed else None, "account_name": e["account_name"],
                 "expected": e["expected"], "actual": e["actual"], "diff": e["diff"]} for e in lst]

    out = []
    for res in applied["statements"]:
        v, st = res["validation"], res["statement"]
        out.append({"fiscal_year": res["fiscal_year"], "statement_id": st.id if committed else None,
                    "status": st.status if committed else "draft",
                    "finalize_candidate": res["finalize_candidate"] and finalize,
                    "finalized": res["finalized"], "ok": v["ok"], "errors": items(v["errors"]),
                    "skipped": items(v["skipped"]), "checks_count": len(v["checks"]),
                    "suspense": res.get("suspense", [])})
    return out


def _parse_form(fiscal_years: str | None, tolerance: str, mapping: str | None
                ) -> tuple[list[int] | None, Decimal, dict | None]:
    try:
        years = [int(x) for x in fiscal_years.split(",") if x.strip()] if fiscal_years else None
    except ValueError:
        raise HTTPException(status_code=422, detail="fiscal_years 는 쉼표로 구분한 연도여야 합니다") from None
    try:
        tol = Decimal(tolerance)
    except InvalidOperation:
        raise HTTPException(status_code=422, detail="tolerance 가 숫자가 아닙니다") from None
    parsed = None
    if mapping:
        try:
            parsed = json.loads(mapping)
        except json.JSONDecodeError:
            parsed = None
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=422, detail="mapping 은 JSON 객체여야 합니다")
    return years, tol, parsed


@router.post("/upload", response_model=UploadResponse)
def upload(file: UploadFile = File(...), mode: str = Form(default="preview"),
           sheet: str | None = Form(default=None), kind: str = Form(default="auto"),
           statement_type: str | None = Form(default=None), basis: str | None = Form(default=None),
           unit: int | None = Form(default=None), fiscal_years: str | None = Form(default=None),
           include_prior: bool = Form(default=False), tolerance: str = Form(default="0"),
           finalize: bool = Form(default=True), mapping: str | None = Form(default=None),
           suspense: bool = Form(default=True),
           user: User = Depends(require_icfr_manager), db: Session = Depends(get_db)) -> UploadResponse:
    """재무제표 엑셀 업로드 (ADR-0037 §3). 권한 `icfr_manager`.

    - `mode=preview` — 저장하지 않는다. 트리·금액·추론 플래그·원본 소계 불일치·연도별 검증 결과.
      검증은 commit 과 같은 경로로 넣어 본 뒤 **롤백**해 얻는다(8-A `validate()` 와 같은 결과).
    - `mode=commit` — 막는 오류 422, 기존 재무제표·계정 대응 미확정 409. 최신 연도는 검증을
      통과하면 확정한다(`finalize=false` 로 끔). 오류 응답의 `detail` 도 같은 모양이다.
    - `mapping` — JSON `{"행번호": "account_id" | "new"}`. 해당 종류 계정이 이미 있으면 필수.
    - `fiscal_years` — 쉼표 구분. 생략 시 공시양식형은 당기(`include_prior` 로 전기 추가), 가로 연도형은 전 연도.
    - `unit` — 시트에 단위 표기가 없으면 필수(1·1000·1000000). 추정하지 않는다.
    """
    if mode not in ("preview", "commit"):
        raise HTTPException(status_code=422, detail="mode 는 'preview' 또는 'commit' 이어야 합니다")
    if kind not in UPLOAD_KINDS:
        raise HTTPException(status_code=422, detail=f"kind 가 올바르지 않습니다: {kind}")
    if statement_type is not None:
        _check_statement_type(statement_type)
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail=".xlsx 파일만 허용됩니다")
    years, tol, parsed_mapping = _parse_form(fiscal_years, tolerance, mapping)

    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="파일이 20MB 를 넘습니다")
    try:
        wb = fs_upload.open_workbook(content)
    except Exception as e:  # noqa: BLE001 — 손상 파일 등 openpyxl 예외 종류가 다양하다
        raise HTTPException(status_code=400, detail=f"엑셀 파일을 열 수 없습니다: {e}") from None

    candidates = fs_upload.scan(wb)
    opts = importer.UploadOptions(basis=basis, unit=unit, fiscal_years=years, include_prior=include_prior,
                                  tolerance=tol, finalize=finalize, mapping=parsed_mapping,
                                  filename=file.filename, suspense=suspense)
    resp: dict = {"mode": mode, "committed": False, "can_commit": False, "filename": file.filename,
                  "sheet": None, "kind": None, "statement_type": statement_type, "basis": None, "unit": None,
                  "unit_label": None, "periods": [], "fiscal_years": [], "sheets": candidates,
                  "errors": [], "warnings": [], "master_empty": True, "mapping_required": False,
                  "suggested_mapping": {}, "conflicts": [], "rows": [], "subtotal_diffs": [], "statements": []}

    def done(code: int | None = None) -> UploadResponse:
        out = UploadResponse.model_validate(resp)
        if code is not None:
            raise HTTPException(status_code=code, detail=out.model_dump(mode="json"))
        return out

    fail = 422 if mode == "commit" else None

    # 시트 선택 — 지정이 없으면 재무제표 후보가 하나일 때만 고른다
    if sheet is not None:
        if sheet not in wb.sheetnames:
            raise HTTPException(status_code=422, detail=f"시트를 찾을 수 없습니다: {sheet}")
        ws = wb[sheet]
    elif len(candidates) == 1:
        ws = wb[candidates[0]["sheet"]]
    else:
        resp["errors"].append("재무제표 시트를 찾지 못했습니다" if not candidates else
                              f"재무제표로 보이는 시트가 {len(candidates)}개입니다 — sheet 를 지정하세요")
        return done(fail)
    resp["sheet"] = ws.title

    try:
        parsed = fs_upload.parse_sheet(ws, None if kind == "auto" else kind, statement_type)
    except ValueError as e:
        resp["errors"].append(str(e))
        return done(fail)
    p = importer.plan(db, parsed, opts)
    resp.update(kind=parsed.kind, statement_type=parsed.statement_type, basis=p.basis, unit=p.unit,
                unit_label=parsed.unit_word, periods=parsed.periods, fiscal_years=p.years,
                errors=p.errors, warnings=p.warnings, master_empty=p.master_empty,
                mapping_required=p.mapping_required, suggested_mapping=p.suggested, conflicts=p.conflicts,
                rows=_rows_payload(parsed, p.mapping), subtotal_diffs=importer.diffs(parsed))
    resp["can_commit"] = not (p.blocked or p.conflicts or p.mapping_required)

    if mode == "preview":
        if not p.blocked:
            try:
                applied = importer.apply(db, parsed, p, opts, user.id, finalize=False)
                resp["warnings"] = p.warnings + applied["structure_warnings"]
                resp["statements"] = _statement_results(applied, committed=False, finalize=opts.finalize)
            except svc.FsError as e:
                resp["errors"] = p.errors + [str(e)]
                resp["can_commit"] = False
            finally:
                db.rollback()   # preview 는 저장하지 않는다
        return done()

    if p.blocked:
        return done(422)
    if p.conflicts or p.mapping_required:
        return done(409)
    try:
        applied = importer.apply(db, parsed, p, opts, user.id, finalize=opts.finalize)
    except svc.FsError as e:
        db.rollback()
        resp["errors"] = p.errors + [str(e)]
        resp["can_commit"] = False
        return done(422)
    db.commit()
    resp.update(committed=True, can_commit=False, warnings=p.warnings + applied["structure_warnings"],
                statements=_statement_results(applied, committed=True, finalize=opts.finalize))
    return done()


@router.post("/upload/attach", response_model=AttachResponse)
def upload_attach(file: UploadFile = File(...), mode: str = Form(default="preview"),
                  sheet: str | None = Form(default=None), statement_type: str | None = Form(default=None),
                  basis: str | None = Form(default=None), unit: int | None = Form(default=None),
                  bridge_column: str | None = Form(default=None), category_map: str | None = Form(default=None),
                  fiscal_years: str | None = Form(default=None), finalize: bool = Form(default=True),
                  suspense: bool = Form(default=True),
                  user: User = Depends(require_icfr_manager), db: Session = Depends(get_db)) -> AttachResponse:
    """정산표(가로 연도형)를 이미 올린 공시 재무제표에 붙인다 (8-B2, ADR-0037 §3.2). 권한 `icfr_manager`.

    정산표 COA 잎을 매핑 열 값으로 공시 행 아래에 달고, 그 공시 행을 소계로 바꾼다. 공시 행 금액 = COA 합을
    8-A 검증이 확인한다. 대상 재무제표가 final 이면 409(재오픈 후). `category_map` — JSON
    `{"매핑 값": "공시 계정명"}`(PL 분류명 → 공시 행). `unit` — 정산표엔 단위 표기가 없어 필수.
    """
    if mode not in ("preview", "commit"):
        raise HTTPException(status_code=422, detail="mode 는 'preview' 또는 'commit' 이어야 합니다")
    if statement_type is not None:
        _check_statement_type(statement_type)
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail=".xlsx 파일만 허용됩니다")
    years, _tol, cmap = _parse_form(fiscal_years, "0", category_map)
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="파일이 20MB 를 넘습니다")
    try:
        wb = fs_upload.open_workbook(content)
    except Exception as e:  # noqa: BLE001 — 손상 파일 등 openpyxl 예외 종류가 다양하다
        raise HTTPException(status_code=400, detail=f"엑셀 파일을 열 수 없습니다: {e}") from None

    resp: dict = {"mode": mode, "committed": False, "can_commit": False, "filename": file.filename, "sheet": None,
                  "statement_type": statement_type, "basis": None, "unit": None, "bridge_column": None,
                  "bridge_candidates": [], "periods": [], "fiscal_years": [], "errors": [], "warnings": [],
                  "conflicts": [], "unmatched": [], "rows": [], "statements": []}
    fail = 422 if mode == "commit" else None

    def done(code: int | None = None) -> AttachResponse:
        out = AttachResponse.model_validate(resp)
        if code is not None:
            raise HTTPException(status_code=code, detail=out.model_dump(mode="json"))
        return out

    candidates = [c for c in fs_upload.scan(wb) if c["kind"] == KIND_HORIZONTAL
                  and (statement_type is None or c["statement_type"] == statement_type)]
    if sheet is not None:
        if sheet not in wb.sheetnames:
            raise HTTPException(status_code=422, detail=f"시트를 찾을 수 없습니다: {sheet}")
        ws = wb[sheet]
    elif len(candidates) == 1:
        ws = wb[candidates[0]["sheet"]]
    else:
        resp["errors"].append("정산표 시트를 찾지 못했습니다" if not candidates else
                              f"정산표로 보이는 시트가 {len(candidates)}개입니다 — sheet 를 지정하세요 "
                              f"({', '.join(c['sheet'] for c in candidates)})")
        return done(fail)
    resp["sheet"] = ws.title
    try:
        parsed = fs_upload.parse_sheet(ws, None, statement_type)
    except ValueError as e:
        resp["errors"].append(str(e))
        return done(fail)

    opts = attach.AttachOptions(basis=basis, unit=unit, bridge_column=bridge_column, category_map=cmap,
                                fiscal_years=years, finalize=finalize, filename=file.filename)
    p = attach.plan(db, parsed, opts)
    resp.update(statement_type=parsed.statement_type, basis=p.basis, unit=p.unit, bridge_column=p.bridge_column,
                bridge_candidates=p.bridge_candidates, periods=parsed.periods, fiscal_years=p.years,
                errors=p.errors, warnings=p.warnings, conflicts=p.conflicts, unmatched=p.unmatched,
                rows=[{"row_no": ar.row.row_no, "raw_label": ar.row.raw_label, "name": ar.name, "bridge": ar.bridge,
                       "source_path": ar.source_path,
                       "target_account_id": ar.target.id if ar.target else None,
                       "target_name": ar.target.name if ar.target else None,
                       "existing_account_id": ar.existing.id if ar.existing else None,
                       "amounts": {str(y): ar.row.amounts.get(y) for y in parsed.periods},
                       "skip_reason": ar.skip_reason} for ar in p.rows])
    resp["can_commit"] = not (p.blocked or p.conflicts)

    if mode == "preview":
        if not p.blocked:
            try:
                # 확정 재무제표가 있어도 preview 는 결과를 보여 준다 — draft 로 가정해 넣어 본 뒤 롤백
                for st in p.statements.values():
                    st.status = "draft"
                db.flush()
                applied = attach.apply(db, parsed, p, user.id, finalize=False, suspense=suspense)
                resp["statements"] = _statement_results(applied, committed=False, finalize=opts.finalize)
            except (svc.FsError, svc.FsConflictError) as e:
                resp["errors"] = p.errors + [str(e)]
                resp["can_commit"] = False
            finally:
                db.rollback()   # preview 는 저장하지 않는다
        return done()

    if p.blocked:
        return done(422)
    if p.conflicts:
        return done(409)
    try:
        applied = attach.apply(db, parsed, p, user.id, finalize=opts.finalize, suspense=suspense)
    except (svc.FsError, svc.FsConflictError) as e:
        db.rollback()
        resp["errors"] = p.errors + [str(e)]
        resp["can_commit"] = False
        return done(422)
    db.commit()
    resp.update(committed=True, can_commit=False,
                statements=_statement_results(applied, committed=True, finalize=opts.finalize))
    return done()


# ── 8-C 템플릿 링크 ─────────────────────────────────────────

@router.get("/template-matches", response_model=TemplateMatchesResponse)
def get_template_matches(user: CurrentUser, statement_type: str = Query(...),
                         template_code: str | None = Query(default=None),
                         template_version: int | None = Query(default=None),
                         db: Session = Depends(get_db)) -> TemplateMatchesResponse:
    """회사 계정별 현재 링크 + 자동 제안(저장 안 됨) + 템플릿 계정별 연결 수 (ADR-0037 §4). 조회 전원."""
    _check_statement_type(statement_type)
    try:
        return TemplateMatchesResponse.model_validate(
            match_svc.matches(db, statement_type, template_code, template_version))
    except svc.FsNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


@router.post("/template-links", response_model=TemplateLinkResponse)
def create_template_links(body: TemplateLinkRequest, user: User = Depends(require_icfr_manager),
                          db: Session = Depends(get_db)) -> TemplateLinkResponse:
    """사람이 확인한 링크 저장. 근거(exact/normalized/manual)는 서버가 이름 규칙으로 판정한다.
    같은 회사 계정의 기존 링크는 대체된다(이력은 소프트 삭제로 남는다). 권한 `icfr_manager`."""
    try:
        links, warnings = match_svc.confirm(db, body.template_code, body.template_version,
                                            [i.model_dump() for i in body.links], user.id)
    except svc.FsNotFoundError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from None
    except svc.FsError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from None
    db.commit()
    return TemplateLinkResponse(links=[TemplateLinkOut.model_validate(x) for x in links], warnings=warnings)


@router.delete("/template-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template_link(link_id: UUID, user: User = Depends(require_icfr_manager),
                         db: Session = Depends(get_db)) -> None:
    """링크 해제(소프트 삭제 — 누가·언제가 감사 컬럼에 남는다). 권한 `icfr_manager`."""
    try:
        match_svc.unlink(db, link_id)
    except svc.FsNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    db.commit()



# ── 임시계정(원본 차이) 검토 ─────────────────────────────────

@router.get("/statements/{statement_id}/suspense", response_model=list[SuspenseItem])
def list_suspense(statement_id: UUID, user: CurrentUser, db: Session = Depends(get_db)) -> list[SuspenseItem]:
    """임시계정 행 — 미해결·해소(이력) 모두. 조회 전원."""
    return [SuspenseItem.model_validate(x) for x in fs_suspense.items(db, _get(db, statement_id))]


@router.post("/statements/{statement_id}/suspense/{amount_id}/resolve", response_model=StatementDetail)
def resolve_suspense(statement_id: UUID, amount_id: UUID, body: SuspenseResolveRequest,
                     user: User = Depends(require_icfr_manager), db: Session = Depends(get_db)) -> StatementDetail:
    """임시계정 해소(ADR-0037 §2.13) — `fix_subtotal`(소계를 하위 합으로 정정) / `reclass`(같은 소계 아래 형제
    계정으로 차액 이동) / `accept`(사유와 함께 유지). 사유 필수, draft 에서만(확정이면 409). 권한 `icfr_manager`."""
    s = _get(db, statement_id)
    try:
        fs_suspense.resolve(db, s, amount_id, body.action, body.reason, user.id, body.target_account_id)
    except svc.FsNotFoundError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from None
    except svc.FsConflictError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from None
    except svc.FsError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from None
    db.commit()
    return _detail(db, s)


@router.patch("/statements/{statement_id}", response_model=StatementDetail)
def update_statement(statement_id: UUID, body: StatementUpdate, user: User = Depends(require_icfr_manager),
                     db: Session = Depends(get_db)) -> StatementDetail:
    """허용 오차 설정(8-D) — 백만원 공시의 반올림 ±1 등. draft 에서만(확정이면 409). 권한 `icfr_manager`."""
    s = _get(db, statement_id)
    try:
        svc.set_tolerance(db, s, body.tolerance)
    except svc.FsConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    except svc.FsError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    db.commit()
    return _detail(db, s)
