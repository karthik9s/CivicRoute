import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    // Never inline fonts as data: URLs - the server's Content-Security-Policy only allows fonts from 'self'.
    assetsInlineLimit: (file) => (/\.(woff2?|ttf|otf)$/.test(file) ? false : undefined),
  },
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
})
