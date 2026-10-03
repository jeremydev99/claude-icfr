/** @type {import('tailwindcss').Config} */
// 곤색 단계 — 원색 파랑 대신(2026-10-03 마스터 지시). blue·sky·indigo 를 이 표로 덮어
// 화면 곳곳의 하드코딩 파랑(bg-blue-50, text-blue-700 …)이 한 번에 곤색 계열로 바뀐다.
const NAVY = {
  50: '#f3f5fa', 100: '#e4e8f2', 200: '#c9d1e3', 300: '#a3b0cc', 400: '#7385ab', 500: '#4f6390',
  600: '#3a4c77', 700: '#2c3c63', 800: '#223052', 900: '#1a2542', 950: '#111a30',
}

module.exports = {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx,js,jsx}'],
  theme: {
    extend: {
      colors: {
        blue: NAVY,
        sky: NAVY,
        indigo: NAVY,
        navy: NAVY,
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        // 사이드바는 자체 팔레트를 갖는다 — 본문 토큰(--foreground/--accent 등)을 그대로
        // 쓰면 남색 배경에서 글자가 보이지 않는다(검정 글자 + 남색 배경).
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar))',
          foreground: 'hsl(var(--sidebar-foreground))',
          muted: 'hsl(var(--sidebar-muted))',
          hover: 'hsl(var(--sidebar-hover))',
          border: 'hsl(var(--sidebar-border))',
          selected: 'hsl(var(--sidebar-selected))',
          'selected-foreground': 'hsl(var(--sidebar-selected-foreground))',
          indicator: 'hsl(var(--sidebar-indicator))',
        },
        brand: {
          from: 'hsl(var(--brand-from))',
          to: 'hsl(var(--brand-to))',
        },
        success: 'hsl(var(--success))',
        warning: 'hsl(var(--warning))',
      },
      boxShadow: {
        // 카드는 테두리 + 아주 옅은 그림자 — 떠 있되 무겁지 않게
        card: '0 1px 2px 0 rgb(16 24 40 / 0.04), 0 1px 3px 0 rgb(16 24 40 / 0.06)',
        lift: '0 4px 12px -2px rgb(16 24 40 / 0.08), 0 2px 4px -2px rgb(16 24 40 / 0.05)',
      },
      fontFamily: {
        sans: ['"Pretendard Variable"', 'Pretendard', '-apple-system', 'BlinkMacSystemFont', 'system-ui', '"Segoe UI"', '"Apple SD Gothic Neo"', '"Noto Sans KR"', '"Malgun Gothic"', 'sans-serif'],
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
    },
  },
  plugins: [require('tailwindcss-animate'), require('@tailwindcss/forms')],
}
