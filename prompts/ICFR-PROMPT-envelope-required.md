# ICFR-PROMPT-envelope-required

## 목적

백엔드 2-A-3 조회 전환(main, `0ea1cf5`) 반영에 따라, RCM source envelope를 **optional 흡수 → required 계약**으로 조인다.
조회(read) 경로만 연결한다. **생성·수정·삭제(mutation) 라우팅은 연결하지 않는다.**

## 전제 / 불변 조건

- envelope는 **flat 계약**이다. 응답 dict 최상위에 `source`, `baseline_id`, `is_overridden`가 실린다. nested wrapper 아님.
- `id`는 항목 기존 `id` 필드를 **정체성 id**로 재사용한다. 별도 instance id 필드 없음.
- DTO는 flat으로 받고, **어댑터에서 도메인 `SourceEnvelope`(nested)로 조립**하는 기존 구조를 유지한다.
- 2-A-3는 형태 변경이 아니라 "API가 resolver를 거치게" 하는 전환이다. → **필드 형태 재설계 금지.**
- POST/PATCH/DELETE는 여전히 legacy `controls` 테이블에 쓴다. → **mutation 연결 금지 (2-A-4 신호 대기).**

---

## 0단계. 환경 준비 (PowerShell 5.1)

> `&&`, `||`, `$()`, `&` 백그라운드, `/dev/null`, heredoc, `grep` 사용 금지. 한 줄에 하나씩 실행.

```powershell
Set-Location E:\claudeprojects\ICFR
```

```powershell
git fetch origin
```

```powershell
git log origin/main --oneline -5
```

→ `0ea1cf5`가 보이는지 확인. 없으면 여기서 멈추고 보고할 것.

```powershell
git checkout main
```

```powershell
git pull origin main
```

```powershell
docker compose up -d --build backend
```

> `docker compose restart`는 코드 변경을 반영하지 않는다. 반드시 `--build`.

```powershell
docker compose ps
```

```powershell
Invoke-RestMethod -Uri http://localhost:8000/health
```

백엔드가 healthy 상태가 아니면 진행하지 말고 로그를 확인할 것.

```powershell
docker compose logs --tail 50 backend
```

---

## 1단계. 브랜치 생성

```powershell
git checkout -b feature/rcm-envelope-required
```

---

## 2단계. 현재 흡수 코드 확인 (읽기 최소화)

커밋 `cfaf4a7`에서 준비한 4계층 optional 흡수 + source 기반 라우팅 헬퍼 위치만 특정한다.
전체 통독하지 말고 아래 심볼이 있는 파일만 찾아 해당 구간만 읽는다.

- DTO 타입 정의: `source`, `baseline_id`, `is_overridden` (optional로 선언된 곳)
- 어댑터: flat DTO → 도메인 `SourceEnvelope` 조립 함수
- 라우팅 헬퍼: source 기반 순수 함수 (mutation 미연결 상태)
- 컨트롤 목록/상세 쿼리 훅

찾은 파일 경로를 먼저 보고한 뒤 편집을 시작한다.

---

## 3단계. DTO: optional → required

- `source`: required. 리터럴 유니온 유지 (`'baseline' | 'instance' | ...` 등 기존 정의 그대로).
- `is_overridden`: required boolean.
- `baseline_id`: **nullable은 유지하되 필드 존재는 required** (`baseline_id: string | null` 형태). baseline 원본 항목은 baseline_id가 없을 수 있으므로 `?` optional 마크만 제거한다.
- `id`는 정체성 id로 그대로 둔다. 신규 필드 추가 금지.

목록 응답(`ControlSearchOut` 대응 DTO)과 상세 응답 **양쪽 모두** 적용한다.

---

## 4단계. 어댑터: fallback 제거 + 명시적 실패

- 4계층 흡수 로직에서 **기본값 주입 fallback을 제거**한다.
- envelope 필드가 없으면 조용히 넘기지 말고 실패시킨다:
  - 개발 모드(`import.meta.env.DEV`): 계약 위반 필드명을 포함한 `Error` throw.
  - 프로덕션: 콘솔 에러 1회 기록 후 안전한 최소값으로 렌더 (화면 전체 크래시 방지).
- 조립 결과 도메인 `SourceEnvelope`(nested)는 기존 형태 그대로 유지한다.

---

## 5단계. 조회 UI: source 뱃지 (읽기 전용)

컨트롤 목록/상세에 source 상태를 노출한다.

- `is_overridden === true` → "재정의" 뱃지 (강조 색)
- `source === 'instance'` → "테넌트" 뱃지
- `source === 'baseline'` → "기준" 뱃지 (약한 톤)

shadcn/ui `Badge` 사용. 새 컴포넌트를 만들 경우 단일 파일로 작게 유지하고, 목록·상세에서 공용으로 쓴다.
필터·정렬 로직에는 손대지 않는다.

---

## 6단계. mutation 임시 가드 (2-A-4까지 한시적)

⚠️ 현재 생성/수정/삭제는 legacy 테이블에 기록되어 **목록에 나타나지 않는다.** "저장했는데 사라짐"으로 보이는 UX를 막는다.

- 컨트롤 **생성 / 수정 / 삭제 버튼을 disabled** 처리.
- 툴팁 문구: `백엔드 이관 작업 중입니다. 통제 등록·수정은 잠시 후 가능합니다.`
- 제거를 쉽게 하기 위해 단일 플래그로 제어한다. 예: `const RCM_MUTATION_LOCKED = true;` 를 한 곳에 정의하고 참조.
- 플래그 정의 지점 바로 위에 주석: `// TODO(2-A-4): mutation 연결 시 이 플래그와 참조 전부 제거`
- **라우팅 헬퍼는 mutation에 연결하지 않는다. 순수 함수 상태 그대로 둔다.**

---

## 7단계. 빌드 및 검증

```powershell
npm run build
```

타입 에러가 나면 3단계 required 전환의 파급 지점이다. 우회(`any`, `as`, optional chaining 남발)로 덮지 말고 정식으로 타입을 맞춘다.

```powershell
npm run dev
```

브라우저 확인 (`admin@acme.example / admin123`):

1. 컨트롤 목록 **95건** 반환
2. `process_code=EL` → **37건**
3. `assertion=E` → **73건**
4. `risk_level=SR` → **1건**
5. 정렬·페이지네이션 정상
6. 상세 진입 200, 없는 id 404
7. source 뱃지가 각 행에 정상 표시
8. 생성/수정/삭제 버튼 비활성 + 툴팁 노출
9. 콘솔에 envelope 계약 위반 에러 **없음**

---

## 8단계. 커밋 및 머지

```powershell
git add -A
```

```powershell
git commit -m "feat(rcm): envelope 계약 optional -> required 전환 및 source 뱃지 노출"
```

```powershell
git checkout main
```

```powershell
git merge --no-ff feature/rcm-envelope-required
```

```powershell
git push origin main
```

---

## 9단계. 문서 동기화

`ClaudeICFR.md` 섹션 12 / 14 갱신:

- 2-A-3 조회 연결 완료, envelope required 전환 완료
- mutation 임시 잠금 상태 및 해제 조건(2-A-4 신호) 명시
- 라우팅 헬퍼는 여전히 미연결임을 기록

```powershell
git add ClaudeICFR.md
```

```powershell
git commit -m "docs: ClaudeICFR 섹션 12/14 - envelope required 전환 반영"
```

```powershell
git push origin main
```

---

## 금지 사항 (재확인)

- ❌ mutation에 source 라우팅 헬퍼 연결
- ❌ envelope를 nested DTO로 재설계
- ❌ 별도 instance id 필드 신설
- ❌ `docker compose restart`로 백엔드 반영 시도
- ❌ 타입 에러를 `any` / `as` 로 덮기
- ❌ bash 문법(`&&`, heredoc, `grep`) 사용

---

`ICFR-PROMPT-envelope-required.md 진행해줘`
