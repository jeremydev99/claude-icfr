# ICFR_remediation_1_20260602.md — Phase 1 작업4: Remediation·설계평가 (사이냅소프트 양식 그룹 8)

## 메타

| 항목 | 값 |
|---|---|
| 작업 유형 | 백엔드 — DesignAssessment 신규 + Deficiency·RemediationPlan 확장 + 4단계 워크플로 + 이력 |
| 담당 | TrustBuilder |
| 결정 출처 | claude.ai 사전 승인 (Q1~Q5) |
| 예상 시간 | 5~7시간 |
| 영향 파일 | `backend/app/models/remediation.py`, `backend/app/schemas/remediation.py`, `backend/app/api/remediation.py`, `backend/app/seeds/remediation.py`, `backend/alembic/versions/*` |
| 커밋 메시지 | `feat(backend): Remediation 풀 확장 + 설계평가 + 워크플로 + 이력 (Phase 1 작업4)` |

---

## 0. 작업 시작

```powershell
cd C:\claudeprojects\ICFR
```

`ClaudeICFR.md`, `backend/app/models/remediation.py` 먼저 확인.

---

## 1. 본질

사이냅소프트 양식 그룹 8 (BG~CC, 약 23개 컬럼) 처리:
- 설계평가 (모범규준 60, 8요소) — 신규 DesignAssessment 모델
- 평가방법·통제수행자 — DesignAssessment 의 일부
- 개선업무 — RemediationPlan 확장 + 4단계 워크플로
- 담당자 의견·결론·확인 — Deficiency·RemediationPlan 확장

작업3 (Test 워크플로) 스타일 그대로 적용 → ICFR 제도 일관성.

---

## 2. 사용자 사전 승인

| Q | 결정 |
|---|---|
| Q1. 작업 범위 | 4개 그룹 한번에 (설계평가·평가방법·개선·결론) |
| Q2. 모델 구조 | Deficiency 확장 + RemediationPlan 확장 + **신규 DesignAssessment** |
| Q3. 워크플로 | **작업3 스타일** — 4단계 (planned→in_progress→completed→approved) + 이력 모델 |
| Q4. 연도별 구분 | **fiscal_year 필드 추가 (unique 제약 없음)** — Deficiency 는 통제별 다수 발생 자연 허용 |
| Q5. 분량 | 표준 5~7시간 |

---

## 3. 양식 매핑

### 3.1 그룹 8 — 설계평가 (BG~BO, 9개 컬럼)

| Excel | 이름 | DB 매핑 |
|---|---|---|
| BG~BM | 설계평가 8요소 (모범규준 60) | `design_assessment.design_score_*` (7개 점수) |
| BN | 종합 설계 판정 | `design_assessment.overall_design` (enum: Effective/Not_Effective) |
| BO | 설계 결과 비고 | `design_assessment.design_notes` (Text) |

### 3.2 그룹 8 — 평가방법·통제수행자 (BP~BV, 7개 컬럼)

| Excel | 이름 | DB 매핑 |
|---|---|---|
| BP | 평가방법 (Walkthrough/Test of Operation) | `design_assessment.assessment_method` (enum) |
| BQ | 통제수행자 | `design_assessment.performer_name` (Text) |
| BR | 통제수행 빈도 | `design_assessment.performance_frequency` (enum) |
| BS~BV | 평가 절차·근거자료 | `design_assessment.procedure`, `evidence_notes` |

### 3.3 그룹 8 — 개선업무 (BW~BY, 3개 컬럼)

| Excel | 이름 | DB 매핑 |
|---|---|---|
| BW | 개선업무 내용 | `remediation_plan.improvement_description` (Text) |
| BX | 개선 우선순위 | `remediation_plan.priority` (enum: High/Medium/Low) |
| BY | 개선 완료 예정일 | `remediation_plan.target_date` (기존, 유지) |

### 3.4 그룹 8 — 담당자 의견·결론 (BZ~CC, 4개 컬럼)

| Excel | 이름 | DB 매핑 |
|---|---|---|
| BZ | 담당자 의견 | `remediation_plan.owner_opinion` (Text) |
| CA | 검토자 의견 | `remediation_plan.reviewer_opinion` (Text) |
| CB | 최종 결론 | `deficiency.final_conclusion` (Text) |
| CC | 확인일 | `deficiency.confirmed_at` (DateTime) |

---

## 4. 모델 변경

### 4.1 신규 모델 2개

#### 4.1.1 DesignAssessment (설계평가)

```python
class DesignAssessment(AuditedBase):
    """설계평가 — 한 통제·한 연도 = 1건."""
    __tablename__ = "design_assessments"
    
    control_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("controls.id"), nullable=False, index=True
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # 8요소 점수 (1~3)
    design_score_1: Mapped[int] = mapped_column(Integer, default=2)
    design_score_2: Mapped[int] = mapped_column(Integer, default=2)
    design_score_3: Mapped[int] = mapped_column(Integer, default=2)
    design_score_4: Mapped[int] = mapped_column(Integer, default=2)
    design_score_5: Mapped[int] = mapped_column(Integer, default=2)
    design_score_6: Mapped[int] = mapped_column(Integer, default=2)
    design_score_7: Mapped[int] = mapped_column(Integer, default=2)
    design_score_8: Mapped[int] = mapped_column(Integer, default=2)
    
    # 종합 판정
    overall_design: Mapped[str] = mapped_column(String(20), default="Effective")
    # "Effective", "Not_Effective"
    design_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 평가방법
    assessment_method: Mapped[str] = mapped_column(String(20), default="Walkthrough")
    # "Walkthrough", "Test_of_Operation", "Hybrid"
    performer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    performance_frequency: Mapped[str | None] = mapped_column(String(2), nullable=True)
    # "O/D/W/M/Q/A"
    procedure: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 평가자
    assessor_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    assessment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # 관계
    control: Mapped["Control"] = relationship()
    
    __table_args__ = (
        UniqueConstraint("control_id", "fiscal_year", name="uq_design_assessment_control_year"),
    )
```

#### 4.1.2 RemediationStatusHistory (상태 변경 이력)

```python
class RemediationStatusHistory(AuditedBase):
    """RemediationPlan 의 상태 변경 이력 — 작업3 의 TestStatusHistory 스타일.
    
    ICFR 제도 추적성 요구 충족.
    """
    __tablename__ = "remediation_status_history"
    
    remediation_plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("remediation_plans.id"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    plan: Mapped["RemediationPlan"] = relationship(back_populates="status_history")
    changed_by: Mapped["User"] = relationship()
```

### 4.2 기존 Deficiency 모델 확장

```python
class Deficiency(AuditedBase):
    __tablename__ = "deficiencies"
    
    # 기존 (Phase 0)
    code: Mapped[str] = ...
    test_run_id: Mapped[UUID | None] = ...
    severity: Mapped[str] = ...
    description: Mapped[str] = ...
    status: Mapped[str] = mapped_column(String(20), default="open")
    
    # 신규 — 연도 + 통제 연결
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    control_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("controls.id"), nullable=True, index=True
    )
    # 통제와 직접 연결 (test_run 없이도 미비점 등록 가능)
    
    # 신규 — 결론
    final_conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)  # CB
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # CC
    confirmed_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
```

### 4.3 RemediationPlan 모델 확장

```python
class RemediationPlan(AuditedBase):
    __tablename__ = "remediation_plans"
    
    # 기존
    deficiency_id: Mapped[UUID] = ...
    owner_id: Mapped[UUID] = ...
    target_date: Mapped[date] = ...
    action_plan: Mapped[str] = ...
    
    # 신규 — 워크플로 4단계 (작업3 스타일)
    status: Mapped[str] = mapped_column(
        String(20), default="planned", index=True
    )  # "planned", "in_progress", "completed", "approved"
    
    # 신규 — 개선 정보 (양식 그룹 8)
    improvement_description: Mapped[str | None] = mapped_column(Text, nullable=True)  # BW
    priority: Mapped[str] = mapped_column(String(10), default="Medium")  # BX
    # "High", "Medium", "Low"
    owner_opinion: Mapped[str | None] = mapped_column(Text, nullable=True)  # BZ
    reviewer_opinion: Mapped[str | None] = mapped_column(Text, nullable=True)  # CA
    
    # 승인 추적
    approved_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # 관계
    deficiency: Mapped["Deficiency"] = relationship(back_populates="remediation_plan")
    status_history: Mapped[list["RemediationStatusHistory"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
```

### 4.4 사용자 원칙 (ADR-0020)

> ⚠️ **절대 금지**:
> - ❌ `WorkflowEngine`, `StateMachine` 클래스
> - ❌ `DesignAssessmentService`, `RemediationService` 추상화
> - ❌ State Pattern
>
> **워크플로 = String 컬럼 + ALLOWED_TRANSITIONS dict + 명시적 if**. 작업3 과 동일 패턴.

---

## 5. API 엔드포인트

### 5.1 DesignAssessment (신규)

```
GET    /api/remediation/design-assessments
POST   /api/remediation/design-assessments
GET    /api/remediation/design-assessments/{id}
PATCH  /api/remediation/design-assessments/{id}
DELETE /api/remediation/design-assessments/{id}
GET    /api/remediation/design-assessments/by-control/{control_id}?fiscal_year={year}
```

### 5.2 RemediationPlan 확장

기존 CRUD + 신규:

```
POST /api/remediation/plans/{id}/transition
Body: { "to_status": "in_progress", "reason": "..." }

GET /api/remediation/plans/{id}/history
```

### 5.3 Deficiency 확장

기존 CRUD + 신규 필드 (fiscal_year, control_id, final_conclusion, confirmed_at).

---

## 6. 워크플로 전이 로직

작업3 스타일 그대로:

```python
ALLOWED_TRANSITIONS = {
    "planned": {"in_progress"},
    "in_progress": {"completed"},
    "completed": {"approved"},
    "approved": set(),
}
```

전이 시 자동 RemediationStatusHistory 1건 추가 + approved 시 approved_by·approved_at 자동.

---

## 7. 시드 데이터

```python
# seeds/remediation.py 갱신
def seed(ctx):
    # 작업3 의 test_run + control 활용
    control = ctx.get("/api/rcm/controls", params={"code": "EL-010-10-10"})["items"][0]
    
    # DesignAssessment 1건
    da = ctx.get_or_create(
        "/api/remediation/design-assessments",
        lookup_key="control_id+fiscal_year",
        lookup_value=(control["id"], 2025),
        create_payload={
            "control_id": control["id"],
            "fiscal_year": 2025,
            "design_score_1": 2,
            # ... 8개 점수 ...
            "overall_design": "Effective",
            "assessment_method": "Walkthrough",
        },
    )
    
    # Deficiency 1건 (test_run 없이도 가능)
    def_ = ctx.post(
        "/api/remediation/deficiencies",
        json={
            "code": "DEF-2025-001",
            "control_id": control["id"],
            "fiscal_year": 2025,
            "severity": "Medium",
            "description": "샘플 미비점 (시드)",
            "status": "open",
        },
    )
    
    # RemediationPlan + 워크플로
    plan = ctx.post(
        "/api/remediation/plans",
        json={
            "deficiency_id": def_["id"],
            "owner_id": tester["id"],
            "target_date": "2026-12-31",
            "action_plan": "샘플 개선 계획",
            "improvement_description": "샘플 개선 업무",
            "priority": "Medium",
        },
    )
    
    # 전이: planned → in_progress
    ctx.post(
        f"/api/remediation/plans/{plan['id']}/transition",
        json={"to_status": "in_progress", "reason": "시드 — 개선 시작"},
    )
```

---

## 8. Alembic 마이그레이션 + 데이터 손실 경고

```bash
docker compose exec backend alembic revision --autogenerate -m "phase1_remediation_full"
docker compose exec backend alembic upgrade head
```

> ⚠️ **데이터 손실 경고** (ADR-0023):
> 본 작업은 모델 확장만이므로 `docker compose down -v` 불필요.
> 시드 재실행만:
> ```bash
> docker compose exec backend python -m app.seeds.run_all
> ```
> 사이냅소프트 95통제 보존됨.

---

## 9. pytest 추가

| 테스트 | 목적 |
|---|---|
| `test_design_assessment_crud` | CRUD |
| `test_design_assessment_unique_per_year` | (control_id, fiscal_year) 유일 |
| `test_deficiency_extended_fields` | 신규 필드 (fiscal_year, control_id, final_conclusion) |
| `test_deficiency_multiple_per_control_year` | 같은 통제·연도에 다수 미비점 허용 (Q4 결정) |
| `test_remediation_plan_workflow` | 4단계 전이 |
| `test_remediation_workflow_no_skip` | 단계 건너뛰기 차단 |
| `test_remediation_workflow_approved_immutable` | approved 불변 |
| `test_remediation_status_history_auto_create` | 생성 시 자동 이력 |
| `test_remediation_status_history_auto_transition` | 전이 시 자동 이력 |
| `test_approved_records_user` | approved 시 approved_by·approved_at 자동 |

→ 기존 65 + 신규 10 = **75개**.

---

## 10. 진행 단계

| Step | 작업 | 시간 |
|---|---|---|
| 1 | models/remediation.py 확장 + 신규 모델 2개 | 1시간 |
| 2 | schemas/remediation.py 추가 | 45분 |
| 3 | Alembic 마이그레이션 | 30분 |
| 4 | DesignAssessment CRUD API | 45분 |
| 5 | Deficiency·RemediationPlan API 확장 | 1시간 |
| 6 | 워크플로 transition + history API | 45분 |
| 7 | 시드 갱신 | 20분 |
| 8 | DB 마이그레이션 + 재시드 | 10분 |
| 9 | pytest 10개 추가 + 통과 | 1시간 |
| 10 | Swagger UI 검증 | 15분 |
| 11 | ClaudeICFR.md 갱신 | 15분 |
| **합계** | **약 6.5시간** |

---

## 11. 검증 체크리스트

- [ ] 신규 모델 2개 (DesignAssessment, RemediationStatusHistory) 테이블 생성
- [ ] Deficiency 확장 (fiscal_year, control_id, final_conclusion, confirmed_at)
- [ ] RemediationPlan 확장 (status, improvement_description, priority, owner_opinion, reviewer_opinion, approved_by_id, approved_at)
- [ ] (control_id, fiscal_year) UniqueConstraint — DesignAssessment 만 (Deficiency 는 아님, Q4)
- [ ] 4단계 워크플로 작동 (planned→in_progress→completed→approved)
- [ ] 단계 건너뜀 차단 (422)
- [ ] approved 불변
- [ ] 자동 이력 (생성 + 전이)
- [ ] pytest 75개 모두 통과
- [ ] Swagger UI 신규 엔드포인트 표시
- [ ] **ADR-0020 준수**: 추상화 0개

---

## 12. ClaudeICFR.md 갱신

### 12.1 섹션 14 (변경 로그)

```markdown
- **2026-06-02 / TrustBuilder + Claude** — Phase 1 작업4 완료. Remediation·설계평가 풀 확장 (사이냅소프트 양식 그룹 8). 신규 모델 2개 (DesignAssessment, RemediationStatusHistory) + Deficiency·RemediationPlan 확장. 작업3 스타일 4단계 워크플로 + 이력. ICFR 제도 일관성. pytest 75. 추상화 0개.
```

### 12.2 섹션 18 (일일 로그)

```markdown
- **TrustBuilder**: 작업4 완료. 설계평가·개선업무·결론 워크플로. 작업3 패턴 그대로 — ICFR 제도 일관성.
```

---

## 13. 완료 시 결과 요약

| 항목 | 결과 |
|---|---|
| 신규 모델 | DesignAssessment, RemediationStatusHistory |
| 확장 모델 | Deficiency, RemediationPlan |
| 신규 엔드포인트 | DesignAssessment CRUD 6개 + transition + history |
| pytest | 75개 모두 통과 |
| 워크플로 | 4단계 + 건너뜀 차단 + approved 불변 |
| 이력 | 자동 기록 |
| 추상화 | 0개 (ADR-0020) |

OK 시 push.

---

## 14. 사용자 OK 후 push

```bash
git add -A
git commit -m "feat(backend): Remediation 풀 확장 + 설계평가 + 워크플로 + 이력 (Phase 1 작업4)"
git push origin main
```
