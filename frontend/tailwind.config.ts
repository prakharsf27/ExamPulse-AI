import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: "#1E3A8A",
          50: "#EEF2FF",
          100: "#E0E7FF",
          600: "#1E40AF",
          700: "#1E3A8A",
          800: "#172554",
        },
        coral: {
          DEFAULT: "#E17055",
          50: "#FDF3F0",
          100: "#FADFD7",
          500: "#E17055",
          600: "#C85A40",
        },
        cream: "#FFFCF5",
        background: "#FFFCF5",
        foreground: "#0F172A",
        border: "#E2E8F0",
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
