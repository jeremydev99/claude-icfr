"""감사 로그 — 경로 틀별 '무엇을 했는가'(2026-10-06, 마스터 "EUC-○○ 수정 저장, RCM-○○ 수정 상신|승인 등 모든 단계").

키 = "메서드 경로틀", 값 = (모듈, 동작, 대상 종류, 대상 경로 변수).
- 대상 경로 변수가 None 이면 응답 JSON 의 `id`(등록) 또는 처리 건수(일괄)로 대상을 정한다.
- 상태를 바꾸는 경로는 **모두** 여기 있어야 한다 — `tests/test_audit_logs.py` 가 앱 라우트와 대조한다.
  새 API 를 만들면 한 줄 추가한다(없으면 경로 동사·메서드로 대충 이름 붙이고 대상은 ID 만 남는다).
대상 종류 → 사람이 읽는 이름(코드·명칭)은 `services/audit_target.py`.
"""
from __future__ import annotations

R = tuple[str, str, str | None, str | None]

RCM, CHG, SC, FS, EV = "RCM", "RCM 변경 결재", "스코핑", "재무제표", "증빙"
USR, ORG, AS, TST, REM = "사용자·권한", "조직·역할·정책", "평가 회차", "테스트", "미비점·개선계획"
EXT, PRO, LNK, SCH, RPT = "외부 사용자", "제안 결재", "통제↔계정 연결", "일정", "보고서"

ROUTES: dict[str, R] = {
    # 인증
    "POST /api/auth/login": ("인증", "로그인", None, None),
    "POST /api/auth/logout": ("인증", "로그아웃", None, None),
    "POST /api/auth/refresh": ("인증", "토큰 갱신", None, None),
    "POST /api/auth/change-password": ("인증", "비밀번호 변경", None, None),
    "POST /api/auth/mfa/verify": ("인증", "2단계 인증", None, None),
    "POST /api/auth/mfa/setup": ("인증", "2단계 인증 등록 시작", None, None),
    "POST /api/auth/mfa/enable": ("인증", "2단계 인증 등록", None, None),
    # 일정
    "PUT /api/schedule/templates": (SCH, "표준 일정 저장", None, None),
    "POST /api/schedule/plans/{fiscal_year}/init": (SCH, "일정안 만들기", "schedule_plan", "fiscal_year"),
    "POST /api/schedule/plans/{fiscal_year}/items": (SCH, "일정 추가", "schedule_plan", "fiscal_year"),
    "PUT /api/schedule/plans/{fiscal_year}/items/{iid}": (SCH, "일정 수정 저장", "schedule_item", "iid"),
    "PATCH /api/schedule/plans/{fiscal_year}/items/{iid}/dates": (SCH, "일정 기간 변경(끌기)", "schedule_item", "iid"),
    "DELETE /api/schedule/plans/{fiscal_year}/items/{iid}": (SCH, "일정 삭제", "schedule_item", "iid"),
    "POST /api/schedule/plans/{fiscal_year}/submit": (SCH, "일정안 결재 요청", "schedule_plan", "fiscal_year"),
    "POST /api/schedule/plans/{fiscal_year}/approve": (SCH, "일정안 승인", "schedule_plan", "fiscal_year"),
    "POST /api/schedule/plans/{fiscal_year}/return": (SCH, "일정안 반려", "schedule_plan", "fiscal_year"),
    # RCM — 계층·통제 직접 편집
    "POST /api/rcm/processes": (RCM, "프로세스 등록", "process", None),
    "PATCH /api/rcm/processes/{process_id}": (RCM, "프로세스 수정 저장", "process", "process_id"),
    "DELETE /api/rcm/processes/{process_id}": (RCM, "프로세스 삭제", "process", "process_id"),
    "POST /api/rcm/sub-processes": (RCM, "하위 프로세스 등록", "sub_process", None),
    "PATCH /api/rcm/sub-processes/{sp_id}": (RCM, "하위 프로세스 수정 저장", "sub_process", "sp_id"),
    "DELETE /api/rcm/sub-processes/{sp_id}": (RCM, "하위 프로세스 삭제", "sub_process", "sp_id"),
    "POST /api/rcm/risks": (RCM, "위험 등록", "risk", None),
    "PATCH /api/rcm/risks/{risk_id}": (RCM, "위험 수정 저장", "risk", "risk_id"),
    "DELETE /api/rcm/risks/{risk_id}": (RCM, "위험 삭제", "risk", "risk_id"),
    "POST /api/rcm/risk-categories": (RCM, "위험 분류 등록", "risk_category", None),
    "PATCH /api/rcm/risk-categories/{rc_id}": (RCM, "위험 분류 수정 저장", "risk_category", "rc_id"),
    "DELETE /api/rcm/risk-categories/{rc_id}": (RCM, "위험 분류 삭제", "risk_category", "rc_id"),
    "POST /api/rcm/controls": (RCM, "통제 등록", "control", None),
    "PATCH /api/rcm/controls/{control_id}": (RCM, "통제 바로 반영", "control", "control_id"),
    "DELETE /api/rcm/controls/{control_id}": (RCM, "통제 삭제", "control", "control_id"),
    "POST /api/rcm/controls/bulk-update": (RCM, "통제 일괄 바로 반영", None, None),
    "POST /api/rcm/controls/bulk-delete": (RCM, "통제 일괄 삭제", None, None),
    "POST /api/rcm/control-assertions": (RCM, "경영자 주장 연결", "control_assertion", None),
    "DELETE /api/rcm/control-assertions/{ca_id}": (RCM, "경영자 주장 연결 해제", "control_assertion", "ca_id"),
    "POST /api/rcm/upload-excel": (RCM, "RCM 엑셀 업로드", None, None),
    # RCM 변경 결재(13.9-95)
    "PUT /api/rcm-changes/control/{control_id}": (CHG, "통제 변경 임시저장", "control", "control_id"),
    "POST /api/rcm-changes/bulk": (CHG, "통제 일괄 변경 임시저장·상신", None, None),
    "POST /api/rcm-changes/{cid}/submit": (CHG, "통제 변경 상신", "control_change", "cid"),
    "POST /api/rcm-changes/{cid}/withdraw": (CHG, "통제 변경 회수", "control_change", "cid"),
    "POST /api/rcm-changes/{cid}/dept-approve": (CHG, "조직장 승인", "control_change", "cid"),
    "POST /api/rcm-changes/{cid}/dept-reject": (CHG, "조직장 반려", "control_change", "cid"),
    "POST /api/rcm-changes/batches": (CHG, "내부회계 일괄 상신", "change_batch", None),
    "POST /api/rcm-changes/batches/{bid}/decide": (CHG, "내부회계관리자 결재", "change_batch", "bid"),
    # 스코핑
    "POST /api/scoping": (SC, "스코핑 시작", "scoping", None),
    "PATCH /api/scoping/{scoping_id}": (SC, "스코핑 수정 저장", "scoping", "scoping_id"),
    "PATCH /api/scoping/{scoping_id}/benchmarks/{kind}": (SC, "기준 금액 수정 저장", "scoping", "scoping_id"),
    "POST /api/scoping/{scoping_id}/adjustments": (SC, "조정 등록", "scoping", "scoping_id"),
    "DELETE /api/scoping/{scoping_id}/adjustments/{adjustment_id}": (SC, "조정 삭제", "scoping", "scoping_id"),
    "PATCH /api/scoping/{scoping_id}/texts/{key}": (SC, "문구 수정 저장", "scoping", "scoping_id"),
    "POST /api/scoping/{scoping_id}/accounts/not-applicable": (SC, "계정 해당 없음 지정", "scoping", "scoping_id"),
    "PATCH /api/scoping/{scoping_id}/accounts/{account_id}": (SC, "계정 판단 수정 저장", "scoping_account", "account_id"),
    "POST /api/scoping/{scoping_id}/reload-from-fs": (SC, "재무제표에서 다시 불러오기", "scoping", "scoping_id"),
    "POST /api/scoping/{scoping_id}/confirm": (SC, "스코핑 확정", "scoping", "scoping_id"),
    "POST /api/scoping/{scoping_id}/transition": (SC, "스코핑 상태 변경", "scoping", "scoping_id"),
    "POST /api/scoping/{scoping_id}/review": (SC, "스코핑 검토", "scoping", "scoping_id"),
    "POST /api/scoping/{scoping_id}/reopen-requests": (SC, "재오픈 요청", "scoping", "scoping_id"),
    "POST /api/scoping/{scoping_id}/reopen-requests/{request_id}/decide": (SC, "재오픈 요청 결정", "scoping", "scoping_id"),
    "POST /api/scoping/{scoping_id}/external-approval": (SC, "외부 승인 등록", "scoping", "scoping_id"),
    # 재무제표
    "POST /api/fs/upload": (FS, "재무제표 업로드", None, None),
    "POST /api/fs/upload/attach": (FS, "재무제표 결합", None, None),
    "PATCH /api/fs/statements/{statement_id}": (FS, "재무제표 수정 저장", "fs_statement", "statement_id"),
    # 결재(ADR-0038 2-2) — 예전 /finalize·/reopen(마스터 단독)은 없앴다
    "POST /api/fs/statements/{statement_id}/transition": (FS, "재무제표 상태 변경", "fs_statement", "statement_id"),
    "POST /api/fs/statements/{statement_id}/review": (FS, "재무제표 검토", "fs_statement", "statement_id"),
    "POST /api/fs/statements/{statement_id}/reopen-requests": (FS, "재오픈 요청", "fs_statement", "statement_id"),
    "POST /api/fs/statements/{statement_id}/reopen-requests/{request_id}/decide":
        (FS, "재오픈 요청 결정", "fs_statement", "statement_id"),
    "POST /api/fs/statements/{statement_id}/external-approval": (FS, "외부 승인 등록", "fs_statement", "statement_id"),
    "POST /api/fs/statements/{statement_id}/suspense/{amount_id}/resolve": (FS, "미분류 금액 처리", "fs_statement", "statement_id"),
    "POST /api/fs/template-links": (FS, "표준 계정 연결", None, None),
    "DELETE /api/fs/template-links/{link_id}": (FS, "표준 계정 연결 해제", None, "link_id"),
    # EUC · IUC
    "POST /api/euc/files": ("EUC", "EUC 등록", "euc", None),
    "PATCH /api/euc/files/{file_id}": ("EUC", "EUC 수정 저장", "euc", "file_id"),
    "DELETE /api/euc/files/{file_id}": ("EUC", "EUC 삭제", "euc", "file_id"),
    "POST /api/iuc/items": ("IUC", "IUC 등록", "iuc", None),
    "PATCH /api/iuc/items/{item_id}": ("IUC", "IUC 수정 저장", "iuc", "item_id"),
    "DELETE /api/iuc/items/{item_id}": ("IUC", "IUC 삭제", "iuc", "item_id"),
    # 미비점·개선계획
    "POST /api/remediation/deficiencies": (REM, "미비점 등록", "deficiency", None),
    "PATCH /api/remediation/deficiencies/{deficiency_id}": (REM, "미비점 수정 저장", "deficiency", "deficiency_id"),
    "DELETE /api/remediation/deficiencies/{deficiency_id}": (REM, "미비점 삭제", "deficiency", "deficiency_id"),
    # 미비점 평가 결재(ADR-0038 2-3)
    "POST /api/remediation/deficiencies/{deficiency_id}/transition":
        (REM, "미비점 평가 상태 변경", "deficiency", "deficiency_id"),
    "POST /api/remediation/deficiencies/{deficiency_id}/review": (REM, "미비점 평가 검토", "deficiency", "deficiency_id"),
    "POST /api/remediation/deficiencies/{deficiency_id}/external-approval":
        (REM, "외부 승인 등록", "deficiency", "deficiency_id"),
    "POST /api/remediation/plans": (REM, "개선계획 등록", "plan", None),
    "PATCH /api/remediation/plans/{plan_id}": (REM, "개선계획 수정 저장", "plan", "plan_id"),
    "DELETE /api/remediation/plans/{plan_id}": (REM, "개선계획 삭제", "plan", "plan_id"),
    "POST /api/remediation/plans/{plan_id}/transition": (REM, "개선계획 상태 변경", "plan", "plan_id"),
    "POST /api/remediation/design-assessments": (REM, "설계평가 등록", "design_assessment", None),
    "PATCH /api/remediation/design-assessments/{assessment_id}": (REM, "설계평가 수정 저장", "design_assessment", "assessment_id"),
    "DELETE /api/remediation/design-assessments/{assessment_id}": (REM, "설계평가 삭제", "design_assessment", "assessment_id"),
    # 증빙
    "POST /api/evidence/files": (EV, "증빙 업로드", "evidence", None),
    "PATCH /api/evidence/files/{file_id}": (EV, "증빙 수정 저장", "evidence", "file_id"),
    "DELETE /api/evidence/files/{file_id}": (EV, "증빙 삭제", "evidence", "file_id"),
    "POST /api/evidence/links": (EV, "증빙 연결", "evidence_link", None),
    "DELETE /api/evidence/links/{link_id}": (EV, "증빙 연결 해제", "evidence_link", "link_id"),
    # 사용자·권한
    "POST /api/users/": (USR, "직원 계정 생성", "user", None),
    "PATCH /api/users/{user_id}": (USR, "사용자 수정 저장", "user", "user_id"),
    "DELETE /api/users/{user_id}": (USR, "사용자 삭제", "user", "user_id"),
    "POST /api/users/{user_id}/reset-password": (USR, "비상용 비밀번호 지정", "user", "user_id"),
    "POST /api/users/{user_id}/setup-link": (USR, "설정 링크 발급", "user", "user_id"),
    "POST /api/account-setup/{token}": (USR, "본인 비밀번호 설정(링크)", None, None),
    "POST /api/users/{user_id}/unlock": (USR, "잠금 해제", "user", "user_id"),
    "POST /api/users/{user_id}/mfa-reset": (USR, "2단계 인증 초기화", "user", "user_id"),
    "POST /api/users/roles": (USR, "권한 등록", None, None),
    "PATCH /api/users/roles/{role_id}": (USR, "권한 수정 저장", None, "role_id"),
    "DELETE /api/users/roles/{role_id}": (USR, "권한 삭제", None, "role_id"),
    # 조직·역할·정책
    "POST /api/org/departments": (ORG, "부서 등록", "department", None),
    "PATCH /api/org/departments/{dept_id}": (ORG, "부서 수정 저장", "department", "dept_id"),
    "DELETE /api/org/departments/{dept_id}": (ORG, "부서 삭제", "department", "dept_id"),
    "POST /api/org/memberships": (ORG, "부서원 배치", "membership", None),
    "PATCH /api/org/memberships/{membership_id}": (ORG, "부서원 수정 저장", "membership", "membership_id"),
    "DELETE /api/org/memberships/{membership_id}": (ORG, "부서원 해제", "membership", "membership_id"),
    "POST /api/org/assignments": (ORG, "역할 배정", "assignment", None),
    "DELETE /api/org/assignments/{assignment_id}": (ORG, "역할 배정 해제", "assignment", "assignment_id"),
    "POST /api/org/assignments/bulk": (ORG, "역할 일괄 배정", None, None),
    "PUT /api/org/policies": (ORG, "정책 저장", None, None),
    # 평가 회차
    "POST /api/assessment/cycles": (AS, "회차 생성", "cycle", None),
    "PATCH /api/assessment/cycles/{cycle_id}": (AS, "회차 수정 저장", "cycle", "cycle_id"),
    "POST /api/assessment/cycles/{cycle_id}/activities": (AS, "평가 수행 기록", "cycle", "cycle_id"),
    "POST /api/assessment/activities/{activity_id}/approvals": (AS, "평가 수행 승인", "activity", "activity_id"),
    "POST /api/assessment/cycles/{cycle_id}/close": (AS, "회차 마감", "cycle", "cycle_id"),
    "POST /api/assessment/cycles/{cycle_id}/approve": (AS, "회차 승인", "cycle", "cycle_id"),
    # 테스트
    "POST /api/test/rawc": (TST, "통제 위험평가 등록", "rawc", None),
    "PATCH /api/test/rawc/{rawc_id}": (TST, "통제 위험평가 수정 저장", "rawc", "rawc_id"),
    "DELETE /api/test/rawc/{rawc_id}": (TST, "통제 위험평가 삭제", "rawc", "rawc_id"),
    "POST /api/test/runs": (TST, "테스트 등록", "test_run", None),
    "PATCH /api/test/runs/{run_id}": (TST, "테스트 수정 저장", "test_run", "run_id"),
    "DELETE /api/test/runs/{run_id}": (TST, "테스트 삭제", "test_run", "run_id"),
    "POST /api/test/runs/{run_id}/transition": (TST, "테스트 상태 변경", "test_run", "run_id"),
    "POST /api/test/steps": (TST, "테스트 단계 등록", "test_step", None),
    "PATCH /api/test/steps/{step_id}": (TST, "테스트 단계 수정 저장", "test_step", "step_id"),
    "DELETE /api/test/steps/{step_id}": (TST, "테스트 단계 삭제", "test_step", "step_id"),
    # 보고서
    "PUT /api/report/documents/{fiscal_year}/{doc_key}": (RPT, "보고서 수정 저장", "report_doc", "doc_key"),
    "POST /api/report/documents/{fiscal_year}/{doc_key}/finalize": (RPT, "보고서 확정", "report_doc", "doc_key"),
    "POST /api/report/documents/{fiscal_year}/{doc_key}/reopen": (RPT, "보고서 재오픈", "report_doc", "doc_key"),
    # 통제↔계정 연결
    "POST /api/control-links/auto": (LNK, "자동 매칭", None, None),
    "POST /api/control-links/links": (LNK, "연결 추가", "control_link", None),
    "DELETE /api/control-links/links/{lid}": (LNK, "연결 삭제", "control_link", "lid"),
    "POST /api/control-links/submit": (LNK, "연결 결재 요청", None, None),
    # 외부 사용자
    "POST /api/external/invitations": (EXT, "초대 요청", "invitation", None),
    "POST /api/external/invitations/{iid}/approve": (EXT, "초대 승인", "invitation", "iid"),
    "POST /api/external/invitations/{iid}/revoke": (EXT, "초대 취소", "invitation", "iid"),
    "PATCH /api/external/users/{pid}": (EXT, "외부 사용자 수정 저장", "external_profile", "pid"),
    "POST /api/external/users/{pid}/revoke": (EXT, "외부 사용자 접근 해지", "external_profile", "pid"),
    "POST /api/external/reviews": (EXT, "접근 권한 검토", None, None),
    "POST /api/invite/{token}/accept": (EXT, "초대 수락", None, None),
    # 제안 결재
    "POST /api/proposals/{pid}/items/{iid}/decide": (PRO, "제안 항목 결정", "proposal", "pid"),
    "POST /api/proposals/{pid}/decide-pending": (PRO, "제안 일괄 결정", "proposal", "pid"),
    "POST /api/proposals/{pid}/review-done": (PRO, "제안 검토 완료", "proposal", "pid"),
    "POST /api/proposals/{pid}/approve": (PRO, "제안 승인", "proposal", "pid"),
    "POST /api/proposals/{pid}/return": (PRO, "제안 반려", "proposal", "pid"),
}


def lookup(method: str, route: str) -> R | None:
    return ROUTES.get(f"{method} {route}")
