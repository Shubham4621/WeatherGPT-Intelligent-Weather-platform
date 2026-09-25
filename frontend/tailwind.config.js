/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#17263c',
        muted: '#718096',
        canvas: '#f4f7fb',
        brand: '#2767d7',
        'brand-dark': '#1c4fae',
        line: '#e5ebf2',
      },
      boxShadow: {
        card: '0 14px 40px rgba(30, 54, 86, 0.07)',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
