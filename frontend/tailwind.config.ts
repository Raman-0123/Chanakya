import type { Config } from "tailwindcss";

/**
 * CHANAKYA design system — "National Energy Crisis Command Center".
 * Bloomberg Terminal + Mission Control: deep navy-black canvas, operational
 * severity colors, cyan intelligence accent, amber energy accent, glow states.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // canvas
        void: "#05070d",
        base: "#0a0e17",
        panel: "#0e1420",
        "panel-raised": "#121a29",
        line: "#1b2536",
        "line-strong": "#26344a",
        // text
        ink: "#e6edf7",
        "ink-muted": "#8b99b3",
        "ink-dim": "#5a677f",
        // intelligence accent (cyan)
        signal: {
          DEFAULT: "#22d3ee",
          dim: "#0e7490",
          glow: "#67e8f9",
        },
        // energy accent (amber)
        energy: {
          DEFAULT: "#f59e0b",
          dim: "#b45309",
          glow: "#fbbf24",
        },
        // operational severity
        nominal: "#10b981",
        elevated: "#eab308",
        high: "#f97316",
        critical: "#ef4444",
        // structured
        indigo: "#6366f1",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        micro: ["0.6875rem", { lineHeight: "0.875rem", letterSpacing: "0.04em" }],
      },
      boxShadow: {
        "glow-signal": "0 0 0 1px rgba(34,211,238,0.35), 0 0 20px -4px rgba(34,211,238,0.45)",
        "glow-critical": "0 0 0 1px rgba(239,68,68,0.4), 0 0 22px -4px rgba(239,68,68,0.5)",
        "glow-nominal": "0 0 0 1px rgba(16,185,129,0.35), 0 0 18px -6px rgba(16,185,129,0.45)",
        panel: "0 1px 0 0 rgba(255,255,255,0.02) inset, 0 8px 24px -12px rgba(0,0,0,0.8)",
      },
      backgroundImage: {
        "grid-faint":
          "linear-gradient(rgba(38,52,74,0.25) 1px, transparent 1px), linear-gradient(90deg, rgba(38,52,74,0.25) 1px, transparent 1px)",
        "radial-fade":
          "radial-gradient(circle at 50% 0%, rgba(34,211,238,0.08), transparent 60%)",
      },
      keyframes: {
        "pulse-ring": {
          "0%": { transform: "scale(0.85)", opacity: "0.7" },
          "70%": { transform: "scale(1.6)", opacity: "0" },
          "100%": { opacity: "0" },
        },
        "sweep": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
        "flicker": {
          "0%,100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
      },
      animation: {
        "pulse-ring": "pulse-ring 2s ease-out infinite",
        sweep: "sweep 2.5s ease-in-out infinite",
        flicker: "flicker 2.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
