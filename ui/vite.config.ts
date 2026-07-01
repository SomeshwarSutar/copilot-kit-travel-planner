import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],

  server: {
    port: 5173,
    // Proxy /api/* to the FastAPI backend during development.
    // This avoids CORS issues and mirrors the production setup where
    // FastAPI serves both the API and the built static files.
    proxy: {
      "/api": {
        target: "http://localhost:8123",
        changeOrigin: true,
      },
    },
  },

  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
