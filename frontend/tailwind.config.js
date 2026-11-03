/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      boxShadow: {
        glow: '0 0 25px rgba(139, 92, 246, 0.3)',
      },
    },
  },
  plugins: [],
};

