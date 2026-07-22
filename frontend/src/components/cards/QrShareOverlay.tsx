import { QRCodeSVG } from 'qrcode.react'
import { X, Copy } from 'lucide-react'
import { toast } from 'sonner'

/** Full-screen QR share overlay (UX port of Arivio card-client.tsx). */
export default function QrShareOverlay({
  url,
  displayName,
  onClose,
}: {
  url: string
  displayName: string
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative bg-white rounded-2xl p-6 mx-4 text-center shadow-xl">
        <button
          onClick={onClose}
          className="absolute top-3 right-3 p-1.5 rounded-lg text-gray-400 hover:bg-gray-100"
        >
          <X className="w-4 h-4" />
        </button>
        <p className="text-sm font-semibold text-gray-900 mb-4">{displayName}</p>
        <div className="bg-white p-2 rounded-lg border w-fit mx-auto">
          <QRCodeSVG value={url} size={200} />
        </div>
        <p className="mt-3 text-xs text-gray-500 max-w-[220px] mx-auto break-all">{url}</p>
        <button
          onClick={() => {
            navigator.clipboard?.writeText(url)
            toast.success('Link copied')
          }}
          className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium border rounded-lg text-gray-700 hover:bg-gray-50"
        >
          <Copy className="w-3.5 h-3.5" /> Copy link
        </button>
      </div>
    </div>
  )
}
