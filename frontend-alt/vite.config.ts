import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const BACKEND = process.env.CAIRN_BACKEND_URL || 'http://127.0.0.1:8000';

const PROXY_PATHS = [
  '/api',
  '/jobs',
  '/study',
  '/ask',
  '/decide',
  '/draft',
  '/explore',
  '/highlight',
  '/highlights',
  '/static',
  '/healthz',
];

const proxyConfig = Object.fromEntries(
  PROXY_PATHS.map((path) => [
    path,
    {
      target: BACKEND,
      changeOrigin: true,
    },
  ]),
);

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: proxyConfig,
  },
  preview: {
    host: '127.0.0.1',
    port: 4173,
    proxy: proxyConfig,
  },
});
