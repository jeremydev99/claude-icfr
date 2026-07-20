# 증빙 관리 메뉴 이동: 보고 그룹 → 평가 그룹

## 목표
사이드바에서 "증빙 관리" 메뉴를 "보고" 그룹에서 "평가" 그룹으로 이동한다.
ICFR 업무 흐름상 증빙은 평가(설계·운영평가) 과정에서 수집되는 자료이므로 평가 그룹이 더 자연스럽다.

## 범위
- 메뉴 구성(그룹 배치)만 변경. 라우트 경로(/evidence)·페이지·기능은 그대로 유지.
- 단순 위치 이동이므로 아키텍처 전환(ADR-0025)과 무관.

## 사전 확인 (읽기만, 수정 금지)
- `frontend/src/config/navigation.ts`

## 작업 순서

### 1. 브랜치 생성
```powershell
git checkout main
git pull origin main
git checkout -b feature/fe-evidence-menu-move
```

### 2. navigation.ts 수정
파일: `frontend/src/config/navigation.ts`

- "보고" 그룹에서 "증빙 관리" 항목(/evidence) 제거
- "평가" 그룹에 "증빙 관리" 항목 추가 (Test, 개선계획 다음, 즉 평가 그룹의 마지막 순서)
- 다른 그룹·항목·순서는 변경하지 말 것
- 결과적으로 "보고" 그룹에는 Report만 남고, "평가" 그룹은 Test → 개선계획 → 증빙 관리 순서가 됨

## 완료 조건
- 사이드바에서 증빙 관리가 평가 그룹 아래에 표시됨
- 보고 그룹에는 Report만 남음
- /evidence 라우트 정상 동작 (메뉴 클릭 시 기존 증빙 페이지 그대로 열림)
- TypeScript 오류 없음
- 빌드 통과

### 3. 커밋 & push
```powershell
git add frontend/src/config/navigation.ts
git commit -m "refactor(frontend): 증빙 관리 메뉴를 보고 그룹에서 평가 그룹으로 이동"
git push -u origin feature/fe-evidence-menu-move
```

### 4. 화면 테스트 후 main 머지
화면 테스트 OK 확인 후:
```powershell
git checkout main
git merge --no-ff feature/fe-evidence-menu-move
git push origin main
```
