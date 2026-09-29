import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev: Vite on 5173 proxies /api to FastAPI on 8000.
// Prod: `vite build` -> dist/, served by FastAPI itself.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
