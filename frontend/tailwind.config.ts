import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0a0a0c",
          900: "#0e0f13",
          850: "#141620",
          800: "#1a1d28",
          700: "#242837",
          600: "#323748",
        },
        bone: "#ede8df",
        mist: "#9aa0b4",
        ember: "#ff5b3a",
        acid: "#c6ff4a",
        azure: "#5ad1ff",
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
