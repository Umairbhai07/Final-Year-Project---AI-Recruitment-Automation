/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Variable"', "Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        display: ['"Plus Jakarta Sans Variable"', '"Inter Variable"', "Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      colors: {
        brand: {
          // black and white: "brand" is the neutral scale, so every accent in the app is black or grey
          50: "#fafafa", 100: "#f5f5f5", 200: "#e5e5e5", 300: "#d4d4d4", 400: "#a3a3a3",
          500: "#525252", 600: "#0a0a0a", 700: "#262626", 800: "#171717", 900: "#0a0a0a",
        },
        ink: { 700: "#262626", 800: "#171717", 900: "#0f0f0f", 950: "#0a0a0a" },
        canvas: "#ffffff",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(15,23,42,.05)",
        card: "0 1px 2px rgba(15,23,42,.04)",
        lift: "0 8px 24px -12px rgba(15,23,42,.18)",
        glow: "0 0 0 4px rgba(10,10,10,.08)",
        brand: "0 10px 24px -12px rgba(0,0,0,.35)",
        "brand-lg": "0 24px 48px -24px rgba(0,0,0,.35)",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #0a0a0a 0%, #404040 100%)",
        "brand-soft": "linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%)",
        "ink-gradient": "linear-gradient(180deg, #0a0a0a 0%, #171717 100%)",
        aurora:
          "radial-gradient(60% 50% at 15% 10%, rgba(99,102,241,.35) 0%, transparent 60%), radial-gradient(50% 45% at 90% 20%, rgba(168,85,247,.30) 0%, transparent 60%), radial-gradient(55% 50% at 60% 100%, rgba(236,72,153,.20) 0%, transparent 60%)",
        "aurora-light":
          "radial-gradient(50% 60% at 10% 0%, rgba(99,102,241,.16) 0%, transparent 60%), radial-gradient(45% 55% at 95% 10%, rgba(168,85,247,.14) 0%, transparent 60%)",
        "grid-faint":
          "linear-gradient(rgba(255,255,255,.06) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.06) 1px, transparent 1px)",
      },
      keyframes: {
        "fade-up": { "0%": { opacity: 0, transform: "translateY(8px)" }, "100%": { opacity: 1, transform: "none" } },
        "fade-in": { "0%": { opacity: 0 }, "100%": { opacity: 1 } },
        "page-in": { "0%": { opacity: 0, transform: "translateY(6px)" }, "100%": { opacity: 1, transform: "none" } },
        "slide-in-left": { "0%": { transform: "translateX(-100%)" }, "100%": { transform: "none" } },
        "pop-in": { "0%": { opacity: 0, transform: "scale(.96)" }, "100%": { opacity: 1, transform: "none" } },
        shimmer: { "0%": { backgroundPosition: "-400px 0" }, "100%": { backgroundPosition: "400px 0" } },
        progress: { "0%": { transform: "translateX(-100%)" }, "100%": { transform: "translateX(250%)" } },
        float: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-6px)" } },
      },
      animation: {
        "fade-up": "fade-up .35s ease-out both",
        "fade-in": "fade-in .2s ease-out both",
        "page-in": "page-in .28s cubic-bezier(.2,.7,.2,1) both",
        "slide-in-left": "slide-in-left .25s cubic-bezier(.2,.7,.2,1) both",
        "pop-in": "pop-in .18s cubic-bezier(.2,.7,.2,1) both",
        shimmer: "shimmer 1.3s linear infinite",
        progress: "progress 1s cubic-bezier(.4,0,.2,1) infinite",
        float: "float 4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
