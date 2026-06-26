# Regina 공유 + 다음 작업 지침 — Evidence 모듈

> 이 문서를 그대로 읽고, Evidence 프론트엔드 작업에 사용하세요. (Regina 본인 + 협업 AI용)

## 1. 백엔드 완료 공유 (main 머지 완료, `git pull` 받으세요)

- **RCM owner_name 정렬·검색** — `sort_by=owner_name` 정렬, 통합검색 `q`에 담당자명 포함
- **작업5 Evidence MinIO 실연동 완료** — 파일 업로드·다운로드·삭제가 실제 MinIO 스토리지에 연결됨. 이제 프론트에서 증빙 파일 화면을 붙일 수 있습니다.

먼저:
```
git pull
```

## 2. Evidence API 스펙

> **정확한 경로 prefix·요청/응답 형태는 백엔드 Swagger(`/docs`) 또는 `/openapi.json`에서 최종 확인하세요.** 아래는 동작 요약입니다.

### 파일 (EvidenceFile)
- `GET /files?skip=&limit=` — 파일 목록
- `POST /files` — **multipart/form-data 업로드**. 폼 필드명 `file` (단일 파일). 성공 시 201 + 파일 메타 반환
- `GET /files/{id}` — 파일 상세
- `PATCH /files/{id}` — filename 수정
- `DELETE /files/{id}` — 삭제 (DB + MinIO object 동반 제거, 204)
- `GET /files/{id}/download` — **presigned 다운로드 URL 발급**. 응답 `{ "url": "...", "expires_in": 900 }`. 이 url로 이동/창열기 하면 실제 파일 다운로드 (15분 유효)

**파일 메타 응답 필드**: `id`, `filename`, `mime_type`, `size_bytes`, `minio_key`, `sha256`, `uploaded_by_id`, `created_at`, `updated_at`

**업로드 제약 (UI에서 사전 검증 권장)**:
- 최대 크기 **50MB** — 초과 시 백엔드 413
- 허용 형식: PDF, PNG, JPEG, XLSX, DOCX, HWP — 그 외 415
- 위 두 에러는 사용자에게 명확한 메시지로 표시

### 링크 (EvidenceLink — 증빙↔엔티티 연결)
- `GET /links?file_id=` — 특정 파일의 연결 목록
- `POST /links` — body `{ file_id, linked_entity_type, linked_entity_id }`로 통제/테스트 등과 연결
- `DELETE /links/{id}` — 연결 해제 (204)

## 3. 다음 작업 지침 (우선순위 순)

### A. Evidence 프론트 화면 (신규)
증빙 파일 관리 UI:
1. **업로드** — 파일 선택 + multipart `POST /files`. 업로드 전 50MB·허용형식 클라이언트 검증, 413/415 에러 핸들링
2. **목록** — `GET /files`로 파일 리스트 (filename, size, 업로더, 일시 표시)
3. **다운로드** — 각 항목에서 `GET /files/{id}/download` 호출 → 받은 `url`로 다운로드
4. **삭제** — `DELETE /files/{id}` + 목록 갱신
5. (선택) **연결 표시** — 파일이 어떤 통제/테스트에 링크됐는지 `/links`로 노출

업로드 진행률·로딩 상태, sha256 표시(무결성 확인용)는 여유 시.

### B. RAWC 화면
백엔드 RAWC 평가 모델은 작업3에서 이미 구현 완료. 프론트에서 RAWC 평가 입력·표시 붙이면 됩니다. 별도 진행.

## 4. 협업 룰 (변동 없음)
- Regina: feature 브랜치 → PR → 머지 플로우 유지
- 백엔드가 한 모듈 선행, 프론트가 인터리브
- Mock 금지, 실 API 연결 (이전 합의 유지)

---

## 끝. Regina AI 실행용 한 줄

```
위 Evidence API 스펙대로 증빙 파일 관리 화면을 만들어줘.
업로드(multipart, file 필드)·목록·다운로드(presigned url)·삭제 + 50MB·허용형식 검증과 413/415 에러 처리 포함.
정확한 경로와 요청/응답은 백엔드 /docs(openapi.json)에서 확인하고 진행해줘.
```
