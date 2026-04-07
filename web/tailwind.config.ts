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
          bg: "#fcfcfd",
          sidebar: "#f5f6f8",
          surface: "#ffffff",
          muted: "#f9fafb",
          border: "#eaecf0",
          borderStrong: "#d0d5dd",
          text: "#101828",
          subtext: "#667085",
          softText: "#98a2b3",
          blue: "#155eef",
          blueSoft: "#eff4ff",
          danger: "#d92d20",
          dangerSoft: "#fef3f2",
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
