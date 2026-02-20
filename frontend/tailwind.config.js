/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        gain: '#22c55e',
        loss: '#ef4444',
        'dark-bg': '#111827',
        'dark-surface': '#1f2937',
        'dark-border': '#374151',
        'dark-muted': '#6b7280',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      minWidth: {
        '1280': '1280px',
      },
    },
  },
  plugins: [],
}
