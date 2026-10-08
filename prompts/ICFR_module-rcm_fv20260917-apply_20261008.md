# ICFR_module-rcm_fv20260917-apply_20261008

**필요 모델**: Opus (기존 운영 데이터 변경 — CLAUDE.md §10-5)
**연관**: `ClaudeICFR.md` 13.9-107 · Regina 결정(2026-10-08) "FV_20260917 반영, 경영지원실 오타 바로잡기, A안"

## 전제 (먼저 확인 — 하나라도 아니면 멈추고 보고)
- 운영 `reopen_requests` 에 2026 RCM 재오픈 요청(노정희, 2026-10-08 21:28)이 **전용남 승인**으로 결정됐고, `approval_states` rcm_fiscal_year 가 `draft`(버전 2)
- `control_instances` 0건 (재오픈 뒤 다른 수정이 없었는지)

## 반영 내용
`scripts/oneoff/rcm_fv20260917/`:
- `changes.json` — 통제 61건 / 필드 62개 (담당자 61, EX-010-20-10 설명 1건 — 원본 "경영지원실이실" → "경영지원실" 로 바로잡음)
- `apply_fv.py` — 앱의 `_apply_control_update` 로 회사 수정분(override) 저장, 행위자 `system:rcm-fv20260917`, 잠금이면 중단, 반영 후 전 필드 일치 검사, 불일치 시 롤백
- 원천: 사용자 업로드 `2026 설계평가 RCM ... FV_20260917.xlsx` (repo 미보관). 2026-10-08 미리보기에서 불일치 0 확인

## 기본 방법 — 화면 엑셀 업로드 (13.9-109 배포 후, Regina 결정 Q4)
1. 백업은 아래 절차 1과 같이 먼저 실행·확인
2. 노정희가 오타 고친 최종 FV_20260917 파일을 전용남에게 전달 → 전용남(내부회계관리자 — 엑셀 반영 권한자) 로그인 → RCM → 통제 → Excel 업로드
3. 미리보기가 "통제 61건 변경, 엑셀에 없음 0, 반영하지 않는 것 0" 이고 EX-010-20-10 설명이 "경영지원실 …" 인지 확인 → 현재 RCM 에 반영
4. Claude 가 아래 절차 5로 검증 → 노정희가 버전 비교(v1 → 현재 RCM) 확인 후 검토 요청 → 전용남 승인 = v2
- 미리보기 숫자가 다르면 반영하지 말고 보고. 화면 반영이 안 되면 아래 스크립트 절차(예비)로.

## 예비 — 스크립트 절차 (CLAUDE.md §8.4 위임)
1. 백업: `ssh icfr-prod /opt/icfr/scripts/backup_db.sh` → `/data/backup/log/backup_YYYYMM.log` 방금 시각 `OK key=… size=…` 확인 (없으면 중단)
2. 복사: `scp scripts/oneoff/rcm_fv20260917/{apply_fv.py,changes.json} icfr-prod:/tmp/` → `docker cp` 로 `icfr-backend:/tmp/`
3. 미리보기: `docker exec -w /app -e PYTHONPATH=/app icfr-backend python /tmp/apply_fv.py /tmp/changes.json` → "필드 변경 62건, 통제 61건, 반영 후 불일치 0건"
4. 반영: 같은 명령 + `--commit` → "COMMIT"
5. 검증: `control_instances` 61건(action override), `GET /api/rcm-years/compare?base=<id>:1&target=live` 상당 — 통제 61건 변경
6. 사용자 안내: 노정희 검토 요청 → 전용남 버전 비교 확인 후 승인 → v2. 승인 후 `rcm_snapshots` v2 통제 93 확인
7. `ClaudeICFR.md` 13.9-107 갱신(백업 키·크기, 반영 건수, v2 결과) + 커밋 메시지 제시 → OK 후 push
