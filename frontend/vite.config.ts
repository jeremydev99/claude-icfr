import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
    // PWA — 설치형 앱(모바일 홈 화면·PC 앱 창). **API 응답은 캐시하지 않는다**: 재무 데이터·로그인 정보가
    // 기기에 남지 않도록 화면 파일(HTML·JS·CSS·아이콘)만 미리 받아 둔다. 새 버전은 사용자가 새로고침을
    // 눌러 적용한다(registerType: 'prompt' — 작업 중 화면이 저절로 바뀌지 않게).
    VitePWA({
      registerType: 'prompt',
      includeAssets: ['favicon.svg', 'icons/apple-touch-icon.png'],
      manifest: {
        name: 'ICFR 내부회계관리시스템',
        short_name: 'ICFR',
        description: '내부회계관리제도 스코핑·RCM·평가·재무제표 관리',
        lang: 'ko',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        background_color: '#ffffff',
        theme_color: '#223052',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // 글꼴(Pretendard 하위 집합 90여 개)은 미리 받지 않는다 — 쓰는 글자 범위만 그때 받아 아래 runtimeCaching 이 보관한다
        globPatterns: ['**/*.{js,css,html,svg,png,ico,webp}'],
        // 링크 공유 미리보기 이미지는 메신저 크롤러용 — 설치된 앱이 미리 받을 필요 없다
        globIgnores: ['og-image.png'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
        // API 는 캐시 대상이 아니다 — 네트워크로만. 글꼴만 한 번 받으면 기기에 보관한다(내용이 바뀌지 않는 파일)
        runtimeCaching: [
          {
            urlPattern: ({ request }) => request.destination === 'font',
            handler: 'CacheFirst',
            options: { cacheName: 'icfr-fonts', expiration: { maxEntries: 120, maxAgeSeconds: 60 * 60 * 24 * 365 } },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
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
