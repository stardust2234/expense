import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const tlsDirectory = resolve(import.meta.dirname, "../data/dev-tls");
const certificatePath = resolve(tlsDirectory, "server.pem");
const privateKeyPath = resolve(tlsDirectory, "server.key");
const developmentHttps =
  existsSync(certificatePath) && existsSync(privateKeyPath)
    ? {
        cert: readFileSync(certificatePath),
        key: readFileSync(privateKeyPath),
      }
    : undefined;

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    https: developmentHttps,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
  },
});

