# ICFR-PROMPT-dialog-a11y-fix

## 목적

브라우저 콘솔에 반복 출력되는 shadcn/ui `DialogContent` 접근성 경고를 제거한다.

```
Warning: Missing `Description` or `aria-describedby={undefined}` for {DialogContent}.
Blocked aria-hidden on an element because its descendant retained focus.
```

Radix UI Dialog는 `DialogContent` 에 `DialogDescription` 또는 `aria-describedby` 가
없으면 경고를 낸다. 스크린리더 사용자에게 다이얼로그 목적이 전달되지 않는 실제 접근성 결함이다.

외부 판매 기준(기업·기관 납품) 상 접근성 경고는 잔존시키지 않는다.

## 절대 하지 말 것

- 다이얼로그의 **동작 로직·상태 관리·폼 제출 흐름 변경 금지**
- API 호출, 훅, 쿼리키 관련 코드 변경 금지
- 경고를 억제하는 편법(콘솔 필터, `aria-describedby={undefined}` 명시) 금지 —
  **실제 설명 텍스트를 넣어 해결한다**
- 기존 UI 레이아웃이 눈에 띄게 바뀌면 안 된다

## 사전 확인

```powershell
Set-Location E:\claudeprojects\ICFR
git status
git fetch origin
git log origin/main --oneline -3
```

원격에 새 커밋 있으면 보고 후 멈춘다.

## 브랜치

```powershell
git checkout -b fix/dialog-a11y
```

---

## Step 1 — 대상 조사

`frontend/src` 전체에서 `DialogContent` 를 사용하는 파일을 모두 찾는다.
(`AlertDialogContent`, `SheetContent` 도 동일한 Radix 경고 대상이므로 함께 조사한다)

각 파일에 대해 다음을 표로 정리해 **먼저 보고한다**:
- 파일 경로
- 다이얼로그 용도(예: 통제 생성, 통제 수정, 삭제 확인)
- `DialogTitle` 유무
- `DialogDescription` 유무

## Step 2 — 수정

각 다이얼로그에 `DialogDescription` 을 추가한다.

- 텍스트는 **한국어**, 해당 다이얼로그의 목적을 한 문장으로 서술
  - 예: 통제 생성 → `새 통제를 등록합니다. 필수 항목을 모두 입력해 주세요.`
  - 예: 삭제 확인 → `이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?`
- `DialogHeader` 안에 `DialogTitle` 바로 다음 위치에 넣는다
- 이미 본문에 같은 뜻의 안내 문구가 있으면 그 문구를 `DialogDescription` 으로 승격시키고
  중복 텍스트는 제거한다
- `DialogTitle` 이 없는 다이얼로그가 있으면 함께 추가한다 (역시 Radix 필수 요소)
- 시각적으로 설명이 불필요한 경우에도 텍스트는 넣되 `sr-only` 로 처리한다
  (숨김이 필요한 경우에만 사용, 남용 금지)

`AlertDialog` 는 `AlertDialogDescription`, `Sheet` 는 `SheetDescription` 사용.

## Step 3 — import 정리

각 파일에서 `DialogDescription` 등 신규 사용 컴포넌트를 import에 추가한다.
사용하지 않게 된 import는 제거한다.

---

## 검증

### 빌드

```powershell
Set-Location E:\claudeprojects\ICFR\frontend
npm run build
```

에러 0.

### 브라우저 확인

```powershell
Set-Location E:\claudeprojects\ICFR
docker compose up -d
```

```powershell
docker compose ps
```

dev 서버는 사용자가 별도 터미널에서 직접 기동한다. **에이전트는 dev 서버를 실행하지 않는다.**

확인 항목 (`admin@acme.example / admin123`):
1. 콘솔에서 `Missing Description` 경고 **0건**
2. `Blocked aria-hidden` 경고 0건
3. 각 다이얼로그 열기/닫기 정상
4. 다이얼로그 내 폼 제출 정상 (생성·수정·삭제)
5. 레이아웃 깨짐 없음

경고가 남으면 어느 다이얼로그인지 특정해서 보고한다.

---

## 커밋 & 머지

```powershell
Set-Location E:\claudeprojects\ICFR
git add -A
```

```powershell
git commit -m "fix(a11y): add DialogDescription to all dialogs

- resolve Radix aria-describedby warnings
- add missing DialogTitle where absent
- no behavioral change"
```

```powershell
git checkout main
```

```powershell
git merge --no-ff fix/dialog-a11y
```

```powershell
git push origin main
```

푸시까지 자동 진행 승인. (UI 문구 추가 — 위험도 낮음)

## 마무리

`ClaudeICFR.md` 섹션 14에 "다이얼로그 접근성 경고 해소" 1줄 추가.

## PowerShell 제약

- `&&`, `||`, `$()`, `grep`, heredoc, `/dev/null`, `curl`, `sleep`, `cat` 금지
- `cd` 대신 `Set-Location`
- 복합 명령 분리 실행, 단일 명령 965바이트 이하
