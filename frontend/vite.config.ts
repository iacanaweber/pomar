import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento, redireciona /api para o backend local (uvicorn na 8000).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
