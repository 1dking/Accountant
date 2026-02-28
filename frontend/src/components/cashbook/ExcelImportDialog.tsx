import { useState, useRef, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import { importExcelPreview, importExcelConfirm } from '@/api/cashbook'
import { Upload } from 'lucide-react'
import type { PaymentAccount, ImportPreview } from '@/types/models'

interface ExcelImportDialogProps {
  isOpen: boolean
  onClose: () => void
  accounts: PaymentAccount[]
  onImported: () => void
}

export default function ExcelImportDialog({
  isOpen,
  onClose,
  accounts,
  onImported,
}: ExcelImportDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [accountId, setAccountId] = useState(
    accounts.length > 0 ? accounts[0].id : ''
  )
  const [isDragging, setIsDragging] = useState(false)

  // Preview mutation
  const previewMutation = useMutation({
    mutationFn: (file: File) => importExcelPreview(file),
    onSuccess: (data) => {
      setPreview(data.data)
    },
  })

  // Confirm mutation
  const confirmMutation = useMutation({
    mutationFn: () => {
      if (!preview) throw new Error('No preview data')
      return importExcelConfirm({
        account_id: accountId,
        rows: preview.rows.filter((r) => r.errors.length === 0),
      })
    },
    onSuccess: () => {
      onImported()
      handleClose()
    },
  })

  const handleClose = () => {
    setSelectedFile(null)
    setPreview(null)
    setAccountId(accounts.length > 0 ? accounts[0].id : '')
    setIsDragging(false)
    onClose()
  }

  const handleFile = useCallback(
    (file: File) => {
      const validTypes = [
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
      ]
      if (
        !validTypes.includes(file.type) &&
        !file.name.endsWith('.xlsx') &&
        !file.name.endsWith('.xls')
      ) {
        return
      }
      setSelectedFile(file)
      previewMutation.mutate(file)
    },
    [previewMutation]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [handleFile]
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  if (!isOpen) return null

  const validRows = preview?.valid_rows ?? 0
  const errorRows = preview?.error_rows ?? 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={handleClose}
      />

      {/* Dialog */}
      <div className="relative bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[85vh] flex flex-col mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">
            Import Excel File
          </h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* Account Selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Import into Account
            </label>
            <select
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="w-full px-3 py-2 text-sm border rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>

          {/* Drop Zone */}
          {!preview && (
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                isDragging
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <Upload className="h-10 w-10 text-gray-400 mx-auto mb-3" />
              <p className="text-sm font-medium text-gray-700">
                {selectedFile
                  ? selectedFile.name
                  : 'Drop your Excel file here or click to browse'}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Accepts .xlsx and .xls files
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls"
                onChange={handleFileChange}
                className="hidden"
              />
            </div>
          )}

          {/* Loading */}
          {previewMutation.isPending && (
            <div className="text-center py-8">
              <div className="animate-spin h-8 w-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-3" />
              <p className="text-sm text-gray-500">Processing file...</p>
            </div>
          )}

          {/* Preview error */}
          {previewMutation.isError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-sm text-red-700">
                {(previewMutation.error as Error).message ||
                  'Failed to parse file'}
              </p>
              <button
                onClick={() => {
                  setSelectedFile(null)
                  setPreview(null)
                  previewMutation.reset()
                }}
                className="mt-2 text-sm text-red-600 underline"
              >
                Try another file
              </button>
            </div>
          )}

          {/* Preview Table */}
          {preview && (
            <>
              <div className="flex items-center gap-4 text-sm">
                <span className="text-gray-600">
                  Total rows:{' '}
                  <span className="font-medium">{preview.total_rows}</span>
                </span>
                <span className="text-green-600">
                  Valid:{' '}
                  <span className="font-medium">{validRows}</span>
                </span>
                {errorRows > 0 && (
                  <span className="text-red-600">
                    Errors:{' '}
                    <span className="font-medium">{errorRows}</span>
                  </span>
                )}
                {preview.sheets_found.length > 1 && (
                  <span className="text-gray-500">
                    Sheets: {preview.sheets_found.join(', ')}
                  </span>
                )}
              </div>

              <div className="border rounded-lg overflow-hidden overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="text-left px-3 py-2 text-xs font-medium text-gray-500 uppercase">
                        Row
                      </th>
                      <th className="text-left px-3 py-2 text-xs font-medium text-gray-500 uppercase">
                        Date
                      </th>
                      <th className="text-left px-3 py-2 text-xs font-medium text-gray-500 uppercase">
                        Description
                      </th>
                      <th className="text-left px-3 py-2 text-xs font-medium text-gray-500 uppercase">
                        Type
                      </th>
                      <th className="text-right px-3 py-2 text-xs font-medium text-gray-500 uppercase">
                        Amount
                      </th>
                      <th className="text-left px-3 py-2 text-xs font-medium text-gray-500 uppercase">
                        Category
                      </th>
                      <th className="text-right px-3 py-2 text-xs font-medium text-gray-500 uppercase">
                        Tax
                      </th>
                      <th className="text-left px-3 py-2 text-xs font-medium text-gray-500 uppercase">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {preview.rows.map((row) => {
                      const hasErrors = row.errors.length > 0
                      return (
                        <tr
                          key={`${row.sheet_name}-${row.row_number}`}
                          className={hasErrors ? 'bg-red-50' : ''}
                        >
                          <td className="px-3 py-2 text-gray-500">
                            {row.row_number}
                          </td>
                          <td className="px-3 py-2 text-gray-700">
                            {row.date || '-'}
                          </td>
                          <td className="px-3 py-2 text-gray-700 max-w-[200px] truncate">
                            {row.description}
                          </td>
                          <td className="px-3 py-2">
                            <span
                              className={`inline-block px-2 py-0.5 text-xs rounded-full ${
                                row.entry_type === 'income'
                                  ? 'bg-green-100 text-green-700'
                                  : 'bg-red-100 text-red-700'
                              }`}
                            >
                              {row.entry_type}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right font-medium">
                            $
                            {Math.abs(row.total_amount).toLocaleString(
                              'en-US',
                              {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              }
                            )}
                          </td>
                          <td className="px-3 py-2 text-gray-600">
                            {row.category_name || '-'}
                          </td>
                          <td className="px-3 py-2 text-right text-gray-600">
                            {row.tax_amount != null
                              ? `$${Math.abs(row.tax_amount).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                              : '-'}
                          </td>
                          <td className="px-3 py-2">
                            {hasErrors ? (
                              <span
                                className="text-xs text-red-600"
                                title={row.errors.join('; ')}
                              >
                                {row.errors.join('; ')}
                              </span>
                            ) : (
                              <span className="text-xs text-green-600">
                                OK
                              </span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {/* Confirm error */}
          {confirmMutation.isError && (
            <p className="text-sm text-red-600">
              {(confirmMutation.error as Error).message ||
                'Failed to import entries'}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
          >
            Close
          </button>
          {preview && validRows > 0 && (
            <button
              onClick={() => confirmMutation.mutate()}
              disabled={!accountId || confirmMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {confirmMutation.isPending
                ? 'Importing...'
                : `Confirm Import (${validRows} rows)`}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
