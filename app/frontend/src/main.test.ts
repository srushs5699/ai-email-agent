/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('application stylesheets', () => {
  it('loads the global stylesheet from the application entry point', () => {
    const entry = readFileSync(resolve(process.cwd(), 'src/main.tsx'), 'utf8')
    expect(entry).toContain("import './index.css'")
  })

  it('loads dashboard layout styles from the application module', () => {
    const app = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8')
    expect(app).toContain("import './App.css'")
  })
})
