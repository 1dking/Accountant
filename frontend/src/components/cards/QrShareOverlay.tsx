import { useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { X, Copy, Nfc, Loader2, Check } from 'lucide-react'
import { toast } from 'sonner'

// Web NFC ships only in Chrome on Android — no iOS/desktop support — so the
// whole NFC affordance is a progressive enhancement behind this check. On
// unsupported browsers the overlay renders exactly as before (QR + copy).
interface NdefRecordInit {
  recordType: string
  data: string
}
interface NdefReaderLike {
  write: (message: { records: NdefRecordInit[] }) => Promise<void>
}
declare global {
  interface Window {
    NDEFReader?: new () => NdefReaderLike
  }
}

type NfcState = 'idle' | 'writing' | 'done'

/** Full-screen QR share overlay (UX port of Arivio card-client.tsx),
 * with self-serve NFC tag writing where the browser supports it. */
export default function QrShareOverlay({
  url,
  displayName,
  onClose,
}: {
  url: string
  displayName: string
  onClose: () => void
}) {
  const [nfcState, setNfcState] = useState<NfcState>('idle')
  const nfcSupported = typeof window !== 'undefined' && 'NDEFReader' in window

  async function writeNfcTag() {
    if (!window.NDEFReader) return
    setNfcState('writing')
    try {
      const writer = new window.NDEFReader()
      // Just the URL (with src attribution) — a tag holding a URL never goes
      // stale, always resolves to the live card; NTAG213's ~144 bytes also
      // can't reliably fit a full vCard.
      const nfcUrl = `${url}${url.includes('?') ? '&' : '?'}src=nfc`
      await writer.write({ records: [{ recordType: 'url', data: nfcUrl }] })
      setNfcState('done')
      toast.success('Tag written — tap it with any phone to test')
    } catch (err) {
      setNfcState('idle')
      toast.error(
        err instanceof Error && err.name === 'NotAllowedError'
          ? 'NFC permission was denied'
          : 'Could not write the tag — hold it against the back of your phone and try again'
      )
    }
  }

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
        <div className="mt-4 flex flex-col items-center gap-2">
          <button
            onClick={() => {
              navigator.clipboard?.writeText(url)
              toast.success('Link copied')
            }}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium border rounded-lg text-gray-700 hover:bg-gray-50"
          >
            <Copy className="w-3.5 h-3.5" /> Copy link
          </button>
          {nfcSupported && (
            <>
              <button
                onClick={writeNfcTag}
                disabled={nfcState === 'writing'}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium border rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-60"
              >
                {nfcState === 'writing' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : nfcState === 'done' ? (
                  <Check className="w-3.5 h-3.5 text-green-600" />
                ) : (
                  <Nfc className="w-3.5 h-3.5" />
                )}
                {nfcState === 'writing' ? 'Hold a blank tag near your phone…' : 'Write to NFC tag'}
              </button>
              {nfcState === 'idle' && (
                <p className="text-[11px] text-gray-400 max-w-[220px]">
                  Works with any blank NFC tag or card — tapping it opens this card.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
