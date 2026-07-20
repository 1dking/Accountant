# O-Brain Pricing Lab — QA Test Report

Date: 2026-07-19 · Target: http://localhost:5174 (Vite dev server, already running) · Tester: automated QA (Playwright headless Chromium, 1440x900)

---

## 1. Stack Report

| Item | Value |
|---|---|
| Language | TypeScript (strict mode; `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`) |
| Framework | React 18.3.1 (function components + hooks; no router — view switching via local `useState` in `App.tsx`) |
| Build tool | Vite 6.4.3 (`@vitejs/plugin-react` 4.7.0, Babel-based) |
| Package manager | pnpm 10.30.3 — `pnpm-lock.yaml` present (only lockfile) |
| Styling | Single plain-CSS file `src/styles.css` (141 lines); no Tailwind, no CSS-in-JS, no CSS modules |
| Charting | Recharts 2.15.4 |
| State management | Local component state only (`useState`/`useMemo`); no Redux/Zustand/Context store |
| Tests | Vitest 2.1.9 (`pnpm test` → `vitest run`), unit tests for pricing math in `src/lib/pricing.test.ts` (8 tests). Vitest resolves its own vite@5.4.21 internally |
| Typecheck | `tsc --noEmit` (typescript 5.9.3 installed; package.json asks ^5.6.3) — also runs as part of `build` |
| Linter | **Not configured** — verified: no ESLint/Prettier config files, no eslint in package.json or pnpm-lock.yaml, no `lint` script |
| Node | v25.2.1 |

### Notable dependencies (exact installed versions from node_modules/.pnpm)
- react 18.3.1, react-dom 18.3.1
- recharts 2.15.4
- typescript 5.9.3
- vite 6.4.3 (app) / 5.4.21 (vitest internal)
- vitest 2.1.9
- @vitejs/plugin-react 4.7.0
- @types/react 18.3.31, @types/react-dom 18.3.7

### Size
- 11 `.ts`/`.tsx` files under `src/`, 920 LOC total (plus 141 lines CSS, 12 lines index.html)
- 16 tracked source/config files at root + src

### Folder structure (2 levels, excl. node_modules/dist)
```
pricing-lab/
├── index.html
├── package.json / pnpm-lock.yaml / tsconfig.json / vite.config.ts / .gitignore
└── src/
    ├── App.tsx          (nav + view switcher)
    ├── main.tsx         (entry)
    ├── data.ts          (demo dataset: tiers, accounts, revenue series)
    ├── styles.css
    ├── lib/             (pricing.ts — simulator model; pricing.test.ts)
    └── views/           (WhatsWorking, TierFunnel, ModuleOutcome, ValueMetric, Revenue, Simulator)
```
Dev server pinned to port 5174 with `strictPort: true` in `vite.config.ts`.

---

## 2. Build & Boot

| Step | Result | Notes |
|---|---|---|
| `pnpm install` | PASS | No-op ("Done in 745ms"). pnpm 10 prints an advisory that esbuild's postinstall build script was ignored (`pnpm approve-builds`) — informational, dev/build both work |
| `pnpm run typecheck` (`tsc --noEmit`) | PASS | 0 errors |
| `pnpm test` (`vitest run`) | PASS | 1 file, 8/8 tests passed (src/lib/pricing.test.ts, 7ms) |
| `pnpm run build` (`tsc --noEmit && vite build`) | PASS | 654 modules → dist. **Warning:** main JS chunk 584.24 kB (>500 kB limit); Recharts is not code-split |
| `pnpm run lint` | not configured | No lint script, no ESLint config anywhere in repo — recorded as "not configured", not a failure |
| Dev server `curl http://localhost:5174/` | PASS | Returns HTML, `<title>O-Brain Pricing Lab</title>` |

---

## 3. Browser Test — Six-View Status

Headless Chromium 1440x900. Each view: nav click → 600ms wait → assert `[data-testid="view-<key>"]` exists with non-trivial innerText → full-page screenshot.

| View | data-view | Status | innerText | Screenshot |
|---|---|---|---|---|
| What's Working | working | **PASS** | 807 chars | qa-screenshots/working.png |
| Tier Funnel | funnel | **PASS** | 569 chars | qa-screenshots/funnel.png |
| Module → Outcome | modules | **PASS** | 973 chars | qa-screenshots/modules.png |
| Value-Metric Explorer | value | **RENDERS-WITH-ERRORS** | 644 chars (972 after interaction) | qa-screenshots/value.png, value-pagesPublished.png |
| Revenue | revenue | **PASS** | 417 chars | qa-screenshots/revenue.png |
| Pricing Simulator | simulator | **PASS** | 911 chars | qa-screenshots/simulator.png, simulator-after.png |

"RENDERS-WITH-ERRORS" qualifier: the Value view renders and stays fully interactive on its default metric with zero console output; the errors appear only after clicking the "Pages published" metric button (details below).

### Console errors / warnings observed
- **94 identical React console errors**, all during the Value-Metric "Pages published" interaction, none anywhere else:
  `Warning: Encountered two children with the same key, 'tick-1-131.2901326893696-131.2901326893696'...` — component stack: Recharts `CartesianAxis` → `XAxis` inside `ValueMetric` (`src/views/ValueMetric.tsx`).
- pageerror events: **none**
- Failed network requests: **none**
- Non-Vite or `/api/*` requests: **none** (21 total requests, all Vite dev assets — as expected for a backend-less app)

### Simulator interaction — live recalculation PROVEN

| Reading | Value |
|---|---|
| sim-mrr initial (baseline) | **$104,934** |
| sim-nrr initial | **94.7%** |
| After `page.fill('[data-testid="price-pro"]', '59')` → sim-mrr | **$102,755** — CHANGED ✔ (sim-nrr also moved 94.7% → 94.6%) |
| After moving `[data-testid="slider-expansion"]` to max (0.05) → sim-nrr | **139.0%** — CHANGED ✔ (sim-mrr rose to $123,006) |
| Independent keyboard check (focus slider, 12× ArrowRight to max) → sim-nrr | 94.7% → **138.2%** — CHANGED ✔ |

Both core interactions recalculate live. No broken core interaction.

Methodology note (harness, not app): a first attempt that set `slider.value` directly via `$eval` + `dispatchEvent('input')` did NOT register — React 18's internal value tracker dedupes direct value assignment, so the synthetic event was ignored. Re-testing with the native `HTMLInputElement` value setter, and independently with real keyboard input, both updated NRR correctly. The app is fine; automated tests against this app must use the native-setter trick or keyboard events for range inputs.

### Value-Metric Explorer interaction
Clicked `[data-metric="pagesPublished"]`: view still renders (innerText 972 chars, chart + score cards intact — see value-pagesPublished.png) but emits the 94 duplicate-key console errors above and the X-axis tick labels visibly overlap/collide (e.g. "36 38 40 42 44 47 48 53 55 57 50 60" rendered on top of each other). Functionality unaffected; switching metrics keeps working.

---

## 4. Prioritized Fix List

Nothing blocking was found. `install`, `typecheck`, `test` (8/8), and `build` all pass; all six views render; both simulator interactions recalculate live; zero page errors, zero failed requests, zero unexpected network calls.

1. **[Bug — cosmetic/console noise, highest priority of what exists]** Duplicate Recharts axis ticks on the Value-Metric sqrt X-axis.
   File: `src/views/ValueMetric.tsx` (XAxis, ~line 53-57: `type="number" dataKey={metric} scale="sqrt"`).
   Cause: with `scale="sqrt"` and the `pagesPublished` data domain, Recharts 2.15.4 generates duplicate tick values (key `tick-1-131.29…-131.29…`), producing 94 React duplicate-key warnings and visually overlapping X-axis labels.
   Fix: supply explicit `ticks`/`tickCount` (or `domain`) for the sqrt axis, or drop `scale="sqrt"` in favor of a linear or log axis with a tick formatter.
2. **[Perf — cosmetic]** Production bundle is one 584 kB chunk (Vite warns >500 kB) because Recharts is bundled into the main chunk. Fix: `build.rollupOptions.output.manualChunks` (split recharts/vendor) or lazy-load chart views. File: `vite.config.ts`.
3. **[Polish — cosmetic, minor]** Value-Metric Y-axis renders unit after the number as `200$` (Recharts `unit="$"` suffixes the tick). File: `src/views/ValueMetric.tsx` YAxis — use `tickFormatter={(v) => '$' + v}` instead of `unit="$"` for conventional `$200` display.
4. **[Tooling — non-blocking]** No linter is configured (no ESLint, no lint script). Not a defect for a lab project, but noted for completeness.

---

## Artifacts
- Report: `C:\Users\Owner\Desktop\Dev\Accountant\pricing-lab\TEST_REPORT.md`
- Screenshots: `C:\Users\Owner\Desktop\Dev\Accountant\pricing-lab\qa-screenshots\` — working.png, funnel.png, modules.png, value.png, revenue.png, simulator.png, simulator-after.png, value-pagesPublished.png
