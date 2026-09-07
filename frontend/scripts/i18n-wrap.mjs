#!/usr/bin/env node
/**
 * i18n-wrap — wrap hard-coded UI strings in t() and emit the English catalogue.
 *
 * Why a codemod: sprint 5 (Bill 96, full French before Quebec launch) has to key
 * ~2,850 English strings across 230+ files. Hand-editing that is a week of typos.
 * This walks each file's AST with @babel/parser and splices `t('ui:File.key')`
 * in BY SOURCE POSITION — no re-printing, so formatting/diffs stay minimal.
 *
 *   node scripts/i18n-wrap.mjs --dry                 # report only
 *   node scripts/i18n-wrap.mjs --apply --files src/pages/CashbookPage.tsx
 *   node scripts/i18n-wrap.mjs --apply               # everything
 *
 * What it wraps
 *   - JSX text nodes with real words (not inside <code>/<pre>/<kbd>)
 *   - JSX attributes: placeholder, title, aria-label, alt, aria-description
 *   - {'literal'} and {cond ? 'A' : 'B'} / {x || 'fallback'} inside JSX
 *   - toast.*('…'), alert('…'), confirm('…'), setError/setErr/setMsg/…('…'),
 *     new Error('…')
 *   - object properties label/title/description/placeholder/hint/message/… : '…'
 * Inside a React component or a use* hook it uses `t` from useTranslation('ui');
 * anywhere else (module constants, plain helpers) it uses i18n.t so the string
 * still resolves. Files that already import useTranslation are left alone —
 * those were keyed by hand in sprints 1–4.
 *
 * What it skips (reported, for hand follow-up): template literals with ${},
 * string concatenations, brand tokens, pure numbers/punctuation.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse } from '@babel/parser'
import traverseModule from '@babel/traverse'

const traverse = traverseModule.default ?? traverseModule
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const SRC = path.join(ROOT, 'src')
const NS = 'ui'

const args = process.argv.slice(2)
const APPLY = args.includes('--apply')
// --force: also process files that already import useTranslation (a second
// pass after the first sweep, or hand-keyed files with leftovers). Existing
// keys are reused for identical text and never overwritten by a new slug.
const FORCE = args.includes('--force')
const filesArg = args.includes('--files') ? args[args.indexOf('--files') + 1].split(',') : null
// --emit-catalogue <path>: in dry mode, write the catalogue this run WOULD add
// to the given JSON file instead of touching en/ui.json. Used to recover the
// English for keys already wired in source (run against `git show HEAD:` copies).
const emitArg = args.includes('--emit-catalogue') ? args[args.indexOf('--emit-catalogue') + 1] : null
const enPath = path.join(SRC, 'i18n/locales/en', `${NS}.json`)
const EXISTING = fs.existsSync(enPath) ? JSON.parse(fs.readFileSync(enPath, 'utf8')) : {}

const ATTRS = new Set(['placeholder', 'title', 'aria-label', 'alt', 'aria-description', 'label', 'description', 'emptyText', 'helperText', 'hint', 'tooltip'])
// Object properties whose ARRAY value is a list of copy strings (plan bullets, FAQ answers…).
const ARRAY_PROPS = new Set(['features', 'bullets', 'benefits', 'highlights', 'items', 'steps', 'points', 'perks'])
const PROPS = new Set(['label', 'title', 'description', 'placeholder', 'hint', 'help', 'helper', 'message',
  'text', 'subtitle', 'heading', 'tooltip', 'emptyText', 'confirmText', 'successMessage', 'errorMessage',
  'cta', 'buttonText', 'summary', 'caption', 'question', 'answer', 'body'])
const CALLS = new Set(['alert', 'confirm', 'setError', 'setErr', 'setMsg', 'setMessage', 'setSuccess',
  'setStatusMessage', 'setInfo', 'setWarning', 'setHint'])
const TOAST = new Set(['success', 'error', 'info', 'warning', 'message', 'loading'])
const SKIP_PARENT_TAGS = new Set(['code', 'pre', 'kbd', 'script', 'style', 'samp'])
const BRANDS = new Set(['O-Brain', 'OCIDM', 'Stripe', 'Twilio', 'Plaid', 'Google', 'Gmail', 'LiveKit', 'Hocuspocus',
  'PDF', 'CSV', 'XLSX', 'Excel', 'URL', 'ID', 'API', 'SMS', 'MMS', 'OK', 'QR', 'JSON', 'HTML', 'CSS', 'JS', 'UTC',
  'CAD', 'USD', 'GST', 'HST', 'PST', 'QST', 'CRA', 'T4', 'T1', 'T2', 'ROE', 'PD7A', 'RRSP', 'CPP', 'EI', 'QPP', 'QPIP',
  'Yjs', 'WebAuthn', 'TOTP', 'Windows Hello', 'Face ID', 'Touch ID', 'YubiKey', 'iPhone', 'Android', 'iOS',
  'React', 'Vite', 'FastAPI', 'Supabase', 'Vercel', 'DreamHost', 'GitHub', 'Slack', 'Zoom', 'Zapier', 'HubSpot',
  'QuickBooks', 'Xero', 'FreshBooks', 'Wave', 'GoHighLevel', 'Interac', 'Visa', 'Mastercard', 'Amex', 'PayPal'])

const SKIP_FILE_PATTERNS = [/\.d\.ts$/, /\.test\.tsx?$/, /\.spec\.tsx?$/, /\/i18n\//, /\/vite-env/]
// .ts files: only lib/ constants carry user-visible labels; everything else in .ts is API/types.
const TS_ALLOW = [/\/lib\/constants\.ts$/, /\/lib\/features\.ts$/]

function isTranslatable(raw) {
  const s = raw.replace(/\s+/g, ' ').trim()
  if (s.length < 2) return false
  if (!/[A-Za-z]{2,}/.test(s)) return false            // needs a real word
  if (/^[\d\s.,:%$€£#()/+-]+$/.test(s)) return false   // numbers/punct only
  if (BRANDS.has(s)) return false
  if (/^[A-Z0-9][A-Z0-9 ./&-]{0,5}$/.test(s) && !/[a-z]/.test(s)) return false // short all-caps token
  if (/^(https?:|mailto:|tel:|\/|#|\.\.?\/)/.test(s)) return false
  if (/^[a-z][a-z0-9_-]*$/.test(s) && !s.includes(' ')) return false // identifiers like "email", "kebab-case"
  if (/^\{\{.*\}\}$/.test(s)) return false
  if (CSS_WORDS.has(s) || looksLikeClasses(s)) return false
  return true
}

function slug(text, used) {
  const words = text.replace(/&[a-z]+;|&#\d+;/g, ' ').replace(/[^A-Za-z0-9 ]+/g, ' ').trim().split(/\s+/).filter(Boolean).slice(0, 5)
  let base = words.map((w, i) => (i === 0 ? w.toLowerCase() : w[0].toUpperCase() + w.slice(1).toLowerCase())).join('')
  if (!base) base = 'text'
  if (/^\d/.test(base)) base = 'n' + base
  base = base.slice(0, 40)
  let key = base, n = 2
  while (used.has(key)) key = `${base}_${n++}`
  used.add(key)
  return key
}

function listFiles() {
  const out = []
  ;(function walk(dir) {
    for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, ent.name)
      if (ent.isDirectory()) walk(p)
      else if (/\.tsx?$/.test(ent.name)) out.push(p)
    }
  })(SRC)
  return out.filter((f) => {
    const rel = f.split(path.sep).join('/')
    if (SKIP_FILE_PATTERNS.some((r) => r.test(rel))) return false
    if (rel.endsWith('.ts') && !TS_ALLOW.some((r) => r.test(rel))) return false
    return true
  })
}

function componentScope(p) {
  // Nearest enclosing function that is a React component (capitalised, contains JSX)
  // or a custom hook (use*). Returns the function path or null (module level / plain helper).
  let fn = p.getFunctionParent()
  while (fn) {
    const name = fnName(fn)
    if (name && (/^use[A-Z0-9]/.test(name) || (/^[A-Z]/.test(name) && containsJSX(fn)))) return fn
    fn = fn.getFunctionParent()
  }
  return null
}
function fnName(fn) {
  if (fn.node.id) return fn.node.id.name
  const par = fn.parentPath
  if (par && par.isVariableDeclarator() && par.node.id.type === 'Identifier') return par.node.id.name
  if (par && par.isCallExpression() && par.parentPath?.isVariableDeclarator()) return par.parentPath.node.id.name // memo(() => …)
  return null
}
const jsxCache = new WeakMap()
function containsJSX(fn) {
  if (jsxCache.has(fn.node)) return jsxCache.get(fn.node)
  let found = false
  fn.traverse({ JSXElement() { found = true }, JSXFragment() { found = true } })
  jsxCache.set(fn.node, found)
  return found
}
function insideSkippedTag(p) {
  let cur = p.parentPath
  while (cur) {
    if (cur.isJSXElement()) {
      const n = cur.node.openingElement.name
      if (n.type === 'JSXIdentifier' && SKIP_PARENT_TAGS.has(n.name)) return true
    }
    cur = cur.parentPath
  }
  return false
}
function onlyThroughExpressions(p) {
  // StringLiteral reachable from a JSXExpressionContainer via conditional/logical/parens only.
  // The container must be a JSX child or the value of a text-type attribute —
  // className={cond ? 'a' : 'b'} and stroke={… 'currentColor'} are NOT copy.
  let cur = p.parentPath
  while (cur) {
    if (cur.isJSXExpressionContainer()) {
      const par = cur.parentPath
      if (par.isJSXAttribute()) return ATTRS.has(par.node.name.name)
      return !insideSkippedTag(cur) // <style>{'.x{…}'}</style> is CSS, not copy
    }
    if (cur.isConditionalExpression() || cur.isLogicalExpression() || cur.isParenthesizedExpression() || cur.isTSAsExpression()) { cur = cur.parentPath; continue }
    return false
  }
  return false
}
const CSS_WORDS = new Set(['currentColor', 'none', 'inherit', 'transparent', 'auto', 'inline', 'block', 'flex', 'grid', 'hidden', 'absolute', 'relative', 'fixed', 'sticky'])
function looksLikeClasses(s) {
  // "text-gray-900 dark:text-gray-100", "pl-8 mt-2", "h-full": every token is a utility class.
  const toks = s.trim().split(/\s+/)
  return toks.length > 0 && toks.every((t) => /^!?-?[a-z][a-z0-9]*(?:-[a-z0-9\[\]#%./]+)+(?:\/[0-9]+)?$/.test(t) || /^[a-z0-9-]+:[a-z0-9:\-\[\]#%./]+$/.test(t))
}

function processFile(file) {
  const rel = path.relative(SRC, file).split(path.sep).join('/')
  const src = fs.readFileSync(file, 'utf8')
  if (!FORCE && /useTranslation\(/.test(src)) return { rel, skippedFile: 'already keyed' }
  const base = path.basename(file).replace(/\.tsx?$/, '')
  const prior = EXISTING[base] || {}
  let ast
  try {
    ast = parse(src, { sourceType: 'module', plugins: ['jsx', 'typescript'], ranges: true, attachComment: false })
  } catch (e) {
    return { rel, skippedFile: 'parse error: ' + e.message }
  }

  const edits = []           // {start, end, text}
  const catalogue = {}       // key -> english
  // Seed from the existing catalogue so a re-run reuses the key for identical
  // text and never hands a NEW text an existing key's slug (that would silently
  // change what an already-wired t() call says).
  const byText = new Map(Object.entries(prior).map(([k, v]) => [v, k]))   // english -> key
  const used = new Set(Object.keys(prior))
  const needHook = new Map() // component fn path -> hook variable name ('t' unless it collides)
  const pending = []         // deferred call-site edits: {start, end, fn, key, wrap, scope, extra}
  let needI18n = false
  const skipped = { template: 0, concat: 0 }
  let lastImportEnd = 0

  const keyFor = (text) => {
    const norm = text.replace(/\s+/g, ' ').trim()
    if (byText.has(norm)) return byText.get(norm)
    const k = slug(norm, used)
    byText.set(norm, k); catalogue[k] = norm
    return k
  }
  // Call sites are recorded first and rendered after traversal, because the
  // hook's variable name for a component is only known once every usage site
  // has been seen: `.map(t => …)` or `const t = transcript` inside the
  // component would shadow a hook named `t`, so that component gets `tr`.
  const record = (p, key, wrap, start = p.node.start, end = p.node.end, extra = '') => {
    const fn = componentScope(p)
    if (fn) {
      if (!needHook.has(fn)) needHook.set(fn, null)
      pending.push({ start, end, fn, key, wrap, scope: p.scope, extra })
    } else {
      needI18n = true
      edits.push({ start, end, text: wrap(`i18n.t('${NS}:${base}.${key}'${extra})`) })
    }
  }
  // `Hello ${name}, ${n} items` -> t('key', { name, n }) with "Hello {{name}}, {{n}} items"
  const recordTemplate = (p, wrap) => {
    const exprs = p.node.expressions
    const names = []
    let text = ''
    p.node.quasis.forEach((q, i) => {
      text += q.value.cooked
      if (i < exprs.length) {
        const e = exprs[i]
        let name = e.type === 'Identifier' ? e.name
          : e.type === 'MemberExpression' && e.property.type === 'Identifier' && !e.computed ? e.property.name
          : `v${i}`
        name = name.replace(/[^A-Za-z0-9_]/g, '_')
        while (names.some((n) => n.name === name)) name = `${name}_${i}`
        names.push({ name, src: src.slice(e.start, e.end) })
        text += `{{${name}}}`
      }
    })
    if (!isTranslatable(text.replace(/\{\{[^}]+\}\}/g, 'x'))) return
    const key = keyFor(text)
    const extra = `, { ${names.map((n) => (n.name === n.src ? n.name : `${n.name}: ${n.src}`)).join(', ')} }`
    record(p, key, wrap, p.node.start, p.node.end, extra)
  }
  const add = (p, text, wrap) => {
    if (!isTranslatable(text)) return
    record(p, keyFor(text), wrap)
  }

  traverse(ast, {
    ImportDeclaration(p) { lastImportEnd = Math.max(lastImportEnd, p.node.end) },
    JSXText(p) {
      const raw = p.node.value
      if (!isTranslatable(raw) || insideSkippedTag(p)) return
      // preserve leading/trailing whitespace outside the wrapped call
      const lead = raw.match(/^\s*/)[0], trail = raw.match(/\s*$/)[0]
      const inner = raw.slice(lead.length, raw.length - trail.length)
      const key = keyFor(inner.replace(/&apos;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&nbsp;/g, ' '))
      record(p, key, (c) => `{${c}}`, p.node.start + lead.length, p.node.end - trail.length)
    },
    JSXAttribute(p) {
      const name = p.node.name.name
      if (!ATTRS.has(name) || !p.node.value || p.node.value.type !== 'StringLiteral') return
      const lit = p.get('value')
      add(lit, lit.node.value, (c) => `{${c}}`)
    },
    StringLiteral(p) {
      if (p.parentPath.isJSXAttribute() || p.parentPath.isImportDeclaration() || p.parentPath.isTSLiteralType()) return
      const par = p.parentPath
      // {'text'} / {cond ? 'A' : 'B'} inside JSX
      if (onlyThroughExpressions(p)) { add(p, p.node.value, (c) => c); return }
      // toast.success('…'), alert('…'), setError('…'), new Error('…')
      if (par.isCallExpression() && par.node.arguments[0] === p.node) {
        const callee = par.node.callee
        const isToast = callee.type === 'MemberExpression' && callee.object.type === 'Identifier' && callee.object.name === 'toast' && TOAST.has(callee.property.name)
        const isBareToast = callee.type === 'Identifier' && callee.name === 'toast'
        const isNamed = callee.type === 'Identifier' && CALLS.has(callee.name)
        const isWinConfirm = callee.type === 'MemberExpression' && callee.object.name === 'window' && ['confirm', 'alert'].includes(callee.property.name)
        if (isToast || isBareToast || isNamed || isWinConfirm) { add(p, p.node.value, (c) => c); return }
      }
      if (par.isNewExpression() && par.node.callee.name === 'Error' && par.node.arguments[0] === p.node) { add(p, p.node.value, (c) => c); return }
      // { label: '…' } object properties
      if (par.isObjectProperty() && par.node.value === p.node && !par.node.computed) {
        const k = par.node.key.type === 'Identifier' ? par.node.key.name : par.node.key.value
        if (PROPS.has(k) || (k === 'name' && /^[A-Z].*\s/.test(p.node.value))) { add(p, p.node.value, (c) => c); return }
      }
    },
    TemplateLiteral(p) {
      if (p.parentPath.isTaggedTemplateExpression()) return
      const par = p.parentPath
      const inJsx = onlyThroughExpressions(p)
      let isCopyCall = false
      if (par.isCallExpression() && par.node.arguments[0] === p.node) {
        const callee = par.node.callee
        isCopyCall = (callee.type === 'MemberExpression' && callee.object.type === 'Identifier' && callee.object.name === 'toast' && TOAST.has(callee.property.name))
          || (callee.type === 'Identifier' && (callee.name === 'toast' || CALLS.has(callee.name)))
          || (callee.type === 'MemberExpression' && callee.object.name === 'window' && ['confirm', 'alert'].includes(callee.property.name))
      }
      const isCopyProp = par.isObjectProperty() && par.node.value === p.node && !par.node.computed
        && PROPS.has(par.node.key.type === 'Identifier' ? par.node.key.name : par.node.key.value)
      const isAttr = par.isJSXExpressionContainer() && par.parentPath.isJSXAttribute() && ATTRS.has(par.parentPath.node.name.name)
      if (!(inJsx || isCopyCall || isCopyProp || isAttr)) return
      if (p.node.expressions.length === 0) {
        const text = p.node.quasis[0].value.cooked
        if (isTranslatable(text)) add(p, text, (c) => c)
        return
      }
      recordTemplate(p, (c) => c)
    },
    ArrayExpression(p) {
      const par = p.parentPath
      if (!(par.isObjectProperty() && par.node.value === p.node && !par.node.computed)) return
      const k = par.node.key.type === 'Identifier' ? par.node.key.name : par.node.key.value
      if (!ARRAY_PROPS.has(k)) return
      for (const el of p.get('elements')) if (el.isStringLiteral()) add(el, el.node.value, (c) => c)
    },
    BinaryExpression(p) {
      if (p.node.operator === '+' && (p.node.left.type === 'StringLiteral' || p.node.right.type === 'StringLiteral') && onlyThroughExpressions(p)) skipped.concat++
    },
  })

  if (edits.length === 0 && pending.length === 0) return { rel, count: 0, skipped }
  // Count strings BEFORE hook/import bookkeeping is added to `edits`. The old
  // formula subtracted needHook.size after the fact, which went to 0 for files
  // whose components already had the hook (second pass) and made the catalogue
  // merge skip them while the source was still rewritten.
  const stringCount = edits.length + pending.length

  // Pick the hook variable per component: 't' unless some usage site (or the
  // component scope itself) already binds it; then 'tr', then 'tt'.
  const alreadyHooked = new Set() // fns that already declare a `ui` hook (second pass)
  for (const fn of needHook.keys()) {
    const sites = pending.filter((s) => s.fn === fn)
    // Re-run on a keyed file: the component already has `const { t } = useTranslation('ui')`
    // (or `t: tr`). Reuse that binding instead of injecting a second hook.
    const bodySrc = src.slice(fn.node.start, fn.node.end)
    const m = bodySrc.match(/const \{ t(?:: (\w+))? \} = useTranslation\('ui'\)/)
    if (m) { needHook.set(fn, m[1] || 't'); alreadyHooked.add(fn); continue }
    const taken = (name) => fn.scope.hasBinding(name) || sites.some((s) => s.scope.hasBinding(name))
    needHook.set(fn, ['t', 'tr', 'tt', 't_'].find((n) => !taken(n)) || 't__')
  }
  for (const s of pending) {
    const name = needHook.get(s.fn)
    edits.push({ start: s.start, end: s.end, text: s.wrap(`${name}('${NS}:${base}.${s.key}'${s.extra || ''})`) })
  }
  // Hook injections: after the opening brace of each component body.
  for (const [fn, tName] of needHook) {
    if (alreadyHooked.has(fn)) continue
    const body = fn.node.body
    if (body.type !== 'BlockStatement') continue // concise arrow — not expected (0 arrow components)
    const decl = tName === 't' ? `const { t } = useTranslation('${NS}')` : `const { t: ${tName} } = useTranslation('${NS}')`
    edits.push({ start: body.start + 1, end: body.start + 1, text: `\n  ${decl}` })
  }
  // Imports
  const imports = []
  if (needHook.size && !/from 'react-i18next'/.test(src)) imports.push(`import { useTranslation } from 'react-i18next'`)
  if (needI18n && !/from '@\/i18n'/.test(src)) imports.push(`import i18n from '@/i18n'`)
  // No existing imports (e.g. lib/constants.ts): put ours at the top with a blank line after.
  if (imports.length) edits.push({ start: lastImportEnd, end: lastImportEnd, text: lastImportEnd ? '\n' + imports.join('\n') : imports.join('\n') + '\n\n' })

  // Apply edits back-to-front so positions stay valid.
  edits.sort((a, b) => b.start - a.start || b.end - a.end)
  let out = src
  for (const e of edits) out = out.slice(0, e.start) + e.text + out.slice(e.end)
  if (APPLY) fs.writeFileSync(file, out)
  return { rel, base, count: stringCount, catalogue, skipped, hooks: needHook.size, moduleLevel: needI18n }
}

const files = (filesArg ? filesArg.map((f) => path.resolve(ROOT, f)) : listFiles())
const results = files.map(processFile)
const catalogue = {}
let total = 0, skippedT = 0, skippedC = 0
for (const r of results) {
  if (r.skippedFile || !r.count) continue
  total += r.count; skippedT += r.skipped.template; skippedC += r.skipped.concat
  catalogue[r.base] = Object.assign(catalogue[r.base] || {}, r.catalogue)
}
if (emitArg && !APPLY) {
  fs.writeFileSync(emitArg, JSON.stringify(catalogue, null, 2) + '\n')
  console.log('emitted catalogue for', Object.keys(catalogue).length, 'files ->', emitArg)
}
if (APPLY) {
  const existing = EXISTING
  for (const [f, keys] of Object.entries(catalogue)) existing[f] = Object.assign(existing[f] || {}, keys)
  fs.writeFileSync(enPath, JSON.stringify(existing, null, 2) + '\n')
}
const report = results.filter((r) => !r.skippedFile).sort((a, b) => (b.count || 0) - (a.count || 0))
console.log(`${APPLY ? 'APPLIED' : 'DRY RUN'}: ${total} strings in ${report.filter((r) => r.count).length} files; skipped ${skippedT} template literals + ${skippedC} concatenations (hand follow-up)`)
console.log('files skipped (already keyed / parse error):', results.filter((r) => r.skippedFile).map((r) => `${r.rel} [${r.skippedFile}]`).join(', '))
console.log('top 12:', report.slice(0, 12).map((r) => `${r.rel}=${r.count}`).join('  '))
if (!APPLY) {
  const sample = Object.entries(catalogue).slice(0, 2)
  for (const [f, keys] of sample) console.log(`sample ${f}:`, JSON.stringify(Object.fromEntries(Object.entries(keys).slice(0, 6)), null, 0))
}
