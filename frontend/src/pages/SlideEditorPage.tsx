import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getOfficeDoc, updateOfficeDoc, starOfficeDoc } from '@/api/office'
import { useAuthStore } from '@/stores/authStore'
import EditorTopBar from '@/components/office/EditorTopBar'
import {
  Plus,
  Play,
  Maximize,
  Trash2,
  ChevronLeft,
  ChevronRight,
  Bold,
  Italic,
  Underline,
  AlignLeft,
  AlignCenter,
  AlignRight,
  ImageIcon,
  Heading1,
  Heading2,
} from 'lucide-react'
import { cn } from '@/lib/utils'

import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import UnderlineExt from '@tiptap/extension-underline'
import TextAlign from '@tiptap/extension-text-align'
import Image from '@tiptap/extension-image'
import Placeholder from '@tiptap/extension-placeholder'

interface SlideContent {
  content: Record<string, unknown> | null
}

interface SlideEditorProps {
  slideContent: Record<string, unknown> | null
  onUpdate: (json: Record<string, unknown>) => void
}

function SlideEditor({ slideContent, onUpdate }: SlideEditorProps) {
  const initialLoadRef = useRef(false)

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

  // Load initial content when editor is ready
  useEffect(() => {
    if (!editor) return
    initialLoadRef.current = false
  }, [editor])

  // Update editor content when slide changes
  useEffect(() => {
    if (!editor) return
    if (slideContent && typeof slideContent === 'object') {
      editor.commands.setContent(slideContent)
    } else {
      editor.commands.clearContent()
    }
  }, [editor, slideContent])

  return (
    <div className="h-full">
      {/* Slide toolbar */}
      {editor && (
        <div className="absolute top-0 left-0 right-0 bg-white/90 border-b px-3 py-1 flex items-center gap-0.5 z-10 opacity-0 hover:opacity-100 transition-opacity">
          <button
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={cn(
              'p-1 rounded text-sm',
              editor.isActive('bold') ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
            )}
          >
            <Bold className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={cn(
              'p-1 rounded text-sm',
              editor.isActive('italic') ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
            )}
          >
            <Italic className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().toggleUnderline().run()}
            className={cn(
              'p-1 rounded text-sm',
              editor.isActive('underline') ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
            )}
          >
            <Underline className="h-3.5 w-3.5" />
          </button>
          <div className="w-px h-4 bg-gray-200 mx-1" />
          <button
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
            className={cn(
              'p-1 rounded text-sm',
              editor.isActive('heading', { level: 1 }) ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
            )}
          >
            <Heading1 className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            className={cn(
              'p-1 rounded text-sm',
              editor.isActive('heading', { level: 2 }) ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
            )}
          >
            <Heading2 className="h-3.5 w-3.5" />
          </button>
          <div className="w-px h-4 bg-gray-200 mx-1" />
          <button
            onClick={() => editor.chain().focus().setTextAlign('left').run()}
            className={cn(
              'p-1 rounded text-sm',
              editor.isActive({ textAlign: 'left' }) ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
            )}
          >
            <AlignLeft className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().setTextAlign('center').run()}
            className={cn(
              'p-1 rounded text-sm',
              editor.isActive({ textAlign: 'center' }) ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
            )}
          >
            <AlignCenter className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().setTextAlign('right').run()}
            className={cn(
              'p-1 rounded text-sm',
              editor.isActive({ textAlign: 'right' }) ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
            )}
          >
            <AlignRight className="h-3.5 w-3.5" />
          </button>
          <div className="w-px h-4 bg-gray-200 mx-1" />
          <button
            onClick={() => {
              const url = prompt('Enter image URL:')
              if (url) editor.chain().focus().setImage({ src: url }).run()
            }}
            className="p-1 rounded text-sm text-gray-600 hover:bg-gray-100"
          >
            <ImageIcon className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
      <EditorContent editor={editor} className="h-full" />
    </div>
  )
}

export default function SlideEditorPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const { user: _user } = useAuthStore()
  const [connectionStatus] = useState<'connected' | 'connecting' | 'disconnected'>('connected')
  const [connectedUsers] = useState<{ name: string; color: string }[]>([])
  const [activeSlide, setActiveSlide] = useState(0)
  const [slides, setSlides] = useState<SlideContent[]>([{ content: null }])
  const [isPresenting, setIsPresenting] = useState(false)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const initialLoadRef = useRef(false)

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
        setSlides(saved.slides)
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

  const handleSlideUpdate = useCallback(
    (index: number, json: Record<string, unknown>) => {
      setSlides((prev) => {
        const updated = [...prev]
        updated[index] = { content: json }
        debouncedSave(updated)
        return updated
      })
    },
    [debouncedSave]
  )

  const addSlide = useCallback(() => {
    setSlides((prev) => {
      const updated = [...prev, { content: null }]
      debouncedSave(updated)
      return updated
    })
    setActiveSlide(slides.length)
  }, [slides.length, debouncedSave])

  const deleteSlide = useCallback(
    (index: number) => {
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
    },
    [slides.length, activeSlide, debouncedSave]
  )

  const handleTitleChange = useCallback(
    (title: string) => {
      updateMutation.mutate({ title })
    },
    [updateMutation]
  )

  // Presentation mode keyboard navigation
  useEffect(() => {
    if (!isPresenting) return

    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ') {
        e.preventDefault()
        setActiveSlide((s) => Math.min(s + 1, slides.length - 1))
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveSlide((s) => Math.max(s - 1, 0))
      } else if (e.key === 'Escape') {
        setIsPresenting(false)
        if (document.fullscreenElement) {
          document.exitFullscreen()
        }
      }
    }

    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [isPresenting, slides.length])

  const startPresentation = () => {
    setIsPresenting(true)
    setActiveSlide(0)
    document.documentElement.requestFullscreen?.()
  }

  if (!id) return null

  // Presentation mode
  if (isPresenting) {
    return (
      <div className="fixed inset-0 bg-black z-50 flex items-center justify-center">
        <div className="w-full max-w-[1280px] aspect-video bg-white rounded-sm overflow-hidden relative">
          <SlideEditor
            slideContent={slides[activeSlide]?.content ?? null}
            onUpdate={(json) => handleSlideUpdate(activeSlide, json)}
          />
        </div>
        {/* Navigation controls */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-4 bg-black/60 rounded-full px-4 py-2">
          <button
            onClick={() => setActiveSlide((s) => Math.max(s - 1, 0))}
            disabled={activeSlide === 0}
            className="text-white disabled:opacity-30"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <span className="text-white text-sm">
            {activeSlide + 1} / {slides.length}
          </span>
          <button
            onClick={() => setActiveSlide((s) => Math.min(s + 1, slides.length - 1))}
            disabled={activeSlide === slides.length - 1}
            className="text-white disabled:opacity-30"
          >
            <ChevronRight className="h-5 w-5" />
          </button>
          <button
            onClick={() => {
              setIsPresenting(false)
              if (document.fullscreenElement) document.exitFullscreen()
            }}
            className="text-white ml-2"
            title="Exit presentation"
          >
            <Maximize className="h-4 w-4" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] bg-gray-200">
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

      {/* Present button bar */}
      <div className="bg-white border-b px-4 py-1.5 flex items-center gap-2">
        <button
          onClick={startPresentation}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-orange-600 rounded-lg hover:bg-orange-700"
        >
          <Play className="h-4 w-4" />
          Present
        </button>
        <div className="flex-1" />
        <span className="text-sm text-gray-500">
          Slide {activeSlide + 1} of {slides.length}
        </span>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Slide thumbnails sidebar */}
        <div className="w-48 bg-gray-100 border-r overflow-y-auto p-3 space-y-2">
          {slides.map((_, index) => (
            <div
              key={index}
              onClick={() => setActiveSlide(index)}
              className={cn(
                'group relative cursor-pointer rounded-md overflow-hidden border-2 transition-colors',
                activeSlide === index
                  ? 'border-orange-500 shadow-md'
                  : 'border-gray-300 hover:border-orange-300'
              )}
            >
              {/* Mini slide preview */}
              <div className="aspect-video bg-white flex items-center justify-center text-xs text-gray-400 p-2">
                <span className="font-medium text-gray-600">Slide {index + 1}</span>
              </div>
              {/* Slide number */}
              <div className="absolute top-1 left-1 bg-black/50 text-white text-[10px] px-1.5 py-0.5 rounded">
                {index + 1}
              </div>
              {/* Delete button */}
              {slides.length > 1 && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    deleteSlide(index)
                  }}
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
            className="w-full aspect-video border-2 border-dashed border-gray-300 rounded-md flex items-center justify-center text-gray-400 hover:border-orange-400 hover:text-orange-500 transition-colors"
          >
            <Plus className="h-6 w-6" />
          </button>
        </div>

        {/* Main slide canvas */}
        <div className="flex-1 flex items-center justify-center p-8 overflow-auto">
          <div className="w-full max-w-[960px] aspect-video bg-white shadow-lg rounded-sm overflow-hidden relative">
            <SlideEditor
              slideContent={slides[activeSlide]?.content ?? null}
              onUpdate={(json) => handleSlideUpdate(activeSlide, json)}
            />
          </div>
        </div>
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
