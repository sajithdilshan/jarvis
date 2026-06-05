import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

// Build to web/dist; the FastAPI server serves dist/index.html + dist/assets.
// Dev server proxies HTTP API calls to the Python app on :4000. The WebSocket is NOT
// proxied — the client connects to :4000 directly (see web/src/socket.js), because
// Vite's WS proxy mishandles server keepalive ping/pong and cycles the connection.
export default defineConfig({
  plugins: [preact()],
  build: { outDir: "dist" },
  server: {
    proxy: {
      "/agent": "http://localhost:4000",
      "/session": "http://localhost:4000",
      "/view-model": "http://localhost:4000",
    },
  },
});
