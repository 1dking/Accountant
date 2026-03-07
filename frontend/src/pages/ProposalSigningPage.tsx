import { useState, useRef, useCallback, useEffect } from 'react'
import { useParams } from 'react-router'
import { useQuery, useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import DOMPurify from 'dompurify'
import { getSigningData, signProposal } from '@/api/proposals'
import type { SigningPageData } from '@/api/proposals'
import {
  Loader2,
  AlertCircle,
  CheckCircle,
  Pen,
  Type,
  Undo2,
  Eraser,
  FileText,
  X,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ContentBlock {
  id: string
  type: 'text' | 'image' | 'video' | 'pricing_table' | 'custom_value' | 'signature' | 'page_break'
  data: Record<string, any>
  order: number
}

interface Stroke {
  points: { x: number; y: number }[]
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const formatCurrency = (amount: number | string, currency = 'USD') =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(
    typeof amount === 'string' ? parseFloat(amount) : amount
  )

function parseBlocks(json: string): ContentBlock[] {
  try {
    const parsed = JSON.parse(json)
    const blocks: ContentBlock[] = Array.isArray(parsed) ? parsed : []
    return blocks.sort((a, b) => a.order - b.order)
  } catch {
    return []
  }
}

// ---------------------------------------------------------------------------
// Content block renderers
// ---------------------------------------------------------------------------

function TextBlock({ data }: { data: Record<string, any> }) {
  return (
    <div
      className="prose prose-sm sm:prose dark:prose-invert max-w-none"
      dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(data.html || data.content || '') }}
    />
  )
}

function ImageBlock({ data }: { data: Record<string, any> }) {
  return (
    <div className="flex justify-center">
      <img
        src={data.url || data.src}
        alt={data.alt || 'Proposal image'}
        className="max-w-full rounded-lg"
        style={{ maxHeight: data.max_height || 480 }}
      />
    </div>
  )
}

function VideoBlock({ data }: { data: Record<string, any> }) {
  const src = data.url || data.src || ''
  // Support YouTube / Vimeo embeds and raw video URLs
  const isEmbed = src.includes('youtube') || src.includes('vimeo') || src.includes('embed')
  if (isEmbed) {
    return (
      <div className="relative w-full" style={{ paddingBottom: '56.25%' }}>
        <iframe
          src={src}
          title={data.title || 'Video'}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          className="absolute inset-0 w-full h-full rounded-lg"
        />
      </div>
    )
  }
  return (
    <video
      src={src}
      controls
      className="w-full rounded-lg"
      style={{ maxHeight: 480 }}
    />
  )
}

function PricingTableBlock({ data, currency }: { data: Record<string, any>; currency: string }) {
  const items: any[] = data.items || data.rows || []
  const subtotal = items.reduce(
    (sum: number, item: any) => sum + (item.quantity ?? 1) * (item.unit_price ?? item.price ?? 0),
    0
  )
  const discount = data.discount ?? 0
  const tax = data.tax ?? 0
  const total = data.total ?? subtotal - discount + tax

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700">
            <th className="text-left py-3 px-2 font-medium text-gray-500 dark:text-gray-400">Item</th>
            <th className="text-right py-3 px-2 font-medium text-gray-500 dark:text-gray-400">Qty</th>
            <th className="text-right py-3 px-2 font-medium text-gray-500 dark:text-gray-400">Price</th>
            <th className="text-right py-3 px-2 font-medium text-gray-500 dark:text-gray-400">Total</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item: any, i: number) => {
            const qty = item.quantity ?? 1
            const price = item.unit_price ?? item.price ?? 0
            return (
              <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
                <td className="py-3 px-2 text-gray-900 dark:text-gray-100">
                  <div>{item.name || item.description}</div>
                  {item.description && item.name && (
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{item.description}</div>
                  )}
                </td>
                <td className="py-3 px-2 text-right text-gray-700 dark:text-gray-300">{qty}</td>
                <td className="py-3 px-2 text-right text-gray-700 dark:text-gray-300">
                  {formatCurrency(price, currency)}
                </td>
                <td className="py-3 px-2 text-right font-medium text-gray-900 dark:text-gray-100">
                  {formatCurrency(qty * price, currency)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div className="flex flex-col items-end gap-1 mt-3">
        <div className="flex justify-between w-48">
          <span className="text-sm text-gray-500 dark:text-gray-400">Subtotal</span>
          <span className="text-sm text-gray-900 dark:text-gray-100">{formatCurrency(subtotal, currency)}</span>
        </div>
        {discount > 0 && (
          <div className="flex justify-between w-48">
            <span className="text-sm text-gray-500 dark:text-gray-400">Discount</span>
            <span className="text-sm text-red-600">-{formatCurrency(discount, currency)}</span>
          </div>
        )}
        {tax > 0 && (
          <div className="flex justify-between w-48">
            <span className="text-sm text-gray-500 dark:text-gray-400">Tax</span>
            <span className="text-sm text-gray-900 dark:text-gray-100">{formatCurrency(tax, currency)}</span>
          </div>
        )}
        <div className="flex justify-between w-48 pt-2 border-t border-gray-300 dark:border-gray-600 mt-1">
          <span className="text-sm font-bold text-gray-900 dark:text-gray-100">Total</span>
          <span className="text-sm font-bold text-gray-900 dark:text-gray-100">{formatCurrency(total, currency)}</span>
        </div>
      </div>
    </div>
  )
}

function CustomValueBlock({ data }: { data: Record<string, any> }) {
  return (
    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
      {data.label && (
        <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
          {data.label}
        </p>
      )}
      <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
        {data.value ?? data.resolved_value ?? '--'}
      </p>
    </div>
  )
}

function PageBreakBlock() {
  return <hr className="border-gray-200 dark:border-gray-700 my-2" />
}

// ---------------------------------------------------------------------------
// Signature block (read-only or interactive)
// ---------------------------------------------------------------------------

interface SignatureBlockProps {
  data: Record<string, any>
  recipientId: string
  alreadySigned: boolean
  onClickSign: () => void
}

function SignatureBlock({ data, recipientId, alreadySigned, onClickSign }: SignatureBlockProps) {
  const isForMe = data.recipient_id === recipientId
  const isSigned = !!data.signature_data || !!data.signed_at

  if (isSigned) {
    return (
      <div className="border border-green-200 dark:border-green-800 rounded-lg p-4 bg-green-50 dark:bg-green-900/20">
        <div className="flex items-center gap-2 mb-2">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <span className="text-sm font-medium text-green-700 dark:text-green-400">Signed</span>
        </div>
        {data.signature_data && (
          <img
            src={data.signature_data}
            alt="Signature"
            className="max-h-20 object-contain"
          />
        )}
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          {data.signer_name || data.name || 'Signer'} &mdash;{' '}
          {data.signed_at ? new Date(data.signed_at).toLocaleString() : ''}
        </p>
      </div>
    )
  }

  if (isForMe && !alreadySigned) {
    return (
      <button
        type="button"
        onClick={onClickSign}
        className="w-full border-2 border-dashed border-blue-300 dark:border-blue-600 rounded-lg p-6 flex flex-col items-center gap-2 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors cursor-pointer"
      >
        <Pen className="h-6 w-6 text-blue-500" />
        <span className="text-sm font-medium text-blue-600 dark:text-blue-400">
          Click here to sign
        </span>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {data.name || 'Your signature'}
        </span>
      </button>
    )
  }

  // Signature slot for another party or already signed
  return (
    <div className="border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-lg p-6 flex flex-col items-center gap-2">
      <Pen className="h-5 w-5 text-gray-300 dark:text-gray-600" />
      <span className="text-sm text-gray-400 dark:text-gray-500">
        {data.name || 'Signature'}{' '}
        {alreadySigned && isForMe ? '(signed)' : '(awaiting signature)'}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Signature capture modal
// ---------------------------------------------------------------------------

interface SignatureCaptureProps {
  signerName: string
  onSign: (signatureData: string, signatureType: 'drawn' | 'typed') => void
  onClose: () => void
}

function SignatureCapture({ signerName, onSign, onClose }: SignatureCaptureProps) {
  const [tab, setTab] = useState<'draw' | 'type'>('draw')
  const [typedName, setTypedName] = useState(signerName)

  // Canvas state
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [isDrawing, setIsDrawing] = useState(false)
  const [strokes, setStrokes] = useState<Stroke[]>([])
  const currentStroke = useRef<{ x: number; y: number }[]>([])

  // Initialize canvas
  useEffect(() => {
    const canvas = canvasRef.current
    const container = containerRef.current
    if (!canvas || !container) return
    const rect = container.getBoundingClientRect()
    const dpr = window.devicePixelRatio || 1
    canvas.width = rect.width * dpr
    canvas.height = 200 * dpr
    canvas.style.width = `${rect.width}px`
    canvas.style.height = '200px'
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.scale(dpr, dpr)
    ctx.strokeStyle = '#1a1a1a'
    ctx.lineWidth = 2.5
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
  }, [tab])

  // Redraw all strokes
  const redraw = useCallback(
    (strokeList: Stroke[]) => {
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      const dpr = window.devicePixelRatio || 1
      ctx.clearRect(0, 0, canvas.width / dpr, canvas.height / dpr)
      ctx.strokeStyle = '#1a1a1a'
      ctx.lineWidth = 2.5
      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'
      for (const stroke of strokeList) {
        if (stroke.points.length < 2) continue
        ctx.beginPath()
        ctx.moveTo(stroke.points[0].x, stroke.points[0].y)
        for (let i = 1; i < stroke.points.length; i++) {
          ctx.lineTo(stroke.points[i].x, stroke.points[i].y)
        }
        ctx.stroke()
      }
    },
    []
  )

  const getPos = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    const canvas = canvasRef.current
    if (!canvas) return { x: 0, y: 0 }
    const rect = canvas.getBoundingClientRect()
    if ('touches' in e) {
      const touch = e.touches[0]
      return { x: touch.clientX - rect.left, y: touch.clientY - rect.top }
    }
    return {
      x: (e as React.MouseEvent).clientX - rect.left,
      y: (e as React.MouseEvent).clientY - rect.top,
    }
  }, [])

  const startDrawing = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      e.preventDefault()
      const pos = getPos(e)
      currentStroke.current = [pos]
      setIsDrawing(true)
      const ctx = canvasRef.current?.getContext('2d')
      if (ctx) {
        ctx.beginPath()
        ctx.moveTo(pos.x, pos.y)
      }
    },
    [getPos]
  )

  const draw = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      e.preventDefault()
      if (!isDrawing) return
      const pos = getPos(e)
      currentStroke.current.push(pos)
      const ctx = canvasRef.current?.getContext('2d')
      if (ctx) {
        ctx.lineTo(pos.x, pos.y)
        ctx.stroke()
      }
    },
    [isDrawing, getPos]
  )

  const endDrawing = useCallback(() => {
    if (!isDrawing) return
    setIsDrawing(false)
    if (currentStroke.current.length > 1) {
      setStrokes((prev) => [...prev, { points: [...currentStroke.current] }])
    }
    currentStroke.current = []
  }, [isDrawing])

  const undoLastStroke = useCallback(() => {
    setStrokes((prev) => {
      const next = prev.slice(0, -1)
      redraw(next)
      return next
    })
  }, [redraw])

  const clearCanvas = useCallback(() => {
    setStrokes([])
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const dpr = window.devicePixelRatio || 1
    ctx.clearRect(0, 0, canvas.width / dpr, canvas.height / dpr)
  }, [])

  const hasDrawnSignature = strokes.length > 0
  const hasTypedSignature = typedName.trim().length > 0

  const handleSign = () => {
    if (tab === 'draw') {
      const canvas = canvasRef.current
      if (!canvas || !hasDrawnSignature) return
      const dataUrl = canvas.toDataURL('image/png')
      onSign(dataUrl, 'drawn')
    } else {
      if (!hasTypedSignature) return
      onSign(typedName.trim(), 'typed')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50 backdrop-blur-sm p-0 sm:p-4">
      <div className="bg-white dark:bg-gray-900 w-full sm:max-w-lg sm:rounded-xl rounded-t-xl shadow-2xl max-h-[90vh] overflow-y-auto">
        {/* Modal header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Add Your Signature
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-6 py-4 space-y-4">
          {/* Tabs */}
          <div className="flex bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
            <button
              type="button"
              onClick={() => setTab('draw')}
              className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-md transition-colors ${
                tab === 'draw'
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700'
              }`}
            >
              <Pen className="h-4 w-4" />
              Draw
            </button>
            <button
              type="button"
              onClick={() => setTab('type')}
              className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-md transition-colors ${
                tab === 'type'
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700'
              }`}
            >
              <Type className="h-4 w-4" />
              Type
            </button>
          </div>

          {/* Draw tab */}
          {tab === 'draw' && (
            <div className="space-y-2">
              <div ref={containerRef} className="relative">
                <canvas
                  ref={canvasRef}
                  className="w-full border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-950 cursor-crosshair touch-none"
                  onMouseDown={startDrawing}
                  onMouseMove={draw}
                  onMouseUp={endDrawing}
                  onMouseLeave={endDrawing}
                  onTouchStart={startDrawing}
                  onTouchMove={draw}
                  onTouchEnd={endDrawing}
                />
                {!hasDrawnSignature && (
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <span className="text-gray-400 dark:text-gray-500 text-sm">
                      Draw your signature here
                    </span>
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={undoLastStroke}
                  disabled={!hasDrawnSignature}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 disabled:opacity-30 transition-colors"
                >
                  <Undo2 className="h-3.5 w-3.5" />
                  Undo
                </button>
                <button
                  type="button"
                  onClick={clearCanvas}
                  disabled={!hasDrawnSignature}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 disabled:opacity-30 transition-colors"
                >
                  <Eraser className="h-3.5 w-3.5" />
                  Clear
                </button>
              </div>
            </div>
          )}

          {/* Type tab */}
          {tab === 'type' && (
            <div className="space-y-3">
              <input
                type="text"
                value={typedName}
                onChange={(e) => setTypedName(e.target.value)}
                placeholder="Type your full name"
                autoFocus
                className="w-full px-4 py-3 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
              />
              {hasTypedSignature && (
                <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-6 bg-gray-50 dark:bg-gray-950 flex items-center justify-center min-h-[100px]">
                  <span
                    className="text-3xl text-gray-900 dark:text-gray-100"
                    style={{
                      fontFamily: "'Segoe Script', 'Dancing Script', 'Brush Script MT', 'Apple Chancery', cursive",
                    }}
                  >
                    {typedName}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Signer info */}
          <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 rounded-lg px-4 py-3">
            <FileText className="h-4 w-4 shrink-0" />
            <div>
              <p>Signing as <span className="font-medium text-gray-700 dark:text-gray-300">{signerName}</span></p>
              <p>{new Date().toLocaleString()}</p>
            </div>
          </div>

          {/* Sign button */}
          <button
            type="button"
            onClick={handleSign}
            disabled={tab === 'draw' ? !hasDrawnSignature : !hasTypedSignature}
            className="w-full py-3 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Sign
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Confirmation dialog
// ---------------------------------------------------------------------------

interface ConfirmDialogProps {
  isPending: boolean
  onConfirm: () => void
  onCancel: () => void
}

function ConfirmDialog({ isPending, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl max-w-md w-full p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">
          Confirm Your Signature
        </h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-6 leading-relaxed">
          By signing, you agree to the terms of this proposal. Your signature,
          IP address, and timestamp will be recorded for verification purposes.
        </p>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isPending}
            className="flex-1 py-2.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPending}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Signing...
              </>
            ) : (
              'Confirm & Sign'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function ProposalSigningPage() {
  const { token } = useParams<{ token: string }>()

  // UI state
  const [showSignatureCapture, setShowSignatureCapture] = useState(false)
  const [pendingSignature, setPendingSignature] = useState<{
    data: string
    type: 'drawn' | 'typed'
  } | null>(null)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [signed, setSigned] = useState(false)

  // Fetch signing data
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['proposal-signing', token],
    queryFn: () => getSigningData(token!),
    enabled: !!token,
  })

  // Sign mutation
  const signMutation = useMutation({
    mutationFn: () => {
      if (!pendingSignature || !signingData) throw new Error('Missing signature data')
      return signProposal(token!, {
        recipient_id: signingData.recipient_id,
        signature_data: pendingSignature.data,
        signature_type: pendingSignature.type,
      })
    },
    onSuccess: (response) => {
      setShowConfirmDialog(false)
      setPendingSignature(null)
      setSigned(true)
      toast.success('Proposal signed successfully!')
      refetch()

      const result = response.data
      if (result.redirect_to_payment && result.proposal_id) {
        // Give user a moment to see the success message, then redirect
        setTimeout(() => {
          window.location.href = `/proposals/${result.proposal_id}/payment`
        }, 2000)
      }
    },
    onError: () => {
      toast.error('Failed to sign the proposal. Please try again.')
      setShowConfirmDialog(false)
    },
  })

  const signingData: SigningPageData | undefined = data?.data

  // Handlers
  const handleSignatureCapture = (signatureData: string, signatureType: 'drawn' | 'typed') => {
    setPendingSignature({ data: signatureData, type: signatureType })
    setShowSignatureCapture(false)
    setShowConfirmDialog(true)
  }

  const handleConfirmSign = () => {
    signMutation.mutate()
  }

  const handleCancelConfirm = () => {
    setShowConfirmDialog(false)
    setPendingSignature(null)
  }

  // ---------------------------------------------------------------------------
  // Loading state
  // ---------------------------------------------------------------------------
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 text-blue-500 animate-spin" />
          <p className="text-sm text-gray-500 dark:text-gray-400">Loading proposal...</p>
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Error state
  // ---------------------------------------------------------------------------
  if (error || !signingData) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center p-4">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-400 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
            Invalid or expired link
          </h1>
          <p className="text-gray-500 dark:text-gray-400 max-w-sm">
            This signing link may have expired or is no longer valid. Please
            contact the sender to request a new link.
          </p>
        </div>
      </div>
    )
  }

  const blocks = parseBlocks(signingData.content_json)
  const alreadySigned = signingData.already_signed || signed

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-950">
      {/* Header */}
      <header className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="min-w-0">
            {signingData.company_name && (
              <p className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
                {signingData.company_name}
              </p>
            )}
            <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
              {signingData.proposal_title}
            </p>
          </div>
          {alreadySigned && (
            <span className="shrink-0 flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/30 rounded-full">
              <CheckCircle className="h-3.5 w-3.5" />
              Signed
            </span>
          )}
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {/* Already signed banner */}
        {alreadySigned && (
          <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl p-4 sm:p-5 mb-6 flex items-start gap-3">
            <CheckCircle className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-green-800 dark:text-green-300">
                You have already signed this document
              </p>
              <p className="text-xs text-green-600 dark:text-green-400 mt-1">
                Your signature has been recorded. You can still review the document below.
              </p>
            </div>
          </div>
        )}

        {/* All signed banner */}
        {signingData.all_signed && (
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4 sm:p-5 mb-6 flex items-start gap-3">
            <CheckCircle className="h-5 w-5 text-blue-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-blue-800 dark:text-blue-300">
                All parties have signed this document
              </p>
              <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                This proposal has been fully executed by all required signers.
              </p>
            </div>
          </div>
        )}

        {/* Recipient info */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 sm:p-5 mb-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                {signingData.recipient_name}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {signingData.recipient_email}
                {signingData.recipient_role && (
                  <> &middot; <span className="capitalize">{signingData.recipient_role}</span></>
                )}
              </p>
            </div>
            {signingData.value && (
              <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {formatCurrency(signingData.value, signingData.currency)}
              </p>
            )}
          </div>
        </div>

        {/* Document content */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
          <div className="px-4 sm:px-8 py-6 sm:py-8 space-y-6">
            {blocks.map((block) => (
              <div key={block.id}>
                {block.type === 'text' && <TextBlock data={block.data} />}
                {block.type === 'image' && <ImageBlock data={block.data} />}
                {block.type === 'video' && <VideoBlock data={block.data} />}
                {block.type === 'pricing_table' && (
                  <PricingTableBlock data={block.data} currency={signingData.currency} />
                )}
                {block.type === 'custom_value' && <CustomValueBlock data={block.data} />}
                {block.type === 'signature' && (
                  <SignatureBlock
                    data={block.data}
                    recipientId={signingData.recipient_id}
                    alreadySigned={alreadySigned}
                    onClickSign={() => setShowSignatureCapture(true)}
                  />
                )}
                {block.type === 'page_break' && <PageBreakBlock />}
              </div>
            ))}

            {blocks.length === 0 && (
              <div className="text-center py-12">
                <FileText className="h-10 w-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  No content available for this proposal.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-8 mb-4">
          <p className="text-xs text-gray-400 dark:text-gray-500">
            {signingData.company_name && <>{signingData.company_name} &middot; </>}
            Powered by Accountant
          </p>
        </div>
      </main>

      {/* Signature capture modal */}
      {showSignatureCapture && (
        <SignatureCapture
          signerName={signingData.recipient_name}
          onSign={handleSignatureCapture}
          onClose={() => setShowSignatureCapture(false)}
        />
      )}

      {/* Confirmation dialog */}
      {showConfirmDialog && (
        <ConfirmDialog
          isPending={signMutation.isPending}
          onConfirm={handleConfirmSign}
          onCancel={handleCancelConfirm}
        />
      )}
    </div>
  )
}
