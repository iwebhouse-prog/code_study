/// <reference types="node" />
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const EXACT_VERSION = /^\d+\.\d+\.\d+$/
const pkg = JSON.parse(readFileSync('package.json', 'utf8')) as {
  dependencies: Record<string, string>
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return sourceFiles(path)
    return /\.(ts|tsx)$/.test(entry.name) ? [path] : []
  })
}

const MONACO_EDITOR_FILE = join('src', 'components', 'document', 'MonacoEditor.tsx')
const sources = sourceFiles('src').map((path) => ({ path, text: readFileSync(path, 'utf8') }))

describe('Monaco setup (T099)', () => {
  it.each(['@monaco-editor/react', 'monaco-editor'])('pins %s to an exact version', (name) => {
    expect(pkg.dependencies[name]).toMatch(EXACT_VERSION)
  })

  it('wraps Monaco in MonacoEditor.tsx and points the loader at the bundled copy', () => {
    const text = readFileSync(MONACO_EDITOR_FILE, 'utf8')
    expect(text).toContain('loader.config({ monaco })')
    // A CDN URL would mean the editor is not bundled locally.
    expect(text).not.toMatch(/https?:\/\//)
  })

  it('imports monaco only inside the wrapper, so it stays out of the main bundle', () => {
    const importers = sources
      .filter(({ text }) => /from ['"](@monaco-editor\/react|monaco-editor[^'"]*)['"]/.test(text))
      .map(({ path }) => path)
    expect(importers).toEqual([MONACO_EDITOR_FILE])
  })

  it('loads the wrapper lazily', () => {
    const importsWrapper = sources.filter(({ text }) => text.includes('/MonacoEditor'))
    expect(importsWrapper.length).toBeGreaterThan(0)
    for (const { text } of importsWrapper) {
      expect(text).not.toMatch(/^import (?!type ).* from ['"][^'"]*\/MonacoEditor['"]/m)
      expect(text).toMatch(/lazy\(\(\) => import\(['"][^'"]*\/MonacoEditor['"]\)\)/)
    }
  })
})
