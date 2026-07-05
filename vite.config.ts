import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiBaseUrl = process.env.TRADEMINER_API_BASE_URL ?? "http://localhost:8000";

export default defineConfig({
  root: "web",
  plugins: [react()],
  server: {
    proxy: {
      "/api": apiBaseUrl
    }
  },
  build: {
    outDir: "../dist/web",
    emptyOutDir: true
  }
});
