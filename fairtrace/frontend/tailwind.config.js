/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Segoe UI", "Trebuchet MS", "ui-sans-serif", "system-ui"],
      },
      boxShadow: {
        soft: "0 24px 80px -32px rgba(0, 0, 0, 0.75)",
      },
    },
  },
  plugins: [],
};

