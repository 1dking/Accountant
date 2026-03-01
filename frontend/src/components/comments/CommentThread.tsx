import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listComments, createComment, deleteComment } from '@/api/collaboration'
import { useAuthStore } from '@/stores/authStore'
import { formatDateTime } from '@/lib/utils'
import type { Comment } from '@/types/models'

interface CommentThreadProps {
  documentId: string
}

export default function CommentThread({ documentId }: CommentThreadProps) {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [newComment, setNewComment] = useState('')
  const [replyTo, setReplyTo] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['comments', documentId],
    queryFn: () => listComments(documentId),
  })

  const createMutation = useMutation({
    mutationFn: (params: { content: string; parent_id?: string }) =>
      createComment(documentId, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments', documentId] })
      setNewComment('')
      setReplyTo(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteComment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments', documentId] })
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newComment.trim()) return
    createMutation.mutate({
      content: newComment.trim(),
      parent_id: replyTo ?? undefined,
    })
  }

  const comments: Comment[] = data?.data ?? []
  const topLevel = comments.filter((c) => !c.parent_id)
  const replies = (parentId: string) => comments.filter((c) => c.parent_id === parentId)

  const renderComment = (comment: Comment, depth: number = 0) => (
    <div key={comment.id} style={{ marginLeft: depth * 24 }} className="mt-3">
      <div className="bg-white dark:bg-gray-900 border rounded-lg p-3">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{comment.user_name}</span>
            <span className="text-xs text-gray-400 dark:text-gray-500">{formatDateTime(comment.created_at)}</span>
            {comment.is_edited && <span className="text-xs text-gray-400 dark:text-gray-500">(edited)</span>}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setReplyTo(comment.id)}
              className="text-xs text-gray-500 dark:text-gray-400 hover:text-blue-600"
            >
              Reply
            </button>
            {(comment.user_id === user?.id || user?.role === 'admin') && (
              <button
                onClick={() => deleteMutation.mutate(comment.id)}
                className="text-xs text-gray-500 dark:text-gray-400 hover:text-red-600"
              >
                Delete
              </button>
            )}
          </div>
        </div>
        <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{comment.content}</p>
      </div>
      {replies(comment.id).map((reply) => renderComment(reply, depth + 1))}
    </div>
  )

  return (
    <div>
      <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-3">
        Comments ({comments.length})
      </h3>

      <form onSubmit={handleSubmit} className="mb-4">
        {replyTo && (
          <div className="flex items-center gap-2 mb-2 text-sm text-gray-500 dark:text-gray-400">
            <span>Replying to comment</span>
            <button
              type="button"
              onClick={() => setReplyTo(null)}
              className="text-red-500 hover:underline"
            >
              Cancel
            </button>
          </div>
        )}
        <div className="flex gap-2">
          <input
            type="text"
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            placeholder="Add a comment..."
            className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={!newComment.trim() || createMutation.isPending}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            Post
          </button>
        </div>
      </form>

      {isLoading ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">Loading comments...</p>
      ) : topLevel.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">No comments yet.</p>
      ) : (
        <div>{topLevel.map((c) => renderComment(c))}</div>
      )}
    </div>
  )
}
