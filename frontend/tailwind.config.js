/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        lgu: {
          pink: '#E6007E',
          dark: '#1a1a2e',
          gray: '#f5f5f5',
        },
      },
      animation: {
        'cursor-blink': 'cursor-blink 0.9s ease-in-out infinite',
      },
      keyframes: {
        'cursor-blink': {
          '0%, 100%': { opacity: '1' },
          '50%':       { opacity: '0' },
        },
      },
    },
  },
  plugins: [],
}
