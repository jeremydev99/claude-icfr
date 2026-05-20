# ICFR_frontend_1_20260520.md — Phase 0 작업4: 프론트엔드 골조

## 메타 정보

| 항목 | 값 |
|---|---|
| 작업 일시 | 2026-05-20 |
| 작업 유형 | 프론트엔드 골조 (Vite + React + TS + shadcn/ui + Tailwind + 인증) |
| 담당 | Regina |
| Phase | Phase 0 — 작업 단위 4 |
| 결정 출처 | claude.ai 사전 승인 (2026-05-20) |
| 예상 작업 시간 | 1~1.5시간 |
| 영향 파일 | `frontend/` 폴더 전체 신규 생성 (약 25~30개 파일) |
| 커밋 메시지 제안 | `feat(frontend): Vite + React + TS + shadcn/ui + 인증 화면 골조 (Phase 0 작업4)` |

---

## 사전 승인된 결정사항

| 항목 | 결정 |
|---|---|
| 폴더 구조 | `features/` 방식 (모듈별 분리, 작업5 이후 11개 모듈 자연 확장) |
| 토큰 저장 | `localStorage` (Phase 0 MVP, Phase 2 SSO 전환 시 개선) |
| 로그인 후 이동 | `/dashboard` (빈 placeholder 페이지) |
| Dockerfile | 포함 (Nginx 기반, docker-compose.yml 연동) |

---

## 작업 지시

`ClaudeICFR.md` (섹션 3 기술스택, 섹션 7 Git 전략, 섹션 10 ADR-0011·0017·0018, 섹션 19 API 명세 표준),
`CLAUDE.md` (섹션 9 명세 동기화 체크)를 먼저 확인하고, 아래 프론트엔드 골조를 순서대로 생성해줘.

**작업 시작 전 필수 체크 (CLAUDE.md 섹션 9)**:
1. `git fetch origin` 으로 원격 최신 상태 가져오기
2. `frontend/` 폴더가 비어 있는지 확인
3. `backend/app/api/auth.py` 최신 엔드포인트 확인

**핵심 결정사항** (재확인):
- 백엔드 API 베이스: `http://localhost:8000` (개발), `VITE_API_BASE_URL` env var 사용
- 인증 흐름: `POST /api/auth/login` (OAuth2PasswordRequestForm) → access_token + refresh_token → localStorage 저장
- Access Token 만료(401) 시 `POST /api/auth/refresh`로 자동 재발급 (axios 인터셉터)
- 인증된 요청 헤더: `Authorization: Bearer <access_token>`
- `GET /api/auth/me` 로 로그인 사용자 정보 조회
- 브랜치: `feature/fe-phase0-skeleton` 생성 후 작업 (ADR-0017 명명 규칙)

---

## 1. frontend/ 폴더 구조

```
frontend/
├── Dockerfile
├── nginx.conf
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── .env.example
├── .eslintrc.cjs
├── .prettierrc
├── index.html
├── components.json           ← shadcn/ui 설정
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── vite-env.d.ts
    ├── features/
    │   └── auth/
    │       ├── components/
    │       │   └── LoginForm.tsx
    │       ├── hooks/
    │       │   └── useAuth.ts
    │       └── store.ts          ← Zustand auth store
    ├── components/
    │   └── ui/                   ← shadcn/ui 컴포넌트 위치
    ├── lib/
    │   ├── axios.ts              ← axios 인스턴스 + 인터셉터
    │   └── queryClient.ts        ← TanStack Query client
    ├── layouts/
    │   ├── AppLayout.tsx         ← 사이드바 + 상단바 쉘
    │   └── AuthLayout.tsx        ← 로그인 페이지 래퍼
    ├── routes/
    │   ├── index.tsx             ← React Router v6 라우트 정의
    │   └── PrivateRoute.tsx      ← 인증 보호 라우트
    └── pages/
        ├── LoginPage.tsx
        └── DashboardPage.tsx     ← 빈 placeholder
```

---

## 2. package.json 주요 의존성

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0",
    "@tanstack/react-query": "^5.56.0",
    "axios": "^1.7.7",
    "zustand": "^4.5.5",
    "react-hook-form": "^7.53.0",
    "zod": "^3.23.8",
    "@hookform/resolvers": "^3.9.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.2",
    "class-variance-authority": "^0.7.0",
    "lucide-react": "^0.446.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.5.3",
    "vite": "^5.4.1",
    "tailwindcss": "^3.4.11",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.45",
    "@tailwindcss/forms": "^0.5.9",
    "eslint": "^9.9.0",
    "prettier": "^3.3.3",
    "vitest": "^2.1.0",
    "@testing-library/react": "^16.0.1"
  }
}
```

---

## 3. 핵심 파일 구현 내용

### 3.1 .env.example

```
VITE_API_BASE_URL=http://localhost:8000
```

### 3.2 lib/axios.ts

- `axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL })`
- **요청 인터셉터**: localStorage에서 `access_token` 읽어 `Authorization: Bearer` 헤더 자동 주입
- **응답 인터셉터 (401 처리)**:
  1. `POST /api/auth/refresh` 호출 (body: `{ "refresh_token": localStorage의 refresh_token }`)
  2. 성공 시 새 access_token을 localStorage에 저장하고 원래 요청 재시도
  3. 실패 시 localStorage 전체 삭제 → `/login` 리다이렉트
- refresh 요청 자체는 인터셉터 무한루프 방지를 위해 제외

### 3.3 features/auth/store.ts (Zustand)

```typescript
interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: UserProfile | null   // { id, email, name, role }
  setTokens: (access: string, refresh: string) => void
  setUser: (user: UserProfile) => void
  logout: () => void
}
```

- 초기화 시 localStorage에서 토큰 복원 (`persist` 미들웨어 또는 수동 hydrate)
- `logout()`: localStorage 삭제 + state 초기화

### 3.4 features/auth/hooks/useAuth.ts

TanStack Query 활용:
- `useLogin()`: `POST /api/auth/login` mutation
  - Content-Type: `application/x-www-form-urlencoded` (`username`, `password` 필드)
  - 성공 시 → store에 토큰 저장 → `GET /api/auth/me` 조회 → `/dashboard` 이동
- `useMe()`: `GET /api/auth/me` query (accessToken 있을 때만 enabled)
- `useLogout()`: `POST /api/auth/logout` mutation → store.logout() → `/login` 이동

### 3.5 features/auth/components/LoginForm.tsx

- React Hook Form + Zod 검증
  - `email` 필드: required, email 형식
  - `password` 필드: required, 최소 6자
- 에러 표시: 필드 하단 인라인 텍스트
- 로딩 상태: 버튼 비활성화 + "로그인 중..." 텍스트
- 백엔드 에러 (401): "이메일 또는 비밀번호가 올바르지 않습니다" 표시
- shadcn/ui 컴포넌트: `Button`, `Input`, `Label`, `Card`

### 3.6 routes/PrivateRoute.tsx

- Zustand store에서 `accessToken` 확인
- 없으면 `<Navigate to="/login" replace />`

### 3.7 routes/index.tsx

```
/login       → <AuthLayout><LoginPage /></AuthLayout>
/            → <Navigate to="/dashboard" />
/dashboard   → <PrivateRoute><AppLayout><DashboardPage /></AppLayout></PrivateRoute>
```

### 3.8 layouts/AppLayout.tsx

- 좌측 사이드바 (너비 240px):
  - 상단: 서비스명 "ICFR" 텍스트 로고
  - 메뉴 7개 (작업5에서 채울 자리, 지금은 빈 링크): Dashboard, 일정관리, RCM, Scoping, EUC, IUC, 개선계획
  - 하단: 로그인 사용자 이름 + 역할 + 로그아웃 버튼
- 우측 콘텐츠 영역: `<Outlet />`

### 3.9 pages/DashboardPage.tsx

```tsx
export default function DashboardPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold">대시보드</h1>
      <p className="mt-2 text-muted-foreground">Phase 1에서 구현 예정입니다.</p>
    </div>
  )
}
```

### 3.10 lib/queryClient.ts

```typescript
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 1000 * 60 * 5 },
  },
})
```

---

## 4. Dockerfile + nginx.conf

### Dockerfile (멀티스테이지)

```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### nginx.conf

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000;
    }
}
```

---

## 5. shadcn/ui 초기 설치

작업4에서 필요한 최소 컴포넌트만 설치. `frontend/` 폴더에서 실행:

```bash
# 1) 의존성 먼저 설치
npm install

# 2) shadcn/ui 초기화 (New York 스타일, CSS variables 사용, Tailwind 자동 설정)
npx shadcn@latest init

# 3) 인증 화면에 필요한 컴포넌트만 추가
npx shadcn@latest add button input label card form
```

> `npx shadcn@latest init` 프롬프트에서:
> - Style: **New York**
> - Base color: **Slate**
> - CSS variables: **Yes**

---

## 6. vite.config.ts 주요 설정

```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
```

---

## 7. 완료 후 필수 작업

### 7.1 ClaudeICFR.md 업데이트
- 섹션 12.1: Phase 0 작업4 상태 → ✅ + 완료일 기입
- 섹션 12.2: 11개 모듈 FE 컬럼 → `🔄 골조`
- 섹션 14: 변경 로그에 "Regina: Phase 0 작업4 완료 — 프론트엔드 골조 + 인증 화면" 한 줄 추가
- 섹션 18.2: 일일 진행 로그 추가

### 7.2 git 작업 (커밋 전 사용자 OK 확인 필수)

```bash
git checkout -b feature/fe-phase0-skeleton
git add frontend/ ClaudeICFR.md
git commit -m "feat(frontend): Vite + React + TS + shadcn/ui + 인증 화면 골조 (Phase 0 작업4)"
git push -u origin feature/fe-phase0-skeleton
```

### 7.3 동작 확인 체크리스트
- [ ] `npm run dev` → `http://localhost:5173` 로그인 화면 표시
- [ ] 잘못된 자격증명 → "이메일 또는 비밀번호가 올바르지 않습니다" 표시
- [ ] 올바른 자격증명 (admin@example.com / .env의 ADMIN_PASSWORD) → `/dashboard` 이동
- [ ] `/dashboard` 새로고침 → 로그인 유지
- [ ] 사이드바 로그아웃 → `/login` 이동 + localStorage 초기화
- [ ] 미인증 상태 `/dashboard` 직접 접근 → `/login` 리다이렉트

---

## 8. 참조

- 기술스택: `ClaudeICFR.md` 섹션 3
- 협업 분담: ADR-0017 (브랜치 명명 규칙 포함)
- API 명세 표준: `ClaudeICFR.md` 섹션 19
- JWT 정책: ADR-0011 (Access 30분, Refresh 7일)
- 백엔드 인증 API: `backend/app/api/auth.py`
- 다음 작업: `prompts/ICFR_frontend_2_YYYYMMDD.md` (작업5 — 11개 모듈 골조)
