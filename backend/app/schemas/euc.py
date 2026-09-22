"""EUC·IUC 스키마 — ADR-0033, 5-1.

허용 값은 모델 상수에서 만든다 — 정규식을 따로 적으면 상수와 어긋나도 알 수 없다
(`schemas/rcm.py` `_one_of` 와 같은 이유).
"""
import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.euc import CHANGE_FREQUENCY_VALUES, COMPLEXITY_VALUES
from app.models.iuc import IMPORTANCE_VALUES, INFO_TYPES


def _one_of(values: tuple[str, ...]) -> str:
    return "^(" + "|".join(re.escape(v) for v in values) + ")$"


# ── 값 목록 (화면 선택지·집계 기준) ─────────────────────────

class Option(BaseModel):
    value: str
    label: str


class EucMeta(BaseModel):
    """선택지를 서버가 준다 — 화면이 목록을 따로 들면 상수와 어긋난다(13.9-40)."""
    complexity: list[Option]
    change_frequency: list[Option]
    risk_grade: list[Option]
    importance: list[Option]
    info_type: list[Option]
    identification_threshold: str


# ── EUC 파일 ───────────────────────────────────────────────

class EucFileBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    has_macro: bool | None = None
    complexity: str | None = Field(None, pattern=_one_of(COMPLEXITY_VALUES))
    change_frequency: str | None = Field(None, pattern=_one_of(CHANGE_FREQUENCY_VALUES))
    storage_path: str | None = Field(None, max_length=500)
    managing_department: str | None = Field(None, max_length=100)
    manager_name: str | None = Field(None, max_length=100)


class EucFileCreate(EucFileBase):
    pass


class EucFileUpdate(BaseModel):
    """PATCH — 전 필드 optional, `exclude_unset` 판별(보낸 필드만 바꾼다. null 로 비우기 가능)."""
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    has_macro: bool | None = None
    complexity: str | None = Field(None, pattern=_one_of(COMPLEXITY_VALUES))
    change_frequency: str | None = Field(None, pattern=_one_of(CHANGE_FREQUENCY_VALUES))
    storage_path: str | None = Field(None, max_length=500)
    managing_department: str | None = Field(None, max_length=100)
    manager_name: str | None = Field(None, max_length=100)


class EucControlRef(BaseModel):
    id: UUID
    code: str
    name: str


class EucFileRead(EucFileBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    source_risk_rating: str | None = None
    source_risk_basis: str | None = None
    # ── 산출값 (저장하지 않는다) ──
    importance: str | None = None
    risk_grade: str | None = None
    identified: bool | None = None
    # 원천 참고값과 산출 등급이 둘 다 있는데 다르면 true — 검토 신호
    source_mismatch: bool = False
    # 참조하는 **살아 있는** 통제. 0건이면 "참조 통제 0건" 으로 보인다
    controls: list[EucControlRef] = []
    can_edit: bool = False
    model_config = ConfigDict(from_attributes=True)


class EucFileList(BaseModel):
    items: list[EucFileRead]
    total: int
    can_create: bool


# ── 정보 항목 ──────────────────────────────────────────────

class InfoItemBase(BaseModel):
    control_id: UUID
    name: str = Field(min_length=1, max_length=200)
    info_type: str = Field(default=INFO_TYPES[0], pattern=_one_of(INFO_TYPES))
    importance: str | None = Field(None, pattern=_one_of(IMPORTANCE_VALUES))
    euc_file_id: UUID | None = None
    system_name: str | None = Field(None, max_length=100)
    itgc_in_scope: str | None = Field(None, max_length=10)
    source_data: str | None = None
    report_logic: str | None = None
    input_parameter: str | None = None
    source_data_review: str | None = None
    report_logic_control: str | None = None
    input_parameter_review: str | None = None
    design_assessment_result: str | None = None


class InfoItemCreate(InfoItemBase):
    pass


class InfoItemUpdate(BaseModel):
    """PATCH — `control_id` 는 바꾸지 않는다. 다른 통제로 옮기는 것은 삭제 후 생성이다
    (옮기면 권한 판정 대상이 바뀌어, 수정 권한만으로 남의 통제에 항목을 넣을 수 있게 된다)."""
    name: str | None = Field(None, min_length=1, max_length=200)
    info_type: str | None = Field(None, pattern=_one_of(INFO_TYPES))
    importance: str | None = Field(None, pattern=_one_of(IMPORTANCE_VALUES))
    euc_file_id: UUID | None = None
    system_name: str | None = Field(None, max_length=100)
    itgc_in_scope: str | None = Field(None, max_length=10)
    source_data: str | None = None
    report_logic: str | None = None
    input_parameter: str | None = None
    source_data_review: str | None = None
    report_logic_control: str | None = None
    input_parameter_review: str | None = None
    design_assessment_result: str | None = None


class InfoItemRead(InfoItemBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    control_code: str | None = None
    control_name: str | None = None
    process_code: str | None = None
    euc_file_name: str | None = None
    can_edit: bool = False
    model_config = ConfigDict(from_attributes=True)


class InfoItemList(BaseModel):
    items: list[InfoItemRead]
    total: int
    # 정보 항목을 **새로 붙일 수 있는** 통제 — 화면이 통제 선택지를 이것으로 좁힌다
    writable_control_ids: list[UUID]


# ── 대시보드 ───────────────────────────────────────────────

class CountBucket(BaseModel):
    value: str
    label: str
    count: int


class EucIucSummary(BaseModel):
    """0 건도 0 으로 낸다. 미평가는 `__none__` 칸으로 따로 센다 — "Low" 와 섞지 않는다."""
    file_total: int
    item_total: int
    identified: int
    unevaluated: int
    unreferenced_files: int
    source_mismatch: int
    identification_threshold: str
    risk_grade: list[CountBucket]
    importance: list[CountBucket]
    info_type: list[CountBucket]
