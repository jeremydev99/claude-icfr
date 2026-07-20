# Evidence 모듈: 증빙 파일 관리 화면 (신규)

## 목표
증빙 파일 업로드·목록·다운로드·삭제 화면을 신규 구축한다.
rcm/test 모듈과 동일한 폴더 구조·패턴을 따른다.

## ⚠️ 중요 — 다운로드 방식 (협업자 문서와 실제 구현 차이)
협업자 공유 문서는 `/files/{id}/download`가 presigned URL(`{url, expires_in}`)을 반환한다고 했으나,
실제 OpenAPI 스펙 확인 결과 **StreamingResponse(파일 바이너리 직접 반환)** 이다.
→ 프론트에서는 `responseType: 'blob'`으로 받아 `URL.createObjectURL(blob)` 후 다운로드 트리거하는 방식으로 구현한다.

## 사전 확인 (읽기만, 수정 금지)
- `frontend/src/features/rcm/api/` 폴더 전체 (구조 패턴 참고)
- `frontend/src/features/rcm/types.ts` (패턴 참고)
- `frontend/src/features/evidence/pages/EvidencePage.tsx` (현재 빈 페이지)
- axios 인스턴스 위치 확인 (`frontend/src/lib/` 또는 `frontend/src/shared/` 등 공통 api client)

## API 스펙 (확정)

### Files
| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | /api/evidence/files?skip=&limit= | - | EvidenceFileRead[] |
| POST | /api/evidence/files | multipart/form-data, field `file` | EvidenceFileRead (201) |
| GET | /api/evidence/files/{file_id} | - | EvidenceFileRead |
| PATCH | /api/evidence/files/{file_id} | { filename? } | EvidenceFileRead |
| DELETE | /api/evidence/files/{file_id} | - | 204 |
| GET | /api/evidence/files/{file_id}/download | - | **blob** (스트림) |

### Links
| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | /api/evidence/links?file_id=&skip=&limit= | - | EvidenceLinkRead[] |
| POST | /api/evidence/links | { file_id, linked_entity_type, linked_entity_id } | EvidenceLinkRead |
| DELETE | /api/evidence/links/{link_id} | - | 204 |

### EvidenceFileRead
```ts
interface EvidenceFile {
  id: string
  filename: string
  mime_type: string
  size_bytes: number
  minio_key: string | null
  sha256: string | null
  uploaded_by_id: string
  created_at: string
  updated_at: string
}
```

### 업로드 제약 (클라이언트 사전 검증)
- 최대 50MB — 초과 시 업로드 버튼 클릭 전에 차단, 안내 메시지 표시
- 허용 형식: PDF, PNG, JPEG, XLSX, DOCX, HWP
- 백엔드 413(용량초과)/415(형식불가) 에러도 별도로 캐치해 사용자에게 명확히 표시 (클라이언트 검증을 우회하는 경우 대비)

## 작업 순서

### 1. 브랜치 생성
```powershell
git checkout main
git pull origin main
git checkout -b feature/fe-evidence-module
```

### 2. types.ts 신규 생성
파일: `frontend/src/features/evidence/types.ts`

위 EvidenceFile 인터페이스 + EvidenceLink 인터페이스 + 목록 응답 타입 정의.
허용 mime_type 상수 배열, MAX_FILE_SIZE_BYTES 상수도 함께 정의.

### 3. evidenceApi.ts 신규 생성
파일: `frontend/src/features/evidence/api/evidenceApi.ts`

rcm api 파일과 동일한 axios 인스턴스 사용 패턴으로:
- `fetchEvidenceFiles(params)` → GET /api/evidence/files
- `uploadEvidenceFile(file: File)` → POST /api/evidence/files (FormData, field명 `file`)
- `downloadEvidenceFile(id)` → GET /api/evidence/files/{id}/download, `responseType: 'blob'`로 받아 Blob 반환
- `deleteEvidenceFile(id)` → DELETE /api/evidence/files/{id}
- `fetchEvidenceLinks(fileId)` → GET /api/evidence/links?file_id=

### 4. useEvidence.ts 신규 생성
파일: `frontend/src/features/evidence/api/useEvidence.ts`

- `useEvidenceFiles(params)` — useQuery
- `useUploadEvidenceFile()` — useMutation, 성공 시 목록 invalidate. 413/415 에러를 구분해 에러 메시지 매핑
- `useDeleteEvidenceFile()` — useMutation, 성공 시 목록 invalidate
- 다운로드는 mutation 불필요, 컴포넌트에서 직접 `downloadEvidenceFile` 호출 후 blob → 가짜 `<a>` 태그로 다운로드 트리거

### 5. EvidenceUploadDialog.tsx 신규 생성
파일: `frontend/src/features/evidence/components/EvidenceUploadDialog.tsx`

- 파일 선택 input
- 선택 즉시 클라이언트 검증: 크기(50MB), 확장자/mime_type
- 검증 실패 시 즉시 에러 메시지, 업로드 버튼 비활성화
- 업로드 버튼 클릭 → `useUploadEvidenceFile` 호출
- 413/415 백엔드 에러 응답 시 명확한 한국어 메시지 표시
- 업로드 중 로딩 스피너 표시

### 6. EvidenceTable.tsx 신규 생성
파일: `frontend/src/features/evidence/components/EvidenceTable.tsx`

테이블 컬럼: 파일명, 크기(MB 변환), 업로더, 업로드일, 액션(다운로드·삭제)

- 다운로드 버튼 클릭 → blob fetch → 자동 다운로드 트리거
- 삭제 버튼 클릭 → AlertDialog 확인 (RCM 패턴 동일) → `useDeleteEvidenceFile` 호출

### 7. EvidencePage.tsx 수정
파일: `frontend/src/features/evidence/pages/EvidencePage.tsx`

- "파일 업로드" 버튼 → EvidenceUploadDialog 오픈
- EvidenceTable 렌더링 (useEvidenceFiles 데이터 연결)
- 빈 목록일 때 안내 문구

## 완료 조건
- 파일 업로드 성공 (실 API, MinIO 실연동 확인)
- 50MB 초과 또는 허용 외 형식 선택 시 클라이언트에서 즉시 차단
- 백엔드 413/415 에러 발생 시에도 명확한 메시지 표시
- 목록에 업로드된 파일 표시 (실 API)
- 다운로드 클릭 시 실제 파일 다운로드 (blob 처리 확인)
- 삭제 확인 다이얼로그 → 삭제 → 목록 갱신
- TypeScript 오류 없음
- 빌드 통과

### 8. 커밋 & push
```powershell
git add frontend/src/features/evidence/
git commit -m "feat(frontend): Evidence 모듈 — 증빙 파일 업로드·목록·다운로드·삭제"
git push -u origin feature/fe-evidence-module
```

### 9. 화면 테스트 후 main 머지
화면 테스트 OK 확인 후:
```powershell
git checkout main
git merge --no-ff feature/fe-evidence-module
git push origin main
```
