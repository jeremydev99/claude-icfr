"""FV_20260917 담당자·설명 반영 — 앱의 통제 수정 로직(_apply_control_update) 그대로. 사용: python apply_fv.py changes.json [--commit]"""
import json, sys
from app.core.database import SessionLocal
from app.core.tenant_context import set_active_tenant
from app.core.audit_context import system_actor
from app.models.tenant import Tenant
from app.api.rcm import _apply_control_update
from app.services import control_resolver, rcm_approval

changes = json.load(open(sys.argv[1], encoding="utf-8"))
commit = "--commit" in sys.argv
db = SessionLocal()
t = db.query(Tenant).filter(Tenant.code == "DEFAULT").one()
set_active_tenant(t.id)
why = rcm_approval.lock_reason(db)
if why and (commit or "--dry-locked" not in sys.argv):
    sys.exit(f"[중단] 잠김: {why}")
live = {c["code"]: c for c in control_resolver.resolve_controls(db)}
missing = [k for k in changes if k not in live]
if missing:
    sys.exit(f"[중단] 없는 통제: {missing}")
n = 0
with system_actor("system:rcm-fv20260917"):
    for code, ch in sorted(changes.items()):
        c = live[code]
        diff = {f: v for f, v in ch.items() if c.get(f) != v}
        if not diff:
            continue
        for f, v in diff.items():
            print(f"{code} | {f} | {str(c.get(f))[:40]!r} -> {str(v)[:40]!r}")
        assert _apply_control_update(db, c["id"], diff)
        n += len(diff)
    db.flush()
after = {c["code"]: c for c in control_resolver.resolve_controls(db)}
bad = [(k, f) for k, ch in changes.items() for f, v in ch.items() if after[k].get(f) != v]
print(f"필드 변경 {n}건, 통제 {len(changes)}건, 반영 후 불일치 {len(bad)}건 {bad[:5]}")
if commit and not bad:
    db.commit(); print("COMMIT")
else:
    db.rollback(); print("ROLLBACK (미리보기)")
