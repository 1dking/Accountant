// Builds the published-page runtime (src/pages-runtime) as a single IIFE
// + one CSS file into backend/app/pages/static/runtime/<version>/, which
// FastAPI serves at /api/pages/public/runtime/<version>/runtime.{js,css}.
//   pnpm run build:runtime
// The output is committed so a deploy never depends on this build step
// succeeding on the VPS (deploy.sh still runs it).
import { defineConfig } from 'vite'
import path from 'path'
import { RUNTIME_VERSION } from './src/pages-runtime/version'

export default defineConfig({
  publicDir: false,
  build: {
    outDir: path.resolve(__dirname, `../backend/app/pages/static/runtime/${RUNTIME_VERSION}`),
    emptyOutDir: true,
    target: 'es2019',
    minify: 'esbuild',
    sourcemap: false,
    cssCodeSplit: false,
    lib: {
      entry: path.resolve(__dirname, 'src/pages-runtime/index.ts'),
      name: 'PagesRuntime',
      formats: ['iife'],
      fileName: () => 'runtime.js',
      cssFileName: 'runtime',
    },
    rollupOptions: { output: { assetFileNames: 'runtime.[ext]' } },
  },
})
