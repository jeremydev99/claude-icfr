# 사이드바 + 레이아웃 디자인 개선

## 목표
사이드바와 본문 영역의 시각적 구분을 명확히 하고, 메뉴 위계·강조·간격을 정돈해
"테스트 페이지" 같은 밋밋한 느낌을 실무용 SaaS 대시보드 수준으로 끌어올린다.

## 범위 / 원칙
- **기능·라우트·navigation.ts 구조는 변경 금지.** 순수하게 시각(스타일)만 개선.
- 기존 shadcn/ui 토큰 체계(`index.css`의 HSL 변수, `tailwind.config.js`) 안에서 조정. 토큰 구조 자체를 갈아엎지 말 것.
- 아키텍처 전환(ADR-0025)과 무관한 작업.
- 다크모드는 범위 외 (라이트 모드만 손봄).

## 현재 문제 (확인된 사항)
- 사이드바 배경(`bg-card-screen`)과 본문 배경(`bg-background`)이 거의 같은 톤 → 좌우 구분 약함
- active 메뉴 강조가 `bg-accent`(연한 회색)이라 약해서 현재 위치 인지가 어려움
- 본문 영역에 공통 패딩·헤더 구분이 없어 밋밋함

## 사전 확인 (읽기만, 수정 금지)
- `frontend/src/layouts/AppLayout.tsx`
- `frontend/src/index.css` (`:root` HSL 토큰)
- `frontend/tailwind.config.js`

## 작업 순서

### 1. 브랜치 생성
```powershell
git checkout main
git pull origin main
git checkout -b feature/fe-sidebar-redesign
```

### 2. 디자인 토큰 점검·보강 (index.css)
파일: `frontend/src/index.css`

- 사이드바 전용 톤을 위해 `--sidebar` 계열 변수를 추가하거나 기존 토큰을 활용:
  - 사이드바 배경: 본문(흰색)보다 한 단계 낮은 차분한 톤 (예: 옅은 슬레이트/그레이). 본문과 명확히 구분되되 눈에 피로하지 않게.
- active 메뉴 강조용으로 `--primary`(네이비)를 활용할 수 있게 함.
- 기존 변수명을 바꾸지 말고, 필요한 것만 추가.

### 3. AppLayout.tsx 사이드바 개선
파일: `frontend/src/layouts/AppLayout.tsx`

다음을 적용:
- **사이드바 배경**: 본문과 구분되는 차분한 배경색 적용 + 오른쪽 경계선(border-r) 유지·강화
- **로고 영역**: 상단 "ICFR" 타이틀 영역에 약간의 위계 부여 (적절한 폰트 weight·여백)
- **그룹 레이블**: 현재 uppercase tracking 스타일 유지하되, 그룹 간 상하 간격을 조금 더 줘서 묶음이 또렷하게 보이도록
- **active 메뉴**: 연한 회색(`bg-accent`) 대신 primary 톤 강조로 변경 (예: 좌측 accent bar 또는 primary 배경 + 흰 텍스트). 현재 위치가 한눈에 보이게.
- **hover 상태**: active와 구분되는 은은한 hover 배경
- **아이콘**: active일 때와 비활성일 때 색 대비를 줘서 위계 강화
- **하단 사용자/로그아웃 영역**: 상단 경계선 유지, 사용자명·이메일 위계 정리

### 4. 본문 영역 정돈
파일: `frontend/src/layouts/AppLayout.tsx` (main 영역)

- `<main>`에 일관된 배경과 적절한 패딩을 줘서 페이지들이 통일된 여백을 갖도록
- 단, 각 페이지가 이미 자체 패딩(p-6 등)을 갖고 있으면 중복되지 않게 확인 후 한쪽으로 통일

## 완료 조건
- 사이드바와 본문이 색으로 명확히 구분됨
- 현재 선택된 메뉴가 한눈에 보임 (primary 강조)
- 그룹 묶음·간격이 또렷함
- 모든 기존 메뉴·라우트 정상 동작 (기능 변화 없음)
- 레이아웃 깨짐 없음 (반응형·스크롤 정상)
- TypeScript 오류 없음
- 빌드 통과

### 5. 커밋 & push
```powershell
git add frontend/src/layouts/AppLayout.tsx frontend/src/index.css
git commit -m "style(frontend): 사이드바·레이아웃 디자인 개선 (본문 구분·active 강조·위계 정돈)"
git push -u origin feature/fe-sidebar-redesign
```

### 6. 화면 테스트 후 main 머지
화면 테스트 OK 확인 후:
```powershell
git checkout main
git merge --no-ff feature/fe-sidebar-redesign
git push origin main
```
