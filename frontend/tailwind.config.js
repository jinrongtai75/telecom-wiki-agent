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
    },
  },
  plugins: [],
}
