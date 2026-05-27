import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Pages project site serves from /DraftLens/.
// Override with VITE_BASE=/ for a custom domain or local root serving.
const base = process.env.VITE_BASE ?? "/DraftLens/";

export default defineConfig({
  base,
  plugins: [react()],
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
