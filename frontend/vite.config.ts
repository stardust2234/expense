import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const tlsDirectory = resolve(import.meta.dirname, "../data/dev-tls");

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    https: {
      cert: readFileSync(resolve(tlsDirectory, "server.pem")),
      key: readFileSync(resolve(tlsDirectory, "server.key")),
    },
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
  },
});

