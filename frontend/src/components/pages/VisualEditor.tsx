import { useState, useRef, useCallback, useEffect } from 'react'
import {
  Trash2, Copy, Plus, Undo2, Redo2, AlignLeft,
  AlignCenter, AlignRight, AlignJustify,
} from 'lucide-react'

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
}

const FONTS = [
  'Inter', 'Open Sans', 'Roboto', 'Lato', 'Montserrat', 'Poppins',
  'Playfair Display', 'Merriweather', 'Raleway', 'Nunito',
  'Source Sans Pro', 'Oswald', 'PT Sans', 'Work Sans', 'DM Sans',
  'Space Grotesk', 'Outfit', 'Plus Jakarta Sans', 'Manrope', 'Libre Baskerville',
]

const FONT_WEIGHTS = [
  { label: 'Thin', value: '100' }, { label: 'Light', value: '300' },
  { label: 'Regular', value: '400' }, { label: 'Medium', value: '500' },
  { label: 'Semi-Bold', value: '600' }, { label: 'Bold', value: '700' },
  { label: 'Extra-Bold', value: '800' }, { label: 'Black', value: '900' },
]

const SECTION_CATEGORIES = [
  'Hero', 'Features', 'Pricing', 'Testimonials', 'CTA', 'FAQ',
  'Team', 'Stats', 'Contact', 'Footer', 'Gallery', 'Logos',
]

export default function VisualEditor({ html, css, onHtmlChange, onCssChange, onVideoUpload }: VisualEditorProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [selected, setSelected] = useState<SelectedElement | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const [panelTab, setPanelTab] = useState<'typography' | 'colors' | 'image' | 'spacing' | 'section' | 'button' | 'layout' | 'video'>('typography')
  const [undoStack, setUndoStack] = useState<string[]>([])
  const [redoStack, setRedoStack] = useState<string[]>([])
  const [showSectionLibrary, setShowSectionLibrary] = useState(false)

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

      document.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        selectedEl = e.target;
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

      document.addEventListener('dblclick', function(e) {
        e.preventDefault();
        var el = e.target;
        if (['H1','H2','H3','H4','H5','H6','P','SPAN','A','LI','BUTTON','LABEL','TD','TH'].includes(el.tagName)) {
          el.contentEditable = 'true';
          el.focus();
          el.addEventListener('blur', function() {
            el.contentEditable = 'false';
            window.parent.postMessage({ type: 'content-changed', html: document.body.innerHTML }, '*');
          }, { once: true });
        }
      }, true);
    </script>
  `

  const srcdoc = `<!DOCTYPE html><html><head><style>${css}</style></head><body style="cursor:pointer;">${html}${editorScript}</body></html>`

  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.type === 'element-selected') {
        setSelected(e.data.data)
        setPanelOpen(true)
        // Auto-detect panel tab
        const tag = e.data.data.tagName
        if (['IMG'].includes(tag)) setPanelTab('image')
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
      onHtmlChange(iframeDoc.body.innerHTML)
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
      const el = iframeRef.current.contentDocument.querySelector(selected.selector)
      el?.remove()
      onHtmlChange(iframeRef.current.contentDocument.body.innerHTML)
      setSelected(null)
      setPanelOpen(false)
    } catch { /* ignore */ }
  }, [selected, pushUndo, onHtmlChange])

  const duplicateSelected = useCallback(() => {
    if (!selected || !iframeRef.current?.contentDocument) return
    pushUndo()
    try {
      const el = iframeRef.current.contentDocument.querySelector(selected.selector)
      if (el) {
        const clone = el.cloneNode(true) as HTMLElement
        el.parentNode?.insertBefore(clone, el.nextSibling)
        onHtmlChange(iframeRef.current.contentDocument.body.innerHTML)
      }
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

  return (
    <div className="flex h-full relative">
      {/* Toolbar */}
      <div className="absolute top-0 left-0 right-0 z-10 flex items-center gap-1 px-3 py-1.5 bg-white dark:bg-gray-800 border-b text-xs">
        <button onClick={undo} disabled={undoStack.length === 0} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30" title="Undo">
          <Undo2 className="w-4 h-4" />
        </button>
        <button onClick={redo} disabled={redoStack.length === 0} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30" title="Redo">
          <Redo2 className="w-4 h-4" />
        </button>
        <div className="w-px h-5 bg-gray-200 dark:bg-gray-600 mx-1" />
        <button onClick={() => setShowSectionLibrary(true)} className="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300">
          <Plus className="w-3.5 h-3.5" /> Add Section
        </button>
        {selected && (
          <>
            <div className="w-px h-5 bg-gray-200 dark:bg-gray-600 mx-1" />
            <span className="text-gray-400 dark:text-gray-500">{selected.tagName}</span>
            <button onClick={duplicateSelected} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700" title="Duplicate">
              <Copy className="w-3.5 h-3.5" />
            </button>
            <button onClick={deleteSelected} className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-red-500" title="Delete">
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
          title="Visual Editor"
        />
      </div>

      {/* Properties Panel */}
      {panelOpen && selected && (
        <div className="w-72 border-l bg-white dark:bg-gray-800 pt-9 overflow-y-auto shrink-0">
          {/* Panel tabs */}
          <div className="flex flex-wrap gap-1 p-2 border-b">
            {(['typography', 'colors', 'spacing', 'section', 'image', 'button', 'layout', 'video'] as const).map(tab => (
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
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Font Family</label>
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
                    <label className="block text-gray-500 dark:text-gray-400 mb-1">Size (px)</label>
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
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Weight</label>
                  <select
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    value={selected.styles.fontWeight || '400'}
                    onChange={e => applyStyle('font-weight', e.target.value)}
                  >
                    {FONT_WEIGHTS.map(fw => <option key={fw.value} value={fw.value}>{fw.label} ({fw.value})</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Color</label>
                  <div className="flex gap-2">
                    <input type="color" value={selected.styles.color || '#000000'} onChange={e => applyStyle('color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" value={selected.styles.color || ''} onChange={e => applyStyle('color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Alignment</label>
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
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Line Height</label>
                  <input type="range" min="0.8" max="3" step="0.1"
                    value={parseFloat(selected.styles.lineHeight) || 1.5}
                    onChange={e => applyStyle('line-height', e.target.value)}
                    className="w-full" />
                  <span className="text-gray-600 dark:text-gray-300">{parseFloat(selected.styles.lineHeight)?.toFixed(1) || '1.5'}</span>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Letter Spacing</label>
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
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Background Color</label>
                  <div className="flex gap-2">
                    <input type="color" value="#ffffff" onChange={e => applyStyle('background-color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" placeholder="#ffffff" onChange={e => applyStyle('background-color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Text Color</label>
                  <div className="flex gap-2">
                    <input type="color" value={selected.styles.color || '#000000'} onChange={e => applyStyle('color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" value={selected.styles.color || ''} onChange={e => applyStyle('color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Opacity</label>
                  <input type="range" min="0" max="100" step="1"
                    value={Math.round((parseFloat(selected.styles.opacity) || 1) * 100)}
                    onChange={e => applyStyle('opacity', String(parseInt(e.target.value) / 100))}
                    className="w-full" />
                  <span className="text-gray-600 dark:text-gray-300">{Math.round((parseFloat(selected.styles.opacity) || 1) * 100)}%</span>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Border Radius</label>
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
                  <label className="block text-gray-500 dark:text-gray-400 mb-1 font-medium">Padding</label>
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
                  <label className="block text-gray-500 dark:text-gray-400 mb-1 font-medium">Margin</label>
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
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Width</label>
                  <input type="text" value={selected.styles.width || 'auto'}
                    onChange={e => applyStyle('width', e.target.value)}
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Height</label>
                  <input type="text" value={selected.styles.height || 'auto'}
                    onChange={e => applyStyle('height', e.target.value)}
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                </div>
              </>
            )}

            {/* Section controls */}
            {panelTab === 'section' && (
              <>
                <div className="space-y-2">
                  <button onClick={() => setShowSectionLibrary(true)}
                    className="w-full flex items-center gap-2 px-3 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300">
                    <Plus className="w-4 h-4" /> Add Section Below
                  </button>
                  <button onClick={duplicateSelected}
                    className="w-full flex items-center gap-2 px-3 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300">
                    <Copy className="w-4 h-4" /> Duplicate Section
                  </button>
                  <button onClick={deleteSelected}
                    className="w-full flex items-center gap-2 px-3 py-2 border border-red-200 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-red-600">
                    <Trash2 className="w-4 h-4" /> Delete Section
                  </button>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1 font-medium">Background</label>
                  <div className="flex gap-2">
                    <input type="color" value="#ffffff" onChange={e => applyStyle('background-color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" placeholder="Color or gradient" onChange={e => applyStyle('background', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Max Width</label>
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
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Image Source</label>
                  <input type="text" placeholder="Image URL"
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => {
                      if (!iframeRef.current?.contentDocument || !selected) return
                      try {
                        const el = iframeRef.current.contentDocument.querySelector(selected.selector) as HTMLImageElement
                        if (el) { el.src = e.target.value; onHtmlChange(iframeRef.current.contentDocument.body.innerHTML) }
                      } catch { /* ignore */ }
                    }} />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Object Fit</label>
                  <select className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => applyStyle('object-fit', e.target.value)}>
                    <option value="cover">Cover</option>
                    <option value="contain">Contain</option>
                    <option value="fill">Fill</option>
                    <option value="none">None</option>
                  </select>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Alt Text</label>
                  <input type="text" placeholder="Describe the image"
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => {
                      if (!iframeRef.current?.contentDocument || !selected) return
                      try {
                        const el = iframeRef.current.contentDocument.querySelector(selected.selector) as HTMLImageElement
                        if (el) { el.alt = e.target.value; onHtmlChange(iframeRef.current.contentDocument.body.innerHTML) }
                      } catch { /* ignore */ }
                    }} />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Border Radius</label>
                  <input type="range" min="0" max="50" step="1" value={0}
                    onChange={e => applyStyle('border-radius', `${e.target.value}px`)} className="w-full" />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Shadow</label>
                  <select className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => applyStyle('box-shadow', e.target.value)}>
                    <option value="none">None</option>
                    <option value="0 1px 3px rgba(0,0,0,0.12)">Small</option>
                    <option value="0 4px 6px rgba(0,0,0,0.1)">Medium</option>
                    <option value="0 10px 25px rgba(0,0,0,0.15)">Large</option>
                  </select>
                </div>
              </>
            )}

            {/* Button controls */}
            {panelTab === 'button' && (
              <>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Background</label>
                  <div className="flex gap-2">
                    <input type="color" value="#3b82f6" onChange={e => applyStyle('background-color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" placeholder="#3b82f6" onChange={e => applyStyle('background-color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Text Color</label>
                  <div className="flex gap-2">
                    <input type="color" value="#ffffff" onChange={e => applyStyle('color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" placeholder="#ffffff" onChange={e => applyStyle('color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Border Radius</label>
                  <input type="range" min="0" max="50" value={8}
                    onChange={e => applyStyle('border-radius', `${e.target.value}px`)} className="w-full" />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Size</label>
                  <div className="flex gap-1">
                    {[
                      { label: 'S', padding: '6px 16px' },
                      { label: 'M', padding: '10px 24px' },
                      { label: 'L', padding: '14px 32px' },
                      { label: 'Full', padding: '14px 32px', width: '100%' },
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
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Link URL</label>
                  <input type="text" placeholder="https://..."
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => {
                      if (!iframeRef.current?.contentDocument || !selected) return
                      try {
                        const el = iframeRef.current.contentDocument.querySelector(selected.selector) as HTMLAnchorElement
                        if (el && 'href' in el) { el.href = e.target.value; onHtmlChange(iframeRef.current.contentDocument.body.innerHTML) }
                      } catch { /* ignore */ }
                    }} />
                </div>
              </>
            )}

            {/* Layout */}
            {panelTab === 'layout' && (
              <>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Columns</label>
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
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Gap</label>
                  <input type="range" min="0" max="60" step="4" value={16}
                    onChange={e => applyStyle('gap', `${e.target.value}px`)} className="w-full" />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Display</label>
                  <select className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => applyStyle('display', e.target.value)}>
                    <option value="block">Block</option>
                    <option value="flex">Flex</option>
                    <option value="grid">Grid</option>
                    <option value="inline-flex">Inline Flex</option>
                  </select>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Align Items</label>
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

            {/* Video background */}
            {panelTab === 'video' && (
              <>
                <p className="text-gray-500 dark:text-gray-400 mb-2">Add a video background to this section.</p>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Upload Video</label>
                  <input type="file" accept="video/mp4,video/webm,video/quicktime"
                    className="w-full text-xs"
                    onChange={async (e) => {
                      const file = e.target.files?.[0]
                      if (!file || !onVideoUpload) return
                      try {
                        const result = await onVideoUpload(file)
                        // Inject video background into selected section
                        if (iframeRef.current?.contentDocument && selected) {
                          const el = iframeRef.current.contentDocument.querySelector(selected.selector) as HTMLElement
                          if (el) {
                            el.style.position = 'relative'
                            el.style.overflow = 'hidden'
                            const video = iframeRef.current.contentDocument.createElement('video')
                            video.autoplay = true
                            video.muted = true
                            video.loop = true
                            video.playsInline = true
                            video.poster = result.poster_url
                            video.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;z-index:0;'
                            const sourceWebm = iframeRef.current.contentDocument.createElement('source')
                            sourceWebm.src = result.webm_url
                            sourceWebm.type = 'video/webm'
                            const sourceMp4 = iframeRef.current.contentDocument.createElement('source')
                            sourceMp4.src = result.mp4_url
                            sourceMp4.type = 'video/mp4'
                            video.appendChild(sourceWebm)
                            video.appendChild(sourceMp4)
                            el.insertBefore(video, el.firstChild)
                            // Add overlay
                            const overlay = iframeRef.current.contentDocument.createElement('div')
                            overlay.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.4);z-index:0;'
                            el.insertBefore(overlay, video.nextSibling)
                            // Make content relative
                            Array.from(el.children).forEach((child, i) => {
                              if (i > 1) (child as HTMLElement).style.position = 'relative'
                              if (i > 1) (child as HTMLElement).style.zIndex = '1'
                            })
                            onHtmlChange(iframeRef.current.contentDocument.body.innerHTML)
                          }
                        }
                      } catch { /* ignore */ }
                    }} />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Or paste URL</label>
                  <input type="text" placeholder="https://..."
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Overlay Opacity</label>
                  <input type="range" min="0" max="80" step="5" value={40} className="w-full" />
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Section Library Modal */}
      {showSectionLibrary && (
        <div className="absolute inset-0 z-50 bg-black/40 flex items-center justify-center" onClick={() => setShowSectionLibrary(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-[600px] max-h-[80vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100">Add Section</h3>
              <button onClick={() => setShowSectionLibrary(false)} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700">✕</button>
            </div>
            <div className="p-4 grid grid-cols-3 gap-3 overflow-y-auto max-h-[60vh]">
              {SECTION_CATEGORIES.map(cat => (
                <button key={cat}
                  onClick={() => {
                    // Insert a placeholder section
                    pushUndo()
                    const sectionHtml = `<section class="${cat.toLowerCase()} py-20 px-6"><div class="container mx-auto text-center"><h2 class="text-3xl font-bold mb-6">${cat} Section</h2><p class="text-gray-600">Edit this ${cat.toLowerCase()} section content.</p></div></section>`
                    onHtmlChange(html + '\n' + sectionHtml)
                    setShowSectionLibrary(false)
                  }}
                  className="p-4 border rounded-lg hover:border-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 text-center transition-colors">
                  <div className="w-10 h-10 mx-auto mb-2 rounded bg-gray-100 dark:bg-gray-700 flex items-center justify-center text-lg">
                    {cat === 'Hero' ? '🦸' : cat === 'Features' ? '⭐' : cat === 'Pricing' ? '💰' :
                     cat === 'Testimonials' ? '💬' : cat === 'CTA' ? '🎯' : cat === 'FAQ' ? '❓' :
                     cat === 'Team' ? '👥' : cat === 'Stats' ? '📊' : cat === 'Contact' ? '📧' :
                     cat === 'Footer' ? '📑' : cat === 'Gallery' ? '🖼️' : '🏢'}
                  </div>
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{cat}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
