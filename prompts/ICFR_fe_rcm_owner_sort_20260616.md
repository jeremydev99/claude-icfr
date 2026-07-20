# RCM 담당자(owner_name) 정렬 추가

## 목표
ControlTable.tsx 담당자 컬럼 헤더 클릭 시 sort_by=owner_name 정렬 작동

## 사전 확인 (읽기만, 수정 금지)
- frontend/src/features/rcm/types.ts 48번줄 SortCol 타입
- frontend/src/features/rcm/components/ControlTable.tsx 48번줄, 139번줄

## 작업 순서

### 1. 브랜치 생성
```powershell
git checkout main
git pull origin main
git checkout -b feature/fe-rcm-owner-sort
```

### 2. types.ts 수정
파일: frontend/src/features/rcm/types.ts
- SortCol 유니온 타입에 'owner_name' 추가
- sort_by 유니온 타입에도 'owner_name' 추가 (있다면 동일하게)

### 3. ControlTable.tsx 수정
파일: frontend/src/features/rcm/components/ControlTable.tsx
- 48번줄 SortCol 타입에 'owner_name' 추가
- 139번줄 담당자 TableHead를 다른 정렬 가능 컬럼 헤더와 동일한 패턴으로 수정
  - cursor-pointer 클래스 추가
  - onClick={() => toggleSort('owner_name')} 연결
  - SortIcon 컴포넌트 연결 (기존 컬럼과 동일 패턴 사용)

## 완료 조건
- TypeScript 타입 오류 없음
- 담당자 컬럼 헤더 클릭 시 오름차순/내림차순 토글
- 다른 정렬 컬럼과 동일한 UI 패턴

### 4. 커밋 & push
```powershell
git add frontend/src/features/rcm/types.ts
git add frontend/src/features/rcm/components/ControlTable.tsx
git commit -m "feat(frontend): RCM 담당자 컬럼 owner_name 정렬 추가"
git push -u origin feature/fe-rcm-owner-sort
```

### 5. main 머지
```powershell
git checkout main
git merge --no-ff feature/fe-rcm-owner-sort
git push origin main
```
