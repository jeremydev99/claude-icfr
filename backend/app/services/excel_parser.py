"""Excel RCM 헤더 자동 인식 — ADR-0020 준수 (함수만, 클래스·추상화 금지)."""
from __future__ import annotations

HEADER_SYNONYMS: dict[str, list[str]] = {
    "process_code": [
        "프로세스번호", "프로세스 번호",
        "프로세스ID", "프로세스 ID",
        "프로세스코드", "프로세스 코드",
        "Process No", "Process Number",
        "Process ID", "Process Code",
    ],
    "control_code": [
        "통제활동번호", "통제활동 번호",
        "통제번호", "통제 번호",
        "통제코드", "통제 코드",
        "통제ID", "통제 ID",
        "통제활동코드", "통제활동 코드",
        "Control No", "Control Number",
        "Control ID", "Control Code",
        "Control Activity ID",
    ],
    "control_name": [
        "통제활동이름", "통제활동 이름",
        "통제활동명", "통제활동 명",
        "통제이름", "통제 이름",
        "통제명",
        "Control Name",
        "Control Activity Name",
        "Control Activity",
    ],
}


def _normalize(s: str) -> str:
    """공백 제거 + 소문자."""
    if not s:
        return ""
    return s.replace(" ", "").replace(" ", "").lower()


def _row_matches_headers(row, synonyms_dict: dict) -> dict[str, int] | None:
    """한 행에서 필수 헤더 위치 매핑 발견 시 {key: col_idx} 반환, 아니면 None.

    모든 필수 헤더(synonyms_dict의 키)가 매칭되어야 성공.
    """
    normalized_syns = {
        key: [_normalize(s) for s in syns]
        for key, syns in synonyms_dict.items()
    }

    mapping: dict[str, int] = {}
    for col_idx, cell in enumerate(row):
        if cell is None:
            continue
        cell_norm = _normalize(str(cell))
        for key, norm_syns in normalized_syns.items():
            if key in mapping:
                continue
            if cell_norm in norm_syns:
                mapping[key] = col_idx
                break

    if len(mapping) == len(synonyms_dict):
        return mapping
    return None


def _find_header_row(ws, max_row: int) -> tuple[int, dict[str, int]] | None:
    """시트의 1~max_row 안에서 헤더 행 탐색.

    Returns: (header_row_idx, column_mapping) or None
    """
    for row_idx, row in enumerate(
        ws.iter_rows(min_row=1, max_row=max_row, values_only=True),
        start=1,
    ):
        mapping = _row_matches_headers(row, HEADER_SYNONYMS)
        if mapping is not None:
            return row_idx, mapping
    return None


def find_rcm_sheet(wb, max_row: int = 15) -> tuple[str, int, dict[str, int]] | None:
    """모든 시트 순회 → 헤더 매칭 시 (sheet_name, header_row, mapping) 반환.

    첫 번째 매칭 시트 반환. None이면 단계적 확장 응답 필요.
    """
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        result = _find_header_row(ws, max_row)
        if result is not None:
            header_row, mapping = result
            return sheet_name, header_row, mapping
    return None
