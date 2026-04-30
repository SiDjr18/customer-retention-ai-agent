/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#eef4ff',
          100: '#dce9ff',
          200: '#b3d0ff',
          500: '#3b82f6',
          700: '#1d4ed8',
          900: '#1e3a8a',
        },
        risk: {
          high:   '#ef4444',
          medium: '#f59e0b',
          low:    '#22c55e',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
