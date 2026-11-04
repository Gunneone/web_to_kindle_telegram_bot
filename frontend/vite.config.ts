import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

/** Shared gunne.one design system (gunne.css, theme.js, fonts, brand). Point it at a local homepage for development. */
const G1_DS_URL = (process.env.G1_DS_URL || 'https://gunne.one/ds/v1').replace(/\/+$/, '');

/** Where the Python API runs (`python src/web_server.py`) and which port this dev server takes. */
const API_URL = process.env.API_URL || 'http://127.0.0.1:8000';
const PORT = Number(process.env.PORT || 5173);

export default defineConfig({
  root: 'src/client',
  publicDir: '../../public',
  plugins: [
    react(),
    tailwindcss(),
    { name: 'g1-ds-url', transformIndexHtml: (html) => html.replaceAll('%G1_DS_URL%', G1_DS_URL) },
  ],
  define: { __G1_DS_URL__: JSON.stringify(G1_DS_URL) },
  build: { outDir: '../../dist', emptyOutDir: true },
  server: {
    host: 'localhost',
    port: PORT,
    strictPort: true,
    proxy: { '/api': { target: API_URL } },
  },
  test: { root: '.', include: ['tests/**/*.test.ts'] },
});
