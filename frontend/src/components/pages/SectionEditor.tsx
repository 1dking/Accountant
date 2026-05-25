/**
 * SectionEditor — Pages v2 inline section-based editor.
 *
 * Replaces the iframe-based VisualEditor for v2 pages (those with a
 * generation_session_id). Reads from page.sections_json directly,
 * writes structured edits back through the PATCH/POST/DELETE
 * section endpoints. Closes bug #10's architectural mismatch
 * (Visual editor wrote opaque html_content; SectionEditor writes
 * sections_json[i].edited_html — section structure is preserved).
 *
 * Architecture:
 *   - One <SectionBlock> per section in sections_json
 *   - Each block renders the section in its own iframe sandbox
 *     (Tailwind CDN loaded once per iframe; no cross-section style
 *     bleed; no whole-page nested-DOCTYPE bug)
 *   - Single-click → caret on text elements (no dblclick gate)
 *   - On blur of contentEditable → PATCH /sections/{idx} with the
 *     iframe's cleaned body innerHTML as edited_html
 *   - Hover the block → floating controls (Refine AI / Delete /
 *     Duplicate / Revert)
 *   - Background CSS edits via the existing element-selected →
 *     parent-side toolbar pattern, but writes inline styles in
 *     the iframe DOM (captured in edited_html) instead of appending
 *     global CSS rules to page.css_content. Closes the font-size
 *     nth-child !important bug.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Loader2, Sparkles, Trash2, Copy, RotateCcw, X, Replace, Plus,
  Film, Image as ImageIcon, GripVertical, Wand2, Play, Palette,
} from 'lucide-react'
import {
  DndContext, PointerSensor, KeyboardSensor, useSensor, useSensors,
  closestCenter, type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext, useSortable, verticalListSortingStrategy,
  sortableKeyboardCoordinates, arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { pagesApi } from '@/api/pages'
import VariantPickerModal from './VariantPickerModal'
import MediaPickerModal, { type MediaSlotKind } from './MediaPickerModal'
import AnimationPickerModal from './AnimationPickerModal'
import StyleEditorDrawer from './StyleEditorDrawer'
import './section-editor.css'

// Media tokens — kept in sync with backend variants.py MEDIA_TOKENS
// and EMBED_TOKENS whitelists. When jsx_content contains {{TOKEN}}
// for one of these, we render a media-edit pill so the user can swap
// the URL without editing the underlying template.
//
// Element-level tokens (VIDEO_EMBED, MEDIA_EMBED) expand at compile
// time to full <iframe>/<video>/<img> markup based on the URL's
// pattern — a single slot accepts YouTube, Vimeo, mp4, or images.
const MEDIA_TOKEN_PATTERN = /\{\{\s*(VIDEO_URL|VIDEO_POSTER_URL|IMAGE_URL|LOGO_URL|MEDIA_URL|VIDEO_EMBED|MEDIA_EMBED)\s*\}\}/g

// Each token's edit pill writes to media_overrides[URL_KEY]. Element
// tokens map to a backing URL key; plain URL tokens are their own key.
const TOKEN_TO_URL_KEY: Record<string, string> = {
  VIDEO_EMBED: 'VIDEO_URL',
  MEDIA_EMBED: 'MEDIA_URL',
  VIDEO_URL: 'VIDEO_URL',
  VIDEO_POSTER_URL: 'VIDEO_POSTER_URL',
  IMAGE_URL: 'IMAGE_URL',
  LOGO_URL: 'LOGO_URL',
  MEDIA_URL: 'MEDIA_URL',
}

function detectMediaTokens(html: string): string[] {
  if (!html) return []
  const seen = new Set<string>()
  let m: RegExpExecArray | null
  MEDIA_TOKEN_PATTERN.lastIndex = 0
  while ((m = MEDIA_TOKEN_PATTERN.exec(html)) !== null) {
    seen.add(m[1])
  }
  return Array.from(seen)
}

function tokenKindFor(token: string): MediaSlotKind {
  if (token === 'VIDEO_URL' || token === 'VIDEO_EMBED') return 'video'
  if (token === 'MEDIA_URL' || token === 'MEDIA_EMBED') return 'any'
  if (token === 'LOGO_URL') return 'image'
  return 'image'
}

function tokenIcon(token: string) {
  if (token === 'VIDEO_URL' || token === 'VIDEO_EMBED') return <Film className="h-3 w-3" />
  return <ImageIcon className="h-3 w-3" />
}

function tokenLabel(token: string): string {
  // User-facing pill label. Element tokens display as their semantic
  // role rather than the raw token name.
  if (token === 'VIDEO_EMBED') return 'VIDEO'
  if (token === 'MEDIA_EMBED') return 'MEDIA'
  return token
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PageSection {
  id?: string
  type?: string
  title?: string
  summary?: string
  jsx_content?: string
  edited_html?: string | null
  style_overrides?: Record<string, unknown> | null
  media_overrides?: Record<string, string> | null
  /** Commit 4B per-section animation preset + config. preset 'none'
   *  means explicitly no animation; absent means use the variant's
   *  default_animations. */
  animations?: {
    preset?: string
    config?: Record<string, unknown>
    applied_at?: string
    // 4A flat shape compatibility — variant defaults may still live here
    scroll_reveal?: unknown[]
    counter_up?: unknown[]
    parallax?: unknown[]
  } | null
  metadata?: Record<string, any>
}

interface SectionEditorProps {
  pageId: string
  sections: PageSection[]
  /** Called after any successful section mutation. The parent should
   *  refetch the page detail and re-render with updated sections. */
  onChanged: () => void
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * JSX → HTML normalization, mirrors backend _jsx_to_html so the inline
 * editor renders the same output as the published page. Without this
 * the iframe shows the JSX literal `className="..."` as a no-op
 * attribute and Tailwind doesn't apply.
 */
/** Client-side media-token substitution for the iframe preview.
 *  Mirrors substitute_media_tokens() + render_media_embed() in backend
 *  variants.py so the editor preview matches what compile_page produces.
 *  Polymorphic element rendering for {{VIDEO_EMBED}} / {{MEDIA_EMBED}}
 *  tokens — URL pattern decides iframe / video / img. */
function classifyMediaUrl(url: string): 'youtube' | 'vimeo' | 'video' | 'image' | 'unknown' {
  if (!url) return 'unknown'
  if (/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/|v\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/.test(url)) return 'youtube'
  if (/^[A-Za-z0-9_-]{11}$/.test(url)) return 'youtube'
  if (/vimeo\.com\/(?:video\/)?(\d+)/.test(url)) return 'vimeo'
  const base = url.split('?')[0].split('#')[0].toLowerCase()
  if (/\.(?:mp4|webm|ogg|mov)$/.test(base)) return 'video'
  if (/\.(?:jpe?g|png|webp|gif|svg|avif)$/.test(base)) return 'image'
  return 'unknown'
}

function renderMediaEmbed(url: string, poster?: string, kind: 'video' | 'media' = 'media'): string {
  if (!url) return ''
  const detected = classifyMediaUrl(url)
  const escAttr = (s: string) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const u = escAttr(url)
  if (detected === 'youtube' || detected === 'vimeo') {
    return `<iframe src="${u}" class="absolute inset-0 w-full h-full" frameborder="0" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe>`
  }
  if (detected === 'video') {
    const p = poster ? ` poster="${escAttr(poster)}"` : ''
    return `<video autoplay muted loop playsinline${p} class="absolute inset-0 w-full h-full object-cover"><source src="${u}" /></video>`
  }
  if (detected === 'image') {
    return `<img src="${u}" alt="" class="absolute inset-0 w-full h-full object-cover" />`
  }
  // Unknown — slot-kind-dependent default.
  if (kind === 'video') {
    return `<iframe src="${u}" class="absolute inset-0 w-full h-full" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen></iframe>`
  }
  return `<img src="${u}" alt="" class="absolute inset-0 w-full h-full object-cover" />`
}

const _EMBED_TO_URL_KEY: Record<string, string> = {
  VIDEO_EMBED: 'VIDEO_URL',
  MEDIA_EMBED: 'MEDIA_URL',
}

function substituteMediaTokens(html: string, mediaProps: Record<string, string>): string {
  if (!html) return html
  return html.replace(/\{\{\s*([A-Z0-9_]+)\s*\}\}/g, (m, key: string) => {
    // Element tokens — expand to full polymorphic markup.
    if (key === 'VIDEO_EMBED' || key === 'MEDIA_EMBED') {
      const urlKey = _EMBED_TO_URL_KEY[key]
      const url = mediaProps[urlKey]
      if (!url) return m
      return renderMediaEmbed(
        url,
        mediaProps['VIDEO_POSTER_URL'],
        key === 'VIDEO_EMBED' ? 'video' : 'media',
      )
    }
    // URL tokens — straight string substitution.
    const allowed = new Set(['VIDEO_URL', 'VIDEO_POSTER_URL', 'IMAGE_URL', 'LOGO_URL', 'MEDIA_URL'])
    if (!allowed.has(key)) return m
    const v = mediaProps[key]
    return v ? v : m
  })
}

function jsxToHtml(jsx: string): string {
  if (!jsx) return ''
  return jsx
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, '')
    .replace(/\bclassName=/g, 'class=')
    .replace(/\bhtmlFor=/g, 'for=')
    .replace(/\btabIndex=/g, 'tabindex=')
}

function sectionBodyHtml(section: PageSection): string {
  if (section.edited_html) return section.edited_html
  return jsxToHtml(section.jsx_content || '')
}

// ---------------------------------------------------------------------------
// Commit 6 — client-side mirror of backend compile_section_styles.
// Used to derive the live-preview CSS string the drawer posts into the
// iframe on every control change.
//
// Commit 6.0.1 — accepts sectionId and prefixes every rule with
// "#section-{sid}". The iframe-side EDITOR_SCRIPT assigns this same id
// to <body>, so the selector resolves and — critically — beats Tailwind
// utility classes on specificity (id selector wins over class). Mirrors
// compile_page output byte-for-byte so editor preview = published render.
// ---------------------------------------------------------------------------

const CSS_VALUE_REJECT = /[{};<>]/

function camelToKebab(name: string): string {
  return name.replace(/([A-Z])/g, '-$1').toLowerCase()
}

export function compileStyleOverridesPreview(
  overrides: Record<string, Record<string, string | number>> | null | undefined,
  sectionId: string,
): string {
  if (!overrides) return ''
  const scope = `#section-${sectionId}`
  const rules: string[] = []
  for (const selector of Object.keys(overrides)) {
    const props = overrides[selector]
    if (!props || typeof props !== 'object') continue
    const decls: string[] = []
    for (const key of Object.keys(props)) {
      const val = props[key]
      const safe = typeof val === 'number'
        ? String(val)
        : (typeof val === 'string' && !CSS_VALUE_REJECT.test(val) ? val.trim() : null)
      if (!safe) continue
      let v = safe
      const cssProp = camelToKebab(key)
      if (cssProp === 'font-family' && v.includes(' ')
          && !v.startsWith('"') && !v.startsWith("'")) {
        v = `"${v}"`
      }
      decls.push(`  ${cssProp}: ${v};`)
    }
    if (!decls.length) continue
    // Selector mapping mirrors backend _compile_section_styles:
    //   "section" → "#section-{sid}, #section-{sid} > section"
    //   anything else → "#section-{sid} {selector}"
    // The wrapper id is on <body> in the iframe, set by EDITOR_SCRIPT.
    const target = selector === 'section'
      ? `${scope}, ${scope} > section`
      : `${scope} ${selector}`
    rules.push(target + ' {\n' + decls.join('\n') + '\n}')
  }
  return rules.join('\n')
}

// ---------------------------------------------------------------------------
// SectionBlock — one iframe sandbox per section
// ---------------------------------------------------------------------------

interface SectionBlockProps {
  pageId: string
  section: PageSection
  index: number
  onChanged: () => void
  onRequestChangeVariant: (idx: number, category: string) => void
  /** dnd-kit listeners + attributes for the drag handle. Attached
   *  to a specific element (the ⋮⋮ grip icon) so the iframe and
   *  text-editing interactions stay independent of drag. */
  dragHandleProps?: {
    attributes: React.HTMLAttributes<HTMLElement>
    listeners: Record<string, (e: React.SyntheticEvent) => void>
  }
  /** True while this section is the active drag target — for fade
   *  styling so the user sees what's moving. */
  isDragging?: boolean
}

const TAILWIND_CDN = 'https://cdn.tailwindcss.com'
const GSAP_CDN = 'https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js'

/**
 * Iframe-side animation runtime — Commit 4B.1.
 *
 * Adds an in-place replay of the section's animation preset inside
 * the Visual editor's per-section iframe. Public-page (compile_page)
 * runtime still owns the scroll-driven path; this is a stripped-down
 * version that:
 *   - Reads window.__sectionAnimation (injected by srcdoc) for the
 *     preset + config
 *   - Exposes window.replayAnimation() which the parent triggers via
 *     postMessage on preset/config change or Replay button click
 *   - Skips replay when document.activeElement is contentEditable
 *     (queues for after blur)
 *   - Honors prefers-reduced-motion with explicit final state
 *
 * Tier 1 entry presets play once in-place. Tier 2 scrub presets
 * simulate a 0→1 scroll-through over ~2s so the user sees the range
 * without actually scrolling.
 */
const ANIMATION_RUNTIME_SCRIPT = `
<script>
(function () {
  var pendingReplay = false;

  // Entry preset library mirrors backend animation_presets.py Tier 1.
  var ENTRY_PRESETS = {
    fade_up:          {from: {y: 40, opacity: 0},  to: {y: 0, opacity: 1}},
    fade_down:        {from: {y: -40, opacity: 0}, to: {y: 0, opacity: 1}},
    slide_left:       {from: {x: -60, opacity: 0}, to: {x: 0, opacity: 1}},
    slide_right:      {from: {x: 60, opacity: 0},  to: {x: 0, opacity: 1}},
    scale_in:         {from: {scale: 0.85, opacity: 0}, to: {scale: 1, opacity: 1}},
    scale_out:        {from: {scale: 1.15, opacity: 0}, to: {scale: 1, opacity: 1}},
    blur_in:          {from: {filter: 'blur(12px)', opacity: 0}, to: {filter: 'blur(0px)', opacity: 1}},
    rotate_in:        {from: {rotation: -8, opacity: 0}, to: {rotation: 0, opacity: 1}},
    stagger_children: {from: {y: 30, opacity: 0}, to: {y: 0, opacity: 1}, target: 'children'},
  };

  function isEditing() {
    var el = document.activeElement;
    return !!(el && el.isContentEditable);
  }

  function reduceMotion() {
    return window.matchMedia
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function setFinalState() {
    // Strip any inline transforms/opacity/filter left by a previous
    // animation. Effectively a "settle" — section renders fully visible.
    var nodes = [document.body, ...document.body.querySelectorAll('*')];
    nodes.forEach(function (n) {
      n.style.opacity = '';
      n.style.transform = '';
      n.style.filter = '';
    });
  }

  function playEntry(presetId, cfg) {
    var preset = ENTRY_PRESETS[presetId];
    if (!preset || !window.gsap) return;
    var targets;
    if (preset.target === 'children') {
      var firstChild = document.body.firstElementChild;
      targets = firstChild ? Array.from(firstChild.children) : [];
    } else {
      targets = document.body.firstElementChild
        ? [document.body.firstElementChild]
        : [];
    }
    if (!targets.length) return;
    window.gsap.fromTo(targets, preset.from, Object.assign({}, preset.to, {
      duration: (cfg && cfg.duration) != null ? cfg.duration : 0.8,
      ease: (cfg && cfg.ease) || 'power2.out',
      delay: (cfg && cfg.delay) || 0,
      stagger: (cfg && cfg.stagger) || 0,
    }));
  }

  function playScrubSimulation(presetId, cfg) {
    // Editor doesn't have a real scroll context. Simulate the scroll
    // range as a 2s timeline so the user can see the motion character.
    if (!window.gsap) return;
    var target = document.body.firstElementChild;
    if (!target) return;
    if (presetId === 'parallax_bg') {
      window.gsap.fromTo(target, {y: 0}, {y: -80, duration: 2, ease: 'none', yoyo: true, repeat: 1});
    } else if (presetId === 'parallax_fg') {
      window.gsap.fromTo(target, {y: 0}, {y: 50, duration: 2, ease: 'none', yoyo: true, repeat: 1});
    } else if (presetId === 'scale_with_scroll') {
      window.gsap.fromTo(target, {scale: 0.9}, {scale: 1.1, duration: 2, ease: 'none', yoyo: true, repeat: 1});
    } else if (presetId === 'opacity_scrub') {
      var tl = window.gsap.timeline();
      tl.fromTo(target, {opacity: 0}, {opacity: 1, duration: 0.6})
        .to(target, {opacity: 1, duration: 0.8})
        .to(target, {opacity: 0, duration: 0.6})
        .to(target, {opacity: 1, duration: 0.3});  // settle at visible
    } else if (presetId === 'pin_and_scrub') {
      // Subtle scale wobble to communicate "section pins here"
      window.gsap.fromTo(target, {scale: 1, y: 0}, {scale: 0.98, y: -4, duration: 1, ease: 'power1.inOut', yoyo: true, repeat: 1});
    }
  }

  // ---------- Tier 4 hover effects in the editor iframe ----------
  // Apply hover listeners directly to the section (first body child)
  // so the user gets the effect when they hover the iframe. Listeners
  // are removed/re-attached as the animation spec changes.
  var hoverCleanup = null;
  function clearHoverListeners() {
    if (hoverCleanup) { try { hoverCleanup(); } catch (e) {} hoverCleanup = null; }
    var t = document.body.firstElementChild;
    if (t) {
      t.style.transition = '';
      t.style.transform = '';
      t.style.boxShadow = '';
      t.style.perspective = '';
      t.style.transformStyle = '';
      t.style.willChange = '';
    }
    // Remove any underline-draw style block we may have injected
    var s = document.getElementById('__se_hover_underline');
    if (s) s.remove();
  }
  function installHover(presetId, cfg) {
    var target = document.body.firstElementChild;
    if (!target) return;
    var hasHover = window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    function isEditing() {
      var el = document.activeElement;
      return !!(el && el.isContentEditable);
    }

    if (presetId === 'hover_lift') {
      var liftDur = (cfg && cfg.duration_ms) || 200;
      target.style.transition = 'transform ' + liftDur + 'ms cubic-bezier(0.32, 0.72, 0, 1), box-shadow ' + liftDur + 'ms cubic-bezier(0.32, 0.72, 0, 1)';
      target.style.willChange = 'transform';
      var onEnter = function () {
        if (isEditing()) return;
        target.style.transform = 'translateY(-' + ((cfg && cfg.translate_y) || 4) + 'px)';
        target.style.boxShadow = '0 12px 32px rgba(0,0,0,0.18), 0 4px 12px rgba(0,0,0,0.08)';
      };
      var onLeave = function () {
        target.style.transform = '';
        target.style.boxShadow = '';
      };
      target.addEventListener('mouseenter', onEnter, { passive: true });
      target.addEventListener('mouseleave', onLeave, { passive: true });
      hoverCleanup = function () {
        target.removeEventListener('mouseenter', onEnter);
        target.removeEventListener('mouseleave', onLeave);
      };

    } else if (presetId === 'hover_tilt' && hasHover) {
      var maxRot = (cfg && cfg.max_rotate) || 8;
      var ease = (cfg && cfg.ease) || 0.15;
      var trx = 0, tryy = 0, crx = 0, cryy = 0;
      var raf = null;
      target.style.perspective = '1000px';
      target.style.transformStyle = 'preserve-3d';
      target.style.willChange = 'transform';
      function loopT() {
        crx += (trx - crx) * ease;
        cryy += (tryy - cryy) * ease;
        target.style.transform = 'rotateX(' + crx.toFixed(2) + 'deg) rotateY(' + cryy.toFixed(2) + 'deg)';
        if (Math.abs(trx - crx) > 0.05 || Math.abs(tryy - cryy) > 0.05) {
          raf = requestAnimationFrame(loopT);
        } else { raf = null; }
      }
      var onMove = function (e) {
        if (isEditing()) return;
        var rect = target.getBoundingClientRect();
        var cx = rect.left + rect.width / 2;
        var cy = rect.top + rect.height / 2;
        tryy = ((e.clientX - cx) / (rect.width / 2)) * maxRot;
        trx = -((e.clientY - cy) / (rect.height / 2)) * maxRot;
        if (!raf) raf = requestAnimationFrame(loopT);
      };
      var onMoveLeave = function () {
        trx = 0; tryy = 0;
        if (!raf) raf = requestAnimationFrame(loopT);
      };
      target.addEventListener('mousemove', onMove, { passive: true });
      target.addEventListener('mouseleave', onMoveLeave, { passive: true });
      hoverCleanup = function () {
        target.removeEventListener('mousemove', onMove);
        target.removeEventListener('mouseleave', onMoveLeave);
        if (raf) cancelAnimationFrame(raf);
      };

    } else if (presetId === 'hover_magnetic' && hasHover) {
      var radius = (cfg && cfg.radius) || 120;
      var maxT = (cfg && cfg.max_translate) || 12;
      var easeM = (cfg && cfg.ease) || 0.15;
      var tx = 0, ty = 0, cxv = 0, cyv = 0;
      var rafM = null;
      target.style.willChange = 'transform';
      function loopM() {
        cxv += (tx - cxv) * easeM;
        cyv += (ty - cyv) * easeM;
        target.style.transform = 'translate3d(' + cxv.toFixed(2) + 'px,' + cyv.toFixed(2) + 'px,0)';
        if (Math.abs(tx - cxv) > 0.1 || Math.abs(ty - cyv) > 0.1) {
          rafM = requestAnimationFrame(loopM);
        } else { rafM = null; }
      }
      var onMoveM = function (e) {
        if (isEditing()) return;
        var rect = target.getBoundingClientRect();
        var cx = rect.left + rect.width / 2;
        var cy = rect.top + rect.height / 2;
        var dx = e.clientX - cx, dy = e.clientY - cy;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < radius) {
          var pull = 1 - dist / radius;
          tx = (dx / radius) * maxT * pull;
          ty = (dy / radius) * maxT * pull;
        } else { tx = 0; ty = 0; }
        if (!rafM) rafM = requestAnimationFrame(loopM);
      };
      var onLeaveM = function () {
        tx = 0; ty = 0;
        if (!rafM) rafM = requestAnimationFrame(loopM);
      };
      target.addEventListener('mousemove', onMoveM, { passive: true });
      target.addEventListener('mouseleave', onLeaveM, { passive: true });
      hoverCleanup = function () {
        target.removeEventListener('mousemove', onMoveM);
        target.removeEventListener('mouseleave', onLeaveM);
        if (rafM) cancelAnimationFrame(rafM);
      };

    } else if (presetId === 'hover_underline_draw') {
      var dur = (cfg && cfg.duration_ms) || 300;
      var easeU = (cfg && cfg.ease) || 'cubic-bezier(0.4, 0, 0.2, 1)';
      var style = document.createElement('style');
      style.id = '__se_hover_underline';
      style.textContent =
        'body h1, body h2, body h3, body a {' +
        '  position: relative; display: inline-block;' +
        '}' +
        'body h1::after, body h2::after, body h3::after, body a::after {' +
        '  content: ""; position: absolute; left: 0; bottom: -2px;' +
        '  width: 0; height: 2px;' +
        '  background: linear-gradient(90deg, #6366f1, #ec4899);' +
        '  transition: width ' + dur + 'ms ' + easeU + ';' +
        '}' +
        'body h1:hover::after, body h2:hover::after, body h3:hover::after, body a:hover::after {' +
        '  width: 100%;' +
        '}';
      document.head.appendChild(style);
    }
  }

  function isHoverPreset(id) {
    return id === 'hover_lift' || id === 'hover_tilt'
      || id === 'hover_magnetic' || id === 'hover_underline_draw';
  }

  // Visible "hover hint" — when Replay is clicked for a hover preset,
  // briefly simulate the hover state since these effects need a real
  // pointer event to fire.
  function playHoverHint(presetId, cfg) {
    var target = document.body.firstElementChild;
    if (!target) return;
    if (presetId === 'hover_lift' && window.gsap) {
      window.gsap.fromTo(target, {y: 0}, {y: -(((cfg && cfg.translate_y) || 4)), duration: 0.25, yoyo: true, repeat: 1, ease: 'power2.out'});
    } else if (presetId === 'hover_tilt' && window.gsap) {
      window.gsap.fromTo(target, {rotation: 0}, {rotation: -2, duration: 0.3, yoyo: true, repeat: 1, ease: 'power2.inOut'});
    } else if (presetId === 'hover_magnetic' && window.gsap) {
      window.gsap.fromTo(target, {x: 0}, {x: ((cfg && cfg.max_translate) || 12) * 0.6, duration: 0.3, yoyo: true, repeat: 1, ease: 'power2.inOut'});
    }
    // hover_underline_draw: no hint — the underline is per-element on
    // hover; replay would need an element to hover over, doesn't have
    // a "preview" character on its own.
  }

  window.replayAnimation = function () {
    if (isEditing()) {
      pendingReplay = true;
      return;
    }
    var spec = window.__sectionAnimation;
    // Always tear down hover listeners on replay — they get re-installed
    // below if the new preset is still a hover one. Stops listeners from
    // a previous preset lingering after a swap.
    clearHoverListeners();
    if (!spec || !spec.preset || spec.preset === 'none' || spec.preset === 'default') {
      setFinalState();
      return;
    }
    if (reduceMotion()) {
      setFinalState();
      return;
    }
    setFinalState();
    if (ENTRY_PRESETS[spec.preset]) {
      playEntry(spec.preset, spec.config);
    } else if (isHoverPreset(spec.preset)) {
      // Install listeners so the user gets the effect on hover, AND
      // play a one-shot hint so they see what it does immediately.
      installHover(spec.preset, spec.config);
      playHoverHint(spec.preset, spec.config);
    } else {
      playScrubSimulation(spec.preset, spec.config);
    }
  };

  // Fire any queued replay when the user blurs out of a contentEditable.
  document.addEventListener('focusout', function () {
    setTimeout(function () {
      if (pendingReplay && !isEditing()) {
        pendingReplay = false;
        window.replayAnimation();
      }
    }, 50);
  });

  // Parent posts {type:'replay-animation'} when the user picks a preset
  // or finishes adjusting a config slider.
  window.addEventListener('message', function (e) {
    if (e.data && e.data.type === 'replay-animation' && e.data.sectionId === window.__sectionId) {
      // Wait for GSAP if not ready yet (CDN may still be loading).
      if (!window.gsap) {
        var tries = 0;
        var poll = setInterval(function () {
          if (window.gsap || tries++ > 20) {
            clearInterval(poll);
            window.replayAnimation();
          }
        }, 50);
      } else {
        window.replayAnimation();
      }
    }
  });
})();
<\/script>
`

/**
 * Injected iframe-side editor script. Single-click → contentEditable
 * for text tags; blur posts the cleaned body HTML to the parent.
 * Mirrors the cleanBodyHtml() helper from VisualEditor — strips the
 * editor's own DOM before serialization.
 */
const EDITOR_SCRIPT = `
<script>
  var TEXT_TAGS = ['H1','H2','H3','H4','H5','H6','P','SPAN','A','LI','BUTTON','LABEL','TD','TH','EM','STRONG'];
  var selectedEl = null;
  var overlay = null;

  function createOverlay() {
    if (overlay) overlay.remove();
    overlay = document.createElement('div');
    overlay.id = '__editor_overlay';
    overlay.style.cssText = 'position:absolute;border:2px solid #6366f1;pointer-events:none;z-index:99999;transition:all 0.1s;border-radius:4px;';
    document.body.appendChild(overlay);
  }

  function cleanBodyHtml() {
    var clone = document.body.cloneNode(true);
    var ov = clone.querySelectorAll('#__editor_overlay');
    for (var i = 0; i < ov.length; i++) ov[i].remove();
    var sc = clone.querySelectorAll('script');
    for (var j = 0; j < sc.length; j++) sc[j].remove();
    var all = clone.querySelectorAll('*');
    for (var k = 0; k < all.length; k++) {
      var el = all[k];
      var attrs = Array.prototype.slice.call(el.attributes);
      for (var a = 0; a < attrs.length; a++) {
        if (attrs[a].name.indexOf('data-editor-') === 0) {
          el.removeAttribute(attrs[a].name);
        }
      }
      if (el.hasAttribute('contenteditable')) {
        el.removeAttribute('contenteditable');
      }
    }
    return clone.innerHTML;
  }

  function postSize() {
    var h = document.body.scrollHeight;
    window.parent.postMessage({ type: 'iframe-resize', sectionId: window.__sectionId, height: h }, '*');
  }

  document.addEventListener('click', function(e) {
    var clicked = e.target;
    var isText = TEXT_TAGS.indexOf(clicked.tagName) !== -1;

    // <details>/<summary> handling — Commit 5.1.
    //   The default behavior calls preventDefault() on any non-text
    //   tag, which kills the browser's native <details> toggle. Walk
    //   up to find a <summary> ancestor and special-case:
    //     - Click on chevron icon / summary padding → let native
    //       toggle fire. No overlay, no edit mode.
    //     - Click on inner text span → block native toggle so the
    //       accordion doesn't flap while the user is typing.
    var summaryAncestor = clicked.closest && clicked.closest('summary');
    if (summaryAncestor && (!isText || clicked === summaryAncestor)) {
      e.stopPropagation();
      return;
    }
    if (summaryAncestor) {
      e.preventDefault();
    } else if (!isText) {
      e.preventDefault();
    }
    e.stopPropagation();
    selectedEl = clicked;

    if (isText && clicked.getAttribute('contenteditable') !== 'true') {
      clicked.contentEditable = 'true';
      clicked.focus();
      clicked.addEventListener('blur', function() {
        clicked.contentEditable = 'false';
        window.parent.postMessage({
          type: 'section-content-changed',
          sectionId: window.__sectionId,
          html: cleanBodyHtml(),
        }, '*');
      }, { once: true });
    }

    if (!overlay) createOverlay();
    var rect = clicked.getBoundingClientRect();
    overlay.style.top = (rect.top + window.scrollY) + 'px';
    overlay.style.left = (rect.left + window.scrollX) + 'px';
    overlay.style.width = rect.width + 'px';
    overlay.style.height = rect.height + 'px';

    // Commit 6 — broadcast the selected element's tag to the parent so
    // the StyleEditorDrawer knows which selector to apply edits to.
    // Tag is lowercased; this is the same key compile_page uses for
    // style_overrides.
    window.parent.postMessage({
      type: 'section-element-selected',
      sectionId: window.__sectionId,
      selector: (clicked.tagName || '').toLowerCase(),
    }, '*');
  }, true);

  // Resize observer — sections grow when the user types
  var ro = new ResizeObserver(postSize);
  ro.observe(document.body);
  window.addEventListener('load', postSize);
  postSize();

  // Commit 6.0.1 — assign a stable id to the iframe body so the
  // style-overrides preview rules can be scoped exactly like
  // compile_page emits them on the published page:
  //   #section-{sid} h1 { ... }
  // The id-selector beats Tailwind utility classes on specificity
  // (0,1,0,1 > 0,0,1,0). Without this, bare h1/p/etc rules lose to
  // .text-5xl / .font-extrabold / .text-white on the same element.
  document.body.id = 'section-' + window.__sectionId;

  // Commit 6 — live style preview channel. Parent posts a CSS string
  // built from the drawer's pending style_overrides; we inject (or
  // replace) a <style id="se-overrides"> in the iframe head so the
  // preview matches what compile_page will emit. No srcdoc rebuild,
  // no Tailwind/GSAP reload.
  window.addEventListener('message', function(e) {
    if (!e || !e.data) return;
    if (e.data.type === 'style-overrides-preview'
        && e.data.sectionId === window.__sectionId) {
      var styleEl = document.getElementById('se-overrides');
      if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'se-overrides';
        document.head.appendChild(styleEl);
      }
      styleEl.textContent = e.data.css || '';
    }
  });
<\/script>
`

/** Sortable wrapper for SectionBlock — provides the dnd-kit drag
 *  handle attributes and transform style. The handle is exposed via
 *  dragHandleProps so only the grip icon (not the iframe content)
 *  initiates drag. */
function SortableSectionWrapper(props: SectionBlockProps & { sortId: string }) {
  const { sortId, ...rest } = props
  const {
    attributes, listeners, setNodeRef, transform, transition, isDragging,
  } = useSortable({ id: sortId })

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    // Cast the dragging item above siblings while it animates.
    zIndex: isDragging ? 50 : undefined,
    opacity: isDragging ? 0.55 : 1,
  }

  return (
    <div ref={setNodeRef} style={style}>
      <SectionBlock
        {...rest}
        isDragging={isDragging}
        dragHandleProps={{
          // dnd-kit types its listeners as a generic record; cast at
          // the boundary so React's strict event-handler typing
          // doesn't fight the SyntheticEvent shape.
          attributes: attributes as unknown as React.HTMLAttributes<HTMLElement>,
          listeners: (listeners ?? {}) as Record<string, (e: React.SyntheticEvent) => void>,
        }}
      />
    </div>
  )
}


/** Hover-zone between sections (and at the top of the list). Renders
 *  a thin gutter that grows into a horizontal accent line + circular
 *  "+" button on hover. Clicking opens the category picker for an
 *  insert-at-position add. */
function InsertionZone({ onClick }: { onClick: () => void }) {
  return (
    <div
      className="se-insertion-zone group"
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick()
        }
      }}
      aria-label="Add section here"
    >
      <span className="se-insertion-line" />
      <span className="se-insertion-button">
        <Plus className="h-3.5 w-3.5" />
        <span className="se-tooltip">Add section here</span>
      </span>
      <span className="se-insertion-line" />
    </div>
  )
}


function SectionBlock({
  pageId, section, index, onChanged, onRequestChangeVariant,
  dragHandleProps, isDragging,
}: SectionBlockProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [iframeHeight, setIframeHeight] = useState(240)
  const [hovered, setHovered] = useState(false)
  const [refining, setRefining] = useState(false)
  const [showRefineInput, setShowRefineInput] = useState(false)
  const [refineInstruction, setRefineInstruction] = useState('')
  // Active media slot — token name being edited via MediaPickerModal.
  // null means picker closed.
  const [mediaSlot, setMediaSlot] = useState<string | null>(null)
  // Animation picker open state. Reads section.animations to pre-select
  // the current preset.
  const [animOpen, setAnimOpen] = useState(false)
  // Commit 6 — style editor drawer.
  //   styleOpen        — visibility
  //   styleSelector    — element being styled ("h1", "section", ...).
  //                      Defaults to "section" when the user opens the
  //                      drawer without first clicking an element.
  //   selectedElement  — most-recent element click from the iframe.
  //                      Drawer reads this to pre-target the right
  //                      selector when opened via the hover bar icon.
  const [styleOpen, setStyleOpen] = useState(false)
  const [styleSelector, setStyleSelector] = useState<string>('section')
  const selectedElementRef = useRef<string>('section')

  const sectionId = section.id || `section-${index}`

  /** Send a replay message to this section's iframe. Used by the
   *  AnimationPickerModal on preset/config change (4B.1) and by the
   *  Replay button in the section badge. */
  const replayInIframe = useCallback(() => {
    const win = iframeRef.current?.contentWindow
    if (!win) return
    win.postMessage(
      { type: 'replay-animation', sectionId },
      '*',
    )
  }, [sectionId])
  const html = sectionBodyHtml(section)
  // Detect which MEDIA_TOKENS the rendered content has. Scans both the
  // edited_html (if user-edited) and jsx_content; either path may carry
  // {{X_URL}} placeholders. The picker pill lets users swap the URL
  // without re-rendering the variant template.
  const mediaTokens = useMemo(() => {
    return detectMediaTokens(html)
  }, [html])
  const mediaOverrides = section.media_overrides || {}
  const mediaDefaults = (section.metadata?.props || {}) as Record<string, string>

  // Mark this iframe with its section id so messages can be routed back.
  // We can't pass JS variables into srcdoc; inject via window.__sectionId.
  // Substitute media tokens client-side so the preview shows the real
  // video/image, not literal {{VIDEO_URL}} text.
  const previewHtml = useMemo(() => {
    return substituteMediaTokens(html, { ...mediaDefaults, ...mediaOverrides })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [html, JSON.stringify(mediaDefaults), JSON.stringify(mediaOverrides)])

  // Inject the section's animation spec so the iframe-side replay
  // function can read it without an attribute round-trip. Excludes the
  // "default"/"none" branches — those are static in the editor preview.
  const animationSpecJson = useMemo(() => {
    const a = section.animations
    if (!a || !a.preset || a.preset === 'none' || a.preset === 'default') {
      return 'null'
    }
    return JSON.stringify({ preset: a.preset, config: a.config || {} })
  }, [section.animations])

  // Commit 6.0.2 — pre-compute the scoped CSS block derived from the
  // section's persisted style_overrides. Byte-identical to what
  // compile_page emits for the published page (#section-{sid} h1 {...}).
  // Baked into srcdoc below so the iframe paints correctly on initial
  // mount; the post-mount useEffect handles subsequent updates via
  // postMessage so the iframe doesn't re-mount on every persisted edit.
  const styleOverridesCss = useMemo(() => {
    return compileStyleOverridesPreview(
      section.style_overrides as Record<string, Record<string, string | number>> | undefined,
      sectionId,
    )
  }, [section.style_overrides, sectionId])

  // style_overrides is intentionally NOT in this useMemo's deps array.
  //
  // Initial mount: srcdoc includes baked <style id="se-overrides">
  //   {styleOverridesCss} — iframe paints with correct overrides
  //   immediately, matches Preview tab + published render.
  // Subsequent updates: the post-mount useEffect below syncs via
  //   postMessage by rewriting that same <style id="se-overrides">
  //   element's textContent. No iframe re-mount.
  //
  // If style_overrides WERE a dep here, the iframe would re-mount on
  // every persisted edit — killing GSAP scroll-triggers, scroll
  // position, hover state, and any animation runtime state. The
  // postMessage approach (useEffect below) preserves all of that.
  const srcdoc = useMemo(() => {
    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="${TAILWIND_CDN}"><\/script>
  <script src="${GSAP_CDN}" defer><\/script>
  <style>
    body { margin: 0; font-family: 'Inter', system-ui, -apple-system, sans-serif; }
    *:hover { cursor: text; }
    [contenteditable="true"]:focus { outline: 2px solid #6366f1; outline-offset: 2px; }
  </style>
  <style id="se-overrides">${styleOverridesCss}</style>
</head>
<body>
  <script>
    window.__sectionId = ${JSON.stringify(sectionId)};
    window.__sectionAnimation = ${animationSpecJson};
  <\/script>
  ${previewHtml}
  ${ANIMATION_RUNTIME_SCRIPT}
  ${EDITOR_SCRIPT}
</body>
</html>`
    // styleOverridesCss intentionally excluded — see comment above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewHtml, sectionId, animationSpecJson])

  // Listen for messages from THIS section's iframe
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.sectionId !== sectionId) return
      if (e.data?.type === 'iframe-resize') {
        const h = Math.max(120, Math.min(2000, Number(e.data.height) || 240))
        setIframeHeight(h)
      } else if (e.data?.type === 'section-content-changed') {
        patchMut.mutate({ edited_html: e.data.html })
      } else if (e.data?.type === 'section-element-selected') {
        // Commit 6 — remember which element the user last clicked so
        // opening the Style drawer via the hover bar targets it.
        const sel = String(e.data.selector || 'section')
        selectedElementRef.current = sel
        // If the drawer is already open, switch its target live so the
        // user can re-target without close/reopen.
        if (styleOpen) setStyleSelector(sel)
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sectionId, styleOpen])

  /** Push a CSS string into the iframe via postMessage. Used for the
   *  drawer's live-preview channel — fires on every control change,
   *  no PATCH round-trip required. */
  const pushPreviewCss = useCallback((
    overrides: Record<string, Record<string, string | number>>,
  ) => {
    const win = iframeRef.current?.contentWindow
    if (!win) return
    win.postMessage({
      type: 'style-overrides-preview',
      sectionId,
      css: compileStyleOverridesPreview(overrides, sectionId),
    }, '*')
  }, [sectionId])

  // Commit 6.0.2 — post-mount style sync.
  //
  // Initial mount is handled by the srcdoc's baked <style id="se-overrides">
  // block (above). This effect handles every subsequent change to
  // section.style_overrides from any source — PATCH refetch (after the
  // drawer's debounced save), navigation back to this page, parent
  // component re-renders that bring fresh server data.
  //
  // We use postMessage (not srcdoc re-render) because the iframe must
  // stay mounted to preserve GSAP scroll-triggers, scroll position,
  // hover state, and animation runtime. The message handler in
  // EDITOR_SCRIPT finds the existing <style id="se-overrides"> by id
  // and rewrites its textContent — no flash, no re-paint of unstyled
  // content.
  useEffect(() => {
    const overrides = section.style_overrides as
      Record<string, Record<string, string | number>> | undefined
    if (!overrides) return
    // Defer one tick so the iframe load + EDITOR_SCRIPT message
    // listener attachment have completed before we post.
    const t = setTimeout(() => pushPreviewCss(overrides), 0)
    return () => clearTimeout(t)
  }, [section.style_overrides, pushPreviewCss])

  /** Open style drawer with the currently-selected element (or
   *  "section" if no element was clicked). Closes any other drawer
   *  open on this section so only one is active at a time
   *  (Commit 6 Workstream D.2). */
  const openStyleDrawer = useCallback(() => {
    setAnimOpen(false)
    setMediaSlot(null)
    setStyleSelector(selectedElementRef.current || 'section')
    setStyleOpen(true)
  }, [])

  const queryClient = useQueryClient()
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['page', pageId] })
    onChanged()
  }

  const patchMut = useMutation({
    mutationFn: (data: {
      edited_html?: string | null
      style_overrides?: Record<string, unknown> | null
      media_overrides?: Record<string, string> | null
    }) => pagesApi.patchSection(pageId, index, data as Record<string, unknown>),
    onSuccess: invalidate,
    onError: (e: any) => toast.error(`Save failed: ${e?.message || 'unknown'}`),
  })

  const duplicateMut = useMutation({
    mutationFn: () => pagesApi.duplicateSection(pageId, index),
    onSuccess: () => { toast.success('Section duplicated'); invalidate() },
    onError: (e: any) => toast.error(`Duplicate failed: ${e?.message || 'unknown'}`),
  })

  const deleteMut = useMutation({
    mutationFn: () => pagesApi.deleteSection(pageId, index),
    onSuccess: () => { toast.success('Section deleted'); invalidate() },
    onError: (e: any) => toast.error(`Delete failed: ${e?.message || 'unknown'}`),
  })

  const revertMut = useMutation({
    mutationFn: () => pagesApi.revertSection(pageId, index),
    onSuccess: () => { toast.success('Reverted to AI original'); invalidate() },
    onError: (e: any) => toast.error(`Revert failed: ${e?.message || 'unknown'}`),
  })

  const refineMut = useMutation({
    mutationFn: (instruction: string) =>
      pagesApi.aiRefineSection(pageId, index, instruction),
    onSuccess: () => {
      toast.success('Section refined')
      setShowRefineInput(false)
      setRefineInstruction('')
      setRefining(false)
      invalidate()
    },
    onError: (e: any) => {
      toast.error(`Refine failed: ${e?.message || 'unknown'}`)
      setRefining(false)
    },
  })

  const handleRefine = () => {
    const i = refineInstruction.trim()
    if (!i) return
    setRefining(true)
    refineMut.mutate(i)
  }

  const hasEdits = !!section.edited_html

  const sectionTypeClass = section.type ? `se-type-${section.type}` : ''
  const sectionDraggingClass = isDragging ? 'se-section-dragging' : ''

  return (
    <div
      className={`se-section ${sectionTypeClass} ${sectionDraggingClass} group bg-white dark:bg-gray-900`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Drag handle — top-left ⋮⋮ grip. Listens for pointer + keyboard
          via dnd-kit. Only rendered when the parent provides handle
          props (i.e. when the section is inside a SortableContext). */}
      {dragHandleProps && hovered && (
        <button
          type="button"
          className="se-drag-handle"
          aria-label={`Drag to reorder ${section.type || 'section'} #${index + 1}`}
          {...dragHandleProps.attributes}
          {...dragHandleProps.listeners}
        >
          <GripVertical className="h-4 w-4" />
        </button>
      )}

      {/* Hover controls — Liquid Glass floating bar, top-right.
          Commit 6 Workstream D — visual grouping with a 1px divider.
          Primary cluster (style / animations / variant) groups the
          design-altering tools; secondary cluster (refine-ai /
          duplicate / revert / delete) groups content/lifecycle
          operations. */}
      {hovered && (
        <div className="absolute top-3 right-3 z-20 se-control-bar">
          <button
            onClick={openStyleDrawer}
            className="se-control-btn se-ctrl-style"
            aria-label="Style"
          >
            <Palette className="h-4 w-4" />
            <span className="se-tooltip">Style</span>
          </button>
          <button
            onClick={() => { setStyleOpen(false); setMediaSlot(null); setAnimOpen(true) }}
            className="se-control-btn se-ctrl-anim"
            aria-label="Animations"
          >
            <Wand2 className="h-4 w-4" />
            <span className="se-tooltip">Animations</span>
          </button>
          <button
            onClick={() => onRequestChangeVariant(index, section.type || 'hero')}
            className="se-control-btn se-ctrl-variant"
            aria-label="Change variant"
          >
            <Replace className="h-4 w-4" />
            <span className="se-tooltip">Change variant</span>
          </button>

          <span className="se-control-divider" aria-hidden="true" />

          <button
            onClick={() => setShowRefineInput(true)}
            disabled={refining}
            className="se-control-btn se-ctrl-refine"
            aria-label="Refine with AI"
          >
            {refining ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            <span className="se-tooltip">Refine with AI</span>
          </button>
          <button
            onClick={() => duplicateMut.mutate()}
            disabled={duplicateMut.isPending}
            className="se-control-btn"
            aria-label="Duplicate section"
          >
            <Copy className="h-4 w-4" />
            <span className="se-tooltip">Duplicate section</span>
          </button>
          {hasEdits && (
            <button
              onClick={() => {
                if (confirm('Revert this section to the AI original? Your edits will be lost.')) {
                  revertMut.mutate()
                }
              }}
              disabled={revertMut.isPending}
              className="se-control-btn se-ctrl-revert"
              aria-label="Revert to AI original"
            >
              <RotateCcw className="h-4 w-4" />
              <span className="se-tooltip">Revert to AI original</span>
            </button>
          )}
          <button
            onClick={() => {
              if (confirm('Delete this section?')) {
                deleteMut.mutate()
              }
            }}
            disabled={deleteMut.isPending}
            className="se-control-btn se-ctrl-delete"
            aria-label="Delete section"
          >
            <Trash2 className="h-4 w-4" />
            <span className="se-tooltip">Delete section</span>
          </button>
        </div>
      )}

      {/* Refine input — modal at top of section */}
      {showRefineInput && (
        <div className="absolute top-2 left-2 right-12 z-30 bg-white dark:bg-gray-800 border border-indigo-200 dark:border-indigo-700 rounded-lg shadow-xl p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-indigo-700 dark:text-indigo-300 uppercase tracking-wider">
              Refine {section.type || 'section'} with AI
            </span>
            <button onClick={() => { setShowRefineInput(false); setRefineInstruction('') }} className="text-gray-400 hover:text-gray-600">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          <textarea
            value={refineInstruction}
            onChange={(e) => setRefineInstruction(e.target.value)}
            placeholder="e.g. 'make the headline more playful' or 'change the color scheme to warm tones'"
            rows={2}
            maxLength={2000}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleRefine()
            }}
            className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
          />
          <div className="flex items-center justify-between mt-1.5">
            <span className="text-[10px] text-gray-400">⌘↵ to submit</span>
            <button
              onClick={handleRefine}
              disabled={refining || !refineInstruction.trim()}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded disabled:opacity-50"
            >
              {refining ? <><Loader2 className="h-3 w-3 animate-spin" /> Working…</> : <><Sparkles className="h-3 w-3" /> Refine</>}
            </button>
          </div>
        </div>
      )}

      {/* The actual section iframe */}
      <iframe
        ref={iframeRef}
        srcDoc={srcdoc}
        title={`section-${sectionId}`}
        sandbox="allow-scripts allow-same-origin"
        className="w-full border-0 block"
        style={{ height: `${iframeHeight}px` }}
      />

      {/* Section badge — Liquid Glass surface, bottom-left, only on hover.
          Includes a ▶ replay affordance when a non-default animation is
          applied so the user can replay without opening the picker. */}
      {hovered && (
        <div className="absolute bottom-3 left-3 z-20 se-badge">
          <span>{section.type || 'section'}</span>
          <span className="opacity-60">·</span>
          <span>#{index + 1}</span>
          {hasEdits && (
            <>
              <span className="opacity-60">·</span>
              <span className="se-badge-edited">edited</span>
            </>
          )}
          {section.animations
            && section.animations.preset
            && section.animations.preset !== 'default'
            && section.animations.preset !== 'none' && (
            <>
              <span className="opacity-60">·</span>
              <button
                onClick={(e) => { e.stopPropagation(); replayInIframe() }}
                className="se-badge-replay"
                title="Replay animation"
                aria-label="Replay animation"
              >
                <Play className="h-2.5 w-2.5" fill="currentColor" />
              </button>
            </>
          )}
        </div>
      )}

      {/* Media slot pills — bottom-right, only on hover. One pill per
          detected {{TOKEN}} in the section. Click → MediaPickerModal. */}
      {hovered && mediaTokens.length > 0 && (
        <div className="absolute bottom-3 right-3 z-20 flex items-center gap-1.5">
          {mediaTokens.map((tok) => (
            <button
              key={tok}
              onClick={() => {
                setStyleOpen(false); setAnimOpen(false); setMediaSlot(tok)
              }}
              className="se-media-pill"
              title={`Edit ${tokenLabel(tok)}`}
            >
              {tokenIcon(tok)}
              <span>{tokenLabel(tok)}</span>
            </button>
          ))}
        </div>
      )}

      {/* Animation picker — Commit 4B. Reads section.animations to
          pre-select the current preset. Commit 4B.1: onApplied also
          triggers an in-place replay in the section iframe so the
          user sees the new animation without tab-switching. */}
      <AnimationPickerModal
        open={animOpen}
        pageId={pageId}
        sectionIndex={index}
        current={section.animations || null}
        onClose={() => setAnimOpen(false)}
        onApplied={() => {
          invalidate()
          // Defer slightly so React-Query refetch + iframe srcdoc
          // re-render with the new animationSpec finishes first.
          setTimeout(replayInIframe, 80)
        }}
        onReplay={replayInIframe}
      />

      {/* Style editor drawer — Commit 6 Workstream A. Opens via the
          hover bar 🎨 icon. Live-preview channel mutates the iframe's
          <style id="se-overrides"> on every control change; debounced
          PATCH then persists to sections_json[i].style_overrides. */}
      <StyleEditorDrawer
        open={styleOpen}
        pageId={pageId}
        sectionIndex={index}
        selector={styleSelector}
        initialOverrides={
          (section.style_overrides as Record<
            string, Record<string, string | number>
          > | undefined) ?? undefined
        }
        onPreview={pushPreviewCss}
        onSaved={invalidate}
        onClose={() => setStyleOpen(false)}
      />

      {/* Media picker modal — opens when a slot pill is clicked. The
          target URL key may differ from the token name (element tokens
          like VIDEO_EMBED back onto VIDEO_URL in media_overrides). */}
      <MediaPickerModal
        open={mediaSlot !== null}
        tokenName={mediaSlot ? tokenLabel(mediaSlot) : ''}
        slotKind={mediaSlot ? tokenKindFor(mediaSlot) : 'any'}
        currentValue={
          mediaSlot
            ? (mediaOverrides[TOKEN_TO_URL_KEY[mediaSlot] || mediaSlot]
                || mediaDefaults[TOKEN_TO_URL_KEY[mediaSlot] || mediaSlot]
                || '')
            : null
        }
        onClose={() => setMediaSlot(null)}
        onPick={(newValue) => {
          if (!mediaSlot) return
          const urlKey = TOKEN_TO_URL_KEY[mediaSlot] || mediaSlot
          const merged = { ...mediaOverrides, [urlKey]: newValue }
          patchMut.mutate({ media_overrides: merged })
          setMediaSlot(null)
        }}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Top-level component
// ---------------------------------------------------------------------------

export default function SectionEditor({ pageId, sections, onChanged }: SectionEditorProps) {
  const queryClient = useQueryClient()

  // Picker state: { mode, lockedCategory?, swapIndex? }
  type PickerState =
    | { mode: 'add' }
    | { mode: 'swap'; swapIndex: number; lockedCategory: string }
    | null
  const [picker, setPicker] = useState<PickerState>(null)

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['page', pageId] })
    onChanged()
  }

  // Pending insertion position: when set, the next add fires with
  // ?after_idx=N. Lets the hover-zone "+" buttons between sections
  // insert at a specific position instead of appending.
  const [pendingInsertAfter, setPendingInsertAfter] = useState<number | null>(null)

  const addMut = useMutation({
    mutationFn: (args: { data: { category: string; variant_id: string }; afterIdx?: number }) =>
      pagesApi.addSection(pageId, args.data, args.afterIdx),
    onSuccess: () => { toast.success('Section added'); invalidate() },
    onError: (e: any) => toast.error(`Add failed: ${e?.message || 'unknown'}`),
  })

  const reorderMut = useMutation({
    mutationFn: (args: { fromIndex: number; toIndex: number }) =>
      pagesApi.reorderSections(pageId, args.fromIndex, args.toIndex),
    onSuccess: () => { invalidate() },
    onError: (e: any) => toast.error(`Reorder failed: ${e?.message || 'unknown'}`),
  })

  // Stable sortable IDs for dnd-kit. Falls back to index-based ids
  // for any section row that's missing one (defensive — every section
  // should have an id from variant_to_section).
  const sortIds = useMemo(
    () => (sections || []).map((s, i) => s.id || `s-${i}`),
    [sections],
  )

  const sensors = useSensors(
    useSensor(PointerSensor, {
      // 8px threshold prevents accidental drag when the user means to
      // click into a text element. Drag only engages after the pointer
      // moves at least 8px.
      activationConstraint: { distance: 8 },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  )

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const fromIndex = sortIds.indexOf(String(active.id))
    const toIndex = sortIds.indexOf(String(over.id))
    if (fromIndex < 0 || toIndex < 0) return
    // Optimistic: update the React-Query cache so the editor reorders
    // instantly. The PATCH then confirms; on error, invalidate rolls
    // back via refetch.
    queryClient.setQueryData(['page', pageId], (old: any) => {
      if (!old?.data?.sections_json) return old
      try {
        const arr = JSON.parse(old.data.sections_json)
        const moved = arrayMove(arr, fromIndex, toIndex)
        return {
          ...old,
          data: { ...old.data, sections_json: JSON.stringify(moved) },
        }
      } catch {
        return old
      }
    })
    reorderMut.mutate({ fromIndex, toIndex })
  }

  const changeMut = useMutation({
    mutationFn: (args: { idx: number; data: { category: string; variant_id: string } }) =>
      pagesApi.changeVariant(pageId, args.idx, args.data),
    onSuccess: (resp: any) => {
      const migrated: string[] = resp?.meta?.migrated_tokens ?? []
      if (migrated.length > 0) {
        toast.success(`Variant swapped — ${migrated.length} field${migrated.length === 1 ? '' : 's'} migrated`)
      } else {
        toast.success('Variant swapped')
      }
      invalidate()
    },
    onError: (e: any) => toast.error(`Swap failed: ${e?.message || 'unknown'}`),
  })

  const handlePick = (variant: { category: string; variant_id: string }) => {
    if (!picker) return
    if (picker.mode === 'add') {
      const data = { category: variant.category, variant_id: variant.variant_id }
      const afterIdx = pendingInsertAfter ?? undefined
      addMut.mutate({ data, afterIdx })
      setPendingInsertAfter(null)
    } else {
      changeMut.mutate({ idx: picker.swapIndex, data: { category: variant.category, variant_id: variant.variant_id } })
    }
    setPicker(null)
  }

  /** Open the category picker pre-set to insert at a specific position.
   *  afterIdx = -1 means insert at the very top.
   *  afterIdx = sections.length - 1 means insert at the very bottom. */
  const openPickerForInsertAfter = (afterIdx: number) => {
    setPendingInsertAfter(afterIdx)
    setPicker({ mode: 'add' })
  }

  const empty = !sections || sections.length === 0

  // Add Section button — inline at the end of the section list (not
  // sticky). Sticky + pointer-events gymnastics in Commit 2 broke
  // discoverability for Nate; inline is the simplest path that
  // guarantees the button is reachable. Renders for both populated
  // and empty section lists.
  const addSectionButton = (
    <div className="flex justify-center pt-2 pb-6">
      <button
        type="button"
        onClick={() => {
          setPendingInsertAfter(null)  // append at end
          setPicker({ mode: 'add' })
        }}
        disabled={addMut.isPending}
        className="se-add-section"
      >
        {addMut.isPending ? (
          <><Loader2 className="h-4 w-4 animate-spin" /> Adding…</>
        ) : (
          <><Plus className="h-4 w-4" /> Add Section</>
        )}
      </button>
    </div>
  )

  return (
    <div className="se-root h-full overflow-y-auto bg-gray-50 dark:bg-gray-900">
      <div className="p-4 space-y-3 pb-6">
        {empty ? (
          <div className="flex flex-col items-center justify-center text-gray-400 dark:text-gray-500 py-20">
            <p className="text-sm">No sections yet.</p>
            <p className="text-xs mt-1 mb-6">
              Pick a variant below to get started.
            </p>
            {addSectionButton}
          </div>
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext items={sortIds} strategy={verticalListSortingStrategy}>
              {/* Insertion zone before the first section. afterIdx=-1
                  inserts at the very top (sections[0]). */}
              <InsertionZone onClick={() => openPickerForInsertAfter(-1)} />
              {sections.map((sec, idx) => (
                <div key={sortIds[idx]}>
                  <SortableSectionWrapper
                    sortId={sortIds[idx]}
                    pageId={pageId}
                    section={sec}
                    index={idx}
                    onChanged={onChanged}
                    onRequestChangeVariant={(swapIndex, category) =>
                      setPicker({ mode: 'swap', swapIndex, lockedCategory: category })
                    }
                  />
                  {/* Between-sections insertion zone. afterIdx=idx puts
                      the new section at idx+1 (right after this one). */}
                  <InsertionZone onClick={() => openPickerForInsertAfter(idx)} />
                </div>
              ))}
            </SortableContext>
            {addSectionButton}
            <div className="text-center text-xs text-gray-400 dark:text-gray-500">
              {sections.length} {sections.length === 1 ? 'section' : 'sections'} · click any text to edit
            </div>
          </DndContext>
        )}
      </div>

      <VariantPickerModal
        open={picker !== null}
        mode={picker?.mode ?? 'add'}
        lockedCategory={picker?.mode === 'swap' ? picker.lockedCategory : undefined}
        onClose={() => setPicker(null)}
        onPick={handlePick}
      />
    </div>
  )
}
