import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, /api apunta al gateway nginx levantado con docker compose.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": process.env.API_PROXY || "http://localhost:8080" },
  },
});
