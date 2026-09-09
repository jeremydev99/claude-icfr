# 증빙 관리 API 계약

> **스냅샷 문서 — 기준 커밋 `4b1d912` / 2026-09-09 시점. API 변경 시 갱신 필요.**
>
> 자동 생성 문서(FastAPI `/docs`)가 API 스펙의 단일 진실 공급원이다(ADR-0017 §19).
> 이 문서는 그것이 드러내지 못하는 것 — **권한 판정 규칙, 실제 에러 문구, 삭제 의미론** —
> 을 코드에서 읽어 정리한 것이다. 스펙을 대체하지 않는다.
>
> 근거 파일: `backend/app/api/evidence.py`, `backend/app/schemas/evidence.py`,
> `backend/app/models/evidence.py`, `backend/app/minio_client.py`,
> `backend/app/models/role_assignment.py`
>
> 근거 ADR: ADR-0032 §2.7·§2.9(증빙·보존기간), ADR-0031(역할·권한).
> 형식은 `rcm-hierarchy-contract.md`·`org-contract.md` 와 같다.

**모든 응답 예시는 실제 왕복에서 얻은 원문이다.** 추정으로 적은 값은 없다.

**증빙은 감사 증거물이다.** 다른 데이터와 다르게 다뤄야 한다 — 지워지면 안 되고,
누가 언제 올렸다가 지웠는지가 감사에서 실제로 묻는 질문이며, 보존기간이 법정 최소
5년이다. 아래 계약의 여러 지점이 그 성질에서 나온다.

---

## 1. 엔드포인트

| 동작 | 경로 | 삭제분 포함 |
|---|---|---|
| 업로드 | `POST /api/evidence/files` → 201 | — |
| 목록 | `GET /api/evidence/files` | **제외** |
| 상세 | `GET /api/evidence/files/{file_id}` | **제외**(404) |
| **이력** | **`GET /api/evidence/files/{file_id}/history`** | **포함** |
| 다운로드 | `GET /api/evidence/files/{file_id}/download` | — |
| 삭제 | `DELETE /api/evidence/files/{file_id}` → 204 | — |

목록 쿼리 파라미터: `skip`·`limit`. 봉투는 기존 규약과 동일 —
`{"items": [...], "total": int, "skip": int, "limit": int}`.

`/api/evidence/links` 계열(`EvidenceLink`)이 남아 있으나 **신규 증빙은 쓰지 않는다.**
통제×회차 직접 부착으로 바뀌었기 때문이다(§6). 용도 정리는 별건(13.9-30).

## 2. 요청/응답 스키마

### 2.1 업로드 — `multipart/form-data`

**파트 3개가 모두 필수다.**

| 파트 | 종류 | 타입 | 필수 | 비고 |
|---|---|---|---|---|
| `cycle_id` | form field | UUID | ✅ | 평가 회차 |
| `control_id` | form field | UUID | ✅ | 통제 **정체성 id** |
| `file` | file | — | ✅ | 원본 파일 |

`control_id` 는 RCM 목록에서 받은 `id` 를 그대로 넣으면 된다 — baseline 유래인지
회사 add 인지 구분할 필요가 없다(정체성 id 규칙, ADR-0027).

**허용 MIME**(`ALLOWED_MIME`) — 그 외는 `415`.

```
application/pdf
image/png, image/jpeg
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet   (xlsx)
application/vnd.openxmlformats-officedocument.wordprocessingml.document  (docx)
application/haansofthwp, application/x-hwp   (hwp)
```

크기 상한 초과는 `413`. 상한은 정책값이다(§5).

**응답** (`EvidenceFileRead`)

```json
{
  "filename": "2026년 1분기 대사표.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 15,
  "minio_key": "d0000000-0000-0000-0000-000000000001/cycles/01a083f3-0a78-.../controls/01a083f3-0a76-.../01a083f3-45a8-...",
  "sha256": "d0975b81b2e708ccc0710aaa2011269e27ea6567fedca01cbae6b85ec20d9984",
  "id": "01a083f3-45a8-7eb3-8ebb-2f8ed51d74bc",
  "cycle_id": "01a083f3-0a78-7441-a2f5-8171ef12730e",
  "control_id": "01a083f3-0a76-7261-babd-491238593d62",
  "uploaded_by_id": "01a083f3-0b42-7e41-a556-8a79a9326450",
  "created_at": "2026-09-09T02:15:53",
  "updated_at": "2026-09-09T02:15:53"
}
```

목록·상세도 같은 형태다.

**저장 경로에 파일명이 들어가지 않는다.** 내부 식별자(`id`)로 저장하고 원본명은
`filename` 에 둔다 — 한글 파일명·중복 이름·경로 조작 시도가 한 번에 해결된다.
`../../탈출시도.pdf` 를 올려도 경로에는 `..` 이 남지 않고 `filename` 에만 원본이 남는다.

### 2.2 다운로드

```
HTTP 200
content-type: application/pdf
content-disposition: attachment; filename*=UTF-8''2026%EB%85%84%201%EB%B6%84%EA%B8%B0%20...
```

**원본 파일명이 `Content-Disposition` 으로 내려온다**(RFC 5987 인코딩). 사용자는
내부 식별자로 저장된다는 사실을 느끼지 않는다.

### 2.3 이력 — `EvidenceFileHistory`

```json
{
  "id": "01a083f3-45a8-7eb3-8ebb-2f8ed51d74bc",
  "filename": "2026년 1분기 대사표.pdf",
  "is_deleted": true,
  "uploaded_by_id": "01a083f3-0b42-...",
  "uploaded_by_name": "김세영",
  "uploaded_at": "2026-09-09T02:15:53",
  "deleted_by_id": "01a083f3-09d1-...",
  "deleted_by_name": "System Administrator",
  "deleted_at": "2026-09-09T02:15:53.721152",
  "delete_reason": "오등록 정정",
  "minio_key": "d0000000-.../cycles/.../controls/.../01a083f3-45a8-..."
}
```

삭제 전에는 `is_deleted: false`, `deleted_*` 3필드와 `delete_reason` 이 모두 `null` 이다.

## 3. 권한 — 403 문구 3종

**권한 판정은 두 축이다** — 회차 상태 × 통제 단위 역할(ADR-0032 §2.5).

| 회차 상태 | 통제책임자 | `icfr_manager` |
|---|---|---|
| 진행 중(`open`) | 가능 (정책 토글로 차단 가능) | 가능 |
| 마감(`closed`)·최종승인(`approved`) | **불가** | 가능 |

셋 다 `403` 이므로 **`detail` 문구로 구분해야 한다.** 상황과 사용자 조치가 다르다.

### ① 마감된 회차

```json
{"detail": "마감된 회차의 증빙은 내부회계관리자만 편집할 수 있습니다 (상태: closed)"}
```

**상황** — 회차가 마감·최종승인되어 통제책임자가 더 이상 편집할 수 없다.
**사용자 조치** — 정정이 필요하면 내부회계관리자에게 요청한다. 관리자가 편집하면
그 사실이 업로더·삭제자 계정으로 이력에 남는다.
**구분 문자열** — `"내부회계관리자만"`. 상태값이 문구에 포함된다(`closed`/`approved`).

### ② 정책 토글이 꺼져 있음

```json
{"detail": "증빙 편집이 비활성화되어 있습니다 (정책: evidence_edit_enabled)"}
```

**상황** — 회차는 진행 중이나 회사 정책이 통제책임자의 증빙 편집을 막고 있다.
**사용자 조치** — 정책을 켜려면 내부회계관리자가 `PUT /api/org/policies` 로 바꾼다.
**구분 문자열** — `"비활성화"`.

### ③ 이 통제의 담당자가 아님

```json
{"detail": "이 통제의 통제책임자만 증빙을 편집할 수 있습니다"}
```

**상황** — 회차도 진행 중이고 정책도 켜져 있으나, **이 통제**의 통제책임자가 아니다.
판정은 통제 단위다 — 통제 A 의 책임자가 통제 B 의 증빙을 올릴 수 없다(ADR-0031 §2.2).
**사용자 조치** — 배정을 확인한다. 화면에서 이 통제의 책임자를 보여주면
`GET /api/org/controls/{control_id}/roles` 로 누구인지 알 수 있다.
**구분 문자열** — `"통제책임자만"`.

### `external_auditor`

위 셋보다 앞서 걸린다(`require_write`).

```json
{"detail": "외부감사인은 조회만 가능합니다"}
```

업로드·삭제 모두 거부되고 조회는 `200` 이다. FE 는 `/me` 의 `can_write` 로 미리 알 수
있다(`org-contract.md` §5.0).

## 4. 삭제와 이력

### 4.1 삭제해도 파일이 남는다

**DB 레코드도, MinIO 파일도 지우지 않는다**(ADR-0032 §2.4). 삭제 표시만 하고
조회에서 제외한다.

레코드만 남기고 파일을 지우면 "그때 지운 게 뭐였나"에 답할 수 없다. 보존기간이
5년 이상이므로 파일도 그 기간을 따른다(§2.9).

> **이것은 2026-09-04 에 고친 결함이다.** 그 전에는 삭제 시 MinIO 객체를 실제로
> 지웠고, 운영 실측에서 `is_deleted=true` 인 2건의 객체가 이미 사라져 있었다
> (테스트 파일이라 손실은 없었다). 커밋 `5074473`.

### 4.2 사유 파라미터

```
DELETE /api/evidence/files/{file_id}?reason=오등록%20정정   → 204
```

`reason` 은 **선택**이다. 넣으면 이력의 `delete_reason` 에 남는다.

### 4.3 조회 범위가 엔드포인트마다 다르다

| 엔드포인트 | 삭제된 증빙 |
|---|---|
| `GET /files` (목록) | 나오지 않음 |
| `GET /files/{id}` (상세) | **404** |
| `GET /files/{id}/history` | **나옴** (`is_deleted: true`) |

**이력 엔드포인트는 `is_deleted` 를 필터하지 않는다 — 삭제된 것을 보는 것이 목적이다.**
"누가 언제 올렸다가 지웠는지"가 감사에서 실제로 묻는 질문이고, 그 답이 여기 있다.

`minio_key` 를 이력 응답에도 실어, 삭제 후에도 파일 소재를 확인할 수 있게 했다.

## 5. 정책 3종

전부 `PUT /api/org/policies` 로 설정하며 **`icfr_manager` 전용**이다(`org-contract.md` §5.1).
미설정이면 아래 기본값이 적용된다.

| `policy_key` | 기본값 | 의미 |
|---|---|---|
| `evidence_edit_enabled` | **허용**(미설정 = true) | 진행 중 회차에서 통제책임자의 편집 허용 여부 |
| `evidence_max_bytes` | **52428800** (50MB) | 업로드 크기 상한 |
| `evidence_retention_years` | **0** (영구) | 보존기간(년). **최소 5년 강제** |

```json
PUT /api/org/policies
{"policy_key": "evidence_retention_years", "policy_value": "5"}
→ 200 {"id": "...", "policy_key": "evidence_retention_years", "policy_value": "5", "updated_at": "..."}
```

### 보존기간은 최소 5년을 시스템이 강제한다

근거: 내부회계관리제도 업무지침 — 회계정보 및 관련 문서 5년 보관(ADR-0032 §2.9).

```json
{"policy_key": "evidence_retention_years", "policy_value": "3"}
→ 409 {"detail": "보존기간은 최소 5년입니다 (내부회계관리제도 업무지침). 0 은 영구 보존입니다"}

{"policy_key": "evidence_retention_years", "policy_value": "영구"}
→ 422 {"detail": "보존기간은 숫자여야 합니다 (0 = 영구 보존)"}
```

`0` 은 영구 보존이며 허용된다. **이번에는 설정값만 저장한다** — 실제 만료 삭제 처리는
아카이브 설계와 함께 다룬다(ADR-0032 §5).

### 크기 상한이 정책인 이유

ADR-0032 §2.7 은 "크기 상한을 두지 않는다"고 정했으나, **업로드가 `file.read()` 로
전체를 메모리에 적재하는 현재 구조에서 상한을 없애면 대용량 파일이 백엔드 메모리를
소진한다.** 스트리밍 전환이 선행되어야 한다(13.9-31). 그때까지 상한을 유지하되
코드에 하드코딩하지 않고 정책으로 두어, 전환 후에는 값만 올리면 되게 했다.

잘못된 정책값(숫자 아님, 0 이하)에는 예외를 던지지 않고 기본값으로 떨어뜨린다 —
설정 하나가 깨졌다고 업로드 전체가 막히면 안 된다.

## 6. 기존 구조에서 바뀐 점 — 재배선에 직접 걸리는 부분

**① 증빙이 통제 → 통제 × 회차로 바뀌었다.**
같은 통제라도 회차가 다르면 다른 증빙이다. 화면도 "이 통제의 증빙"이 아니라
"이 통제 × 이 회차의 증빙"을 보여야 한다. 응답에 `cycle_id`·`control_id` 가 함께 온다.

**② 업로드에 `cycle_id`·`control_id` 가 필수다.**

```
누락        → 422 {"detail": [{"type": "missing", "loc": ["body", "cycle_id"], ...}]}
없는 회차   → 404 {"detail": "AssessmentCycle not found"}
```

컬럼 자체는 nullable 이지만 **핸들러가 막는다.** 기존 4건(시드·테스트 잔재) 때문에
NOT NULL 로 만들 수 없었고, 그 데이터를 조작하지 않기로 확정했다(13.9-29).
"레거시는 NULL 허용, 신규는 만들지 않는다"를 애플리케이션이 담당한다.

**③ `minio_key` 는 표시용이 아니다.** 다운로드는 항상 `/download` 를 쓴다.
경로를 파라미터로 받아 파일을 읽는 엔드포인트는 **없다** — 경로가 판정 근거가 되면
테넌트 격리가 경로 조작에 노출된다. 서버는 DB 레코드를 조회하고(ADR-0025 자동 격리)
그 레코드의 `minio_key` 로 읽는다.

**④ 기존 `evidence_files` 4건은 `cycle_id` NULL 레거시로 남는다.**
시드·테스트 잔재이며 정리하지 않았다(실데이터 조작을 하지 않는다). 목록에 섞여
나오므로 화면에서 회차별로 필터하면 자연히 빠진다. 경로에 `tenant_id` 가 없으나
조회가 DB 레코드의 `minio_key` 를 쓰므로 신규 규칙과 충돌하지 않는다(13.9-29).

**⑤ 삭제 시 파일이 남는다.** 이전 동작(파일 삭제)에 기대어 만든 화면이 있다면
"완전 삭제" 같은 표현은 사실과 다르다.

## 7. 미검증 항목

**§5-6(삭제 후 MinIO 파일 잔존)은 대역 검증만 됐다.**

테스트 환경에 MinIO 가 없어 저장소 호출을 메모리 대역으로 바꿔
**"삭제 경로가 저장소 삭제를 호출하지 않는다"** 까지만 확인했다
(`tests/test_evidence_retention.py`). `test_evidence_module_has_no_storage_delete_path`
가 `remove_object_safe` import 부재까지 잠근다.

**운영 실증은 화면 재배선 후에 한다** — 실제 업로드 → 삭제 → 객체 잔존을 확인해야
§2.4 가 실증된다(13.9-33).

```bash
docker exec icfr-minio mc ls -r local/icfr-evidence
```

그 밖의 §5 검증 14개는 로컬에서 통과했다(`ruff` All checks passed,
`pytest` 2회 반복 동일 — 241 passed · 1 skipped · 1 xfailed · 0 failed).
