#!/usr/bin/env node
/**
 * Merge translated slices into src/i18n/locales/fr-CA/ui.json and report coverage.
 *
 *   node scripts/i18n-merge-fr.mjs <dir-with-fr_part*.json> [--write]
 *
 * Validates each slice against the English catalogue: unknown files/keys are
 * reported (a stale slug after a codemod re-run), missing keys are counted per
 * file, and interpolation placeholders ({{name}}) must match the English
 * exactly. Without --write it only reports.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const EN = path.join(ROOT, 'src/i18n/locales/en/ui.json')
const FR = path.join(ROOT, 'src/i18n/locales/fr-CA/ui.json')
const dir = process.argv[2]
const WRITE = process.argv.includes('--write')

const en = JSON.parse(fs.readFileSync(EN, 'utf8'))
const fr = fs.existsSync(FR) ? JSON.parse(fs.readFileSync(FR, 'utf8')) : {}
const parts = fs.readdirSync(dir).filter((f) => /^fr_part\d+\.json$/.test(f)).sort((a, b) => parseInt(a.match(/\d+/)[0]) - parseInt(b.match(/\d+/)[0]))
const unknown = [], placeholderMismatch = []
const ph = (s) => (s.match(/\{\{[^}]+\}\}/g) || []).sort().join(',')
for (const p of parts) {
  const slice = JSON.parse(fs.readFileSync(path.join(dir, p), 'utf8'))
  for (const [file, keys] of Object.entries(slice)) {
    if (!en[file]) { unknown.push(`${p}: ${file}.*`); continue }
    fr[file] = fr[file] || {}
    for (const [k, v] of Object.entries(keys)) {
      if (!(k in en[file])) { unknown.push(`${p}: ${file}.${k}`); continue }
      if (ph(en[file][k]) !== ph(v)) placeholderMismatch.push(`${file}.${k}`)
      fr[file][k] = v
    }
  }
}
let total = 0, done = 0
const missingByFile = []
for (const [file, keys] of Object.entries(en)) {
  const n = Object.keys(keys).length
  const have = Object.keys(keys).filter((k) => fr[file]?.[k]).length
  total += n; done += have
  if (have < n) missingByFile.push(`${file} ${have}/${n}`)
}
console.log(`coverage: ${done}/${total} keys (${((done / total) * 100).toFixed(1)}%) from ${parts.length} slice(s)`)
if (unknown.length) console.log('UNKNOWN keys (stale slugs?):', unknown.length, unknown.slice(0, 12))
if (placeholderMismatch.length) console.log('PLACEHOLDER mismatches:', placeholderMismatch)
if (missingByFile.length) console.log('incomplete files:', missingByFile.length, '→', missingByFile.slice(0, 15).join(' | '))
if (WRITE) {
  fs.writeFileSync(FR, JSON.stringify(fr, null, 2) + '\n')
  console.log('wrote', FR)
}
