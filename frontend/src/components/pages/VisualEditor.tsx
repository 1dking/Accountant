import { useState, useRef, useCallback, useEffect } from 'react'
import {
  Trash2, Copy, Plus, Undo2, Redo2, AlignLeft,
  AlignCenter, AlignRight, AlignJustify, Columns3, Blocks,
} from 'lucide-react'
import { listForms } from '@/api/forms'
import { pagesApi } from '@/api/pages'
import SectionThumb from './SectionThumb'
import type { FormListItem } from '@/types/models'
import { useTranslation } from 'react-i18next'
import i18n from '@/i18n'

// ---------------------------------------------------------------------------
// Doc-shape helpers (Pages v2 compat)
// ---------------------------------------------------------------------------

/**
 * If `input` is a full <!DOCTYPE html> document, return just the body's
 * innerHTML. Otherwise return the input untouched.
 *
 * Why: compile_page() in Pages v2 emits a full HTML5 doc into
 * page.html_content. Wrapping that again inside the editor's iframe
 * srcdoc (`<body>${html}${editorScript}</body>`) produced nested
 * <!DOCTYPE>/<html>/<head>/<body> which the browser's HTML parser
 * "cleaned up" by discarding the inner structure — sections vanished
 * from the DOM, and the subsequent autosave persisted the wreckage.
 * Unwrapping before composition keeps the parser happy.
 */
function bodyInnerFromFullDoc(input: string): string {
  if (!input) return ''
  const trimmed = input.trim()
  if (!/^<!doctype/i.test(trimmed)) return input
  const match = trimmed.match(/<body[^>]*>([\s\S]*)<\/body>/i)
  return match ? match[1] : input
}

/**
 * Read body.innerHTML from the editor iframe AFTER stripping the
 * editor's own injected DOM (overlay div, editor <script>, any
 * data-editor-* attributes, and any lingering contenteditable=true
 * attribute from a blur edge case). Prevents the editor from
 * accidentally serializing itself back into the saved html_content.
 */
function getCleanBodyHtml(iframeDoc: Document | null | undefined): string {
  if (!iframeDoc) return ''
  const clone = iframeDoc.body.cloneNode(true) as HTMLElement
  clone.querySelectorAll('#__editor_overlay').forEach((n) => n.remove())
  clone.querySelectorAll('script').forEach((n) => n.remove())
  clone.querySelectorAll('*').forEach((el) => {
    Array.from(el.attributes).forEach((attr) => {
      if (attr.name.startsWith('data-editor-')) {
        el.removeAttribute(attr.name)
      }
    })
    if (el.hasAttribute('contenteditable')) {
      el.removeAttribute('contenteditable')
    }
  })
  return clone.innerHTML
}

interface VisualEditorProps {
  html: string
  css: string
  onHtmlChange: (html: string) => void
  onCssChange: (css: string) => void
  onVideoUpload?: (file: File) => Promise<{ mp4_url: string; webm_url: string; poster_url: string }>
}

interface SelectedElement {
  selector: string
  tagName: string
  text: string
  styles: Record<string, string>
  rect: { x: number; y: number; width: number; height: number }
  contentType?: string
}

// Mirrors the injected editor script's selector-path algorithm (see
// editorScript below) so parent-side DOM mutations — convert-to-image/
// video/form — can re-select the element they just created without a
// postMessage round-trip.
function computeSelectorPath(doc: Document, el: Element): string {
  const path: string[] = []
  let cur: Element | null = el
  while (cur && cur !== doc.body && cur.parentElement) {
    const idx = Array.from(cur.parentElement.children).indexOf(cur)
    path.unshift(`${cur.tagName.toLowerCase()}:nth-child(${idx + 1})`)
    cur = cur.parentElement
  }
  return path.join(' > ')
}

function buildSelectedElement(doc: Document, el: HTMLElement): SelectedElement {
  const rect = el.getBoundingClientRect()
  const computed = doc.defaultView?.getComputedStyle(el)
  const style = (k: keyof CSSStyleDeclaration) => (computed ? String(computed[k] ?? '') : '')
  return {
    selector: computeSelectorPath(doc, el),
    tagName: el.tagName,
    text: el.textContent?.substring(0, 200) || '',
    contentType: el.getAttribute('data-content-type') || undefined,
    styles: {
      fontFamily: style('fontFamily'), fontSize: style('fontSize'), fontWeight: style('fontWeight'),
      color: style('color'), backgroundColor: style('backgroundColor'), textAlign: style('textAlign'),
      lineHeight: style('lineHeight'), letterSpacing: style('letterSpacing'),
      paddingTop: style('paddingTop'), paddingRight: style('paddingRight'),
      paddingBottom: style('paddingBottom'), paddingLeft: style('paddingLeft'),
      marginTop: style('marginTop'), marginRight: style('marginRight'),
      marginBottom: style('marginBottom'), marginLeft: style('marginLeft'),
      borderRadius: style('borderRadius'), opacity: style('opacity'),
      width: style('width'), height: style('height'),
    },
    rect: { x: rect.left, y: rect.top, width: rect.width, height: rect.height },
  }
}

// Moves the iframe's blue selection outline to match a parent-side
// re-selection (convert-to-X), so the visual indicator doesn't stay
// stuck over the element's old location until the next real click.
function repositionOverlay(doc: Document, el: HTMLElement) {
  const overlay = doc.getElementById('__editor_overlay')
  if (!overlay) return
  const rect = el.getBoundingClientRect()
  overlay.style.top = `${rect.top + (doc.defaultView?.scrollY || 0)}px`
  overlay.style.left = `${rect.left + (doc.defaultView?.scrollX || 0)}px`
  overlay.style.width = `${rect.width}px`
  overlay.style.height = `${rect.height}px`
  overlay.style.display = 'block'
}

// Walks up from whatever's selected (a column itself, or something
// nested inside one, like its heading or icon) to the nearest grid/flex
// ancestor with more than one child — the "row of columns" that a new
// column should actually be added to.
function findColumnContainer(doc: Document, start: HTMLElement): HTMLElement | null {
  let cur: HTMLElement | null = start
  while (cur && cur !== doc.body) {
    const display = doc.defaultView?.getComputedStyle(cur).display
    if ((display === 'grid' || display === 'flex') && cur.children.length > 1) return cur
    cur = cur.parentElement
  }
  return null
}

const FONTS = [
  'Inter', 'Open Sans', 'Roboto', 'Lato', 'Montserrat', 'Poppins',
  'Playfair Display', 'Merriweather', 'Raleway', 'Nunito',
  'Source Sans Pro', 'Oswald', 'PT Sans', 'Work Sans', 'DM Sans',
  'Space Grotesk', 'Outfit', 'Plus Jakarta Sans', 'Manrope', 'Libre Baskerville',
]

const FONT_WEIGHTS = [
  { label: i18n.t('ui:VisualEditor.thin'), value: '100' }, { label: i18n.t('ui:VisualEditor.light'), value: '300' },
  { label: i18n.t('ui:VisualEditor.regular'), value: '400' }, { label: i18n.t('ui:VisualEditor.medium'), value: '500' },
  { label: i18n.t('ui:VisualEditor.semiBold'), value: '600' }, { label: i18n.t('ui:VisualEditor.bold'), value: '700' },
  { label: i18n.t('ui:VisualEditor.extraBold'), value: '800' }, { label: i18n.t('ui:VisualEditor.black'), value: '900' },
]

// Self-contained gradient placeholders for image slots — no external
// hotlinks that can rot; users swap in real URLs via the Image panel.
const PLACEHOLDER_IMGS = [
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='450'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%236366f1'/%3E%3Cstop offset='1' stop-color='%23c7d2fe'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='600' height='450' fill='url(%23g)'/%3E%3C/svg%3E",
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='450'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%238b5cf6'/%3E%3Cstop offset='1' stop-color='%23ddd6fe'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='600' height='450' fill='url(%23g)'/%3E%3C/svg%3E",
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='450'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%230ea5e9'/%3E%3Cstop offset='1' stop-color='%23bae6fd'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='600' height='450' fill='url(%23g)'/%3E%3C/svg%3E",
]

// Section Library — served by the backend block library
// (GET /api/pages/variants, block model v2). One library for the Visual
// tab, the classic SectionEditor picker and the AI planner: the 72
// layouts that used to be hard-coded here were tokenized into seeds
// (backend/app/pages/seeds/visual_editor_layouts.json).
interface LibraryVariant { name: string; html: string; variantId: string; dynamic: boolean }
interface LibraryCategory { key: string; label: string; variants: LibraryVariant[] }
interface LibraryVariantRow {
  category: string
  variant_id: string
  display_name: string
  preview_html?: string
  capabilities?: string[]
  is_active?: boolean
}
const CATEGORY_LABELS: Record<string, string> = {
  nav: 'Navbar', hero: 'Hero', features: 'Features', pricing: 'Pricing',
  testimonials: 'Testimonials', cta: 'CTA', faq: 'FAQ', team: 'Team', stats: 'Stats',
  contact: 'Contact', booking: 'Booking', location: 'Location', services: 'Services', footer: 'Footer', gallery: 'Gallery', logos: 'Logos',
}
const CATEGORY_ORDER = Object.keys(CATEGORY_LABELS)
function groupLibrary(rows: LibraryVariantRow[]): LibraryCategory[] {
  const byCat = new Map<string, LibraryVariant[]>()
  for (const r of rows) {
    if (!r.preview_html) continue
    const list = byCat.get(r.category) ?? []
    list.push({
      name: r.display_name,
      html: r.preview_html,
      variantId: r.variant_id,
      dynamic: (r.capabilities ?? []).some(c => c !== 'static'),
    })
    byCat.set(r.category, list)
  }
  const keys = [...byCat.keys()].sort((a, b) => {
    const ia = CATEGORY_ORDER.indexOf(a), ib = CATEGORY_ORDER.indexOf(b)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib) || a.localeCompare(b)
  })
  return keys.map(key => ({
    key,
    label: CATEGORY_LABELS[key] ?? key.charAt(0).toUpperCase() + key.slice(1),
    variants: byCat.get(key)!,
  }))
}

// Individual elements insertable into any selected container — a lighter
// counterpart to the Section Library: atomic blocks rather than whole
// pre-composed layouts. Each `html` is appended as the selected
// element's last child by insertElement().
interface ElementDef { key: string; name: string; icon: string; html: string }
const ELEMENT_LIBRARY: ElementDef[] = [
  { key: 'heading', name: 'Heading', icon: '🔠', html: `<h2 class="text-3xl font-bold text-slate-900 mb-2">New Heading</h2>` },
  { key: 'paragraph', name: 'Paragraph', icon: '📝', html: `<p class="text-slate-600 leading-relaxed">Add your text here.</p>` },
  { key: 'button', name: 'Button', icon: '🔘', html: `<a href="#" class="inline-block px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition">Click Me</a>` },
  { key: 'image', name: 'Image', icon: '🖼️', html: `<img src="${PLACEHOLDER_IMGS[0]}" alt="" class="w-full h-auto rounded-lg" />` },
  { key: 'video', name: 'Video', icon: '🎬', html: `<video controls class="w-full rounded-lg" style="max-height:400px"></video>` },
  { key: 'form', name: 'Form', icon: '🧾', html: `<div data-content-type="form" class="p-6 border-2 border-dashed border-slate-300 rounded-lg text-center text-slate-400 text-sm">Choose a form in the panel →</div>` },
  { key: 'icon', name: i18n.t('ui:VisualEditor.iconBox'), icon: '⭐', html: `<div class="w-12 h-12 rounded-xl bg-indigo-100 text-2xl flex items-center justify-center mb-3">⭐</div>` },
  { key: 'list', name: 'List', icon: '📃', html: `<ul class="space-y-2 text-slate-600 list-disc list-inside"><li>First item</li><li>Second item</li><li>Third item</li></ul>` },
  { key: 'divider', name: 'Divider', icon: '➖', html: `<hr class="border-t border-slate-200 my-6" />` },
  { key: 'spacer', name: 'Spacer', icon: '⬜', html: `<div style="height:40px"></div>` },
]


export default function VisualEditor({ html, css, onHtmlChange, onCssChange, onVideoUpload }: VisualEditorProps) {
  const { t } = useTranslation('ui')
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [selected, setSelected] = useState<SelectedElement | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const [panelTab, setPanelTab] = useState<'typography' | 'colors' | 'image' | 'spacing' | 'section' | 'button' | 'layout' | 'video' | 'form'>('typography')
  const [undoStack, setUndoStack] = useState<string[]>([])
  const [redoStack, setRedoStack] = useState<string[]>([])
  const [showSectionLibrary, setShowSectionLibrary] = useState(false)
  const [pickerCategory, setPickerCategory] = useState<string | null>(null)
  const [library, setLibrary] = useState<LibraryCategory[] | null>(null)
  const [libraryError, setLibraryError] = useState<string | null>(null)

  // Load the block library the first time the Section Library opens.
  useEffect(() => {
    if (!showSectionLibrary || library !== null) return
    let cancelled = false
    ;(pagesApi.listVariants() as Promise<{ data: LibraryVariantRow[] }>)
      .then(resp => { if (!cancelled) setLibrary(groupLibrary(resp?.data ?? [])) })
      .catch((e: any) => { if (!cancelled) setLibraryError(e?.message || 'unknown') })
    return () => { cancelled = true }
  }, [showSectionLibrary, library])
  const pickerCat = pickerCategory ? library?.find(c => c.key === pickerCategory) ?? null : null
  const [showElementLibrary, setShowElementLibrary] = useState(false)
  const [forms, setForms] = useState<FormListItem[]>([])
  const [formsLoading, setFormsLoading] = useState(false)
  const [formsLoaded, setFormsLoaded] = useState(false)

  // Inject editor overlay script into iframe
  const editorScript = `
    <script>
      let selectedEl = null;
      let overlay = null;

      function createOverlay() {
        if (overlay) overlay.remove();
        overlay = document.createElement('div');
        overlay.id = '__editor_overlay';
        overlay.style.cssText = 'position:absolute;border:2px solid #3b82f6;pointer-events:none;z-index:99999;transition:all 0.15s;';
        document.body.appendChild(overlay);
      }

      var TEXT_TAGS = ['H1','H2','H3','H4','H5','H6','P','SPAN','A','LI','BUTTON','LABEL','TD','TH'];

      document.addEventListener('click', function(e) {
        var clicked = e.target;
        var isText = TEXT_TAGS.indexOf(clicked.tagName) !== -1;

        // For NON-text elements (sections, divs, etc.) preventDefault
        // so links don't navigate and forms don't submit. For text
        // elements we let the browser handle the click so the caret
        // positions correctly inside contentEditable.
        if (!isText) {
          e.preventDefault();
        }
        e.stopPropagation();

        selectedEl = clicked;

        // Single-click → caret. Make text elements editable on first
        // selection. Was dblclick — undiscoverable; users thought edits
        // were broken. State-of-the-art editors (Lovable, v0, Framer)
        // all do single-click → caret.
        if (isText && clicked.getAttribute('contenteditable') !== 'true') {
          clicked.contentEditable = 'true';
          clicked.focus();
          clicked.addEventListener('blur', function() {
            clicked.contentEditable = 'false';
            window.parent.postMessage({ type: 'content-changed', html: __cleanBodyHtml() }, '*');
          }, { once: true });
        }

        if (!overlay) createOverlay();

        var rect = selectedEl.getBoundingClientRect();
        overlay.style.top = (rect.top + window.scrollY) + 'px';
        overlay.style.left = (rect.left + window.scrollX) + 'px';
        overlay.style.width = rect.width + 'px';
        overlay.style.height = rect.height + 'px';
        overlay.style.display = 'block';

        var computed = getComputedStyle(selectedEl);
        var path = [];
        var el = selectedEl;
        while (el && el !== document.body) {
          var idx = Array.from(el.parentNode.children).indexOf(el);
          path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (idx+1) + ')');
          el = el.parentNode;
        }

        window.parent.postMessage({
          type: 'element-selected',
          data: {
            selector: path.join(' > '),
            tagName: selectedEl.tagName,
            text: selectedEl.textContent?.substring(0, 200) || '',
            contentType: selectedEl.getAttribute('data-content-type') || null,
            styles: {
              fontFamily: computed.fontFamily,
              fontSize: computed.fontSize,
              fontWeight: computed.fontWeight,
              color: computed.color,
              backgroundColor: computed.backgroundColor,
              textAlign: computed.textAlign,
              lineHeight: computed.lineHeight,
              letterSpacing: computed.letterSpacing,
              paddingTop: computed.paddingTop,
              paddingRight: computed.paddingRight,
              paddingBottom: computed.paddingBottom,
              paddingLeft: computed.paddingLeft,
              marginTop: computed.marginTop,
              marginRight: computed.marginRight,
              marginBottom: computed.marginBottom,
              marginLeft: computed.marginLeft,
              borderRadius: computed.borderRadius,
              opacity: computed.opacity,
              width: computed.width,
              height: computed.height,
            },
            rect: { x: rect.left, y: rect.top, width: rect.width, height: rect.height },
          }
        }, '*');
      }, true);

      // Read body.innerHTML stripped of editor-only DOM: the overlay
      // div, the editor script tag, data-editor-* attributes, and any
      // lingering contenteditable=true. Keep this in lockstep with the
      // parent-side getCleanBodyHtml() helper.
      function __cleanBodyHtml() {
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

      // (dblclick handler removed — single-click now owns enter-edit.)
    </script>
  `

  // Pages v2 emits full HTML5 docs into html_content. Unwrap to
  // body-inner before composing srcdoc so we don't nest <!DOCTYPE>
  // inside <body> (the browser parser destroys the structure if we do).
  // Body-fragment input (legacy v1) passes through untouched.
  const innerHtml = bodyInnerFromFullDoc(html)
  const srcdoc = `<!DOCTYPE html><html><head><script src="https://cdn.tailwindcss.com"></script><style>${css}</style></head><body style="cursor:pointer;">${innerHtml}${editorScript}</body></html>`

  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.type === 'element-selected') {
        setSelected(e.data.data)
        setPanelOpen(true)
        // Auto-detect panel tab
        const tag = e.data.data.tagName
        if (['IMG'].includes(tag)) setPanelTab('image')
        else if (tag === 'VIDEO') setPanelTab('video')
        else if (e.data.data.contentType === 'form') setPanelTab('form')
        else if (['BUTTON', 'A'].includes(tag) && e.data.data.text.length < 50) setPanelTab('button')
        else if (['SECTION', 'DIV', 'HEADER', 'FOOTER', 'MAIN'].includes(tag)) setPanelTab('section')
        else setPanelTab('typography')
      } else if (e.data?.type === 'content-changed') {
        pushUndo()
        onHtmlChange(e.data.html)
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [html])

  const pushUndo = useCallback(() => {
    setUndoStack(prev => [...prev.slice(-20), html])
    setRedoStack([])
  }, [html])

  const undo = useCallback(() => {
    if (undoStack.length === 0) return
    const prev = undoStack[undoStack.length - 1]
    setUndoStack(s => s.slice(0, -1))
    setRedoStack(s => [...s, html])
    onHtmlChange(prev)
  }, [undoStack, html, onHtmlChange])

  const redo = useCallback(() => {
    if (redoStack.length === 0) return
    const next = redoStack[redoStack.length - 1]
    setRedoStack(s => s.slice(0, -1))
    setUndoStack(s => [...s, html])
    onHtmlChange(next)
  }, [redoStack, html, onHtmlChange])

  // Apply style to selected element via iframe postMessage
  const applyStyle = useCallback((prop: string, value: string) => {
    if (!selected || !iframeRef.current?.contentWindow) return
    pushUndo()
    const iframeDoc = iframeRef.current.contentDocument
    if (!iframeDoc) return

    // Find element by selector
    try {
      const el = iframeDoc.querySelector(selected.selector) || iframeDoc.body
      ;(el as HTMLElement).style.setProperty(prop, value)
      onHtmlChange(getCleanBodyHtml(iframeDoc))
      // Update selected styles
      const computed = iframeDoc.defaultView?.getComputedStyle(el as Element)
      if (computed) {
        setSelected(prev => prev ? { ...prev, styles: { ...prev.styles, [prop]: value } } : null)
      }
    } catch {
      // Fallback: inject CSS rule
      const rule = `${selected.selector} { ${prop}: ${value} !important; }`
      onCssChange(css + '\n' + rule)
    }
  }, [selected, html, css, pushUndo, onHtmlChange, onCssChange])

  const deleteSelected = useCallback(() => {
    if (!selected || !iframeRef.current?.contentDocument) return
    pushUndo()
    try {
      const doc = iframeRef.current.contentDocument
      const el = doc.querySelector(selected.selector)
      el?.remove()
      onHtmlChange(getCleanBodyHtml(doc))
      setSelected(null)
      setPanelOpen(false)
    } catch { /* ignore */ }
  }, [selected, pushUndo, onHtmlChange])

  const duplicateSelected = useCallback(() => {
    if (!selected || !iframeRef.current?.contentDocument) return
    pushUndo()
    try {
      const doc = iframeRef.current.contentDocument
      const el = doc.querySelector(selected.selector)
      if (el) {
        const clone = el.cloneNode(true) as HTMLElement
        el.parentNode?.insertBefore(clone, el.nextSibling)
        onHtmlChange(getCleanBodyHtml(doc))
      }
    } catch { /* ignore */ }
  }, [selected, pushUndo, onHtmlChange])

  // Swap whatever's inside the selected element (a section, a grid
  // column, anything) for an image, a video, or an embeddable form —
  // re-selects the newly-created node so its dedicated panel (Image/
  // Video/Form) opens immediately, matching what a real click would do.
  const convertSelectedTo = useCallback((type: 'image' | 'video' | 'form') => {
    if (!selected || !iframeRef.current?.contentDocument) return
    pushUndo()
    const doc = iframeRef.current.contentDocument
    try {
      const el = doc.querySelector(selected.selector) as HTMLElement
      if (!el) return
      el.removeAttribute('data-content-type')
      if (type === 'image') {
        el.innerHTML = `<img src="${PLACEHOLDER_IMGS[0]}" alt="" class="w-full h-full object-cover rounded-lg" />`
        onHtmlChange(getCleanBodyHtml(doc))
        const img = el.querySelector('img')
        if (img) {
          setSelected(buildSelectedElement(doc, img))
          setPanelTab('image')
          setPanelOpen(true)
          repositionOverlay(doc, img)
        }
      } else if (type === 'video') {
        el.innerHTML = `<video controls class="w-full rounded-lg" style="max-height:400px"></video>`
        onHtmlChange(getCleanBodyHtml(doc))
        const video = el.querySelector('video')
        if (video) {
          setSelected(buildSelectedElement(doc, video))
          setPanelTab('video')
          setPanelOpen(true)
          repositionOverlay(doc, video)
        }
      } else {
        el.setAttribute('data-content-type', 'form')
        el.innerHTML = `<div class="p-6 border-2 border-dashed border-slate-300 rounded-lg text-center text-slate-400 text-sm">Choose a form in the panel →</div>`
        onHtmlChange(getCleanBodyHtml(doc))
        setSelected(buildSelectedElement(doc, el))
        setPanelTab('form')
        setPanelOpen(true)
        repositionOverlay(doc, el)
      }
    } catch { /* ignore */ }
  }, [selected, pushUndo, onHtmlChange])

  // Fetch the account's forms the first time the Form panel opens —
  // not eagerly, since most editing sessions never touch it.
  useEffect(() => {
    if (panelTab !== 'form' || formsLoaded) return
    setFormsLoading(true)
    listForms(1, 100)
      .then(res => setForms(res.data))
      .catch(() => { /* form list is optional — embedding still works once one exists */ })
      .finally(() => { setFormsLoading(false); setFormsLoaded(true) })
  }, [panelTab, formsLoaded])

  const embedForm = useCallback((formId: string) => {
    if (!formId || !selected || !iframeRef.current?.contentDocument) return
    pushUndo()
    const doc = iframeRef.current.contentDocument
    try {
      const el = doc.querySelector(selected.selector) as HTMLElement
      if (!el) return
      el.setAttribute('data-content-type', 'form')
      el.innerHTML = `<iframe src="${window.location.origin}/f/${formId}" style="width:100%;min-height:480px;border:0;" title="Embedded form"></iframe>`
      onHtmlChange(getCleanBodyHtml(doc))
      setSelected(buildSelectedElement(doc, el))
    } catch { /* ignore */ }
  }, [selected, pushUndo, onHtmlChange])

  // Adds another column to whatever row the current selection lives in
  // (found via findColumnContainer, so this works whether a column
  // itself, or something nested inside one, is selected) by cloning its
  // last column — inherits that column's own styling for free — and
  // widening the grid template so the new column sits in the row
  // instead of wrapping onto its own line.
  const addColumn = useCallback(() => {
    if (!selected || !iframeRef.current?.contentDocument) return
    const doc = iframeRef.current.contentDocument
    try {
      const el = doc.querySelector(selected.selector) as HTMLElement
      if (!el) return
      const container = findColumnContainer(doc, el)
      if (!container || container.children.length === 0) return
      pushUndo()
      const lastChild = container.children[container.children.length - 1] as HTMLElement
      const clone = lastChild.cloneNode(true) as HTMLElement
      container.appendChild(clone)
      if (doc.defaultView?.getComputedStyle(container).display === 'grid') {
        container.style.gridTemplateColumns = `repeat(${container.children.length}, 1fr)`
      }
      onHtmlChange(getCleanBodyHtml(doc))
      setSelected(buildSelectedElement(doc, clone))
      setPanelOpen(true)
      repositionOverlay(doc, clone)
    } catch { /* ignore */ }
  }, [selected, pushUndo, onHtmlChange])

  const canAddColumn = (() => {
    if (!selected || !iframeRef.current?.contentDocument) return false
    const doc = iframeRef.current.contentDocument
    const el = doc.querySelector(selected.selector) as HTMLElement | null
    return !!(el && findColumnContainer(doc, el))
  })()

  // Appends any block from the Element Library as the last child of
  // whatever's selected — same "acts on the current selection" model as
  // Convert Content, Add Column, and the section background controls.
  const insertElement = useCallback((elementHtml: string) => {
    if (!selected || !iframeRef.current?.contentDocument) return
    pushUndo()
    const doc = iframeRef.current.contentDocument
    try {
      const el = doc.querySelector(selected.selector) as HTMLElement
      if (!el) return
      const temp = doc.createElement('div')
      temp.innerHTML = elementHtml
      const node = temp.firstElementChild as HTMLElement | null
      if (!node) return
      el.appendChild(node)
      onHtmlChange(getCleanBodyHtml(doc))
      setSelected(buildSelectedElement(doc, node))
      setPanelOpen(true)
      repositionOverlay(doc, node)
      setShowElementLibrary(false)
      // Auto-switch tab to match the new element (mirrors the injected
      // script's own auto-detect rules).
      if (node.tagName === 'IMG') setPanelTab('image')
      else if (node.tagName === 'VIDEO') setPanelTab('video')
      else if (node.getAttribute('data-content-type') === 'form') setPanelTab('form')
      else if (['A', 'BUTTON'].includes(node.tagName)) setPanelTab('button')
      else setPanelTab('typography')
    } catch { /* ignore */ }
  }, [selected, pushUndo, onHtmlChange])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) { e.preventDefault(); undo() }
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && e.shiftKey) { e.preventDefault(); redo() }
      if (e.key === 'Delete' && selected) { e.preventDefault(); deleteSelected() }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [undo, redo, selected, deleteSelected])

  const parsePixels = (v: string) => parseInt(v) || 0

  // Shown at the top of Section/Image/Video/Form so any selected block —
  // a whole section or a single grid column — can be swapped to any
  // other content type, from any of those tabs.
  const convertButtons = selected && (
    <div>
      <label className="block text-gray-500 dark:text-gray-400 mb-1 font-medium">{t('ui:VisualEditor.convertContent')}</label>
      <div className="grid grid-cols-3 gap-2">
        <button onClick={() => convertSelectedTo('image')}
          className="flex flex-col items-center gap-1 px-2 py-2.5 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300">
          <span className="text-base">🖼️</span><span>{t('ui:VisualEditor.image')}</span>
        </button>
        <button onClick={() => convertSelectedTo('video')}
          className="flex flex-col items-center gap-1 px-2 py-2.5 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300">
          <span className="text-base">🎬</span><span>{t('ui:VisualEditor.video')}</span>
        </button>
        <button onClick={() => convertSelectedTo('form')}
          className="flex flex-col items-center gap-1 px-2 py-2.5 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300">
          <span className="text-base">📝</span><span>{t('ui:VisualEditor.form')}</span>
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex h-full relative">
      {/* Toolbar */}
      <div className="absolute top-0 left-0 right-0 z-10 flex items-center gap-1 px-3 py-1.5 bg-white dark:bg-gray-800 border-b text-xs">
        <button onClick={undo} disabled={undoStack.length === 0} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30" title={t('ui:VisualEditor.undo')}>
          <Undo2 className="w-4 h-4" />
        </button>
        <button onClick={redo} disabled={redoStack.length === 0} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30" title={t('ui:VisualEditor.redo')}>
          <Redo2 className="w-4 h-4" />
        </button>
        <div className="w-px h-5 bg-gray-200 dark:bg-gray-600 mx-1" />
        <button onClick={() => setShowSectionLibrary(true)} className="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300">
          <Plus className="w-3.5 h-3.5" /> {t('ui:VisualEditor.addSection')}
        </button>
        {selected && (
          <>
            <div className="w-px h-5 bg-gray-200 dark:bg-gray-600 mx-1" />
            <span className="text-gray-400 dark:text-gray-500">{selected.tagName}</span>
            <button onClick={duplicateSelected} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700" title={t('ui:VisualEditor.duplicate')}>
              <Copy className="w-3.5 h-3.5" />
            </button>
            <button onClick={deleteSelected} className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-red-500" title={t('ui:VisualEditor.delete')}>
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </>
        )}
      </div>

      {/* Canvas */}
      <div className="flex-1 pt-9 bg-gray-100 dark:bg-gray-900 overflow-auto">
        <iframe
          ref={iframeRef}
          srcDoc={srcdoc}
          className="w-full h-full border-0 bg-white"
          sandbox="allow-scripts allow-same-origin"
          title={t('ui:VisualEditor.visualEditor')}
        />
      </div>

      {/* Properties Panel */}
      {panelOpen && selected && (
        <div className="w-72 border-l bg-white dark:bg-gray-800 pt-9 overflow-y-auto shrink-0">
          {/* Panel tabs */}
          <div className="flex flex-wrap gap-1 p-2 border-b">
            {(['typography', 'colors', 'spacing', 'section', 'image', 'button', 'layout', 'video', 'form'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setPanelTab(tab)}
                className={`px-2 py-1 text-xs rounded ${panelTab === tab ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600' : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700'}`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          <div className="p-3 space-y-4 text-xs">
            {/* Typography */}
            {panelTab === 'typography' && (
              <>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.fontFamily')}</label>
                  <select
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    value={selected.styles.fontFamily?.split(',')[0]?.replace(/"/g, '').trim() || 'Inter'}
                    onChange={e => applyStyle('font-family', `"${e.target.value}", sans-serif`)}
                  >
                    {FONTS.map(f => <option key={f} value={f}>{f}</option>)}
                  </select>
                </div>
                <div className="flex gap-2">
                  <div className="flex-1">
                    <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.sizePx')}</label>
                    <input
                      type="range" min="8" max="120" step="1"
                      value={parsePixels(selected.styles.fontSize)}
                      onChange={e => applyStyle('font-size', `${e.target.value}px`)}
                      className="w-full"
                    />
                    <span className="text-gray-600 dark:text-gray-300">{parsePixels(selected.styles.fontSize)}px</span>
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.weight')}</label>
                  <select
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    value={selected.styles.fontWeight || '400'}
                    onChange={e => applyStyle('font-weight', e.target.value)}
                  >
                    {FONT_WEIGHTS.map(fw => <option key={fw.value} value={fw.value}>{fw.label} ({fw.value})</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.color')}</label>
                  <div className="flex gap-2">
                    <input type="color" value={selected.styles.color || '#000000'} onChange={e => applyStyle('color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" value={selected.styles.color || ''} onChange={e => applyStyle('color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.alignment')}</label>
                  <div className="flex gap-1">
                    {[
                      { icon: AlignLeft, val: 'left' }, { icon: AlignCenter, val: 'center' },
                      { icon: AlignRight, val: 'right' }, { icon: AlignJustify, val: 'justify' },
                    ].map(({ icon: Icon, val }) => (
                      <button key={val} onClick={() => applyStyle('text-align', val)}
                        className={`p-1.5 rounded ${selected.styles.textAlign === val ? 'bg-blue-100 dark:bg-blue-900/30' : 'hover:bg-gray-100 dark:hover:bg-gray-700'}`}>
                        <Icon className="w-4 h-4" />
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.lineHeight')}</label>
                  <input type="range" min="0.8" max="3" step="0.1"
                    value={parseFloat(selected.styles.lineHeight) || 1.5}
                    onChange={e => applyStyle('line-height', e.target.value)}
                    className="w-full" />
                  <span className="text-gray-600 dark:text-gray-300">{parseFloat(selected.styles.lineHeight)?.toFixed(1) || '1.5'}</span>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.letterSpacing')}</label>
                  <input type="range" min="-2" max="10" step="0.5"
                    value={parsePixels(selected.styles.letterSpacing)}
                    onChange={e => applyStyle('letter-spacing', `${e.target.value}px`)}
                    className="w-full" />
                </div>
              </>
            )}

            {/* Colors */}
            {panelTab === 'colors' && (
              <>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.backgroundColor')}</label>
                  <div className="flex gap-2">
                    <input type="color" value="#ffffff" onChange={e => applyStyle('background-color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" placeholder="#ffffff" onChange={e => applyStyle('background-color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.textColor')}</label>
                  <div className="flex gap-2">
                    <input type="color" value={selected.styles.color || '#000000'} onChange={e => applyStyle('color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" value={selected.styles.color || ''} onChange={e => applyStyle('color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.opacity')}</label>
                  <input type="range" min="0" max="100" step="1"
                    value={Math.round((parseFloat(selected.styles.opacity) || 1) * 100)}
                    onChange={e => applyStyle('opacity', String(parseInt(e.target.value) / 100))}
                    className="w-full" />
                  <span className="text-gray-600 dark:text-gray-300">{Math.round((parseFloat(selected.styles.opacity) || 1) * 100)}%</span>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.borderRadius')}</label>
                  <input type="range" min="0" max="50" step="1"
                    value={parsePixels(selected.styles.borderRadius)}
                    onChange={e => applyStyle('border-radius', `${e.target.value}px`)}
                    className="w-full" />
                  <span className="text-gray-600 dark:text-gray-300">{parsePixels(selected.styles.borderRadius)}px</span>
                </div>
              </>
            )}

            {/* Spacing */}
            {panelTab === 'spacing' && (
              <>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1 font-medium">{t('ui:VisualEditor.padding')}</label>
                  <div className="grid grid-cols-2 gap-2">
                    {(['Top', 'Right', 'Bottom', 'Left'] as const).map(side => (
                      <div key={side}>
                        <label className="text-gray-400 text-[10px]">{side}</label>
                        <input type="number" min="0" max="200"
                          value={parsePixels(selected.styles[`padding${side}` as keyof typeof selected.styles] || '0')}
                          onChange={e => applyStyle(`padding-${side.toLowerCase()}`, `${e.target.value}px`)}
                          className="w-full p-1 border rounded text-center bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1 font-medium">{t('ui:VisualEditor.margin')}</label>
                  <div className="grid grid-cols-2 gap-2">
                    {(['Top', 'Right', 'Bottom', 'Left'] as const).map(side => (
                      <div key={side}>
                        <label className="text-gray-400 text-[10px]">{side}</label>
                        <input type="number" min="-100" max="200"
                          value={parsePixels(selected.styles[`margin${side}` as keyof typeof selected.styles] || '0')}
                          onChange={e => applyStyle(`margin-${side.toLowerCase()}`, `${e.target.value}px`)}
                          className="w-full p-1 border rounded text-center bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.width')}</label>
                  <input type="text" value={selected.styles.width || 'auto'}
                    onChange={e => applyStyle('width', e.target.value)}
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.height')}</label>
                  <input type="text" value={selected.styles.height || 'auto'}
                    onChange={e => applyStyle('height', e.target.value)}
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                </div>
              </>
            )}

            {/* Section controls */}
            {panelTab === 'section' && (
              <>
                {convertButtons}
                <div className="space-y-2">
                  <button onClick={addColumn} disabled={!canAddColumn}
                    title={canAddColumn ? t('ui:VisualEditor.cloneTheLastColumnIn') : t('ui:VisualEditor.selectAColumnOrSomething')}
                    className="w-full flex items-center gap-2 px-3 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent dark:disabled:hover:bg-transparent">
                    <Columns3 className="w-4 h-4" /> {t('ui:VisualEditor.addColumn')}
                  </button>
                  <button onClick={() => setShowElementLibrary(true)}
                    className="w-full flex items-center gap-2 px-3 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300">
                    <Blocks className="w-4 h-4" /> {t('ui:VisualEditor.addElement')}
                  </button>
                  <button onClick={() => setShowSectionLibrary(true)}
                    className="w-full flex items-center gap-2 px-3 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300">
                    <Plus className="w-4 h-4" /> {t('ui:VisualEditor.addSectionBelow')}
                  </button>
                  <button onClick={duplicateSelected}
                    className="w-full flex items-center gap-2 px-3 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300">
                    <Copy className="w-4 h-4" /> {t('ui:VisualEditor.duplicateSection')}
                  </button>
                  <button onClick={deleteSelected}
                    className="w-full flex items-center gap-2 px-3 py-2 border border-red-200 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-red-600">
                    <Trash2 className="w-4 h-4" /> {t('ui:VisualEditor.deleteSection')}
                  </button>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1 font-medium">{t('ui:VisualEditor.background')}</label>
                  <div className="flex gap-2">
                    <input type="color" value="#ffffff" onChange={e => applyStyle('background-color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" placeholder={t('ui:VisualEditor.colorOrGradient')} onChange={e => applyStyle('background', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.maxWidth')}</label>
                  <input type="range" min="800" max="1400" step="50"
                    value={1200}
                    onChange={e => applyStyle('max-width', `${e.target.value}px`)}
                    className="w-full" />
                </div>
              </>
            )}

            {/* Image controls */}
            {panelTab === 'image' && (
              <>
                {convertButtons}
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.imageSource')}</label>
                  <input type="text" placeholder={t('ui:VisualEditor.imageUrl')}
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => {
                      if (!iframeRef.current?.contentDocument || !selected) return
                      try {
                        const el = iframeRef.current.contentDocument.querySelector(selected.selector) as HTMLImageElement
                        if (el) { el.src = e.target.value; onHtmlChange(getCleanBodyHtml(iframeRef.current.contentDocument)) }
                      } catch { /* ignore */ }
                    }} />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.objectFit')}</label>
                  <select className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => applyStyle('object-fit', e.target.value)}>
                    <option value="cover">{t('ui:VisualEditor.cover')}</option>
                    <option value="contain">{t('ui:VisualEditor.contain')}</option>
                    <option value="fill">{t('ui:VisualEditor.fill')}</option>
                    <option value="none">{t('ui:VisualEditor.none')}</option>
                  </select>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.altText')}</label>
                  <input type="text" placeholder={t('ui:VisualEditor.describeTheImage')}
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => {
                      if (!iframeRef.current?.contentDocument || !selected) return
                      try {
                        const el = iframeRef.current.contentDocument.querySelector(selected.selector) as HTMLImageElement
                        if (el) { el.alt = e.target.value; onHtmlChange(getCleanBodyHtml(iframeRef.current.contentDocument)) }
                      } catch { /* ignore */ }
                    }} />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.borderRadius')}</label>
                  <input type="range" min="0" max="50" step="1" value={0}
                    onChange={e => applyStyle('border-radius', `${e.target.value}px`)} className="w-full" />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.shadow')}</label>
                  <select className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => applyStyle('box-shadow', e.target.value)}>
                    <option value="none">{t('ui:VisualEditor.none')}</option>
                    <option value="0 1px 3px rgba(0,0,0,0.12)">{t('ui:VisualEditor.small')}</option>
                    <option value="0 4px 6px rgba(0,0,0,0.1)">{t('ui:VisualEditor.medium')}</option>
                    <option value="0 10px 25px rgba(0,0,0,0.15)">{t('ui:VisualEditor.large')}</option>
                  </select>
                </div>
              </>
            )}

            {/* Button controls */}
            {panelTab === 'button' && (
              <>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.background')}</label>
                  <div className="flex gap-2">
                    <input type="color" value="#3b82f6" onChange={e => applyStyle('background-color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" placeholder="#3b82f6" onChange={e => applyStyle('background-color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.textColor')}</label>
                  <div className="flex gap-2">
                    <input type="color" value="#ffffff" onChange={e => applyStyle('color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" placeholder="#ffffff" onChange={e => applyStyle('color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.borderRadius')}</label>
                  <input type="range" min="0" max="50" value={8}
                    onChange={e => applyStyle('border-radius', `${e.target.value}px`)} className="w-full" />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.size')}</label>
                  <div className="flex gap-1">
                    {[
                      { label: 'S', padding: '6px 16px' },
                      { label: 'M', padding: '10px 24px' },
                      { label: 'L', padding: '14px 32px' },
                      { label: t('ui:VisualEditor.full'), padding: '14px 32px', width: '100%' },
                    ].map(s => (
                      <button key={s.label} onClick={() => {
                        applyStyle('padding', s.padding)
                        if (s.width) applyStyle('width', s.width)
                      }}
                        className="flex-1 px-2 py-1 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-center">
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.linkUrl')}</label>
                  <input type="text" placeholder="https://..."
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => {
                      if (!iframeRef.current?.contentDocument || !selected) return
                      try {
                        const el = iframeRef.current.contentDocument.querySelector(selected.selector) as HTMLAnchorElement
                        if (el && 'href' in el) { el.href = e.target.value; onHtmlChange(getCleanBodyHtml(iframeRef.current.contentDocument)) }
                      } catch { /* ignore */ }
                    }} />
                </div>
              </>
            )}

            {/* Layout */}
            {panelTab === 'layout' && (
              <>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.columns')}</label>
                  <div className="flex gap-1">
                    {[1, 2, 3, 4].map(n => (
                      <button key={n} onClick={() => applyStyle('grid-template-columns', `repeat(${n}, 1fr)`)}
                        className="flex-1 px-2 py-2 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-center">
                        {n}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.gap')}</label>
                  <input type="range" min="0" max="60" step="4" value={16}
                    onChange={e => applyStyle('gap', `${e.target.value}px`)} className="w-full" />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.display')}</label>
                  <select className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => applyStyle('display', e.target.value)}>
                    <option value="block">{t('ui:VisualEditor.block')}</option>
                    <option value="flex">{t('ui:VisualEditor.flex')}</option>
                    <option value="grid">{t('ui:VisualEditor.grid')}</option>
                    <option value="inline-flex">{t('ui:VisualEditor.inlineFlex')}</option>
                  </select>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.alignItems')}</label>
                  <div className="flex gap-1">
                    {['flex-start', 'center', 'flex-end'].map(v => (
                      <button key={v} onClick={() => applyStyle('align-items', v)}
                        className="flex-1 px-2 py-1 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-center text-[10px]">
                        {v.replace('flex-', '')}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}

            {/* Video — either the selected element's own content (a
                <video> inserted via Convert Content) or, when the
                selection is a section/column instead, a full-bleed
                background video behind its existing content. */}
            {panelTab === 'video' && (
              <>
                {convertButtons}
                <p className="text-gray-500 dark:text-gray-400 mb-2">
                  {selected?.tagName === 'VIDEO' ? t('ui:VisualEditor.thisVideoIsTheBlock') : t('ui:VisualEditor.addAVideoBackgroundTo')}
                </p>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.uploadVideo')}</label>
                  <input type="file" accept="video/mp4,video/webm,video/quicktime"
                    className="w-full text-xs"
                    onChange={async (e) => {
                      const file = e.target.files?.[0]
                      if (!file || !onVideoUpload) return
                      try {
                        const result = await onVideoUpload(file)
                        if (!iframeRef.current?.contentDocument || !selected) return
                        const doc = iframeRef.current.contentDocument
                        const el = doc.querySelector(selected.selector) as HTMLElement
                        if (!el) return
                        pushUndo()
                        if (selected.tagName === 'VIDEO') {
                          // Direct-content video: set this element's own source.
                          el.innerHTML = ''
                          el.setAttribute('poster', result.poster_url)
                          const sourceWebm = doc.createElement('source')
                          sourceWebm.src = result.webm_url
                          sourceWebm.type = 'video/webm'
                          const sourceMp4 = doc.createElement('source')
                          sourceMp4.src = result.mp4_url
                          sourceMp4.type = 'video/mp4'
                          el.appendChild(sourceWebm)
                          el.appendChild(sourceMp4)
                          ;(el as HTMLVideoElement).load()
                          onHtmlChange(getCleanBodyHtml(doc))
                        } else {
                          // Legacy path: video BACKGROUND behind the
                          // selected section's existing content.
                          el.style.position = 'relative'
                          el.style.overflow = 'hidden'
                          const video = doc.createElement('video')
                          video.autoplay = true
                          video.muted = true
                          video.loop = true
                          video.playsInline = true
                          video.poster = result.poster_url
                          video.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;z-index:0;'
                          const sourceWebm = doc.createElement('source')
                          sourceWebm.src = result.webm_url
                          sourceWebm.type = 'video/webm'
                          const sourceMp4 = doc.createElement('source')
                          sourceMp4.src = result.mp4_url
                          sourceMp4.type = 'video/mp4'
                          video.appendChild(sourceWebm)
                          video.appendChild(sourceMp4)
                          el.insertBefore(video, el.firstChild)
                          const overlay = doc.createElement('div')
                          overlay.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.4);z-index:0;'
                          el.insertBefore(overlay, video.nextSibling)
                          Array.from(el.children).forEach((child, i) => {
                            if (i > 1) (child as HTMLElement).style.position = 'relative'
                            if (i > 1) (child as HTMLElement).style.zIndex = '1'
                          })
                          onHtmlChange(getCleanBodyHtml(doc))
                        }
                      } catch { /* ignore */ }
                    }} />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.orPasteUrl')}</label>
                  <input type="text" placeholder="https://..."
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => {
                      const url = e.target.value.trim()
                      if (!url || !iframeRef.current?.contentDocument || !selected) return
                      pushUndo()
                      const doc = iframeRef.current.contentDocument
                      try {
                        const el = doc.querySelector(selected.selector) as HTMLElement
                        if (!el) return
                        if (selected.tagName === 'VIDEO') {
                          el.innerHTML = `<source src="${url}">`
                          ;(el as HTMLVideoElement).load()
                        } else {
                          el.style.position = 'relative'
                          el.style.overflow = 'hidden'
                          const video = doc.createElement('video')
                          video.autoplay = true
                          video.muted = true
                          video.loop = true
                          video.playsInline = true
                          video.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;z-index:0;'
                          video.innerHTML = `<source src="${url}">`
                          el.insertBefore(video, el.firstChild)
                          const overlay = doc.createElement('div')
                          overlay.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.4);z-index:0;'
                          el.insertBefore(overlay, video.nextSibling)
                          Array.from(el.children).forEach((child, i) => {
                            if (i > 1) (child as HTMLElement).style.position = 'relative'
                            if (i > 1) (child as HTMLElement).style.zIndex = '1'
                          })
                        }
                        onHtmlChange(getCleanBodyHtml(doc))
                      } catch { /* ignore */ }
                    }} />
                </div>
                {selected?.tagName !== 'VIDEO' && (
                  <div>
                    <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.overlayOpacity')}</label>
                    <input type="range" min="0" max="80" step="5" value={40} className="w-full" />
                  </div>
                )}
              </>
            )}

            {/* Form — embed one of the account's real forms via its
                public /f/:formId page. */}
            {panelTab === 'form' && (
              <>
                {convertButtons}
                <p className="text-gray-500 dark:text-gray-400 mb-2">{t('ui:VisualEditor.embedOneOfYourForms')}</p>
                {formsLoading ? (
                  <p className="text-gray-400">{t('ui:VisualEditor.loadingForms')}</p>
                ) : forms.length === 0 ? (
                  <div className="text-gray-500 dark:text-gray-400 space-y-2">
                    <p>{t('ui:VisualEditor.youDonTHaveAny')}</p>
                    <a href="/forms" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">{t('ui:VisualEditor.createAForm')}</a>
                  </div>
                ) : (
                  <div>
                    <label className="block text-gray-500 dark:text-gray-400 mb-1">{t('ui:VisualEditor.form')}</label>
                    <select
                      defaultValue=""
                      className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                      onChange={e => embedForm(e.target.value)}>
                      <option value="" disabled>{t('ui:VisualEditor.chooseAForm')}</option>
                      {forms.map(f => (
                        <option key={f.id} value={f.id}>{f.name}</option>
                      ))}
                    </select>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Section Library Modal — futuristic two-step picker: category, then live-previewed layout variants */}
      {showSectionLibrary && (
        <div
          className="absolute inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={() => { setShowSectionLibrary(false); setPickerCategory(null) }}>
          <div
            className="relative w-[860px] max-w-[92vw] max-h-[85vh] overflow-hidden rounded-2xl border border-indigo-400/20 bg-slate-950 shadow-[0_0_90px_-15px_rgba(99,102,241,0.5)]"
            onClick={e => e.stopPropagation()}>
            {/* ambient glow accents */}
            <div className="pointer-events-none absolute -top-24 -left-24 w-72 h-72 rounded-full bg-indigo-600/20 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-24 -right-24 w-72 h-72 rounded-full bg-violet-600/20 blur-3xl" />

            <div className="relative flex items-center justify-between px-6 py-4 border-b border-white/10">
              <div>
                {pickerCategory ? (
                  <button
                    onClick={() => setPickerCategory(null)}
                    className="flex items-center gap-1.5 text-xs font-medium text-indigo-300 hover:text-indigo-200 mb-1 transition-colors">
                   {t('ui:VisualEditor.backToSections')}
                  </button>
                ) : (
                  <p className="text-xs font-medium tracking-widest uppercase text-indigo-400 mb-1">{t('ui:VisualEditor.sectionLibrary')}</p>
                )}
                <h3 className="text-lg font-bold bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
                  {pickerCat ? t('ui:VisualEditor.pickercategoryLayouts', { pickerCategory: pickerCat.label }) : t('ui:VisualEditor.addASection')}
                </h3>
              </div>
              <button
                onClick={() => { setShowSectionLibrary(false); setPickerCategory(null) }}
                className="w-8 h-8 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white transition-colors">✕</button>
            </div>

            <div className="relative p-6 overflow-y-auto max-h-[calc(85vh-73px)]">
              {libraryError ? (
                <div className="py-16 text-center text-sm text-rose-300">
                  {t('ui:VisualEditor.libraryLoadFailed')} <span className="text-slate-500">({libraryError})</span>
                </div>
              ) : library === null ? (
                <div className="py-16 text-center text-sm text-slate-400">{t('ui:VisualEditor.loadingLibrary')}</div>
              ) : !pickerCat ? (
                <div className="grid grid-cols-3 gap-4">
                  {library.map(cat => (
                    <button key={cat.key}
                      onClick={() => setPickerCategory(cat.key)}
                      className="group relative rounded-xl overflow-hidden border border-white/10 bg-white/[0.03] hover:border-indigo-400/60 hover:bg-white/[0.06] transition-all hover:shadow-[0_0_25px_-5px_rgba(99,102,241,0.5)] text-left">
                      <div className="relative">
                        <SectionThumb html={cat.variants[0].html} width={252} className="rounded-lg" />
                        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent" />
                      </div>
                      <div className="px-3 py-2.5 flex items-center justify-between">
                        <span className="text-sm font-semibold text-slate-100">{cat.label}</span>
                        <span className="text-[11px] font-medium text-indigo-300/80 opacity-0 group-hover:opacity-100 transition-opacity">
                          {cat.variants.length} {t('ui:VisualEditor.layouts')}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-5">
                  {pickerCat.variants.map(variant => (
                    <button key={variant.variantId}
                      onClick={() => {
                        pushUndo()
                        onHtmlChange(html + '\n' + variant.html)
                        setShowSectionLibrary(false)
                        setPickerCategory(null)
                      }}
                      className="group relative rounded-xl overflow-hidden border border-white/10 bg-white/[0.03] hover:border-indigo-400/60 hover:bg-white/[0.06] transition-all hover:shadow-[0_0_30px_-5px_rgba(99,102,241,0.5)] text-left">
                      <SectionThumb html={variant.html} width={368} ratio={368 / 210} className="rounded-lg" />
                      <div className="px-4 py-3 flex items-center justify-between border-t border-white/10">
                        <span className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                          {variant.name}
                          {variant.dynamic && (
                            <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-200">{t('ui:VisualEditor.dynamic')}</span>
                          )}
                        </span>
                        <span className="text-xs font-medium text-indigo-300 opacity-0 group-hover:opacity-100 transition-opacity">{t('ui:VisualEditor.useThisLayout')}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Element Library Modal — atomic blocks appended to whatever's
          selected, the lighter counterpart to the Section Library above. */}
      {showElementLibrary && (
        <div
          className="absolute inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={() => setShowElementLibrary(false)}>
          <div
            className="relative w-[480px] max-w-[92vw] max-h-[80vh] overflow-hidden rounded-2xl border border-indigo-400/20 bg-slate-950 shadow-[0_0_90px_-15px_rgba(99,102,241,0.5)]"
            onClick={e => e.stopPropagation()}>
            <div className="pointer-events-none absolute -top-24 -left-24 w-72 h-72 rounded-full bg-indigo-600/20 blur-3xl" />
            <div className="relative flex items-center justify-between px-6 py-4 border-b border-white/10">
              <div>
                <p className="text-xs font-medium tracking-widest uppercase text-indigo-400 mb-1">{t('ui:VisualEditor.elementLibrary')}</p>
                <h3 className="text-lg font-bold bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">{t('ui:VisualEditor.addAnElement')}</h3>
              </div>
              <button
                onClick={() => setShowElementLibrary(false)}
                className="w-8 h-8 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white transition-colors">✕</button>
            </div>
            <div className="relative p-6 overflow-y-auto max-h-[calc(80vh-73px)] grid grid-cols-3 gap-3">
              {ELEMENT_LIBRARY.map(item => (
                <button key={item.key}
                  onClick={() => insertElement(item.html)}
                  className="flex flex-col items-center gap-2 p-4 rounded-xl border border-white/10 bg-white/[0.03] hover:border-indigo-400/60 hover:bg-white/[0.06] transition-all text-slate-200">
                  <span className="text-2xl">{item.icon}</span>
                  <span className="text-xs font-medium">{item.name}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
