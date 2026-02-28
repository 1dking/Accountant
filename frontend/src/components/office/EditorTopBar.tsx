import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { ArrowLeft, Star, Share2, FileText, Table2, Presentation } from 'lucide-react'
import CollaboratorAvatars from './CollaboratorAvatars'
import ShareDialog from './ShareDialog'
import type { DocType } from '@/types/models'

interface AwarenessUser {
  name: string
  color: string
}

interface EditorTopBarProps {
  docType: DocType
  docId: string
  title: string
  isStarred: boolean
  onTitleChange: (title: string) => void
  onStar: () => void
  connectedUsers?: AwarenessUser[]
  connectionStatus?: 'connected' | 'connecting' | 'disconnected'
}

const DOC_ICONS: Record<DocType, typeof FileText> = {
  document: FileText,
  spreadsheet: Table2,
  presentation: Presentation,
}

const DOC_COLORS: Record<DocType, string> = {
  document: 'text-blue-600',
  spreadsheet: 'text-green-600',
  presentation: 'text-orange-600',
}

const BACK_ROUTES: Record<DocType, string> = {
  document: '/docs',
  spreadsheet: '/sheets',
  presentation: '/slides',
}

export default function EditorTopBar({
  docType,
  docId,
  title,
  isStarred,
  onTitleChange,
  onStar,
  connectedUsers = [],
  connectionStatus = 'connecting',
}: EditorTopBarProps) {
  const navigate = useNavigate()
  const [editingTitle, setEditingTitle] = useState(false)
  const [localTitle, setLocalTitle] = useState(title)
  const [showShare, setShowShare] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const Icon = DOC_ICONS[docType]

  useEffect(() => {
    setLocalTitle(title)
  }, [title])

  useEffect(() => {
    if (editingTitle && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editingTitle])

  const handleTitleBlur = () => {
    setEditingTitle(false)
    const trimmed = localTitle.trim()
    if (trimmed && trimmed !== title) {
      onTitleChange(trimmed)
    } else {
      setLocalTitle(title)
    }
  }

  const handleTitleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleTitleBlur()
    } else if (e.key === 'Escape') {
      setLocalTitle(title)
      setEditingTitle(false)
    }
  }

  return (
    <>
      <div className="bg-white border-b px-4 py-2 flex items-center gap-3">
        {/* Back button */}
        <button
          onClick={() => navigate(BACK_ROUTES[docType])}
          className="p-1.5 rounded-md text-gray-500 hover:text-gray-700 hover:bg-gray-100"
          title={`Back to ${docType === 'document' ? 'Docs' : docType === 'spreadsheet' ? 'Sheets' : 'Slides'}`}
        >
          <ArrowLeft className="h-5 w-5" />
        </button>

        {/* Doc type icon */}
        <Icon className={`h-5 w-5 ${DOC_COLORS[docType]} shrink-0`} />

        {/* Title */}
        {editingTitle ? (
          <input
            ref={inputRef}
            type="text"
            value={localTitle}
            onChange={(e) => setLocalTitle(e.target.value)}
            onBlur={handleTitleBlur}
            onKeyDown={handleTitleKeyDown}
            className="text-lg font-medium text-gray-900 bg-transparent border-b-2 border-blue-500 outline-none px-1 py-0 min-w-[200px]"
          />
        ) : (
          <button
            onClick={() => setEditingTitle(true)}
            className="text-lg font-medium text-gray-900 hover:bg-gray-50 px-1 py-0 rounded min-w-0 truncate"
            title="Click to rename"
          >
            {title || 'Untitled'}
          </button>
        )}

        {/* Star */}
        <button
          onClick={onStar}
          className={`p-1.5 rounded-md transition-colors ${
            isStarred
              ? 'text-yellow-500 hover:bg-yellow-50'
              : 'text-gray-400 hover:text-yellow-500 hover:bg-gray-100'
          }`}
          title={isStarred ? 'Remove star' : 'Add star'}
        >
          <Star className="h-5 w-5" fill={isStarred ? 'currentColor' : 'none'} />
        </button>

        {/* Connection status */}
        <div className="flex items-center gap-1.5 ml-2">
          <div
            className={`h-2 w-2 rounded-full ${
              connectionStatus === 'connected'
                ? 'bg-green-500'
                : connectionStatus === 'connecting'
                  ? 'bg-yellow-500 animate-pulse'
                  : 'bg-red-500'
            }`}
          />
          <span className="text-xs text-gray-400 capitalize">{connectionStatus}</span>
        </div>

        <div className="flex-1" />

        {/* Collaborator avatars */}
        <CollaboratorAvatars users={connectedUsers} />

        {/* Share button */}
        <button
          onClick={() => setShowShare(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 rounded-full hover:bg-blue-100 transition-colors"
        >
          <Share2 className="h-4 w-4" />
          Share
        </button>
      </div>

      <ShareDialog docId={docId} isOpen={showShare} onClose={() => setShowShare(false)} />
    </>
  )
}
