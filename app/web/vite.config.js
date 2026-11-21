import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/",
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 1500 },
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:7860", "/files": "http://127.0.0.1:7860", "/ws": { target: "ws://127.0.0.1:7860", ws: true } } },
});
