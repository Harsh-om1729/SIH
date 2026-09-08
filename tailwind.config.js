/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#0a0f0d',
        'bg-surface': '#111917',
        'bg-elevated': '#16201d',
        'border-subtle': '#25322e',
        'text-muted': '#5c6f68',
        'text-dim': '#8fa39b',
        'text-primary': '#e6ece9',
        'accent-teal': '#5fd6c4',
        'accent-green': '#4fbf7a',
        'accent-green-deep': '#2f6e64',
        'accent-yellow': '#e6c34a',
        'accent-red': '#e5484d',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
