import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Plus Jakarta Sans'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      colors: {
        dify: {
          bg: "rgb(var(--color-bg) / <alpha-value>)",
          sidebar: "rgb(var(--color-sidebar) / <alpha-value>)",
          surface: "rgb(var(--color-surface) / <alpha-value>)",
          muted: "rgb(var(--color-muted) / <alpha-value>)",
          border: "rgb(var(--color-border) / <alpha-value>)",
          borderStrong: "rgb(var(--color-border-strong) / <alpha-value>)",
          text: "rgb(var(--color-text) / <alpha-value>)",
          subtext: "rgb(var(--color-subtext) / <alpha-value>)",
          softText: "rgb(var(--color-soft-text) / <alpha-value>)",
          blue: "rgb(var(--color-primary) / <alpha-value>)",
          blueHover: "rgb(var(--color-primary-hover) / <alpha-value>)",
          blueSoft: "rgb(var(--color-primary-soft) / <alpha-value>)",
          accent: "rgb(var(--color-accent) / <alpha-value>)",
          accentSoft: "rgb(var(--color-accent-soft) / <alpha-value>)",
          danger: "rgb(var(--color-danger) / <alpha-value>)",
          dangerSoft: "rgb(var(--color-danger-soft) / <alpha-value>)",
          overlay: "rgb(var(--color-overlay) / <alpha-value>)",
          chart1: "rgb(var(--color-chart-1) / <alpha-value>)",
          chart2: "rgb(var(--color-chart-2) / <alpha-value>)",
          chart3: "rgb(var(--color-chart-3) / <alpha-value>)",
          chart4: "rgb(var(--color-chart-4) / <alpha-value>)",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(16, 24, 40, 0.06)",
      },
      keyframes: {
        "rise-in": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "rise-in": "rise-in .24s ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
