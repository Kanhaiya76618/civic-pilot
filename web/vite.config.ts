import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In development the API runs on :8000 (uvicorn executor.api:app). In production FastAPI serves dist/.
const api = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/app": api,
      "/v1": api,
      "/api": api,
      "^/citizen/[^/]+/(state|approve|human|approval\\.png|final\\.png)": api,
      "^/citizen/[^/]+/live": { target: api, ws: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
