# 상위 3계층(Process / SubProcess / Risk) CRUD UI + 신규 탭

## 목표
RCM 모듈에 상위 3계층 CRUD 화면을 **신규 탭**으로 추가한다.
백엔드 계약은 Control과 4계층 완전 동일(TrustBuilder 확정). 신규 코드를 발명하지 말고
**기존 Control 레이어 패턴을 그대로 미러링**한다.
근거: `docs/api/rcm-hierarchy-contract.md`

---

## 0. 선행 조사 (구현 전 필수 · 통독 금지, 해당 파일만)
아래 실제 구조를 먼저 파악한 뒤 구현한다.
- Control mutation 훅(생성/수정/삭제) — 파일 위치·시그니처
- Control 생성/편집 폼 컴포넌트
- Control `dto.ts` / 어댑터 (flat 수신 → 도메인 `SourceEnvelope` 조립)
- 409 등 4xx 에러 핸들링 위치
- RCM 모듈 탭이 정의되는 지점
- `docs/api/rcm-hierarchy-contract.md` §5(스키마)·§6(제약)

---

## 1. 범위
1. **목록** — Process / SubProcess / Risk 각 목록.
   상위참조 nullable → 상위 없는(orphan) 행도 반드시 렌더.
2. **생성 폼** — `code` 입력 가능. 상위 선택은 **드롭다운(기존 항목에서만)**. 자유입력 금지.
3. **편집 폼** — `code`·상위참조 필드는 **read-only/비활성**(PATCH가 조용히 무시함). 나머지 필드만 수정.
4. **삭제** — Control 삭제 다이얼로그 패턴 재사용.
5. **409 핸들러** — **4계층 공통** 단일 핸들러. 응답 `detail` 그대로 표시. 충돌 종류 문자열 매칭 금지.
6. **권한 seam** — 편집/삭제 버튼 노출을 인라인 하드코딩하지 말고 단일 헬퍼(예: `canEditHierarchy`) 뒤에 둔다.
   지금은 무조건 `true` 반환. **역할 판단 로직은 넣지 않는다**(ADR-0031 미확정).

---

## 2. 계약 제약 (반드시 준수)
- **envelope**: 읽기는 required 전환 완료. mutation 훅은 신규(현재 0건).
- **상위 id**: baseline/instance 구분 불필요 — 목록에서 받은 id 그대로 전송. 서버가 판별.
- **PATCH**: `code`·상위참조 변경 불가(무시됨) → UI에서 아예 못 바꾸게.
- **존재하지 않는 상위 id → 201 상위-null**로 생성됨. 드롭다운 선택으로만 원천 차단.
- **낙관적 잠금(row_version) 없음** → 이번 범위 밖. 구현하지 말 것.

---

## 3. 게이트
- `tsc` 통과
- 기존 단위테스트 통과 + mutation 훅 신규 테스트 추가
- **커밋까지만. main push 금지** — 라이브 쓰기 경로에 닿으므로 브라우저 검증 후 사용자가 push.
- 커밋은 feat 단위 1건(docs와 분리).

---

## 4. 셸 (PowerShell 5.1 전용)
`&&` 금지(→ `;`), `grep` 금지(→ `Select-String`), `cd` 금지(→ `Set-Location`),
`/tmp`·heredoc·`nohup`·`2>&1` 금지. bash 구문 생성 금지.
