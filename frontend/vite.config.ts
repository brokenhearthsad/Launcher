/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    build: {
      rollupOptions: {
        output: { manualChunks: { charts: ["recharts"], vendor: ["react", "react-dom", "react-router-dom"] } },
      },
    },
    server: {
      host: "127.0.0.1", // explicit IPv4: avoids localhost resolving to ::1 only on Windows
      port: 5173,
      strictPort: true,
      // The dev server proxies API and WebSocket traffic to the backend,
      // so the browser only talks to http://localhost:5173.
      proxy: {
        "/api": { target: backend, changeOrigin: true },
        "/ws": { target: backend.replace(/^http/, "ws"), ws: true },
      },
    },
    preview: {
      port: 5173,
      strictPort: true,
      proxy: {
        "/api": { target: backend, changeOrigin: true },
        "/ws": { target: backend.replace(/^http/, "ws"), ws: true },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
      css: false,
    },
  };
});
