import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './', // Relative base path for portable deployment to GitHub Pages or Vercel
  build: {
    outDir: 'dist',
  }
});
