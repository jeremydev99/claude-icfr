"""기존 RCM 데이터 → baseline 이관 (ADR-0027 §7 하이브리드C, 2-A-2).

1회성 이관 스크립트. **alembic 마이그레이션이 아니다** — 실데이터 위험이 최고조이므로
마스터가 결과를 보며 실행하고, 다른 환경의 `upgrade head` 로 자동 실행되지 않게 한다.

실행 (컨테이너 내부, WORKDIR=/app):
    docker compose exec backend python -m scripts.migrate_rcm_to_baseline

성격 (명세 §1):
- baseline 6테이블만 채운다. **instance 는 생성하지 않는다**(암묵 adopt — resolver 가
  instance 없으면 baseline 을 그대로 반환). 회사가 아직 아무 결정도 안 한 상태이므로.
- 기존 6테이블은 **미변경**(복사, 이동 아님). API 가 아직 사용(2-A-3 전환 전).

안전장치 (명세 §3):
- 단일 트랜잭션 — 중간 실패 시 전부 롤백(부분 이관 없음).
- 재실행 안전 — baseline 에 이미 데이터가 있으면 중단·보고. 덮어쓰기 옵션 없음.
- 검증 출력 — 원본 대비 대상 수, 불일치 시 에러 중단.

원본 읽기는 활성 tenant(DEFAULT=사이냅소프트) 컨텍스트에서 수행한다(원본은 AuditedBase →
자동 격리 대상). baseline 은 IdentityBase(전역)이라 tenant 무관 — before_flush stamp·
읽기 필터 모두 baseline 에 영향 없음.
"""
from app.core.database import SessionLocal
from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.rcm import (
    Control,
    ControlAssertion,
    Process,
    Risk,
    RiskCategory,
    SubProcess,
)
from app.models.rcm_baseline import (
    BaselineControl,
    BaselineControlAssertion,
    BaselineProcess,
    BaselineRisk,
    BaselineRiskCategory,
    BaselineSubProcess,
)

# Control 미러링 필드 (risk_id 는 매핑 필요 → 별도 처리, baseline_version 은 default=1).
# models/rcm.py Control 과 1:1 대조 확인.
_CONTROL_FIELDS = [
    "code", "name", "description",
    "objective", "owner_name",
    "is_key_control", "preventive_detective", "auto_manual",
    "activity_approval", "activity_verification", "activity_physical",
    "activity_master_data", "activity_reconciliation", "activity_supervision",
    "related_accounts", "frequency", "ipe_relevant", "related_systems", "euc_description",
]

_BASELINE_MODELS = [
    BaselineProcess, BaselineSubProcess, BaselineRisk,
    BaselineRiskCategory, BaselineControl, BaselineControlAssertion,
]


def _active(db, model):
    """is_deleted=False 활성 행만 (soft-delete 된 것은 이관 대상 아님)."""
    return db.query(model).filter(model.is_deleted == False).all()  # noqa: E712


def _assert_baseline_empty(db) -> None:
    """재실행 안전 — baseline 에 데이터가 하나라도 있으면 중단."""
    existing = {m.__tablename__: db.query(m).count() for m in _BASELINE_MODELS}
    total = sum(existing.values())
    if total > 0:
        nonempty = {t: c for t, c in existing.items() if c > 0}
        raise SystemExit(
            f"[중단] baseline 테이블에 이미 데이터가 있습니다: {nonempty}\n"
            "  이관은 baseline 이 비어 있을 때만 실행됩니다. 덮어쓰기 옵션은 제공하지 않습니다.\n"
            "  재이관이 필요하면 마스터가 baseline 상태를 직접 확인·정리한 뒤 실행하세요."
        )


def migrate() -> None:
    db = SessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)  # 원본(AuditedBase) 읽기 위한 tenant 컨텍스트
    try:
        _assert_baseline_empty(db)

        # ── 원본 로드 (활성 행) ──
        src_processes = _active(db, Process)
        src_sub_processes = _active(db, SubProcess)
        src_risks = _active(db, Risk)
        src_risk_categories = _active(db, RiskCategory)
        src_controls = _active(db, Control)
        src_assertions = _active(db, ControlAssertion)

        # ── 계층 순서대로 이관 + id 매핑 (상위 먼저) ──
        map_process: dict = {}
        for p in src_processes:
            bp = BaselineProcess(code=p.code, name=p.name, description=p.description)
            db.add(bp)
            db.flush()  # bp.id 확보
            map_process[p.id] = bp.id

        map_sub: dict = {}
        for sp in src_sub_processes:
            bsp = BaselineSubProcess(
                code=sp.code, name=sp.name, process_id=map_process[sp.process_id],
            )
            db.add(bsp)
            db.flush()
            map_sub[sp.id] = bsp.id

        map_risk: dict = {}
        for r in src_risks:
            br = BaselineRisk(
                code=r.code, description=r.description,
                assessment_level=r.assessment_level,
                sub_process_id=map_sub[r.sub_process_id],
            )
            db.add(br)
            db.flush()
            map_risk[r.id] = br.id

        map_rc: dict = {}
        for rc in src_risk_categories:
            brc = BaselineRiskCategory(code=rc.code, name=rc.name, description=rc.description)
            db.add(brc)
            db.flush()
            map_rc[rc.id] = brc.id

        map_control: dict = {}
        for c in src_controls:
            bc = BaselineControl(
                risk_id=map_risk[c.risk_id],
                **{f: getattr(c, f) for f in _CONTROL_FIELDS},
            )  # baseline_version=1 (default)
            db.add(bc)
            db.flush()
            map_control[c.id] = bc.id

        for a in src_assertions:
            db.add(BaselineControlAssertion(
                baseline_control_id=map_control[a.control_id],
                baseline_risk_category_id=map_rc[a.risk_category_id],
            ))
        db.flush()

        # ── 검증 (원본 vs 대상) ──
        pairs = [
            ("processes", len(src_processes), BaselineProcess),
            ("sub_processes", len(src_sub_processes), BaselineSubProcess),
            ("risks", len(src_risks), BaselineRisk),
            ("risk_categories", len(src_risk_categories), BaselineRiskCategory),
            ("controls", len(src_controls), BaselineControl),
            ("control_assertions", len(src_assertions), BaselineControlAssertion),
        ]
        mismatch = []
        for name, src_n, model in pairs:
            dst_n = db.query(model).count()
            marker = "OK" if src_n == dst_n else "MISMATCH"
            print(f"  {name:20s}{src_n:5d} -> {model.__tablename__} {dst_n}  [{marker}]")
            if src_n != dst_n:
                mismatch.append((name, src_n, dst_n))

        if mismatch:
            db.rollback()
            raise SystemExit(f"[중단] 원본/대상 수 불일치 — 전체 롤백: {mismatch}")

        # ── 원본 불변 확인 (읽기 후에도 그대로) ──
        controls_src = db.query(Control).filter(Control.is_deleted == False).count()  # noqa: E712
        ca_src = db.query(ControlAssertion).filter(ControlAssertion.is_deleted == False).count()  # noqa: E712
        print(f"  기존 테이블 행 수 (불변 확인): controls {controls_src}, control_assertions {ca_src}")

        db.commit()
        print("\n✓ 이관 완료 — 단일 트랜잭션 커밋. instance 0건 (암묵 adopt).")
    except SystemExit:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        print("[에러] 예외 발생 — 전체 롤백했습니다.")
        raise
    finally:
        reset_active_tenant(tok)
        db.close()


if __name__ == "__main__":
    migrate()
