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
import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Loader2, Sparkles, Trash2, Copy, RotateCcw, X, Replace, Plus,
  Film, Image as ImageIcon, GripVertical, Wand2,
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
    if (!isText) {
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
  }, true);

  // Resize observer — sections grow when the user types
  var ro = new ResizeObserver(postSize);
  ro.observe(document.body);
  window.addEventListener('load', postSize);
  postSize();
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

  const sectionId = section.id || `section-${index}`
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

  const srcdoc = useMemo(() => {
    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="${TAILWIND_CDN}"><\/script>
  <style>
    body { margin: 0; font-family: 'Inter', system-ui, -apple-system, sans-serif; }
    *:hover { cursor: text; }
    [contenteditable="true"]:focus { outline: 2px solid #6366f1; outline-offset: 2px; }
  </style>
</head>
<body>
  <script>window.__sectionId = ${JSON.stringify(sectionId)};<\/script>
  ${previewHtml}
  ${EDITOR_SCRIPT}
</body>
</html>`
  }, [previewHtml, sectionId])

  // Listen for messages from THIS section's iframe
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.sectionId !== sectionId) return
      if (e.data?.type === 'iframe-resize') {
        const h = Math.max(120, Math.min(2000, Number(e.data.height) || 240))
        setIframeHeight(h)
      } else if (e.data?.type === 'section-content-changed') {
        patchMut.mutate({ edited_html: e.data.html })
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sectionId])

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

      {/* Hover controls — Liquid Glass floating bar, top-right */}
      {hovered && (
        <div className="absolute top-3 right-3 z-20 se-control-bar">
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
            onClick={() => setAnimOpen(true)}
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

      {/* Section badge — Liquid Glass surface, bottom-left, only on hover */}
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
        </div>
      )}

      {/* Media slot pills — bottom-right, only on hover. One pill per
          detected {{TOKEN}} in the section. Click → MediaPickerModal. */}
      {hovered && mediaTokens.length > 0 && (
        <div className="absolute bottom-3 right-3 z-20 flex items-center gap-1.5">
          {mediaTokens.map((tok) => (
            <button
              key={tok}
              onClick={() => setMediaSlot(tok)}
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
          pre-select the current preset. */}
      <AnimationPickerModal
        open={animOpen}
        pageId={pageId}
        sectionIndex={index}
        current={section.animations || null}
        onClose={() => setAnimOpen(false)}
        onApplied={() => invalidate()}
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
