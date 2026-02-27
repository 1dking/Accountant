import { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { Camera, ImagePlus, RotateCcw, Upload, CheckCircle2, AlertTriangle, FileText, Receipt, Loader2 } from 'lucide-react'
import { quickCapture, type QuickCaptureResult } from '@/api/documents'

type CaptureState = 'idle' | 'preview' | 'processing' | 'result' | 'error'

export default function CapturePage() {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const galleryInputRef = useRef<HTMLInputElement>(null)

  const [state, setState] = useState<CaptureState>('idle')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [result, setResult] = useState<QuickCaptureResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setSelectedFile(file)
    setPreviewUrl(URL.createObjectURL(file))
    setState('preview')

    // Reset input so same file can be re-selected
    e.target.value = ''
  }, [])

  const handleSubmit = useCallback(async () => {
    if (!selectedFile) return

    setState('processing')
    setError(null)

    try {
      const response = await quickCapture(selectedFile)
      setResult(response.data)
      setState('result')
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Upload failed. Please try again.'
      setError(message)
      setState('error')
    }
  }, [selectedFile])

  const handleReset = useCallback(() => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setSelectedFile(null)
    setPreviewUrl(null)
    setResult(null)
    setError(null)
    setState('idle')
  }, [previewUrl])

  const formatCurrency = (amount: number | null) => {
    if (amount === null) return '--'
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount)
  }

  return (
    <div className="flex flex-col items-center min-h-full px-4 py-6">
      {/* Header */}
      <div className="w-full max-w-md mb-6">
        <h1 className="text-xl font-bold text-gray-900">Capture Receipt</h1>
        <p className="text-sm text-gray-500 mt-1">
          Take a photo or choose from gallery
        </p>
      </div>

      {/* IDLE state -- camera + gallery buttons */}
      {state === 'idle' && (
        <div className="w-full max-w-md flex flex-col items-center gap-4 mt-8">
          {/* Hidden file inputs */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={handleFileSelect}
          />
          <input
            ref={galleryInputRef}
            type="file"
            accept="image/*,application/pdf"
            className="hidden"
            onChange={handleFileSelect}
          />

          {/* Camera button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="w-full max-w-xs aspect-square rounded-2xl border-2 border-dashed border-blue-300 bg-blue-50/50 flex flex-col items-center justify-center gap-4 hover:bg-blue-50 active:bg-blue-100 transition-colors"
          >
            <div className="h-20 w-20 rounded-full bg-blue-600 flex items-center justify-center shadow-lg">
              <Camera className="h-10 w-10 text-white" />
            </div>
            <span className="text-blue-700 font-semibold text-lg">Take Photo</span>
            <span className="text-blue-500 text-sm">Uses rear camera</span>
          </button>

          {/* Gallery button */}
          <button
            onClick={() => galleryInputRef.current?.click()}
            className="w-full max-w-xs py-4 rounded-xl border border-gray-200 bg-white flex items-center justify-center gap-3 hover:bg-gray-50 active:bg-gray-100 transition-colors"
          >
            <ImagePlus className="h-5 w-5 text-gray-600" />
            <span className="text-gray-700 font-medium">Choose from Gallery</span>
          </button>
        </div>
      )}

      {/* PREVIEW state -- image preview + submit/retake */}
      {state === 'preview' && previewUrl && (
        <div className="w-full max-w-md flex flex-col items-center gap-4">
          <div className="w-full rounded-xl overflow-hidden border border-gray-200 bg-gray-100">
            <img
              src={previewUrl}
              alt="Receipt preview"
              className="w-full max-h-[60vh] object-contain"
            />
          </div>

          <div className="w-full flex gap-3">
            <button
              onClick={handleReset}
              className="flex-1 py-3 rounded-xl border border-gray-200 bg-white flex items-center justify-center gap-2 text-gray-700 font-medium hover:bg-gray-50 active:bg-gray-100 transition-colors"
            >
              <RotateCcw className="h-5 w-5" />
              Retake
            </button>
            <button
              onClick={handleSubmit}
              className="flex-1 py-3 rounded-xl bg-blue-600 flex items-center justify-center gap-2 text-white font-medium hover:bg-blue-700 active:bg-blue-800 transition-colors"
            >
              <Upload className="h-5 w-5" />
              Submit
            </button>
          </div>
        </div>
      )}

      {/* PROCESSING state -- spinner */}
      {state === 'processing' && (
        <div className="w-full max-w-md flex flex-col items-center gap-6 mt-12">
          <Loader2 className="h-16 w-16 text-blue-600 animate-spin" />
          <div className="text-center">
            <p className="text-lg font-semibold text-gray-900">Uploading & Analyzing</p>
            <p className="text-sm text-gray-500 mt-1">
              Extracting receipt data with AI...
            </p>
          </div>
          {previewUrl && (
            <div className="w-32 h-32 rounded-lg overflow-hidden border border-gray-200 opacity-60">
              <img src={previewUrl} alt="" className="w-full h-full object-cover" />
            </div>
          )}
        </div>
      )}

      {/* RESULT state -- success with extracted data */}
      {state === 'result' && result && (
        <div className="w-full max-w-md flex flex-col gap-4">
          {/* Success header */}
          <div className="flex items-center gap-3 p-4 rounded-xl bg-green-50 border border-green-200">
            <CheckCircle2 className="h-8 w-8 text-green-600 shrink-0" />
            <div>
              <p className="font-semibold text-green-900">Receipt Captured</p>
              <p className="text-sm text-green-700">
                Processed in {(result.processing_time_ms / 1000).toFixed(1)}s
              </p>
            </div>
          </div>

          {/* Extracted data */}
          {result.extraction ? (
            <div className="rounded-xl border border-gray-200 bg-white divide-y divide-gray-100">
              {result.expense_vendor && (
                <div className="flex justify-between items-center px-4 py-3">
                  <span className="text-sm text-gray-500">Vendor</span>
                  <span className="text-sm font-medium text-gray-900">{result.expense_vendor}</span>
                </div>
              )}
              {result.expense_amount !== null && (
                <div className="flex justify-between items-center px-4 py-3">
                  <span className="text-sm text-gray-500">Amount</span>
                  <span className="text-lg font-bold text-gray-900">{formatCurrency(result.expense_amount)}</span>
                </div>
              )}
              {result.expense_date && (
                <div className="flex justify-between items-center px-4 py-3">
                  <span className="text-sm text-gray-500">Date</span>
                  <span className="text-sm font-medium text-gray-900">{result.expense_date}</span>
                </div>
              )}
              <div className="flex justify-between items-center px-4 py-3">
                <span className="text-sm text-gray-500">Document</span>
                <span className="text-sm font-medium text-gray-900 truncate ml-4">{result.document_title}</span>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 p-4 rounded-xl bg-yellow-50 border border-yellow-200">
              <AlertTriangle className="h-6 w-6 text-yellow-600 shrink-0" />
              <div>
                <p className="font-medium text-yellow-900">Could not extract data</p>
                <p className="text-sm text-yellow-700">The receipt was saved but AI extraction failed. You can add details manually.</p>
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex flex-col gap-2 mt-2">
            {result.expense_id && (
              <button
                onClick={() => navigate(`/expenses/${result.expense_id}`)}
                className="w-full py-3 rounded-xl bg-blue-600 flex items-center justify-center gap-2 text-white font-medium hover:bg-blue-700 transition-colors"
              >
                <Receipt className="h-5 w-5" />
                View Expense
              </button>
            )}
            <button
              onClick={() => navigate(`/documents/${result.document_id}`)}
              className="w-full py-3 rounded-xl border border-gray-200 bg-white flex items-center justify-center gap-2 text-gray-700 font-medium hover:bg-gray-50 transition-colors"
            >
              <FileText className="h-5 w-5" />
              View Document
            </button>
            <button
              onClick={handleReset}
              className="w-full py-3 rounded-xl border border-gray-200 bg-white flex items-center justify-center gap-2 text-gray-700 font-medium hover:bg-gray-50 transition-colors"
            >
              <Camera className="h-5 w-5" />
              Capture Another
            </button>
          </div>
        </div>
      )}

      {/* ERROR state */}
      {state === 'error' && (
        <div className="w-full max-w-md flex flex-col items-center gap-4 mt-8">
          <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 border border-red-200 w-full">
            <AlertTriangle className="h-8 w-8 text-red-600 shrink-0" />
            <div>
              <p className="font-semibold text-red-900">Upload Failed</p>
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </div>

          <div className="w-full flex gap-3">
            <button
              onClick={handleReset}
              className="flex-1 py-3 rounded-xl border border-gray-200 bg-white flex items-center justify-center gap-2 text-gray-700 font-medium hover:bg-gray-50 transition-colors"
            >
              <RotateCcw className="h-5 w-5" />
              Start Over
            </button>
            <button
              onClick={handleSubmit}
              className="flex-1 py-3 rounded-xl bg-blue-600 flex items-center justify-center gap-2 text-white font-medium hover:bg-blue-700 transition-colors"
            >
              <Upload className="h-5 w-5" />
              Retry
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
