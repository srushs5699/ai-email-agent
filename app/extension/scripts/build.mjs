import { build } from '../../frontend/node_modules/vite/dist/node/index.js'
import { cpSync, mkdirSync, rmSync } from 'node:fs'

rmSync('dist', { recursive: true, force: true }); mkdirSync('dist', { recursive: true })
async function bundle(entry, file, format) {
  await build({ configFile: false, build: { emptyOutDir: false, outDir: `dist/${file.split('/')[0]}`, lib: { entry, name: 'AiEmailAgentExtension', formats: [format], fileName: () => file.split('/')[1] }, target: 'es2022' } })
}
await bundle('src/popup/popup.ts', 'popup/popup.js', 'es')
await bundle('src/background/service-worker.ts', 'background/service-worker.js', 'es')
await bundle('src/content/linkedin-content.ts', 'content/linkedin-content.js', 'iife')
await bundle('src/content/job-content.ts', 'content/job-content.js', 'iife')
await bundle('src/content/application-bridge.ts', 'content/application-bridge.js', 'iife')
mkdirSync('dist/popup', { recursive: true })
cpSync('src/popup/popup.html', 'dist/popup/popup.html')
cpSync('manifest.json', 'dist/manifest.json')
