"""EUC 파일 — ADR-0033 §2.1(정정)·§2.2(정정)·§2.3·§2.4, 5-1.

**EUC 파일은 통제에 딸리지 않는 독립 대상이다**(2026-09-18 정정). 엑셀 파일 하나를 여러
통제가 공유할 수 있으므로, 통제 중심으로 두면 공유 파일이 통제마다 중복 등록되고 EUC 통제
4종(5-2)도 중복 평가된다. 통제와의 연결은 정보 항목(`models/iuc.py`)이 맡는다:

    RCM 통제 ──1:N── 정보 항목(IUC) ──N:1── EUC 파일 ── (5-2) EUC 통제 4종

**여기에 입력받는 값은 복잡도뿐이다**(§2.2 정정). 파일 중요성·위험 등급·통제 식별 여부는
연결된 정보 항목에서 **조회 시 산출**하고 저장하지 않는다(`services/euc_risk.py`) —
정보 항목의 중요성이 바뀔 때마다 파일 값을 다시 맞추는 동기화 경로를 만들지 않기 위해서다
(ADR-0029 §2.2, 유도 가능한 값은 저장하지 않는다).
"""
from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditedBase

# ── 값 상수 — 정의처는 여기 하나다 ─────────────────────────────────
# 값 집합이 상수로 없으면 화면·집계가 "데이터에 있는 값"만 나열한다 — 대시보드에서 0건 분류가
# 사라졌던 13.9-40 의 교훈이다. 라벨은 화면에 필요하므로 코드값과 함께 둔다(순서 = 표시 순서).

# 복잡도 (ADR-0033 §2.3) — 파일 자체의 성질이라 파일에 입력한다(§2.2 정정).
COMPLEXITY_SIMPLE = "simple"
COMPLEXITY_FORMULA = "formula"
COMPLEXITY_MACRO_MODEL = "macro_model"
COMPLEXITY_LABELS = {
    COMPLEXITY_SIMPLE: "단순 기록",
    COMPLEXITY_FORMULA: "수식 재가공",
    COMPLEXITY_MACRO_MODEL: "매크로·링크·모델",
}
COMPLEXITY_VALUES = tuple(COMPLEXITY_LABELS)

# 위험 등급 — 코드값은 소문자다. 원천 양식이 `Low` 로 적고 수식은 `"moderate"` 로 비교하는 등
# 대소문자가 섞여 있어 하나로 정규화했다(원천 수식 쪽 표기를 따른다). 순서가 곧 서열이다.
RISK_LOW = "low"
RISK_MODERATE = "moderate"
RISK_HIGH = "high"
RISK_LABELS = {RISK_LOW: "Low", RISK_MODERATE: "Moderate", RISK_HIGH: "High"}
RISK_GRADES = tuple(RISK_LABELS)

# 파일변경주기 — **EUC 전용 상수다. RCM 수행주기(`FREQUENCY_VALUES`, O/D/W/M/Q/A)를 재사용하지
# 않는다.** 원천 범례가 E/D/W/M/Q/S/A/건별 이라 재사용하면 E·S·건별이 선택지와 집계에서
# 조용히 빠진다(13.9-43). 이름이 비슷해도 축이 다르면 상수를 나눈다.
CHANGE_FREQUENCY_LABELS = {
    "E": "수시",
    "D": "일",
    "W": "주",
    "M": "월",
    "Q": "분기",
    "S": "반기",
    "A": "연",
    "adhoc": "건별",
}
CHANGE_FREQUENCY_VALUES = tuple(CHANGE_FREQUENCY_LABELS)
# 원천 양식은 범례(약자)와 달리 실제 값을 영문 단어로 적었다(`Annually`). 시드가 옮길 때 쓴다.
CHANGE_FREQUENCY_ALIASES = {
    "event": "E", "daily": "D", "weekly": "W", "monthly": "M",
    "quarterly": "Q", "semiannually": "S", "semi-annually": "S",
    "annually": "A", "annual": "A", "건별": "adhoc",
}

# 통제 식별 임계값 정책 키 (§2.4). **하드코딩하지 않는다** — 회사·감사인 협의로 조정된다.
# 기본값 moderate 는 원천 양식 수식 `=IF(OR(위험평가="moderate",위험평가="high"),"통제식별","")`
# 과 같다.
POLICY_EUC_IDENTIFICATION_THRESHOLD = "euc_identification_threshold"
DEFAULT_EUC_IDENTIFICATION_THRESHOLD = RISK_MODERATE


class EucFile(AuditedBase):
    """EUC 파일 — 현업이 만든 엑셀·액세스·매크로 등 IT부서 통제 밖의 도구(§1.1).

    **실물 파일은 보관하지 않는다**(§5 미해결). 목록과 속성만 관리한다.
    """
    __tablename__ = "euc_files"
    __table_args__ = (
        # 정보 항목이 (euc_file_id, tenant_id) 로 가리키는 복합 FK 대상 (ADR-0030 §2.3)
        UniqueConstraint("id", "tenant_id", name="uq_euc_files_id_tenant"),
        # **처음부터 부분 유니크다.** 소프트 삭제 행이 이름을 점유하면 지웠다 다시 만들 수 없다 —
        # user_roles(13.9-35 ④)·departments(13.9-42)에서 사후에 두 번 고쳤다.
        Index(
            "uq_euc_files_tenant_name", "tenant_id", "name",
            unique=True, sqlite_where=text("is_deleted = 0"),
            postgresql_where=text("NOT is_deleted"),
        ),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_macro: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # **NULL = 미평가.** 원천 양식에는 복잡도가 없고 매크로 여부만 있다 — "매크로·링크·모델"
    # 단계는 외부 링크·모델도 포함하므로 매크로가 없다는 것만으로 채우지 않는다(5-1 §2.3).
    complexity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    change_frequency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 관리부서·관리자는 **문자열**이다 — 원천이 "경영지원팀 담당자" 처럼 계정이 아닌 이름을 적는다.
    # 부서·계정 연결은 RCM owner_name 과 같은 미결 과제(13.9-20)라 여기서 먼저 풀지 않는다.
    managing_department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    manager_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # **원천 참고값.** 원천 양식은 위험평가를 직접 적었고 우리 모델은 산출한다. 둘을 섞지 않고
    # 보존해 두면, 산출 등급과 달라졌을 때 그것이 곧 검토 신호가 된다.
    source_risk_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_risk_basis: Mapped[str | None] = mapped_column(Text, nullable=True)
