import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listOfficeComments, addOfficeComment, updateOfficeComment, deleteOfficeComment } from '@/api/office'
import { useAuthStore } from '@/stores/authStore'
import { getInitials } from '@/lib/utils'
import { MessageSquare, Send, Pencil, Trash2, Reply, X, Check } from 'lucide-react'
import type { OfficeComment } from '@/types/models'

interface CommentsPanelProps {
  docId: string
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export default function CommentsPanel({ docId }: CommentsPanelProps) {
  const queryClient = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)
  const [newComment, setNewComment] = useState('')
  const [replyTo, setReplyTo] = useState<string | null>(null)
  const [replyText, setReplyText] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')

  const { data } = useQuery({
    queryKey: ['office-comments', docId],
    queryFn: () => listOfficeComments(docId),
  })

  const comments = useMemo(() => data?.data ?? [], [data])
  const topLevel = comments.filter((c) => !c.parent_id)
  const repliesFor = (id: string) => comments.filter((c) => c.parent_id === id)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['office-comments', docId] })

  const addMutation = useMutation({
    mutationFn: (vars: { content: string; parent_id?: string | null }) =>
      addOfficeComment(docId, vars),
    onSuccess: () => {
      invalidate()
      setNewComment('')
      setReplyText('')
      setReplyTo(null)
    },
    onError: (err: Error) => alert(`Failed to add comment: ${err.message}`),
  })

  const editMutation = useMutation({
    mutationFn: (vars: { id: string; content: string }) => updateOfficeComment(vars.id, vars.content),
    onSuccess: () => {
      invalidate()
      setEditingId(null)
    },
    onError: (err: Error) => alert(`Failed to edit comment: ${err.message}`),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteOfficeComment(id),
    onSuccess: invalidate,
    onError: (err: Error) => alert(`Failed to delete comment: ${err.message}`),
  })

  const renderComment = (c: OfficeComment, isReply = false) => {
    const isMine = currentUser?.id === c.user_id
    const isEditing = editingId === c.id

    return (
      <div key={c.id} className={isReply ? 'pl-8 mt-2' : ''}>
        <div className="flex items-start gap-2">
          <div className="h-7 w-7 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400 flex items-center justify-center text-[10px] font-medium shrink-0">
            {getInitials(c.user_name)}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{c.user_name}</span>
              <span className="text-[11px] text-gray-400 dark:text-gray-500">{timeAgo(c.created_at)}</span>
              {c.is_edited && <span className="text-[11px] text-gray-400 dark:text-gray-500">(edited)</span>}
            </div>

            {isEditing ? (
              <div className="mt-1 flex items-start gap-1">
                <textarea
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  className="flex-1 text-sm border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  rows={2}
                  autoFocus
                />
                <button
                  onClick={() => editText.trim() && editMutation.mutate({ id: c.id, content: editText.trim() })}
                  className="p-1 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/30 rounded"
                  title="Save"
                >
                  <Check className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => setEditingId(null)}
                  className="p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                  title="Cancel"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ) : (
              <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words">{c.content}</p>
            )}

            {!isEditing && (
              <div className="flex items-center gap-3 mt-0.5">
                {!isReply && (
                  <button
                    onClick={() => setReplyTo(replyTo === c.id ? null : c.id)}
                    className="flex items-center gap-1 text-[11px] text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400"
                  >
                    <Reply className="h-3 w-3" /> Reply
                  </button>
                )}
                {isMine && (
                  <>
                    <button
                      onClick={() => {
                        setEditingId(c.id)
                        setEditText(c.content)
                      }}
                      className="flex items-center gap-1 text-[11px] text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400"
                    >
                      <Pencil className="h-3 w-3" /> Edit
                    </button>
                    <button
                      onClick={() => confirm('Delete this comment?') && deleteMutation.mutate(c.id)}
                      className="flex items-center gap-1 text-[11px] text-gray-500 dark:text-gray-400 hover:text-red-500"
                    >
                      <Trash2 className="h-3 w-3" /> Delete
                    </button>
                  </>
                )}
              </div>
            )}

            {replyTo === c.id && (
              <div className="mt-2 flex items-start gap-1">
                <textarea
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Write a reply..."
                  className="flex-1 text-sm border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  rows={2}
                  autoFocus
                />
                <button
                  onClick={() =>
                    replyText.trim() && addMutation.mutate({ content: replyText.trim(), parent_id: c.id })
                  }
                  disabled={!replyText.trim() || addMutation.isPending}
                  className="p-1.5 text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
                  title="Send reply"
                >
                  <Send className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </div>
        </div>

        {!isReply && repliesFor(c.id).map((reply) => renderComment(reply, true))}
      </div>
    )
  }

  return (
    <div className="w-72 shrink-0 bg-white dark:bg-gray-900 border-l dark:border-gray-700 flex flex-col overflow-hidden">
      <div className="px-3 py-2 border-b dark:border-gray-700 flex items-center gap-2">
        <MessageSquare className="h-4 w-4 text-gray-500 dark:text-gray-400" />
        <span className="text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wide">
          Comments
        </span>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        {topLevel.length === 0 ? (
          <p className="text-xs text-gray-400 dark:text-gray-500 italic">No comments yet. Start the discussion.</p>
        ) : (
          topLevel.map((c) => renderComment(c))
        )}
      </div>

      <div className="border-t dark:border-gray-700 p-2 flex items-start gap-1">
        <textarea
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          placeholder="Add a comment..."
          className="flex-1 text-sm border border-gray-300 dark:border-gray-600 rounded px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
          rows={2}
        />
        <button
          onClick={() => newComment.trim() && addMutation.mutate({ content: newComment.trim() })}
          disabled={!newComment.trim() || addMutation.isPending}
          className="p-2 text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
          title="Post comment"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
