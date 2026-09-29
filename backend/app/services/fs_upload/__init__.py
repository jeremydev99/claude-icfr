"""재무제표 엑셀 업로드 파서 (8-B, ADR-0037 §3).

- `cells`      셀 해석(금액·단위·접두) — 순수 함수
- `disclosure` 공시양식형 판독기 / `horizontal` 가로 연도형 판독기
- `structure`  트리·합계·부호·섹션 추론 — 순수 함수
- `importer`   preview/commit — 8-A 서비스 함수만 호출한다

DB 를 모르는 앞 네 모듈은 실 샘플 회귀 테스트가 DB 없이 돌 수 있게 분리했다.
"""
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.services.fs_upload import disclosure, horizontal, structure
from app.services.fs_upload.parsed import KIND_DISCLOSURE, KIND_HORIZONTAL, ParsedSheet

SUPPORTED_STATEMENTS = ("BS", "PL", "CF")   # SCE 는 매트릭스라 8-B 미지원(마스터 확정 Q7)
_SCE_UNSUPPORTED = ("자본변동표는 업로드를 지원하지 않습니다 — 행×자본구성요소 표라 계정당 금액 1개 구조에 "
                    "맞지 않습니다(저장 구조 별도 결정)")


def open_workbook(content: bytes) -> Workbook:
    # data_only=True — 수식이 아니라 엑셀이 마지막으로 계산해 저장한 값을 읽는다.
    # read_only 는 셀 서식(들여쓰기·굵게)을 온전히 주지 않아 쓰지 않는다.
    return load_workbook(BytesIO(content), data_only=True)


def detect_kind(ws: Worksheet) -> str | None:
    """공시양식 머리(과목 + 제 N 기)를 먼저 본다 — 정산표도 1행에 `과목` 이 있지만 `제 N 기` 가 없다."""
    if disclosure.looks_like(ws):
        return KIND_DISCLOSURE
    if horizontal.looks_like(ws):
        return KIND_HORIZONTAL
    return None


def parse_sheet(ws: Worksheet, kind: str | None = None, statement_type: str | None = None) -> ParsedSheet:
    """시트 하나를 읽고 구조를 추론한다. 막는 오류는 `sheet.errors` 에 담는다(예외 대신)."""
    kind = kind or detect_kind(ws)
    if kind == KIND_DISCLOSURE:
        sheet = disclosure.read(ws)
    elif kind == KIND_HORIZONTAL:
        sheet = horizontal.read(ws)
        sheet.statement_type = structure.detect_statement_type(sheet)
    elif disclosure.title_type(ws) == "SCE":
        sheet = ParsedSheet(kind=KIND_DISCLOSURE, sheet_name=ws.title, statement_type="SCE", periods=[], rows=[])
        sheet.errors.append(_SCE_UNSUPPORTED)
        return sheet
    else:
        raise ValueError(f"'{ws.title}' 시트에서 재무제표 양식을 찾지 못했습니다")

    detected = sheet.statement_type
    if statement_type is not None:
        if detected is not None and detected != statement_type:
            sheet.errors.append(f"지정한 재무제표 종류({statement_type})와 시트 내용({detected})이 다릅니다")
        sheet.statement_type = statement_type
    if sheet.statement_type is None:
        sheet.errors.append("재무제표 종류를 알 수 없습니다 — statement_type 을 지정하세요")
        return sheet
    if sheet.statement_type not in SUPPORTED_STATEMENTS:
        sheet.errors.append(_SCE_UNSUPPORTED)
        return sheet
    if not sheet.periods:
        sheet.errors.append("읽을 수 있는 회계연도 열이 없습니다")
        return sheet
    if not sheet.rows:
        sheet.errors.append("계정 행이 없습니다")
        return sheet
    structure.infer(sheet)
    return sheet


def scan(wb: Workbook) -> list[dict]:
    """재무제표로 보이는 시트 목록 — 시트를 지정하지 않았을 때 후보로 보여 준다."""
    out = []
    for ws in wb.worksheets:
        kind = detect_kind(ws)
        if kind is None:
            continue
        stype = None
        try:
            if kind == KIND_DISCLOSURE:
                stype = disclosure.read(ws).statement_type
            else:
                stype = structure.detect_statement_type(horizontal.read(ws))
        except ValueError:
            continue
        if stype not in SUPPORTED_STATEMENTS:
            continue   # 연도 열만 있는 명세표(리스·잔액증명 등)는 후보가 아니다
        out.append({"sheet": ws.title, "kind": kind, "statement_type": stype})
    return out
