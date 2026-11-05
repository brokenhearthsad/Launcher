/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        radiant: { DEFAULT: "#4ade80", dark: "#166534", soft: "#14532d" },
        dire: { DEFAULT: "#f87171", dark: "#991b1b", soft: "#450a0a" },
        surface: { DEFAULT: "#111827", raised: "#1a2233", border: "#273248" },
        accent: { DEFAULT: "#f59e0b", soft: "#78350f" },
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
