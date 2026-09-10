/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#000000',
        'bg-surface': '#08080d',
        'bg-elevated': '#12121c',
        'border-subtle': '#1e1f2d',
        'text-muted': '#64748b',
        'text-dim': '#94a3b8',
        'text-primary': '#ffffff',
        'accent-teal': '#00f0ff',
        'accent-cyan': '#00e5ff',
        'accent-green': '#00ff88',
        'accent-green-deep': '#00a859',
        'accent-yellow': '#ffaa00',
        'accent-red': '#ff0055',
        'accent-purple': '#9d4edd',
      },
      boxShadow: {
        '3d-card': '0 16px 36px -10px rgba(0,0,0,0.95), inset 0 1px 0 rgba(255,255,255,0.15)',
        '3d-card-hover': '0 20px 42px -10px rgba(0,0,0,0.95), inset 0 1px 0 rgba(255,255,255,0.2)',
        '3d-btn': '0 6px 20px -4px rgba(0,240,255,0.4), inset 0 1px 0 rgba(255,255,255,0.4)',
        'neon-teal': '0 0 20px rgba(0, 240, 255, 0.35)',
        'neon-red': '0 0 20px rgba(255, 0, 85, 0.35)',
        'neon-green': '0 0 20px rgba(0, 255, 136, 0.35)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
