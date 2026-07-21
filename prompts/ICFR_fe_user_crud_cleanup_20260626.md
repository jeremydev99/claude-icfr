# BE 4건 FE 연동: 사용자 CRUD·비번 + 임시 우회코드 제거

## 목표
협업자가 완료한 백엔드 4건을 프론트에 연동하고, 그동안 프론트에 임시로 넣었던 우회 코드를 정리한다.

1. 사용자 CRUD (등록·수정·삭제·비밀번호 리셋) UI 추가
2. deficiency 삭제 임시 클라이언트 가드 제거 (백엔드 409 가드로 대체)
3. remediation history changed_by 실명 직접 사용 (UUID→이름 우회 매핑 제거)

## 사전 확인 (읽기만, 수정 금지)
- `frontend/src/features/users/` 전체 (기존 구조)
- `frontend/src/features/users/components/UserTable.tsx`, `UserDetailSheet.tsx`
- `frontend/src/features/users/api/usersApi.ts`, `useUsers.ts`
- `frontend/src/features/remediation/pages/RemediationPage.tsx` (임시 가드 위치)
- `frontend/src/features/remediation/components/DeficiencyTable.tsx` (임시 가드 위치)
- `frontend/src/features/remediation/components/RemediationPlanDetailSheet.tsx` (changed_by 우회 매핑 위치)

## API 스펙 (확정, 신규)

### 사용자 CRUD (관리자 전용)
| Method | Path | Request | Response |
|--------|------|---------|----------|
| POST | /api/users/ | { email, password, display_name, role } | UserRead (201) |
| PATCH | /api/users/{user_id} | { display_name?, role?, is_active? } | UserRead |
| DELETE | /api/users/{user_id} | - | 204 (soft delete) |
| POST | /api/users/{user_id}/reset-password | { new_password } (min 8자) | { detail } |

특이사항:
- PATCH는 email·password 변경 불가 (email은 식별자, 비번은 reset-password 전용)
- DELETE 시 본인 계정·마지막 admin이면 409 → 에러 메시지 표시
- reset-password는 기존 비번 검증 없음 (관리자 강제 재설정)

```ts
interface UserCreatePayload {
  email: string
  password: string
  display_name: string
  role: string   // 기본 "user"
}
interface UserUpdatePayload {
  display_name?: string
  role?: string
  is_active?: boolean
}
interface ResetPasswordPayload {
  new_password: string  // min 8자
}
```

## 작업 순서

### 1. 브랜치 생성
```powershell
git checkout main
git pull origin main
git checkout -b feature/fe-user-crud-cleanup
```

### 2. usersApi.ts 보강
파일: `frontend/src/features/users/api/usersApi.ts`
- createUser, updateUser, deleteUser, resetUserPassword 추가

### 3. useUsers.ts 보강
파일: `frontend/src/features/users/api/useUsers.ts`
- useCreateUser, useUpdateUser, useDeleteUser, useResetPassword (각 mutation, 성공 시 users 쿼리 invalidate)
- 409 등 에러 메시지를 사용자에게 그대로 노출할 수 있게 에러 처리

### 4. UserFormDialog.tsx 신규 생성
파일: `frontend/src/features/users/components/UserFormDialog.tsx`
- 등록 모드: email, password, display_name, role 입력
- 편집 모드: display_name, role, is_active만 입력 (email·password 비활성/숨김)
- role은 기존 ROLE_NAME_OPTIONS 상수 재사용 (있으면)

### 5. ResetPasswordDialog.tsx 신규 생성
파일: `frontend/src/features/users/components/ResetPasswordDialog.tsx`
- new_password 입력 (min 8자 클라이언트 검증)
- 저장 시 useResetPassword 호출

### 6. UserTable.tsx 수정
파일: `frontend/src/features/users/components/UserTable.tsx`
- 액션 컬럼에 편집·삭제·비번리셋 버튼 추가
- 삭제는 AlertDialog 확인 (409 에러 시 메시지 표시)

### 7. UsersPage.tsx 수정
파일: `frontend/src/features/users/pages/UsersPage.tsx`
- 사용자 뷰에 "+ 사용자 등록" 버튼 추가 → UserFormDialog (등록 모드)
- 편집·비번리셋·삭제 핸들러 연결

### 8. deficiency 임시 가드 제거
파일: `DeficiencyTable.tsx` 또는 `RemediationPage.tsx` 중 임시 가드가 있는 곳
- 삭제 전 "연결된 개선계획 있는지 클라이언트 필터링해서 막던" 임시 로직 제거
- 대신 삭제 mutation에서 백엔드 409 응답이 오면 그 에러 메시지를 toast로 표시하도록 변경

### 9. remediation history 실명 직접 사용
파일: `frontend/src/features/remediation/components/RemediationPlanDetailSheet.tsx`
- 상태 이력 타임라인에서 changed_by_id를 useUsers로 매핑하던 우회 코드 제거
- 백엔드가 주는 `changed_by.display_name`을 직접 사용
- types.ts의 RemediationStatusHistory에 `changed_by: { id: string; display_name: string }` 필드 추가
- 미비점·담당자 표시(미비점=code, owner=display_name)는 changed_by와 무관하므로 그대로 유지

## 완료 조건
- 사용자 등록·수정·삭제·비번리셋 실 API 동작
- 본인/마지막 admin 삭제 시 409 메시지 표시
- deficiency 삭제 시 연결된 개선계획 있으면 백엔드 409 메시지 표시 (클라이언트 임시 가드 제거됨)
- remediation 상태 이력에 실명 정상 표시 (우회 매핑 제거됨)
- TypeScript 오류 없음
- 빌드 통과

### 10. 커밋 & push
```powershell
git add frontend/src/features/users/ frontend/src/features/remediation/
git commit -m "feat(frontend): 사용자 CRUD·비번 FE 연동 + deficiency 가드·history 실명 우회코드 제거"
git push -u origin feature/fe-user-crud-cleanup
```

### 11. 화면 테스트 후 main 머지
화면 테스트 OK 확인 후:
```powershell
git checkout main
git merge --no-ff feature/fe-user-crud-cleanup
git push origin main
```
