"""일정관리 (2026-10-06, 마스터 지시) — 표준 일정 + 회계연도별 일정안 + 전결라인 결재.

- **표준 일정(`ScheduleTemplate`)** — 회사 단위. 마스터관리자가 편집한다. 저장된 것이 없으면 내장 표준 8개를 쓴다
  (`BUILTIN_TEMPLATES`, 화면 `schedule.pure.ts` 의 STANDARD_TEMPLATE 과 같은 값). 월은 회계월 오프셋(1 = 첫 달, 13~15 = 익년).
- **일정안(`SchedulePlan`)** — 회계연도마다 하나. 항목(`ScheduleItem`)은 표준(표준 일정에서 가져옴)·사용자 지정 둘.
  내부회계 담당자(1~3단계)가 고친다. 상태 draft → in_review → approved. 승인된 일정안을 고치면 새 판(draft, 판 +1)이 된다.
- **결재선** — 정책 `schedule_approval_line`(예 `lead,master`)을 요청 시점에 복사해 둔다. 단계: lead(책임관리자)·
  master(마스터관리자)·ceo(대표이사). **요청자·앞 단계 승인자는 다음 단계를 승인할 수 없다**(ADR-0038 자기 승인 금지).
"""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditedBase

ENTITY_SCHEDULE = "schedule_plan"
POLICY_SCHEDULE_APPROVAL_LINE = "schedule_approval_line"
DEFAULT_APPROVAL_LINE = "lead,master"
APPROVAL_LINES = ("none", "lead", "master", "lead,master", "master,ceo", "lead,master,ceo")
STEP_LABELS = {"lead": "책임관리자", "master": "마스터관리자", "ceo": "대표이사"}

PLAN_DRAFT, PLAN_REVIEW, PLAN_APPROVED = "draft", "in_review", "approved"
PLAN_STATUS_LABELS = {PLAN_DRAFT: "작성 중", PLAN_REVIEW: "결재 중", PLAN_APPROVED: "승인"}
KIND_STANDARD, KIND_CUSTOM = "standard", "custom"
CATEGORIES = ("planning", "design", "operation", "remediation", "reporting", "audit", "other")

BUILTIN_TEMPLATES: list[dict] = [
    {"code": "scoping", "name": "스코핑·중요성 결정", "category": "planning", "start_offset": 1, "end_offset": 2,
     "description": "전기 재무제표 기준 중요성 금액 산정, 유의한 계정·프로세스·사업단위 선정",
     "tasks": ["중요성 금액 산정", "유의한 계정과목·주석 선정", "평가 범위(사업단위·프로세스) 확정"]},
    {"code": "rcm", "name": "RCM 갱신", "category": "planning", "start_offset": 2, "end_offset": 3,
     "description": "프로세스 변경 반영, 위험·통제 매트릭스 개정 및 승인",
     "tasks": ["프로세스 변경사항 수집", "위험·통제 추가/폐기 반영", "RCM 개정 승인"]},
    {"code": "design", "name": "설계평가", "category": "design", "start_offset": 3, "end_offset": 5,
     "description": "핵심통제 설계의 적정성 검토(워크스루)",
     "tasks": ["설계평가 회차 생성", "통제별 워크스루·설계평가 기록", "설계 미비점 식별"]},
    {"code": "op-interim", "name": "운영평가 (중간)", "category": "operation", "start_offset": 6, "end_offset": 8,
     "description": "상반기 표본 기준 운영 효과성 테스트",
     "tasks": ["운영평가(중간) 회차 생성", "표본 추출·증빙 수집", "테스트 결과 기록·승인"]},
    {"code": "op-final", "name": "운영평가 (기말)", "category": "operation", "start_offset": 10, "end_offset": 13,
     "description": "잔여기간(Roll-forward) 및 기말 결산 통제 테스트",
     "tasks": ["운영평가(기말) 회차 생성", "Roll-forward 테스트", "기말 결산통제(FCRP) 테스트"]},
    {"code": "remediation", "name": "미비점 개선·재테스트", "category": "remediation", "start_offset": 4, "end_offset": 13,
     "description": "식별된 미비점의 개선계획 수립·이행 및 재테스트 (연중 상시, 기말 집중)",
     "tasks": ["미비점 개선계획 이행 점검", "개선 완료 통제 재테스트"]},
    {"code": "reporting", "name": "경영진 운영실태 보고·이사회/감사위원회 보고", "category": "reporting",
     "start_offset": 14, "end_offset": 15, "description": "대표이사 운영실태 보고, 감사(위원회) 평가보고, 이사회 보고",
     "tasks": ["운영실태 보고서 작성", "감사위원회 평가보고", "이사회 보고"]},
    {"code": "audit", "name": "외부감사인 대응", "category": "audit", "start_offset": 12, "end_offset": 15,
     "description": "외부감사인 내부회계관리제도 감사 자료 요청 대응",
     "tasks": ["감사인 PBC 자료 대응", "감사인 발견사항 협의"]},
]


class ScheduleTemplate(AuditedBase):
    __tablename__ = "schedule_templates"
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tasks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SchedulePlan(AuditedBase):
    __tablename__ = "schedule_plans"
    __table_args__ = (
        Index("uq_schedule_plans_year", "tenant_id", "fiscal_year", unique=True,
              sqlite_where=text("is_deleted = 0"), postgresql_where=text("NOT is_deleted")),
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PLAN_DRAFT)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    approval_line: Mapped[list] = mapped_column(JSON, nullable=False, default=list)   # 요청 시점 결재선 복사
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approvals: Mapped[list] = mapped_column(JSON, nullable=False, default=list)       # [{step, user_id, name, at, note}]
    requested_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    returned_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 마지막 승인본(2026-10-07, 13.9-100) — 화면(간트·이번 달 할 일)은 이것만 본다. 수정은 작성 중 판에만 쌓이고
    # 최종 승인 때 이 사본을 바꾼다. 반려돼도 승인본은 그대로. 한 번도 승인되지 않았으면 None(화면은 표준 일정)
    approved_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    approved_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ScheduleItem(AuditedBase):
    __tablename__ = "schedule_items"
    plan_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("schedule_plans.id"), nullable=False,
                                          index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default=KIND_CUSTOM)
    template_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tasks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
