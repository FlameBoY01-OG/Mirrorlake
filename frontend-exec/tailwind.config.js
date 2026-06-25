/** @type {import('tailwindcss').Config} */
// Design tokens ported from SPEC §16.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: { primary: "#FAFAF8", secondary: "#F2F0EB", card: "#FFFFFF" },
        ink: { primary: "#1A1918", secondary: "#6B6966", muted: "#9B9895" },
        line: "#E5E3DC",
        teal: "#0F6E56",
        coral: "#993C1D",
        purple: "#534AB7",
        ok: "#16A34A",
        warn: "#D97706",
        danger: "#DC2626",
      },
      borderRadius: { sm: "6px", md: "8px", lg: "12px" },
    },
  },
  plugins: [],
};
