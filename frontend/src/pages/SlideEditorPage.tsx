import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { useParams } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getOfficeDoc, updateOfficeDoc, starOfficeDoc } from '@/api/office'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/authStore'
import EditorTopBar from '@/components/office/EditorTopBar'
import {
  Plus,
  Play,
  Trash2,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Bold,
  Italic,
  Underline,
  AlignLeft,
  AlignCenter,
  AlignRight,
  ImageIcon,
  Heading1,
  Heading2,
  Square,
  Circle,
  Triangle,
  ArrowRight,
  Type,
  Download,
  Upload,
  Layout,
  Palette,
  Sparkles,
  PanelRight,
  PanelRightClose,
  StickyNote,
  Timer,
  X,
  GripVertical,
  RotateCw,
  Eye,
} from 'lucide-react'
import { cn } from '@/lib/utils'

import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import UnderlineExt from '@tiptap/extension-underline'
import TextAlign from '@tiptap/extension-text-align'
import Image from '@tiptap/extension-image'
import Placeholder from '@tiptap/extension-placeholder'

// ---------------------------------------------------------------------------
// Data model
// ---------------------------------------------------------------------------

type SlideLayout = 'blank' | 'title' | 'title-content' | 'two-column' | 'section-header' | 'image-left' | 'image-right' | 'comparison'
type SlideTransition = 'none' | 'fade' | 'slide-left' | 'slide-right' | 'zoom'
type ElementAnimation = 'none' | 'fade-in' | 'slide-left' | 'slide-right' | 'slide-up' | 'zoom-in'
type ShapeType = 'rectangle' | 'circle' | 'rounded-rect' | 'triangle' | 'arrow-right'

interface SlideElement {
  id: string
  type: 'text' | 'shape' | 'image'
  x: number
  y: number
  width: number
  height: number
  content?: Record<string, unknown>
  shapeType?: ShapeType
  fillColor?: string
  borderColor?: string
  src?: string
  rotation?: number
  opacity?: number
  animation?: {
    type: ElementAnimation
    delay?: number
    duration?: number
  }
}

interface SlideContent {
  content: Record<string, unknown> | null
  elements?: SlideElement[]
  speakerNotes?: string
  layout?: SlideLayout
  transition?: SlideTransition
  backgroundColor?: string
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function uid(): string {
  return Math.random().toString(36).slice(2, 10)
}

const LAYOUTS: { value: SlideLayout; label: string }[] = [
  { value: 'blank', label: 'Blank' },
  { value: 'title', label: 'Title Slide' },
  { value: 'title-content', label: 'Title + Content' },
  { value: 'two-column', label: 'Two Column' },
  { value: 'section-header', label: 'Section Header' },
  { value: 'image-left', label: 'Image Left' },
  { value: 'image-right', label: 'Image Right' },
  { value: 'comparison', label: 'Comparison' },
]

const TRANSITIONS: { value: SlideTransition; label: string }[] = [
  { value: 'none', label: 'None' },
  { value: 'fade', label: 'Fade' },
  { value: 'slide-left', label: 'Slide Left' },
  { value: 'slide-right', label: 'Slide Right' },
  { value: 'zoom', label: 'Zoom' },
]

const ANIMATIONS: { value: ElementAnimation; label: string }[] = [
  { value: 'none', label: 'None' },
  { value: 'fade-in', label: 'Fade In' },
  { value: 'slide-left', label: 'Slide Left' },
  { value: 'slide-right', label: 'Slide Right' },
  { value: 'slide-up', label: 'Slide Up' },
  { value: 'zoom-in', label: 'Zoom In' },
]

function makeLayoutElements(layout: SlideLayout): SlideElement[] {
  switch (layout) {
    case 'title':
      return [
        { id: uid(), type: 'text', x: 10, y: 30, width: 80, height: 30, content: { type: 'doc', content: [{ type: 'heading', attrs: { level: 1, textAlign: 'center' }, content: [{ type: 'text', text: 'Presentation Title' }] }] } },
      ]
    case 'title-content':
      return [
        { id: uid(), type: 'text', x: 10, y: 5, width: 80, height: 15, content: { type: 'doc', content: [{ type: 'heading', attrs: { level: 1, textAlign: 'left' }, content: [{ type: 'text', text: 'Slide Title' }] }] } },
        { id: uid(), type: 'text', x: 10, y: 25, width: 80, height: 60, content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Body content goes here...' }] }] } },
      ]
    case 'two-column':
      return [
        { id: uid(), type: 'text', x: 5, y: 5, width: 90, height: 12, content: { type: 'doc', content: [{ type: 'heading', attrs: { level: 1, textAlign: 'center' }, content: [{ type: 'text', text: 'Two Columns' }] }] } },
        { id: uid(), type: 'text', x: 5, y: 22, width: 42, height: 65, content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Left column...' }] }] } },
        { id: uid(), type: 'text', x: 53, y: 22, width: 42, height: 65, content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Right column...' }] }] } },
      ]
    case 'section-header':
      return [
        { id: uid(), type: 'text', x: 10, y: 30, width: 80, height: 30, content: { type: 'doc', content: [{ type: 'heading', attrs: { level: 1, textAlign: 'center' }, content: [{ type: 'text', text: 'Section Title' }] }] } },
      ]
    case 'image-left':
      return [
        { id: uid(), type: 'image', x: 3, y: 10, width: 44, height: 75, src: '' },
        { id: uid(), type: 'text', x: 52, y: 10, width: 44, height: 75, content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Description...' }] }] } },
      ]
    case 'image-right':
      return [
        { id: uid(), type: 'text', x: 3, y: 10, width: 44, height: 75, content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Description...' }] }] } },
        { id: uid(), type: 'image', x: 52, y: 10, width: 44, height: 75, src: '' },
      ]
    case 'comparison':
      return [
        { id: uid(), type: 'text', x: 5, y: 3, width: 90, height: 10, content: { type: 'doc', content: [{ type: 'heading', attrs: { level: 1, textAlign: 'center' }, content: [{ type: 'text', text: 'Comparison' }] }] } },
        { id: uid(), type: 'text', x: 5, y: 16, width: 42, height: 10, content: { type: 'doc', content: [{ type: 'heading', attrs: { level: 2, textAlign: 'center' }, content: [{ type: 'text', text: 'Option A' }] }] } },
        { id: uid(), type: 'text', x: 53, y: 16, width: 42, height: 10, content: { type: 'doc', content: [{ type: 'heading', attrs: { level: 2, textAlign: 'center' }, content: [{ type: 'text', text: 'Option B' }] }] } },
        { id: uid(), type: 'text', x: 5, y: 30, width: 42, height: 58, content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Details...' }] }] } },
        { id: uid(), type: 'text', x: 53, y: 30, width: 42, height: 58, content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Details...' }] }] } },
      ]
    default: // blank
      return []
  }
}

// ---------------------------------------------------------------------------
// Shape SVG renderer
// ---------------------------------------------------------------------------

function ShapeSVG({ shape, fill, border }: { shape: ShapeType; fill: string; border: string }) {
  const style = { width: '100%', height: '100%' }
  const f = fill || '#3b82f6'
  const s = border || 'transparent'
  switch (shape) {
    case 'circle':
      return <svg viewBox="0 0 100 100" style={style}><ellipse cx="50" cy="50" rx="48" ry="48" fill={f} stroke={s} strokeWidth="2" /></svg>
    case 'rounded-rect':
      return <svg viewBox="0 0 100 60" style={style} preserveAspectRatio="none"><rect x="1" y="1" width="98" height="58" rx="12" fill={f} stroke={s} strokeWidth="2" /></svg>
    case 'triangle':
      return <svg viewBox="0 0 100 87" style={style} preserveAspectRatio="none"><polygon points="50,2 98,85 2,85" fill={f} stroke={s} strokeWidth="2" /></svg>
    case 'arrow-right':
      return <svg viewBox="0 0 100 60" style={style} preserveAspectRatio="none"><polygon points="0,15 65,15 65,0 100,30 65,60 65,45 0,45" fill={f} stroke={s} strokeWidth="2" /></svg>
    default: // rectangle
      return <svg viewBox="0 0 100 60" style={style} preserveAspectRatio="none"><rect x="1" y="1" width="98" height="58" fill={f} stroke={s} strokeWidth="2" /></svg>
  }
}

// ---------------------------------------------------------------------------
// Inline Tiptap editor for text elements
// ---------------------------------------------------------------------------

interface ElementTextEditorProps {
  content: Record<string, unknown> | null
  onUpdate: (json: Record<string, unknown>) => void
  isSelected: boolean
}

function ElementTextEditor({ content, onUpdate, isSelected }: ElementTextEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({ history: false } as any),
      UnderlineExt,
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      Placeholder.configure({ placeholder: 'Type here...' }),
    ],
    editorProps: {
      attributes: {
        class: 'focus:outline-none h-full text-sm leading-snug',
      },
    },
    onUpdate: ({ editor: ed }) => {
      onUpdate(ed.getJSON() as Record<string, unknown>)
    },
  })

  useEffect(() => {
    if (!editor) return
    if (content && typeof content === 'object') {
      const currentJSON = JSON.stringify(editor.getJSON())
      const incomingJSON = JSON.stringify(content)
      if (currentJSON !== incomingJSON) {
        editor.commands.setContent(content)
      }
    } else {
      editor.commands.clearContent()
    }
    // Only run on mount / when content identity changes from outside
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor])

  useEffect(() => {
    if (!editor) return
    editor.setEditable(isSelected)
  }, [editor, isSelected])

  return <EditorContent editor={editor} className="h-full w-full overflow-hidden" />
}

// ---------------------------------------------------------------------------
// Main Tiptap editor for slide background content (legacy/fallback)
// ---------------------------------------------------------------------------

interface SlideMainEditorProps {
  slideContent: Record<string, unknown> | null
  onUpdate: (json: Record<string, unknown>) => void
}

function SlideMainEditor({ slideContent, onUpdate }: SlideMainEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      UnderlineExt,
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      Image,
      Placeholder.configure({ placeholder: 'Click to add text...' }),
    ],
    editorProps: {
      attributes: {
        class: 'focus:outline-none min-h-full p-10 text-lg',
      },
    },
    onUpdate: ({ editor: ed }) => {
      onUpdate(ed.getJSON() as Record<string, unknown>)
    },
  })

  useEffect(() => {
    if (!editor) return
    if (slideContent && typeof slideContent === 'object') {
      editor.commands.setContent(slideContent)
    } else {
      editor.commands.clearContent()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor, slideContent])

  return (
    <div className="h-full relative">
      {editor && (
        <div className="absolute top-0 left-0 right-0 bg-white/90 dark:bg-gray-900/90 border-b dark:border-gray-700 px-3 py-1 flex items-center gap-0.5 z-10 opacity-0 hover:opacity-100 transition-opacity">
          <button onClick={() => editor.chain().focus().toggleBold().run()} className={cn('p-1 rounded text-sm', editor.isActive('bold') ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700')}><Bold className="h-3.5 w-3.5" /></button>
          <button onClick={() => editor.chain().focus().toggleItalic().run()} className={cn('p-1 rounded text-sm', editor.isActive('italic') ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700')}><Italic className="h-3.5 w-3.5" /></button>
          <button onClick={() => editor.chain().focus().toggleUnderline().run()} className={cn('p-1 rounded text-sm', editor.isActive('underline') ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700')}><Underline className="h-3.5 w-3.5" /></button>
          <div className="w-px h-4 bg-gray-200 dark:bg-gray-700 mx-1" />
          <button onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()} className={cn('p-1 rounded text-sm', editor.isActive('heading', { level: 1 }) ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700')}><Heading1 className="h-3.5 w-3.5" /></button>
          <button onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} className={cn('p-1 rounded text-sm', editor.isActive('heading', { level: 2 }) ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700')}><Heading2 className="h-3.5 w-3.5" /></button>
          <div className="w-px h-4 bg-gray-200 dark:bg-gray-700 mx-1" />
          <button onClick={() => editor.chain().focus().setTextAlign('left').run()} className={cn('p-1 rounded text-sm', editor.isActive({ textAlign: 'left' }) ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700')}><AlignLeft className="h-3.5 w-3.5" /></button>
          <button onClick={() => editor.chain().focus().setTextAlign('center').run()} className={cn('p-1 rounded text-sm', editor.isActive({ textAlign: 'center' }) ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700')}><AlignCenter className="h-3.5 w-3.5" /></button>
          <button onClick={() => editor.chain().focus().setTextAlign('right').run()} className={cn('p-1 rounded text-sm', editor.isActive({ textAlign: 'right' }) ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700')}><AlignRight className="h-3.5 w-3.5" /></button>
          <div className="w-px h-4 bg-gray-200 dark:bg-gray-700 mx-1" />
          <button onClick={() => { const url = prompt('Enter image URL:'); if (url) editor.chain().focus().setImage({ src: url }).run() }} className="p-1 rounded text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"><ImageIcon className="h-3.5 w-3.5" /></button>
        </div>
      )}
      <EditorContent editor={editor} className="h-full" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Dropdown wrapper
// ---------------------------------------------------------------------------

function Dropdown({ trigger, children, className }: { trigger: React.ReactNode; children: React.ReactNode; className?: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  return (
    <div ref={ref} className="relative">
      <div onClick={() => setOpen((o) => !o)}>{trigger}</div>
      {open && (
        <div className={cn('absolute top-full left-0 mt-1 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg shadow-lg z-50 py-1 min-w-[160px]', className)} onClick={() => setOpen(false)}>
          {children}
        </div>
      )}
    </div>
  )
}

function DropdownItem({ onClick, children, className }: { onClick: () => void; children: React.ReactNode; className?: string }) {
  return (
    <button onClick={onClick} className={cn('w-full text-left px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2', className)}>
      {children}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Properties panel
// ---------------------------------------------------------------------------

interface PropertiesPanelProps {
  element: SlideElement | null
  onUpdate: (patch: Partial<SlideElement>) => void
  onDelete: () => void
}

function PropertiesPanel({ element, onUpdate, onDelete }: PropertiesPanelProps) {
  if (!element) {
    return (
      <div className="p-4 text-sm text-gray-400 dark:text-gray-500 text-center">
        Select an element to edit its properties
      </div>
    )
  }

  return (
    <div className="p-3 space-y-4 text-sm overflow-y-auto h-full">
      <h3 className="font-semibold text-gray-700 dark:text-gray-300 uppercase text-xs tracking-wide">
        {element.type === 'text' ? 'Text Box' : element.type === 'shape' ? 'Shape' : 'Image'}
      </h3>

      {/* Position */}
      <div className="space-y-2">
        <label className="text-xs text-gray-500 dark:text-gray-400 font-medium">Position</label>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <span className="text-[10px] text-gray-400">X %</span>
            <input type="number" min={0} max={100} value={Math.round(element.x)} onChange={(e) => onUpdate({ x: Number(e.target.value) })} className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-xs" />
          </div>
          <div>
            <span className="text-[10px] text-gray-400">Y %</span>
            <input type="number" min={0} max={100} value={Math.round(element.y)} onChange={(e) => onUpdate({ y: Number(e.target.value) })} className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-xs" />
          </div>
        </div>
      </div>

      {/* Size */}
      <div className="space-y-2">
        <label className="text-xs text-gray-500 dark:text-gray-400 font-medium">Size</label>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <span className="text-[10px] text-gray-400">W %</span>
            <input type="number" min={1} max={100} value={Math.round(element.width)} onChange={(e) => onUpdate({ width: Number(e.target.value) })} className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-xs" />
          </div>
          <div>
            <span className="text-[10px] text-gray-400">H %</span>
            <input type="number" min={1} max={100} value={Math.round(element.height)} onChange={(e) => onUpdate({ height: Number(e.target.value) })} className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-xs" />
          </div>
        </div>
      </div>

      {/* Rotation & Opacity */}
      <div className="space-y-2">
        <label className="text-xs text-gray-500 dark:text-gray-400 font-medium">Appearance</label>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <span className="text-[10px] text-gray-400 flex items-center gap-1"><RotateCw className="h-2.5 w-2.5" /> Rotation</span>
            <input type="number" min={0} max={360} value={element.rotation ?? 0} onChange={(e) => onUpdate({ rotation: Number(e.target.value) })} className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-xs" />
          </div>
          <div>
            <span className="text-[10px] text-gray-400 flex items-center gap-1"><Eye className="h-2.5 w-2.5" /> Opacity</span>
            <input type="range" min={0} max={100} value={(element.opacity ?? 1) * 100} onChange={(e) => onUpdate({ opacity: Number(e.target.value) / 100 })} className="w-full" />
          </div>
        </div>
      </div>

      {/* Shape-specific */}
      {element.type === 'shape' && (
        <div className="space-y-2">
          <label className="text-xs text-gray-500 dark:text-gray-400 font-medium">Shape</label>
          <select value={element.shapeType || 'rectangle'} onChange={(e) => onUpdate({ shapeType: e.target.value as ShapeType })} className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-xs">
            <option value="rectangle">Rectangle</option>
            <option value="circle">Circle</option>
            <option value="rounded-rect">Rounded Rect</option>
            <option value="triangle">Triangle</option>
            <option value="arrow-right">Arrow</option>
          </select>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="text-[10px] text-gray-400">Fill</span>
              <input type="color" value={element.fillColor || '#3b82f6'} onChange={(e) => onUpdate({ fillColor: e.target.value })} className="w-full h-7 rounded border dark:border-gray-600 cursor-pointer" />
            </div>
            <div>
              <span className="text-[10px] text-gray-400">Border</span>
              <input type="color" value={element.borderColor || '#000000'} onChange={(e) => onUpdate({ borderColor: e.target.value })} className="w-full h-7 rounded border dark:border-gray-600 cursor-pointer" />
            </div>
          </div>
        </div>
      )}

      {/* Image-specific */}
      {element.type === 'image' && (
        <div className="space-y-2">
          <label className="text-xs text-gray-500 dark:text-gray-400 font-medium">Image URL</label>
          <input type="text" value={element.src || ''} onChange={(e) => onUpdate({ src: e.target.value })} placeholder="https://..." className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-xs" />
        </div>
      )}

      {/* Animation */}
      <div className="space-y-2">
        <label className="text-xs text-gray-500 dark:text-gray-400 font-medium">Animation</label>
        <select value={element.animation?.type || 'none'} onChange={(e) => onUpdate({ animation: { ...element.animation, type: e.target.value as ElementAnimation, delay: element.animation?.delay ?? 0, duration: element.animation?.duration ?? 500 } })} className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-xs">
          {ANIMATIONS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
        </select>
        {element.animation?.type && element.animation.type !== 'none' && (
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="text-[10px] text-gray-400">Delay (ms)</span>
              <input type="number" min={0} step={100} value={element.animation.delay ?? 0} onChange={(e) => onUpdate({ animation: { ...element.animation!, delay: Number(e.target.value) } })} className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-xs" />
            </div>
            <div>
              <span className="text-[10px] text-gray-400">Duration (ms)</span>
              <input type="number" min={100} step={100} value={element.animation.duration ?? 500} onChange={(e) => onUpdate({ animation: { ...element.animation!, duration: Number(e.target.value) } })} className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-xs" />
            </div>
          </div>
        )}
      </div>

      {/* Delete */}
      <button onClick={onDelete} className="w-full px-3 py-1.5 text-sm text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800 rounded hover:bg-red-50 dark:hover:bg-red-900/30 flex items-center gap-2 justify-center">
        <Trash2 className="h-3.5 w-3.5" /> Delete Element
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Element renderer on canvas
// ---------------------------------------------------------------------------

interface CanvasElementProps {
  el: SlideElement
  isSelected: boolean
  onSelect: () => void
  onUpdate: (patch: Partial<SlideElement>) => void
  canvasRef: React.RefObject<HTMLDivElement | null>
}

function CanvasElement({ el, isSelected, onSelect, onUpdate, canvasRef }: CanvasElementProps) {
  const dragRef = useRef<{ startX: number; startY: number; elX: number; elY: number } | null>(null)
  const resizeRef = useRef<{ startX: number; startY: number; elW: number; elH: number; elXPct: number; elYPct: number; corner: string } | null>(null)

  const handleMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation()
    onSelect()
    if (!canvasRef.current) return
    const rect = canvasRef.current.getBoundingClientRect()
    dragRef.current = { startX: e.clientX, startY: e.clientY, elX: el.x, elY: el.y }

    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current || !canvasRef.current) return
      const dx = ((ev.clientX - dragRef.current.startX) / rect.width) * 100
      const dy = ((ev.clientY - dragRef.current.startY) / rect.height) * 100
      onUpdate({
        x: Math.max(0, Math.min(100 - el.width, dragRef.current.elX + dx)),
        y: Math.max(0, Math.min(100 - el.height, dragRef.current.elY + dy)),
      })
    }
    const onUp = () => {
      dragRef.current = null
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  const handleResizeMouseDown = (e: React.MouseEvent, corner: string) => {
    e.stopPropagation()
    if (!canvasRef.current) return
    const rect = canvasRef.current.getBoundingClientRect()
    resizeRef.current = { startX: e.clientX, startY: e.clientY, elW: el.width, elH: el.height, elXPct: el.x, elYPct: el.y, corner }

    const onMove = (ev: MouseEvent) => {
      if (!resizeRef.current || !canvasRef.current) return
      const dx = ((ev.clientX - resizeRef.current.startX) / rect.width) * 100
      const dy = ((ev.clientY - resizeRef.current.startY) / rect.height) * 100
      const { elW, elH, corner: c } = resizeRef.current

      const patch: Partial<SlideElement> = {}
      if (c.includes('e')) patch.width = Math.max(5, elW + dx)
      if (c.includes('w')) { patch.width = Math.max(5, elW - dx); patch.x = resizeRef.current.elXPct + dx }
      if (c.includes('s')) patch.height = Math.max(5, elH + dy)
      if (c.includes('n')) { patch.height = Math.max(5, elH - dy); patch.y = resizeRef.current.elYPct + dy }
      onUpdate(patch)
    }
    const onUp = () => {
      resizeRef.current = null
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  const style: React.CSSProperties = {
    position: 'absolute',
    left: `${el.x}%`,
    top: `${el.y}%`,
    width: `${el.width}%`,
    height: `${el.height}%`,
    transform: el.rotation ? `rotate(${el.rotation}deg)` : undefined,
    opacity: el.opacity ?? 1,
    zIndex: isSelected ? 20 : 10,
  }

  const corners = ['nw', 'ne', 'sw', 'se']
  const cursorMap: Record<string, string> = { nw: 'nw-resize', ne: 'ne-resize', sw: 'sw-resize', se: 'se-resize' }
  const posMap: Record<string, string> = { nw: '-top-1 -left-1', ne: '-top-1 -right-1', sw: '-bottom-1 -left-1', se: '-bottom-1 -right-1' }

  return (
    <div style={style} onMouseDown={handleMouseDown} className={cn('cursor-move', isSelected && 'ring-2 ring-blue-500 ring-offset-1')}>
      {/* Render content based on type */}
      {el.type === 'shape' && (
        <ShapeSVG shape={el.shapeType || 'rectangle'} fill={el.fillColor || '#3b82f6'} border={el.borderColor || 'transparent'} />
      )}
      {el.type === 'text' && (
        <div className="w-full h-full overflow-hidden bg-transparent p-1">
          <ElementTextEditor content={(el.content as Record<string, unknown>) ?? null} onUpdate={(json) => onUpdate({ content: json })} isSelected={isSelected} />
        </div>
      )}
      {el.type === 'image' && (
        <div className="w-full h-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center overflow-hidden rounded">
          {el.src ? (
            <img src={el.src} alt="" className="w-full h-full object-cover" draggable={false} />
          ) : (
            <ImageIcon className="h-8 w-8 text-gray-400" />
          )}
        </div>
      )}

      {/* Resize handles */}
      {isSelected && corners.map((c) => (
        <div
          key={c}
          onMouseDown={(e) => handleResizeMouseDown(e, c)}
          className={cn('absolute w-2.5 h-2.5 bg-blue-500 border border-white rounded-sm z-30', posMap[c])}
          style={{ cursor: cursorMap[c] }}
        />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Presenter mode
// ---------------------------------------------------------------------------

interface PresenterModeProps {
  slides: SlideContent[]
  initialSlide: number
  onExit: () => void
}

function PresenterMode({ slides, initialSlide, onExit }: PresenterModeProps) {
  const [currentSlide, setCurrentSlide] = useState(initialSlide)
  const [elapsed, setElapsed] = useState(0)
  const startTimeRef = useRef(Date.now())

  useEffect(() => {
    const iv = setInterval(() => setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000)), 1000)
    return () => clearInterval(iv)
  }, [])

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ') {
        e.preventDefault()
        setCurrentSlide((s) => Math.min(s + 1, slides.length - 1))
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault()
        setCurrentSlide((s) => Math.max(s - 1, 0))
      } else if (e.key === 'Escape') {
        onExit()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [slides.length, onExit])

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
  }

  const slide = slides[currentSlide]
  const nextSlide = slides[currentSlide + 1]

  const renderSlidePreview = (s: SlideContent, _interactive?: boolean) => (
    <div
      className="w-full aspect-video relative overflow-hidden rounded"
      style={{ backgroundColor: s?.backgroundColor || '#ffffff' }}
    >
      {/* Elements */}
      {(s?.elements || []).map((el) => (
        <div
          key={el.id}
          className="absolute overflow-hidden"
          style={{
            left: `${el.x}%`, top: `${el.y}%`, width: `${el.width}%`, height: `${el.height}%`,
            transform: el.rotation ? `rotate(${el.rotation}deg)` : undefined,
            opacity: el.opacity ?? 1,
          }}
        >
          {el.type === 'shape' && <ShapeSVG shape={el.shapeType || 'rectangle'} fill={el.fillColor || '#3b82f6'} border={el.borderColor || 'transparent'} />}
          {el.type === 'text' && el.content && (
            <div className="w-full h-full p-1 text-sm" dangerouslySetInnerHTML={{ __html: tiptapJsonToHtml(el.content) }} />
          )}
          {el.type === 'image' && el.src && <img src={el.src} alt="" className="w-full h-full object-cover" />}
        </div>
      ))}
      {/* Fallback main content as rendered HTML */}
      {s?.content && (!s.elements || s.elements.length === 0) && (
        <div className="p-10 text-lg" dangerouslySetInnerHTML={{ __html: tiptapJsonToHtml(s.content) }} />
      )}
    </div>
  )

  return (
    <div className="fixed inset-0 bg-gray-950 z-50 flex">
      {/* Current slide - large */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-[960px]">
          {renderSlidePreview(slide, false)}
        </div>
      </div>

      {/* Right panel: next slide + notes + controls */}
      <div className="w-80 bg-gray-900 border-l border-gray-800 flex flex-col">
        {/* Next slide preview */}
        <div className="p-3">
          <div className="text-xs text-gray-400 mb-1 font-medium">Next Slide</div>
          {nextSlide ? (
            <div className="opacity-70">{renderSlidePreview(nextSlide, false)}</div>
          ) : (
            <div className="aspect-video bg-gray-800 rounded flex items-center justify-center text-gray-500 text-xs">
              End of presentation
            </div>
          )}
        </div>

        {/* Speaker notes */}
        <div className="flex-1 p-3 overflow-y-auto">
          <div className="text-xs text-gray-400 mb-1 font-medium">Speaker Notes</div>
          <div className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">
            {slide?.speakerNotes || <span className="text-gray-600 italic">No notes for this slide</span>}
          </div>
        </div>

        {/* Controls bar */}
        <div className="p-3 border-t border-gray-800 flex items-center gap-3">
          <button onClick={() => setCurrentSlide((s) => Math.max(s - 1, 0))} disabled={currentSlide === 0} className="text-white disabled:opacity-30 p-1">
            <ChevronLeft className="h-5 w-5" />
          </button>
          <span className="text-white text-sm font-medium">{currentSlide + 1} / {slides.length}</span>
          <button onClick={() => setCurrentSlide((s) => Math.min(s + 1, slides.length - 1))} disabled={currentSlide === slides.length - 1} className="text-white disabled:opacity-30 p-1">
            <ChevronRight className="h-5 w-5" />
          </button>
          <div className="flex-1" />
          <div className="flex items-center gap-1.5 text-gray-400 text-sm">
            <Timer className="h-4 w-4" />
            {formatTime(elapsed)}
          </div>
          <button onClick={onExit} className="text-gray-400 hover:text-white p-1" title="Exit (Esc)">
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  )
}

/** Minimal Tiptap JSON to HTML converter for presentation rendering */
function tiptapJsonToHtml(json: Record<string, unknown>): string {
  if (!json || !json.content) return ''
  const nodes = json.content as any[]
  return nodes.map((node: any) => {
    if (!node) return ''
    const textAlign = node.attrs?.textAlign ? ` style="text-align:${node.attrs.textAlign}"` : ''
    const inner = (node.content || []).map((child: any) => {
      if (child.type === 'text') {
        let txt = escapeHtml(child.text || '')
        if (child.marks) {
          for (const m of child.marks) {
            if (m.type === 'bold') txt = `<strong>${txt}</strong>`
            if (m.type === 'italic') txt = `<em>${txt}</em>`
            if (m.type === 'underline') txt = `<u>${txt}</u>`
          }
        }
        return txt
      }
      return ''
    }).join('')
    switch (node.type) {
      case 'heading': return `<h${node.attrs?.level || 1}${textAlign}>${inner}</h${node.attrs?.level || 1}>`
      case 'paragraph': return `<p${textAlign}>${inner}</p>`
      case 'bulletList': return `<ul>${inner}</ul>`
      case 'listItem': return `<li>${inner}</li>`
      default: return inner
    }
  }).join('')
}

function escapeHtml(str: string): string {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function SlideEditorPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const { user: _user } = useAuthStore()
  const [connectionStatus] = useState<'connected' | 'connecting' | 'disconnected'>('connected')
  const [connectedUsers] = useState<{ name: string; color: string }[]>([])
  const [activeSlide, setActiveSlide] = useState(0)
  const [slides, setSlides] = useState<SlideContent[]>([{ content: null, elements: [], layout: 'blank', transition: 'none', backgroundColor: '#ffffff', speakerNotes: '' }])
  const [isPresenting, setIsPresenting] = useState(false)
  const [selectedElementId, setSelectedElementId] = useState<string | null>(null)
  const [showProperties, setShowProperties] = useState(true)
  const [showNotes, setShowNotes] = useState(false)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const initialLoadRef = useRef(false)
  const canvasRef = useRef<HTMLDivElement>(null)
  const importInputRef = useRef<HTMLInputElement>(null)

  const { data: docData } = useQuery({
    queryKey: ['office-doc', id],
    queryFn: () => getOfficeDoc(id!),
    enabled: !!id,
  })

  const doc = docData?.data

  const updateMutation = useMutation({
    mutationFn: (data: { title?: string; content_json?: Record<string, unknown> }) => updateOfficeDoc(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['office-doc', id] })
    },
  })

  const starMutation = useMutation({
    mutationFn: () => starOfficeDoc(id!, !doc?.is_starred),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['office-doc', id] })
    },
  })

  // Load initial content from backend
  useEffect(() => {
    if (!doc || initialLoadRef.current) return
    initialLoadRef.current = true

    if (doc.content_json && typeof doc.content_json === 'object') {
      const saved = doc.content_json as { slides?: SlideContent[] }
      if (saved.slides && Array.isArray(saved.slides) && saved.slides.length > 0) {
        setSlides(saved.slides.map((s) => ({
          content: s.content ?? null,
          elements: s.elements ?? [],
          speakerNotes: s.speakerNotes ?? '',
          layout: s.layout ?? 'blank',
          transition: s.transition ?? 'none',
          backgroundColor: s.backgroundColor ?? '#ffffff',
        })))
      }
    }
  }, [doc])

  // Cleanup save timer
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [])

  const debouncedSave = useCallback(
    (updatedSlides: SlideContent[]) => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
      saveTimerRef.current = setTimeout(() => {
        updateMutation.mutate({ content_json: { slides: updatedSlides } as Record<string, unknown> })
      }, 2000)
    },
    [updateMutation]
  )

  const currentSlide = slides[activeSlide]
  const selectedElement = useMemo(() => {
    if (!selectedElementId || !currentSlide?.elements) return null
    return currentSlide.elements.find((e) => e.id === selectedElementId) ?? null
  }, [selectedElementId, currentSlide])

  // ---------------------------------------------------------------------------
  // Slide manipulation
  // ---------------------------------------------------------------------------

  const updateSlide = useCallback((index: number, patch: Partial<SlideContent>) => {
    setSlides((prev) => {
      const updated = [...prev]
      updated[index] = { ...updated[index], ...patch }
      debouncedSave(updated)
      return updated
    })
  }, [debouncedSave])

  const handleSlideContentUpdate = useCallback((index: number, json: Record<string, unknown>) => {
    updateSlide(index, { content: json })
  }, [updateSlide])

  const addSlide = useCallback(() => {
    const newSlide: SlideContent = { content: null, elements: [], layout: 'blank', transition: 'none', backgroundColor: '#ffffff', speakerNotes: '' }
    setSlides((prev) => {
      const updated = [...prev, newSlide]
      debouncedSave(updated)
      return updated
    })
    setActiveSlide(slides.length)
    setSelectedElementId(null)
  }, [slides.length, debouncedSave])

  const deleteSlide = useCallback((index: number) => {
    if (slides.length <= 1) return
    setSlides((prev) => {
      const updated = prev.filter((_, i) => i !== index)
      debouncedSave(updated)
      return updated
    })
    if (activeSlide >= slides.length - 1) {
      setActiveSlide(Math.max(0, slides.length - 2))
    } else if (activeSlide > index) {
      setActiveSlide(activeSlide - 1)
    }
    setSelectedElementId(null)
  }, [slides.length, activeSlide, debouncedSave])

  // Drag-to-reorder slides
  const dragSlideRef = useRef<number | null>(null)
  const handleSlideDragStart = (index: number) => { dragSlideRef.current = index }
  const handleSlideDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault()
    if (dragSlideRef.current === null || dragSlideRef.current === index) return
    setSlides((prev) => {
      const updated = [...prev]
      const [moved] = updated.splice(dragSlideRef.current!, 1)
      updated.splice(index, 0, moved)
      debouncedSave(updated)
      return updated
    })
    if (activeSlide === dragSlideRef.current) setActiveSlide(index)
    dragSlideRef.current = index
  }
  const handleSlideDragEnd = () => { dragSlideRef.current = null }

  // ---------------------------------------------------------------------------
  // Element manipulation
  // ---------------------------------------------------------------------------

  const addElement = useCallback((type: 'text' | 'shape' | 'image', extra?: Partial<SlideElement>) => {
    const el: SlideElement = {
      id: uid(),
      type,
      x: 20,
      y: 20,
      width: 30,
      height: 20,
      rotation: 0,
      opacity: 1,
      animation: { type: 'none', delay: 0, duration: 500 },
      ...(type === 'text' ? { content: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Text' }] }] } } : {}),
      ...(type === 'shape' ? { shapeType: 'rectangle' as ShapeType, fillColor: '#3b82f6', borderColor: 'transparent' } : {}),
      ...(type === 'image' ? { src: '' } : {}),
      ...extra,
    }
    setSlides((prev) => {
      const updated = [...prev]
      const curr = { ...updated[activeSlide] }
      curr.elements = [...(curr.elements || []), el]
      updated[activeSlide] = curr
      debouncedSave(updated)
      return updated
    })
    setSelectedElementId(el.id)
  }, [activeSlide, debouncedSave])

  const updateElement = useCallback((elementId: string, patch: Partial<SlideElement>) => {
    setSlides((prev) => {
      const updated = [...prev]
      const curr = { ...updated[activeSlide] }
      curr.elements = (curr.elements || []).map((el) => el.id === elementId ? { ...el, ...patch } : el)
      updated[activeSlide] = curr
      debouncedSave(updated)
      return updated
    })
  }, [activeSlide, debouncedSave])

  const deleteElement = useCallback((elementId: string) => {
    setSlides((prev) => {
      const updated = [...prev]
      const curr = { ...updated[activeSlide] }
      curr.elements = (curr.elements || []).filter((el) => el.id !== elementId)
      updated[activeSlide] = curr
      debouncedSave(updated)
      return updated
    })
    setSelectedElementId(null)
  }, [activeSlide, debouncedSave])

  // Delete key handler
  useEffect(() => {
    if (isPresenting) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Delete' && selectedElementId) {
        // Don't delete if user is typing in an input/textarea
        const tag = (e.target as HTMLElement)?.tagName
        if (tag === 'INPUT' || tag === 'TEXTAREA') return
        // Don't delete if a tiptap editor is focused
        if ((e.target as HTMLElement)?.closest('.ProseMirror')) return
        deleteElement(selectedElementId)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isPresenting, selectedElementId, deleteElement])

  // ---------------------------------------------------------------------------
  // Layout application
  // ---------------------------------------------------------------------------

  const applyLayout = useCallback((layout: SlideLayout) => {
    const elements = makeLayoutElements(layout)
    updateSlide(activeSlide, { layout, elements, content: null })
    setSelectedElementId(null)
  }, [activeSlide, updateSlide])

  // ---------------------------------------------------------------------------
  // Import / Export
  // ---------------------------------------------------------------------------

  const handleExportPptx = useCallback(async () => {
    try {
      const blob = await api.download(`/office/${id}/export/pptx`)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${doc?.title || 'presentation'}.pptx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('PPTX export failed:', err)
      alert('Export failed. The server may not support PPTX export yet.')
    }
  }, [id, doc?.title])

  const handleExportPdf = useCallback(async () => {
    try {
      const blob = await api.download(`/office/${id}/export/pdf`)
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank')
    } catch (err) {
      console.error('PDF export failed:', err)
      alert('PDF export failed. The server may not support PDF export yet.')
    }
  }, [id])

  const handleImport = useCallback(async (file: File) => {
    try {
      const formData = new FormData()
      formData.append('file', file)
      await api.upload(`/office/${id}/import`, formData)
      // Reload document
      initialLoadRef.current = false
      queryClient.invalidateQueries({ queryKey: ['office-doc', id] })
    } catch (err) {
      console.error('Import failed:', err)
      alert('Import failed. The server may not support PPTX import yet.')
    }
  }, [id, queryClient])

  // ---------------------------------------------------------------------------
  // Title handler
  // ---------------------------------------------------------------------------

  const handleTitleChange = useCallback((title: string) => {
    updateMutation.mutate({ title })
  }, [updateMutation])

  // ---------------------------------------------------------------------------
  // Presentation mode
  // ---------------------------------------------------------------------------

  const startPresentation = useCallback(() => {
    setIsPresenting(true)
    document.documentElement.requestFullscreen?.()
  }, [])

  const exitPresentation = useCallback(() => {
    setIsPresenting(false)
    if (document.fullscreenElement) document.exitFullscreen()
  }, [])

  if (!id) return null

  if (isPresenting) {
    return <PresenterMode slides={slides} initialSlide={activeSlide} onExit={exitPresentation} />
  }

  const hasElements = (currentSlide?.elements?.length ?? 0) > 0

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] bg-gray-200 dark:bg-gray-700">
      <EditorTopBar
        docType="presentation"
        docId={id}
        title={doc?.title || 'Untitled presentation'}
        isStarred={doc?.is_starred ?? false}
        onTitleChange={handleTitleChange}
        onStar={() => starMutation.mutate()}
        connectedUsers={connectedUsers}
        connectionStatus={connectionStatus}
      />

      {/* Toolbar */}
      <div className="bg-white dark:bg-gray-900 border-b dark:border-gray-700 px-4 py-1.5 flex items-center gap-2 flex-wrap">
        {/* Present */}
        <button onClick={startPresentation} className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-orange-600 rounded-lg hover:bg-orange-700">
          <Play className="h-4 w-4" /> Present
        </button>

        <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 mx-1" />

        {/* Layout selector */}
        <Dropdown trigger={
          <button className="flex items-center gap-1.5 px-2.5 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md">
            <Layout className="h-4 w-4" /> Layout <ChevronDown className="h-3 w-3" />
          </button>
        }>
          {LAYOUTS.map((l) => (
            <DropdownItem key={l.value} onClick={() => applyLayout(l.value)}>
              <span className={cn(currentSlide?.layout === l.value && 'font-semibold text-orange-600 dark:text-orange-400')}>{l.label}</span>
            </DropdownItem>
          ))}
        </Dropdown>

        {/* Background color */}
        <label className="flex items-center gap-1.5 px-2.5 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md cursor-pointer" title="Background color">
          <Palette className="h-4 w-4" />
          <input
            type="color"
            value={currentSlide?.backgroundColor || '#ffffff'}
            onChange={(e) => updateSlide(activeSlide, { backgroundColor: e.target.value })}
            className="w-5 h-5 rounded border-0 cursor-pointer"
          />
        </label>

        {/* Transition */}
        <Dropdown trigger={
          <button className="flex items-center gap-1.5 px-2.5 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md">
            <Sparkles className="h-4 w-4" /> Transition <ChevronDown className="h-3 w-3" />
          </button>
        }>
          {TRANSITIONS.map((t) => (
            <DropdownItem key={t.value} onClick={() => updateSlide(activeSlide, { transition: t.value })}>
              <span className={cn(currentSlide?.transition === t.value && 'font-semibold text-orange-600 dark:text-orange-400')}>{t.label}</span>
            </DropdownItem>
          ))}
        </Dropdown>

        <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 mx-1" />

        {/* Add element */}
        <Dropdown trigger={
          <button className="flex items-center gap-1.5 px-2.5 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md">
            <Plus className="h-4 w-4" /> Add <ChevronDown className="h-3 w-3" />
          </button>
        }>
          <DropdownItem onClick={() => addElement('text')}><Type className="h-4 w-4" /> Text Box</DropdownItem>
          <div className="px-3 py-1 text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wider font-medium">Shapes</div>
          <DropdownItem onClick={() => addElement('shape', { shapeType: 'rectangle' })}><Square className="h-4 w-4" /> Rectangle</DropdownItem>
          <DropdownItem onClick={() => addElement('shape', { shapeType: 'circle', width: 20, height: 35 })}><Circle className="h-4 w-4" /> Circle</DropdownItem>
          <DropdownItem onClick={() => addElement('shape', { shapeType: 'rounded-rect' })}><Square className="h-4 w-4 rounded" /> Rounded Rect</DropdownItem>
          <DropdownItem onClick={() => addElement('shape', { shapeType: 'triangle' })}><Triangle className="h-4 w-4" /> Triangle</DropdownItem>
          <DropdownItem onClick={() => addElement('shape', { shapeType: 'arrow-right', width: 25, height: 15 })}><ArrowRight className="h-4 w-4" /> Arrow</DropdownItem>
          <div className="px-3 py-1 text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wider font-medium">Media</div>
          <DropdownItem onClick={() => { const url = prompt('Enter image URL:'); addElement('image', { src: url || '' }) }}><ImageIcon className="h-4 w-4" /> Image (URL)</DropdownItem>
        </Dropdown>

        <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 mx-1" />

        {/* Import/Export */}
        <Dropdown trigger={
          <button className="flex items-center gap-1.5 px-2.5 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md">
            <Download className="h-4 w-4" /> Download <ChevronDown className="h-3 w-3" />
          </button>
        }>
          <DropdownItem onClick={handleExportPptx}><Download className="h-4 w-4" /> Download PPTX</DropdownItem>
          <DropdownItem onClick={handleExportPdf}><Download className="h-4 w-4" /> Download PDF</DropdownItem>
        </Dropdown>

        <button onClick={() => importInputRef.current?.click()} className="flex items-center gap-1.5 px-2.5 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md">
          <Upload className="h-4 w-4" /> Import
        </button>
        <input ref={importInputRef} type="file" accept=".pptx" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImport(f); e.target.value = '' }} />

        <div className="flex-1" />

        {/* Speaker notes toggle */}
        <button onClick={() => setShowNotes((n) => !n)} className={cn('flex items-center gap-1.5 px-2.5 py-1.5 text-sm rounded-md', showNotes ? 'text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800')}>
          <StickyNote className="h-4 w-4" /> Notes
        </button>

        {/* Properties panel toggle */}
        <button onClick={() => setShowProperties((p) => !p)} className={cn('flex items-center gap-1.5 px-2.5 py-1.5 text-sm rounded-md', showProperties ? 'text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800')}>
          {showProperties ? <PanelRightClose className="h-4 w-4" /> : <PanelRight className="h-4 w-4" />}
        </button>

        {/* Slide counter */}
        <span className="text-sm text-gray-500 dark:text-gray-400 ml-2">
          Slide {activeSlide + 1} of {slides.length}
        </span>
      </div>

      {/* Main content area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Slide thumbnails sidebar */}
        <div className="w-48 bg-gray-100 dark:bg-gray-800 border-r dark:border-gray-700 overflow-y-auto p-3 space-y-2 shrink-0">
          {slides.map((s, index) => (
            <div
              key={index}
              draggable
              onDragStart={() => handleSlideDragStart(index)}
              onDragOver={(e) => handleSlideDragOver(e, index)}
              onDragEnd={handleSlideDragEnd}
              onClick={() => { setActiveSlide(index); setSelectedElementId(null) }}
              className={cn(
                'group relative cursor-pointer rounded-md overflow-hidden border-2 transition-colors',
                activeSlide === index
                  ? 'border-orange-500 shadow-md'
                  : 'border-gray-300 dark:border-gray-600 hover:border-orange-300'
              )}
            >
              {/* Mini slide preview */}
              <div className="aspect-video relative overflow-hidden" style={{ backgroundColor: s.backgroundColor || '#ffffff' }}>
                {/* Render mini elements */}
                {(s.elements || []).map((el) => (
                  <div
                    key={el.id}
                    className="absolute overflow-hidden"
                    style={{
                      left: `${el.x}%`, top: `${el.y}%`, width: `${el.width}%`, height: `${el.height}%`,
                      opacity: el.opacity ?? 1,
                    }}
                  >
                    {el.type === 'shape' && <ShapeSVG shape={el.shapeType || 'rectangle'} fill={el.fillColor || '#3b82f6'} border={el.borderColor || 'transparent'} />}
                    {el.type === 'text' && <div className="text-[4px] leading-tight overflow-hidden w-full h-full" />}
                    {el.type === 'image' && el.src && <img src={el.src} alt="" className="w-full h-full object-cover" />}
                  </div>
                ))}
                {!s.elements?.length && (
                  <div className="flex items-center justify-center h-full">
                    <span className="font-medium text-[10px] text-gray-400 dark:text-gray-500">Slide {index + 1}</span>
                  </div>
                )}
              </div>
              {/* Slide number badge */}
              <div className="absolute top-1 left-1 bg-black/50 text-white text-[10px] px-1.5 py-0.5 rounded">
                {index + 1}
              </div>
              {/* Drag handle */}
              <div className="absolute top-1 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-60 transition-opacity">
                <GripVertical className="h-3 w-3 text-white drop-shadow" />
              </div>
              {/* Actions */}
              {slides.length > 1 && (
                <button
                  onClick={(e) => { e.stopPropagation(); deleteSlide(index) }}
                  className="absolute top-1 right-1 p-0.5 bg-red-500/80 text-white rounded opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Delete slide"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              )}
            </div>
          ))}
          <button
            onClick={addSlide}
            className="w-full aspect-video border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-md flex items-center justify-center text-gray-400 dark:text-gray-500 hover:border-orange-400 hover:text-orange-500 transition-colors"
          >
            <Plus className="h-6 w-6" />
          </button>
        </div>

        {/* Center: canvas + notes */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Slide canvas */}
          <div className="flex-1 flex items-center justify-center p-8 overflow-auto" onClick={() => setSelectedElementId(null)}>
            <div
              ref={canvasRef}
              className="w-full max-w-[960px] aspect-video shadow-lg rounded-sm overflow-hidden relative"
              style={{ backgroundColor: currentSlide?.backgroundColor || '#ffffff' }}
            >
              {/* Elements layer */}
              {hasElements ? (
                (currentSlide.elements || []).map((el) => (
                  <CanvasElement
                    key={el.id}
                    el={el}
                    isSelected={selectedElementId === el.id}
                    onSelect={() => setSelectedElementId(el.id)}
                    onUpdate={(patch) => updateElement(el.id, patch)}
                    canvasRef={canvasRef}
                  />
                ))
              ) : (
                /* Fallback: plain Tiptap editor when no elements */
                <SlideMainEditor
                  slideContent={currentSlide?.content ?? null}
                  onUpdate={(json) => handleSlideContentUpdate(activeSlide, json)}
                />
              )}
            </div>
          </div>

          {/* Speaker notes panel */}
          {showNotes && (
            <div className="h-32 border-t dark:border-gray-700 bg-white dark:bg-gray-900 flex flex-col shrink-0">
              <div className="px-3 py-1 text-xs font-medium text-gray-500 dark:text-gray-400 border-b dark:border-gray-700 flex items-center gap-2">
                <StickyNote className="h-3 w-3" /> Speaker Notes
              </div>
              <textarea
                value={currentSlide?.speakerNotes || ''}
                onChange={(e) => updateSlide(activeSlide, { speakerNotes: e.target.value })}
                placeholder="Add speaker notes for this slide..."
                className="flex-1 p-3 text-sm bg-transparent text-gray-700 dark:text-gray-300 resize-none focus:outline-none placeholder:text-gray-400 dark:placeholder:text-gray-600"
              />
            </div>
          )}
        </div>

        {/* Properties panel (right) */}
        {showProperties && (
          <div className="w-64 bg-white dark:bg-gray-900 border-l dark:border-gray-700 overflow-hidden shrink-0">
            <div className="px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 border-b dark:border-gray-700 uppercase tracking-wide">
              Properties
            </div>
            <PropertiesPanel
              element={selectedElement}
              onUpdate={(patch) => { if (selectedElementId) updateElement(selectedElementId, patch) }}
              onDelete={() => { if (selectedElementId) deleteElement(selectedElementId) }}
            />
          </div>
        )}
      </div>

      <style>{`
        .ProseMirror {
          min-height: 100%;
          padding: 40px;
        }
        .ProseMirror p.is-editor-empty:first-child::before {
          content: attr(data-placeholder);
          float: left;
          color: #adb5bd;
          pointer-events: none;
          height: 0;
        }
        .ProseMirror img {
          max-width: 100%;
          height: auto;
        }
        .ProseMirror h1 {
          font-size: 2.5em;
          margin-bottom: 0.5em;
        }
        .ProseMirror h2 {
          font-size: 1.8em;
          margin-bottom: 0.4em;
        }
      `}</style>
    </div>
  )
}
