/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // War-room dark surface system.
        ink: {
          950: "#0a0e14",
          900: "#0d1117",
          850: "#11161f",
          800: "#161b26",
          700: "#1d2430",
          600: "#283041",
          500: "#3a4555",
        },
        line: "#222b39",
        accent: {
          DEFAULT: "#3b82f6",
          soft: "#1e3a5f",
        },
        // Score tiers (low -> high).
        tier: {
          elite: "#22c55e",
          high: "#84cc16",
          mid: "#eab308",
          low: "#f97316",
          risk: "#ef4444",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
