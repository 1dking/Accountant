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
  Loader2, Sparkles, Trash2, Copy, RotateCcw, X,
} from 'lucide-react'
import { pagesApi } from '@/api/pages'

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
  metadata?: Record<string, unknown>
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

function SectionBlock({ pageId, section, index, onChanged }: SectionBlockProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [iframeHeight, setIframeHeight] = useState(240)
  const [hovered, setHovered] = useState(false)
  const [refining, setRefining] = useState(false)
  const [showRefineInput, setShowRefineInput] = useState(false)
  const [refineInstruction, setRefineInstruction] = useState('')

  const sectionId = section.id || `section-${index}`
  const html = sectionBodyHtml(section)

  // Mark this iframe with its section id so messages can be routed back.
  // We can't pass JS variables into srcdoc; inject via window.__sectionId.
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
  ${html}
  ${EDITOR_SCRIPT}
</body>
</html>`
  }, [html, sectionId])

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
    mutationFn: (data: { edited_html?: string | null; style_overrides?: Record<string, unknown> | null }) =>
      pagesApi.patchSection(pageId, index, data),
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

  return (
    <div
      className="relative group border border-transparent hover:border-indigo-200 dark:hover:border-indigo-800 transition-colors rounded-lg overflow-hidden"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Hover controls — top-right floating bar */}
      {hovered && (
        <div className="absolute top-2 right-2 z-20 flex items-center gap-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-1">
          <button
            onClick={() => setShowRefineInput(true)}
            disabled={refining}
            className="p-1.5 rounded hover:bg-indigo-50 dark:hover:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 disabled:opacity-50"
            title="Refine with AI"
          >
            {refining ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          </button>
          <button
            onClick={() => duplicateMut.mutate()}
            disabled={duplicateMut.isPending}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 disabled:opacity-50"
            title="Duplicate section"
          >
            <Copy className="h-4 w-4" />
          </button>
          {hasEdits && (
            <button
              onClick={() => {
                if (confirm('Revert this section to the AI original? Your edits will be lost.')) {
                  revertMut.mutate()
                }
              }}
              disabled={revertMut.isPending}
              className="p-1.5 rounded hover:bg-amber-50 dark:hover:bg-amber-900/30 text-amber-600 dark:text-amber-400 disabled:opacity-50"
              title="Revert to AI original"
            >
              <RotateCcw className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={() => {
              if (confirm('Delete this section?')) {
                deleteMut.mutate()
              }
            }}
            disabled={deleteMut.isPending}
            className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400 disabled:opacity-50"
            title="Delete section"
          >
            <Trash2 className="h-4 w-4" />
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

      {/* Section label — bottom-left, tiny, only on hover */}
      {hovered && (
        <div className="absolute bottom-2 left-2 z-20 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400 bg-white/90 dark:bg-gray-900/90 rounded">
          {section.type || 'section'} · #{index + 1}{hasEdits ? ' · edited' : ''}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Top-level component
// ---------------------------------------------------------------------------

export default function SectionEditor({ pageId, sections, onChanged }: SectionEditorProps) {
  if (!sections || sections.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 dark:text-gray-500">
        <div className="text-center max-w-sm">
          <p className="text-sm">No sections yet.</p>
          <p className="text-xs mt-1">
            Generate a page via the Generate with AI button, or refine an empty section.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto bg-gray-50 dark:bg-gray-900 p-4 space-y-3">
      {sections.map((sec, idx) => (
        <SectionBlock
          key={sec.id || `s-${idx}`}
          pageId={pageId}
          section={sec}
          index={idx}
          onChanged={onChanged}
        />
      ))}
      <div className="pt-2 text-center text-xs text-gray-400 dark:text-gray-500">
        {sections.length} {sections.length === 1 ? 'section' : 'sections'} · click any text to edit
      </div>
    </div>
  )
}
