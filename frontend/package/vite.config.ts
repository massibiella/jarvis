/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// This config file lives in frontend/package/, one level below the actual
// project root (frontend/, where index.html/src/tests/public live). Vite's
// `root` defaults to process.cwd() — not this file's directory — and the
// npm scripts that load this config (see ../package.json) always run with
// cwd = frontend/ (npm sets cwd to the directory containing package.json),
// so root resolves correctly without an explicit override. Paths below are
// therefore root-relative, same as before the config moved.

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/testSetup.ts'],
  },
})
