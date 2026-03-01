import { useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getOfficeDoc, starOfficeDoc } from '@/api/office'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import TextAlign from '@tiptap/extension-text-align'
import Highlight from '@tiptap/extension-highlight'
import Image from '@tiptap/extension-image'
import { Table, TableRow, TableCell, TableHeader } from '@tiptap/extension-table'
import { ArrowLeft, Star, Pencil } from 'lucide-react'

export default function DocReaderPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const initialLoadRef = useRef(false)

  const { data: docData, isLoading } = useQuery({
    queryKey: ['office-doc', id],
    queryFn: () => getOfficeDoc(id!),
    enabled: !!id,
  })

  const doc = docData?.data

  const starMutation = useMutation({
    mutationFn: () => starOfficeDoc(id!, !doc?.is_starred),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['office-doc', id] })
    },
  })

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      Highlight,
      Image,
      Table.configure({ resizable: false }),
      TableRow,
      TableCell,
      TableHeader,
    ],
    editable: false,
    editorProps: {
      attributes: {
        class: 'prose prose-lg max-w-none focus:outline-none dark:prose-invert',
      },
    },
  })

  // Load content into editor when doc data arrives
  useEffect(() => {
    if (!editor || !doc || initialLoadRef.current) return
    initialLoadRef.current = true

    if (doc.content_json && typeof doc.content_json === 'object') {
      editor.commands.setContent(doc.content_json)
    }
  }, [editor, doc])

  // Reset initial load ref if document id changes
  useEffect(() => {
    initialLoadRef.current = false
  }, [id])

  if (!id) return null

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <p className="text-gray-500 dark:text-gray-400">Loading document...</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] bg-gray-50 dark:bg-gray-950">
      {/* Top bar */}
      <div className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 px-4 py-2 flex items-center gap-3">
        {/* Back button */}
        <button
          onClick={() => navigate('/docs')}
          className="p-1.5 rounded-md text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-800"
          title="Back to Docs"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>

        {/* Document title */}
        <h1 className="text-lg font-medium text-gray-900 dark:text-gray-100 truncate min-w-0">
          {doc?.title || 'Untitled document'}
        </h1>

        {/* Star toggle */}
        <button
          onClick={() => starMutation.mutate()}
          className={`p-1.5 rounded-md transition-colors ${
            doc?.is_starred
              ? 'text-yellow-500 hover:bg-yellow-50 dark:hover:bg-yellow-500/10'
              : 'text-gray-400 hover:text-yellow-500 hover:bg-gray-100 dark:hover:bg-gray-800'
          }`}
          title={doc?.is_starred ? 'Remove star' : 'Add star'}
        >
          <Star className="h-5 w-5" fill={doc?.is_starred ? 'currentColor' : 'none'} />
        </button>

        <div className="flex-1" />

        {/* Edit button */}
        <button
          onClick={() => navigate(`/docs/${id}`)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 rounded-full hover:bg-blue-100 dark:text-blue-400 dark:bg-blue-500/10 dark:hover:bg-blue-500/20 transition-colors"
        >
          <Pencil className="h-4 w-4" />
          Edit
        </button>
      </div>

      {/* Reading area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[750px] mx-auto pt-20 pb-32 px-[60px]">
          <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-16">
            <EditorContent editor={editor} />
          </div>
        </div>
      </div>

      <style>{`
        .doc-reader .ProseMirror {
          outline: none;
        }
        .ProseMirror {
          font-size: 1.1rem;
          line-height: 1.8;
          color: #1f2937;
        }
        .dark .ProseMirror {
          color: #e5e7eb;
        }
        .ProseMirror h1 {
          font-size: 2em;
          font-weight: 700;
          margin-top: 1.5em;
          margin-bottom: 0.5em;
          line-height: 1.3;
        }
        .ProseMirror h2 {
          font-size: 1.5em;
          font-weight: 600;
          margin-top: 1.4em;
          margin-bottom: 0.5em;
          line-height: 1.35;
        }
        .ProseMirror h3 {
          font-size: 1.25em;
          font-weight: 600;
          margin-top: 1.3em;
          margin-bottom: 0.4em;
          line-height: 1.4;
        }
        .ProseMirror p {
          margin-bottom: 0.8em;
        }
        .ProseMirror table {
          border-collapse: collapse;
          margin: 1em 0;
          width: 100%;
        }
        .ProseMirror td, .ProseMirror th {
          border: 1px solid #d1d5db;
          padding: 8px 12px;
          vertical-align: top;
        }
        .dark .ProseMirror td, .dark .ProseMirror th {
          border-color: #4b5563;
        }
        .ProseMirror th {
          background-color: #f3f4f6;
          font-weight: 600;
        }
        .dark .ProseMirror th {
          background-color: #374151;
        }
        .ProseMirror img {
          max-width: 100%;
          height: auto;
          border-radius: 4px;
        }
        .ProseMirror blockquote {
          border-left: 3px solid #d1d5db;
          padding-left: 1em;
          color: #6b7280;
          margin: 1em 0;
        }
        .dark .ProseMirror blockquote {
          border-left-color: #4b5563;
          color: #9ca3af;
        }
        .ProseMirror mark {
          background-color: #fef08a;
          padding: 0.125em 0;
        }
        .dark .ProseMirror mark {
          background-color: #854d0e;
          color: #fef08a;
        }
        .ProseMirror ul, .ProseMirror ol {
          padding-left: 1.5em;
          margin: 0.5em 0;
        }
        .ProseMirror li {
          margin-bottom: 0.25em;
        }
        .ProseMirror code {
          background-color: #f3f4f6;
          padding: 0.2em 0.4em;
          border-radius: 3px;
          font-size: 0.9em;
        }
        .dark .ProseMirror code {
          background-color: #374151;
        }
        .ProseMirror pre {
          background-color: #1f2937;
          color: #e5e7eb;
          padding: 1em;
          border-radius: 6px;
          overflow-x: auto;
          margin: 1em 0;
        }
        .dark .ProseMirror pre {
          background-color: #111827;
        }
        .ProseMirror pre code {
          background: none;
          padding: 0;
          color: inherit;
        }
        .ProseMirror hr {
          border: none;
          border-top: 1px solid #e5e7eb;
          margin: 2em 0;
        }
        .dark .ProseMirror hr {
          border-top-color: #374151;
        }
        .ProseMirror a {
          color: #2563eb;
          text-decoration: underline;
        }
        .dark .ProseMirror a {
          color: #60a5fa;
        }
      `}</style>
    </div>
  )
}
