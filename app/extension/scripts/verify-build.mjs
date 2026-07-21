import { existsSync, readFileSync } from 'node:fs'

const dist = new URL('../dist/', import.meta.url)
const manifest = JSON.parse(readFileSync(new URL('manifest.json', dist), 'utf8'))
const moduleSyntax = /^[\t ]*(?:import|export)\b/m

for (const entry of manifest.content_scripts ?? []) {
  for (const file of entry.js ?? []) {
    const artifact = new URL(file, dist)
    if (!existsSync(artifact)) throw new Error(`Manifest content script is missing: ${file}`)
    if (moduleSyntax.test(readFileSync(artifact, 'utf8'))) throw new Error(`Manifest content script contains unresolved module syntax: ${file}`)
  }
}

console.log('Verified manifest content scripts: classic bundles with no unresolved imports or exports.')
