"""통제현황(AW열) 1회 보강 적재 (13.9-134, `docs/investigation_control4.md` §3 결정).

확정된 회계연도 RCM(v4)의 **원본 엑셀**에서 통제현황만 채운다. 새 판·재승인을 만들지 않는다 —
AW열은 승인된 원본에 있었는데 업로드가 버린 칸이고, 채우는 것은 내용 변경이 아니라 누락된 적재의 완성이다.

안전장치(하나라도 걸리면 아무것도 쓰지 않는다):
1. 엑셀 통제 코드 집합 = 현재 RCM 통제 코드 집합
2. 엑셀의 다른 칸(설명·테스트 절차·표본수 등 업로드 비교 칸)이 현재 값과 **모두** 같다 — 다른 판 파일 방지
3. 현재 통제현황이 비어 있는 통제만 채운다. 다른 칸은 건드리지 않는다
확정 스냅샷(`rcm_snapshots`)은 고치지 않는다 — 비교 화면은 `rcm_diff.BACKFILLED` 로 키 없는 옛 판과 비교하지 않는다.

    python -m scripts.backfill_control_status <엑셀 경로>            # 미리 보기(기본, 쓰지 않음)
    python -m scripts.backfill_control_status <엑셀 경로> --apply    # 실제 적재
"""
from __future__ import annotations

import argparse
import hashlib
import sys

from openpyxl import load_workbook

from app.api.rcm import _apply_control_update, _parse_rcm_sheet
from app.core.audit_context import SYSTEM_BACKFILL_CONTROL_STATUS, system_actor
from app.core.database import SessionLocal
from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.services.control_resolver import resolve_controls
from app.services.excel_parser import find_data_start_row, find_rcm_sheet
from app.services.rcm_excel_sync import CONTROL_FIELDS, _same

FIELD = "control_status"


def plan(parsed_controls: list[dict], live_controls: list[dict]) -> tuple[list[tuple[dict, str]], list[str]]:
    """(채울 것 [(현재 통제, 값)], 중단 사유) — 순수 함수. 사유가 하나라도 있으면 쓰지 않는다."""
    xl = {c["code"]: c for c in parsed_controls}
    live = {c["code"]: c for c in live_controls}
    problems: list[str] = []
    if set(xl) != set(live):
        only_x, only_l = sorted(set(xl) - set(live)), sorted(set(live) - set(xl))
        problems.append(f"통제 코드 불일치 — 엑셀에만 {only_x[:10]} / RCM 에만 {only_l[:10]}")
    for code in sorted(set(xl) & set(live)):
        diffs = [f for f in CONTROL_FIELDS
                 if f != FIELD and f in xl[code] and not _same(live[code].get(f), xl[code][f])]
        if diffs:
            problems.append(f"{code}: 현재 RCM 과 다른 칸 {diffs}")
    if not any(xl[c].get(FIELD) for c in xl):
        problems.append("엑셀에서 통제현황 열을 찾지 못했습니다(헤더 '통제현황…')")
    todo = [(live[c], xl[c][FIELD]) for c in sorted(set(xl) & set(live))
            if xl[c].get(FIELD) and not live[c].get(FIELD)]
    return todo, problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path")
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다(없으면 미리 보기)")
    args = ap.parse_args(argv)

    with open(args.path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    wb = load_workbook(args.path, data_only=True)
    name, hr, m = find_rcm_sheet(wb)
    ws = wb[name]
    parsed = _parse_rcm_sheet(ws, find_data_start_row(ws, hr, m["process_code"]) - 1, m)

    tok = set_active_tenant(DEFAULT_TENANT_ID)
    db = SessionLocal()
    try:
        live = resolve_controls(db)
        todo, problems = plan(parsed.controls, live)
        print(f"파일 sha256={digest}")
        print(f"엑셀 통제 {len(parsed.controls)} · RCM 통제 {len(live)} · "
              f"이미 채워짐 {sum(1 for c in live if c.get(FIELD))} · 채울 것 {len(todo)}")
        for p in problems:
            print("중단:", p)
        if problems:
            return 2
        if not args.apply:
            print("미리 보기 — 쓰지 않았습니다(--apply 로 실행)")
            return 0
        with system_actor(SYSTEM_BACKFILL_CONTROL_STATUS):
            for c, value in todo:
                if not _apply_control_update(db, c["id"], {FIELD: value}):
                    raise RuntimeError(f"{c['code']} 를 찾지 못했습니다")
            db.commit()
        after = resolve_controls(db)
        print(f"적재 {len(todo)}건 · 적재 후 채워짐 {sum(1 for c in after if c.get(FIELD))}/{len(after)}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        reset_active_tenant(tok)


if __name__ == "__main__":
    sys.exit(main())
