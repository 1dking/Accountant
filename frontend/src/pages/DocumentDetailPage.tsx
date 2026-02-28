import { useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getDocument, updateDocument, deleteDocument, getDownloadUrl, listVersions } from '@/api/documents'
import { requestApproval, resolveApproval } from '@/api/collaboration'
import { createExpenseFromDocument } from '@/api/accounting'
import { createIncomeFromDocument } from '@/api/income'
import CommentThread from '@/components/comments/CommentThread'
import ExtractionResults from '@/components/documents/ExtractionResults'
import { useAuthStore } from '@/stores/authStore'
import { formatFileSize, formatDate, formatDateTime } from '@/lib/utils'
import { DOCUMENT_TYPES, DOCUMENT_STATUSES } from '@/lib/constants'
import type { DocumentType } from '@/types/models'

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [docType, setDocType] = useState<DocumentType>('other')
  const [approvalAssignee, setApprovalAssignee] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['document', id],
    queryFn: () => getDocument(id!),
    enabled: !!id,
  })

  const { data: versionsData } = useQuery({
    queryKey: ['document-versions', id],
    queryFn: () => listVersions(id!),
    enabled: !!id,
  })

  const updateMutation = useMutation({
    mutationFn: (updates: Partial<{ title: string; description: string; document_type: DocumentType }>) =>
      updateDocument(id!, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] })
      setEditing(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteDocument(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      navigate('/documents')
    },
    onError: (err: Error) => {
      alert(`Failed to delete: ${err.message}`)
    },
  })

  const approvalMutation = useMutation({
    mutationFn: (assignedTo: string) => requestApproval(id!, assignedTo),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] })
    },
  })

  const createExpenseMutation = useMutation({
    mutationFn: () => createExpenseFromDocument(id!),
    onSuccess: (data) => {
      navigate(`/expenses/${data.data.id}`)
    },
  })

  const createIncomeMutation = useMutation({
    mutationFn: () => createIncomeFromDocument(id!),
    onSuccess: (data) => {
      navigate(`/income/${data.data.id}`)
    },
  })

  const adminApproveMutation = useMutation({
    mutationFn: (params: { approvalId: string; status: 'approved' | 'rejected' }) =>
      resolveApproval(params.approvalId, { status: params.status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] })
    },
  })

  const doc = data?.data
  const versions = versionsData?.data ?? []

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/3" />
          <div className="h-64 bg-gray-200 rounded" />
        </div>
      </div>
    )
  }

  if (!doc) {
    return (
      <div className="p-6 text-center">
        <h2 className="text-lg font-medium text-gray-900">Document not found</h2>
        <button onClick={() => navigate('/documents')} className="mt-2 text-blue-600 hover:underline">
          Back to documents
        </button>
      </div>
    )
  }

  const statusInfo = DOCUMENT_STATUSES.find((s) => s.value === doc.status)
  const canEdit = user?.role === 'admin' || user?.role === 'accountant'

  const startEditing = () => {
    setTitle(doc.title || '')
    setDescription(doc.description || '')
    setDocType(doc.document_type)
    setEditing(true)
  }

  const saveEdits = () => {
    updateMutation.mutate({ title, description, document_type: docType })
  }

  return (
    <div className="flex h-[calc(100vh-49px)]">
      {/* Preview area */}
      <div className="flex-1 bg-gray-100 p-6 overflow-y-auto">
        <button onClick={() => navigate('/documents')} className="text-sm text-blue-600 hover:underline mb-4 block">
          {'\u2190'} Back to documents
        </button>

        {doc.mime_type === 'application/pdf' ? (
          <iframe
            src={getDownloadUrl(doc.id)}
            className="w-full h-[calc(100%-40px)] bg-white rounded-lg shadow"
            title={doc.title || doc.original_filename}
          />
        ) : doc.mime_type.startsWith('image/') ? (
          <div className="flex items-center justify-center bg-white rounded-lg shadow p-4">
            <img
              src={getDownloadUrl(doc.id)}
              alt={doc.title || doc.original_filename}
              className="max-w-full max-h-[70vh] object-contain"
            />
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="text-6xl mb-4">{'\uD83D\uDCC4'}</div>
            <p className="text-gray-700 font-medium">{doc.original_filename}</p>
            <a
              href={getDownloadUrl(doc.id)}
              download
              className="inline-block mt-3 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
            >
              Download File
            </a>
          </div>
        )}

        {/* Comments */}
        <div className="mt-6">
          <CommentThread documentId={doc.id} />
        </div>
      </div>

      {/* Metadata panel */}
      <div className="w-80 bg-white border-l overflow-y-auto p-4 space-y-5">
        {/* Title & status */}
        <div>
          {editing ? (
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full text-lg font-bold text-gray-900 border-b border-blue-500 focus:outline-none pb-1"
              placeholder="Document title"
            />
          ) : (
            <h2 className="text-lg font-bold text-gray-900">{doc.title || doc.original_filename}</h2>
          )}
          {statusInfo && (
            <span className={`inline-block mt-1 px-2 py-0.5 text-xs rounded-full ${statusInfo.color}`}>
              {statusInfo.label}
            </span>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-2">
          <a
            href={getDownloadUrl(doc.id)}
            download
            className="px-3 py-1.5 text-sm border rounded-md hover:bg-gray-50"
          >
            Download
          </a>
          {canEdit && !editing && (
            <button onClick={startEditing} className="px-3 py-1.5 text-sm border rounded-md hover:bg-gray-50">
              Edit
            </button>
          )}
          {editing && (
            <>
              <button onClick={saveEdits} className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700">
                Save
              </button>
              <button onClick={() => setEditing(false)} className="px-3 py-1.5 text-sm border rounded-md hover:bg-gray-50">
                Cancel
              </button>
            </>
          )}
          {(user?.role === 'admin' || user?.role === 'accountant') && (
            <button
              onClick={() => {
                if (confirm('Delete this document?')) deleteMutation.mutate()
              }}
              disabled={deleteMutation.isPending}
              className="px-3 py-1.5 text-sm text-red-600 border border-red-200 rounded-md hover:bg-red-50 disabled:opacity-50"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </button>
          )}
        </div>

        {/* Description */}
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase">Description</label>
          {editing ? (
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full mt-1 px-2 py-1 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Add a description..."
            />
          ) : (
            <p className="text-sm text-gray-700 mt-1">{doc.description || 'No description'}</p>
          )}
        </div>

        {/* Type */}
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase">Type</label>
          {editing ? (
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value as DocumentType)}
              className="w-full mt-1 px-2 py-1 text-sm border rounded-md bg-white"
            >
              {DOCUMENT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          ) : (
            <p className="text-sm text-gray-700 mt-1 capitalize">{doc.document_type.replace('_', ' ')}</p>
          )}
        </div>

        {/* File info */}
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase">File Info</label>
          <div className="text-sm text-gray-700 mt-1 space-y-1">
            <p>Name: {doc.original_filename}</p>
            <p>Size: {formatFileSize(doc.file_size)}</p>
            <p>Type: {doc.mime_type}</p>
            <p>Uploaded: {formatDateTime(doc.created_at)}</p>
          </div>
        </div>

        {/* Tags */}
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase">Tags</label>
          <div className="flex flex-wrap gap-1 mt-1">
            {doc.tags.length === 0 ? (
              <p className="text-sm text-gray-400">No tags</p>
            ) : (
              doc.tags.map((tag) => (
                <span
                  key={tag.id}
                  className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600"
                  style={tag.color ? { backgroundColor: tag.color + '20', color: tag.color } : undefined}
                >
                  {tag.name}
                </span>
              ))
            )}
          </div>
        </div>

        {/* AI Extraction */}
        <ExtractionResults
          documentId={doc.id}
          mimeType={doc.mime_type}
          canExtract={canEdit}
        />

        {/* Create Expense / Income from extracted data */}
        {canEdit && doc.extracted_metadata && (
          <div className="space-y-2">
            <label className="text-xs font-medium text-gray-500 uppercase">Create from Document</label>
            <button
              onClick={() => createExpenseMutation.mutate()}
              disabled={createExpenseMutation.isPending}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 disabled:opacity-50 transition-colors"
            >
              {createExpenseMutation.isPending ? 'Creating...' : 'Create Expense'}
            </button>
            {createExpenseMutation.isError && (
              <p className="mt-1 text-xs text-red-600">
                {(createExpenseMutation.error as Error).message || 'Failed to create expense'}
              </p>
            )}
            <button
              onClick={() => createIncomeMutation.mutate()}
              disabled={createIncomeMutation.isPending}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 disabled:opacity-50 transition-colors"
            >
              {createIncomeMutation.isPending ? 'Creating...' : 'Create Income'}
            </button>
            {createIncomeMutation.isError && (
              <p className="mt-1 text-xs text-red-600">
                {(createIncomeMutation.error as Error).message || 'Failed to create income'}
              </p>
            )}
          </div>
        )}

        {/* Approval */}
        {canEdit && doc.status === 'draft' && (
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">Approval</label>
            {user?.role === 'admin' ? (
              <div className="flex gap-2 mt-1">
                <button
                  onClick={() => {
                    // Admin self-approves: create a self-assigned approval, then resolve it
                    approvalMutation.mutate(user.id, {
                      onSuccess: (data) => {
                        const approvalId = data.data.id
                        adminApproveMutation.mutate({ approvalId, status: 'approved' })
                      },
                    })
                  }}
                  disabled={approvalMutation.isPending || adminApproveMutation.isPending}
                  className="flex-1 px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
                >
                  {approvalMutation.isPending || adminApproveMutation.isPending ? 'Approving...' : 'Approve'}
                </button>
              </div>
            ) : (
              <div className="flex gap-2 mt-1">
                <input
                  type="text"
                  value={approvalAssignee}
                  onChange={(e) => setApprovalAssignee(e.target.value)}
                  placeholder="Approver User ID"
                  className="flex-1 px-2 py-1 text-sm border rounded-md"
                />
                <button
                  onClick={() => {
                    if (approvalAssignee) approvalMutation.mutate(approvalAssignee)
                  }}
                  className="px-3 py-1 text-sm bg-yellow-500 text-white rounded-md hover:bg-yellow-600"
                >
                  Request
                </button>
              </div>
            )}
            {approvalMutation.isError && (
              <p className="mt-1 text-xs text-red-600">
                {(approvalMutation.error as Error).message || 'Failed'}
              </p>
            )}
          </div>
        )}

        {/* Versions */}
        {versions.length > 0 && (
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">Version History</label>
            <div className="mt-1 space-y-1">
              {versions.map((v) => (
                <div key={v.id} className="text-sm text-gray-700 flex items-center justify-between">
                  <span>v{v.version_number} - {formatFileSize(v.file_size)}</span>
                  <span className="text-xs text-gray-400">{formatDate(v.created_at)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
