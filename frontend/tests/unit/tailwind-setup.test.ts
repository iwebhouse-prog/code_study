/// <reference types="node" />
import { readFileSync } from 'node:fs'
import postcss from 'postcss'
import tailwindcss from 'tailwindcss'
import { describe, expect, it } from 'vitest'
import componentsJson from '../../components.json?raw'
import mainTsx from '../../src/main.tsx?raw'
import tailwindConfig from '../../tailwind.config'

// Read from disk: Vitest empties .css imports, even with ?raw.
const indexCss = readFileSync('src/index.css', 'utf8')

async function buildCss(): Promise<string> {
  // Same input and config as a real build, so the theme tokens are verified
  // end to end rather than by reading the config.
  const result = await postcss([
    tailwindcss({ ...tailwindConfig, content: [{ raw: USED }] }),
  ]).process(indexCss, { from: 'src/index.css' })
  return result.css
}

const USED = 'bg-primary text-destructive border-input text-muted-foreground rounded-xl'

describe('Tailwind setup', () => {
  it('scans every source file for class names', () => {
    expect(tailwindConfig.content).toEqual(['./index.html', './src/**/*.{ts,tsx}'])
  })

  it('main.tsx loads the stylesheet', () => {
    expect(mainTsx).toContain("import './index.css'")
  })

  it('generates theme classes from the shadcn color tokens', async () => {
    const css = await buildCss()
    expect(css).toMatch(/\.bg-primary\s*{[^}]*hsl\(var\(--primary\)\)/)
    expect(css).toMatch(/\.text-destructive\s*{[^}]*hsl\(var\(--destructive\)\)/)
  })

  it('defines every color token the theme uses', async () => {
    const css = await buildCss()
    for (const token of [
      'background',
      'foreground',
      'primary',
      'destructive',
      'border',
      'input',
      'ring',
    ]) {
      expect(css).toContain(`--${token}:`)
    }
  })

  it('uses a Korean-friendly font stack', async () => {
    expect(await buildCss()).toContain('Malgun Gothic')
  })
})

describe('shadcn setup', () => {
  it('components.json matches the project layout', () => {
    const config = JSON.parse(componentsJson)
    expect(config.tsx).toBe(true)
    expect(config.rsc).toBe(false)
    expect(config.tailwind.cssVariables).toBe(true)
    expect(config.tailwind.css).toBe('src/index.css')
    expect(config.aliases.ui).toBe('@/components/ui')
    expect(config.aliases.utils).toBe('@/lib/utils')
  })
})
