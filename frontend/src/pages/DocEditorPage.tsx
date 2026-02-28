import { useEffect, useMemo, useState, useCallback } from 'react'
import { useParams } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getOfficeDoc, updateOfficeDoc, starOfficeDoc } from '@/api/office'
import { useAuthStore } from '@/stores/authStore'
import EditorTopBar from '@/components/office/EditorTopBar'
import DocToolbar from '@/components/office/DocToolbar'

import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { Collaboration } from '@tiptap/extension-collaboration'
import { CollaborationCursor } from '@tiptap/extension-collaboration-cursor'
import Underline from '@tiptap/extension-underline'
import TextAlign from '@tiptap/extension-text-align'
import Highlight from '@tiptap/extension-highlight'
import Image from '@tiptap/extension-image'
import Placeholder from '@tiptap/extension-placeholder'
import { Table, TableRow, TableCell, TableHeader } from '@tiptap/extension-table'

import * as Y from 'yjs'
import { WebsocketProvider } from 'y-websocket'

function generateColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  const hue = Math.abs(hash) % 360
  return `hsl(${hue}, 70%, 50%)`
}

export default function DocEditorPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'connecting' | 'disconnected'>('connecting')
  const [connectedUsers, setConnectedUsers] = useState<{ name: string; color: string }[]>([])

  const { data: docData } = useQuery({
    queryKey: ['office-doc', id],
    queryFn: () => getOfficeDoc(id!),
    enabled: !!id,
  })

  const doc = docData?.data

  const updateMutation = useMutation({
    mutationFn: (data: { title?: string }) => updateOfficeDoc(id!, data),
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

  // Yjs setup
  const ydoc = useMemo(() => new Y.Doc(), [])

  const wsProvider = useMemo(() => {
    if (!id) return null
    const provider = new WebsocketProvider(
      import.meta.env.VITE_COLLAB_URL || 'ws://localhost:1234',
      id,
      ydoc,
      { params: { token: localStorage.getItem('access_token') || '' } }
    )
    return provider
  }, [id, ydoc])

  // Track connection status and awareness
  useEffect(() => {
    if (!wsProvider) return

    const onStatus = (event: { status: string }) => {
      if (event.status === 'connected') setConnectionStatus('connected')
      else if (event.status === 'connecting') setConnectionStatus('connecting')
      else setConnectionStatus('disconnected')
    }

    wsProvider.on('status', onStatus)

    const awareness = wsProvider.awareness
    const userName = user?.full_name || 'Anonymous'
    const userColor = generateColor(userName)

    awareness.setLocalStateField('user', { name: userName, color: userColor })

    const onAwarenessChange = () => {
      const states = awareness.getStates()
      const users: { name: string; color: string }[] = []
      states.forEach((state, clientId) => {
        if (clientId !== awareness.clientID && state.user) {
          users.push(state.user)
        }
      })
      setConnectedUsers(users)
    }

    awareness.on('change', onAwarenessChange)
    onAwarenessChange()

    return () => {
      wsProvider.off('status', onStatus)
      awareness.off('change', onAwarenessChange)
    }
  }, [wsProvider, user])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsProvider?.destroy()
      ydoc.destroy()
    }
  }, [wsProvider, ydoc])

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ history: false } as any),
      Collaboration.configure({ document: ydoc }),
      ...(wsProvider
        ? [
            CollaborationCursor.configure({
              provider: wsProvider,
              user: {
                name: user?.full_name || 'Anonymous',
                color: generateColor(user?.full_name || 'Anonymous'),
              },
            }),
          ]
        : []),
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
  }, [ydoc, wsProvider])

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
        /* Collaboration cursor */
        .collaboration-cursor__caret {
          border-left: 1px solid #0d0d0d;
          border-right: 1px solid #0d0d0d;
          margin-left: -1px;
          margin-right: -1px;
          pointer-events: none;
          position: relative;
          word-break: normal;
        }
        .collaboration-cursor__label {
          border-radius: 3px 3px 3px 0;
          color: #fff;
          font-size: 11px;
          font-weight: 600;
          left: -1px;
          line-height: normal;
          padding: 0.1rem 0.3rem;
          position: absolute;
          top: -1.4em;
          user-select: none;
          white-space: nowrap;
        }
      `}</style>
    </div>
  )
}
