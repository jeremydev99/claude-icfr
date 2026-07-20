# 사용자/권한 모듈: 사용자 목록·상세 + 역할(UserRole) CRUD

## 목표
사용자 목록·상세 조회 화면(조회만)과 역할(UserRole) 풀 CRUD 화면을 구축한다.

## 범위 제한 (이번 작업 제외, 백엔드 미구현)
- 사용자 생성·수정·삭제 — 백엔드 API 없음, 제외
- 비밀번호 변경 — 백엔드 API 없음, 제외
- 위 두 가지는 협업자(TrustBuilder)에게 별도 요청 예정, 프론트 작업 대상 아님

## 사전 확인 (읽기만, 수정 금지)
- `frontend/src/features/users/api/usersApi.ts`, `useUsers.ts` (기존 내용)
- `frontend/src/features/rcm/components/ControlTable.tsx` (테이블 패턴 참고)
- `frontend/src/features/remediation/components/DeficiencyTable.tsx` (간단한 CRUD 테이블 패턴 참고)

## API 스펙 (확정, prefix: /api/users)

### User (조회만)
| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | /api/users/?skip=&limit= | - | { items: UserRead[], total, skip, limit } |
| GET | /api/users/{user_id} | - | UserRead |

```ts
interface User {
  id: string
  email: string
  display_name: string
  role: string
  is_active: boolean
  created_at: string
}
```

### UserRole (풀 CRUD)
| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | /api/users/roles/list?skip=&limit= | - | { items: UserRoleRead[], total, skip, limit } |
| POST | /api/users/roles | { user_id, role_name, scope? } | UserRoleRead (201) |
| GET | /api/users/roles/{role_id} | - | UserRoleRead |
| PATCH | /api/users/roles/{role_id} | { role_name?, scope? } | UserRoleRead |
| DELETE | /api/users/roles/{role_id} | - | 204 |

```ts
interface UserRole {
  id: string
  user_id: string
  role_name: string
  scope: string | null
  created_at: string
  updated_at: string
}

interface UserRoleCreatePayload {
  user_id: string
  role_name: string
  scope?: string | null
}

interface UserRoleUpdatePayload {
  role_name?: string
  scope?: string | null
}
```

## 작업 순서

### 1. 브랜치 생성
```powershell
git checkout main
git pull origin main
git checkout -b feature/fe-users-module
```

### 2. types.ts 신규 생성
파일: `frontend/src/features/users/types.ts`

위 User, UserRole, UserRoleCreatePayload, UserRoleUpdatePayload 타입 정의.

### 3. API 파일 보강
파일: `frontend/src/features/users/api/usersApi.ts`
- 기존 fetchUsers 유지
- `fetchUserDetail(id)` → GET /api/users/{user_id} 추가

파일: `frontend/src/features/users/api/userRolesApi.ts` 신규
- fetchUserRoles, createUserRole, fetchUserRoleDetail, updateUserRole, deleteUserRole

### 4. 훅 파일 보강
파일: `frontend/src/features/users/api/useUsers.ts`
- 기존 useUsers 유지
- `useUserDetail(id)` 추가

파일: `frontend/src/features/users/api/useUserRoles.ts` 신규
- useUserRoles, useCreateUserRole, useUpdateUserRole, useDeleteUserRole

### 5. 컴포넌트 — 사용자
파일: `frontend/src/features/users/components/UserTable.tsx`
- 컬럼: display_name, email, role(Badge), is_active(Badge), created_at, 액션(상세보기)
- 행 클릭 → 상세 패널 오픈 (간단한 Sheet, 읽기 전용)

파일: `frontend/src/features/users/components/UserDetailSheet.tsx`
- 읽기 전용 정보 표시
- 해당 user_id로 연결된 역할(UserRole) 목록도 하단에 같이 표시 (useUserRoles 필터링)

### 6. 컴포넌트 — 역할
파일: `frontend/src/features/users/components/UserRoleTable.tsx`
- 컬럼: user_id(또는 연결된 사용자 표시), role_name, scope, 액션(편집·삭제)
- 삭제는 RCM/Remediation 패턴과 동일하게 AlertDialog 확인

파일: `frontend/src/features/users/components/UserRoleFormDialog.tsx`
- 등록/편집 겸용 Dialog
- user_id는 useUsers() 데이터 기반 Select 드롭다운 (display_name (email) 표시)
- role_name, scope 입력

### 7. 페이지 구성
파일: `frontend/src/features/users/pages/UsersPage.tsx`
- 상단 토글: "사용자" / "역할 관리" 두 뷰 전환 (Remediation 패턴과 동일한 버튼 그룹)
- 사용자 뷰: UserTable + UserDetailSheet
- 역할 관리 뷰: UserRoleTable + 등록 버튼 + UserRoleFormDialog

## 완료 조건
- 사용자 목록·상세 조회 실 API 동작 (읽기 전용)
- 역할 목록·등록·편집·삭제 실 API 동작
- 역할 등록 시 사용자 드롭다운 정상 동작
- TypeScript 오류 없음
- 빌드 통과

### 8. 커밋 & push
```powershell
git add frontend/src/features/users/
git commit -m "feat(frontend): 사용자/권한 모듈 — 사용자 조회 + 역할 CRUD"
git push -u origin feature/fe-users-module
```

### 9. 화면 테스트 후 main 머지
화면 테스트 OK 확인 후:
```powershell
git checkout main
git merge --no-ff feature/fe-users-module
git push origin main
```
