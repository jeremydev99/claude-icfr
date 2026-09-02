# ICFR-changelog 2026-08-20 작업 기록

## 목적
오늘(2026-08-20) 완료된 13.5/13.6 작업을 ClaudeICFR.md에 기록한다.

## 스코프 가드 (엄수)
- **ClaudeICFR.md 한 파일만** 수정. 다른 문서·코드 금지.
- 없는 사실 지어내지 않는다. 아래 명시된 확인된 사실만 기재.
- bypass/무승인 금지 — per-command 승인.

## 기록 내용

### §14 변경로그에 추가 (2026-08-20)
1. **13.6 Excel 멀티헤더 파싱 버그 — FE 조사·BE 핸드오프**
   - FE 조사 결과 파싱 로직 전무(원본 File을 FormData로 백엔드 전달), 파싱·검증 전부 backend upload-excel 핸들러 소관 확인
   - 픽스는 BE(TrustBuilder) 트랙으로 확정, TrustBuilder에 핸드오프 완료
   - EXCEL_UPLOAD_LOCKED는 BE 픽스 완료 시까지 유지
2. **13.5 문서 정리 (항목 3·4·1)** — 커밋 79a2618
   - §10에 ADR-0024/0025/0027 요약 추가(SSOT 결손 해소)
   - CLAUDE.md·README.md의 docs/adr·api·erd 참조 (예정) 표기
   - README 모듈 목록 나열 제거 → ClaudeICFR.md 참조로 단일화(모듈 수 불일치 해소)
   - 프롬프트 3종 리포 추가 — 커밋 0ab6613
3. **docs/adr 참조 정정** — TrustBuilder 병합으로 docs/adr/ADR-0028(인프라 baseline) 신설됨에 따라 "(예정)" 문구 정정. docs/api·erd는 미존재 유지. (push 완료: b1a5761..3aaa91c)
4. **Regina_ClaudeContext.md 슬림화** — 정적 부트스트랩 전용으로 축소(동적 상태 §4·6, 중복 §2·5 걷어내고 ClaudeICFR.md 참조로 대체). **로컬 전용(gitignore 유지), 커밋 안 함.**

### §12/13 상태 갱신 (해당 시)
- §13에서 13.5(문서 중복 정리) 항목 상태를 **완료**로 갱신
- §13 13.6은 **BE(TrustBuilder) 트랙으로 이관** 표기, FE는 EXCEL_UPLOAD_LOCKED 유지로 대기
- (실제 섹션 번호·기존 항목 표기 형식은 파일 열어 확인 후 그 형식에 맞춰 기재)

## 산출물
1. §14/§12/§13 diff 요약
2. `docs:` 커밋 메시지 초안

## 커밋·push
- `docs:` 커밋, Tier 1(문서)이므로 커밋 후 push. push 전 diff 요약 보고.

## PowerShell 5.1 제약
- `&&` 금지 → `;` / `grep` 금지 → `Select-String` / `cd` 금지 → `Set-Location E:\claudeprojects\ICFR`
- bash 경로·heredoc·`2>&1` 금지 / 단일 명령 965 bytes 이내

---
ICFR-changelog-20260820.md 진행해줘
