import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getOfficeDoc, updateOfficeDoc, starOfficeDoc } from '@/api/office'
import { useAuthStore } from '@/stores/authStore'
import EditorTopBar from '@/components/office/EditorTopBar'
import DocToolbar from '@/components/office/DocToolbar'

import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import TextAlign from '@tiptap/extension-text-align'
import Highlight from '@tiptap/extension-highlight'
import Image from '@tiptap/extension-image'
import Placeholder from '@tiptap/extension-placeholder'
import { Table, TableRow, TableCell, TableHeader } from '@tiptap/extension-table'

export default function DocEditorPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const { user: _user } = useAuthStore()
  const [connectionStatus] = useState<'connected' | 'connecting' | 'disconnected'>('connected')
  const [connectedUsers] = useState<{ name: string; color: string }[]>([])
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

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      Highlight,
      Image,
      Placeholder.configure({ placeholder: 'Start typing...' }),
      Table.configure({ resizable: true }),
      TableRow,
      TableCell,
      TableHeader,
    ],
    editorProps: {
      attributes: {
        class: 'prose prose-lg max-w-none focus:outline-none min-h-[500px] px-16 py-8',
      },
    },
    onUpdate: ({ editor: ed }) => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
      saveTimerRef.current = setTimeout(() => {
        const json = ed.getJSON()
        updateMutation.mutate({ content_json: json as Record<string, unknown> })
      }, 2000)
    },
  })

  // Load initial content from backend
  useEffect(() => {
    if (!editor || !doc || initialLoadRef.current) return
    initialLoadRef.current = true

    if (doc.content_json && typeof doc.content_json === 'object') {
      editor.commands.setContent(doc.content_json)
    }
  }, [editor, doc])

  // Cleanup save timer on unmount
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [])

  const handleTitleChange = useCallback(
    (title: string) => {
      updateMutation.mutate({ title })
    },
    [updateMutation]
  )

  if (!id) return null

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] bg-gray-100">
      <EditorTopBar
        docType="document"
        docId={id}
        title={doc?.title || 'Untitled document'}
        isStarred={doc?.is_starred ?? false}
        onTitleChange={handleTitleChange}
        onStar={() => starMutation.mutate()}
        connectedUsers={connectedUsers}
        connectionStatus={connectionStatus}
      />
      <DocToolbar editor={editor} />
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[850px] mx-auto my-6 bg-white shadow-sm rounded-sm min-h-[1100px] border">
          <EditorContent editor={editor} />
        </div>
      </div>

      <style>{`
        .ProseMirror {
          min-height: 1000px;
          padding: 60px 70px;
        }
        .ProseMirror p.is-editor-empty:first-child::before {
          content: attr(data-placeholder);
          float: left;
          color: #adb5bd;
          pointer-events: none;
          height: 0;
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
        .ProseMirror th {
          background-color: #f3f4f6;
          font-weight: 600;
        }
        .ProseMirror img {
          max-width: 100%;
          height: auto;
        }
        .ProseMirror blockquote {
          border-left: 3px solid #d1d5db;
          padding-left: 1em;
          color: #6b7280;
        }
        .ProseMirror mark {
          background-color: #fef08a;
          padding: 0.125em 0;
        }
      `}</style>
    </div>
  )
}
