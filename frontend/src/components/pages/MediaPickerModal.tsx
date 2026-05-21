/**
 * MediaPickerModal — pick a source for a section's media slot.
 *
 * Triggered from the SectionEditor media slot pill. Submits to the
 * parent via onPick({ url }) which writes the result into
 * sections_json[idx].media_overrides[TOKEN] via PATCH /sections/{idx}.
 *
 * Tabs (Commit 3 trimmed):
 *   - Video: YouTube URL + direct mp4 URL inputs
 *   - Image: Upload from local file → R2 (POST /pages/media/upload)
 *   - Stock: empty state ("Add UNSPLASH_ACCESS_KEY to enable")
 *   - AI: empty state ("Coming after Imagen auth setup")
 */
import { useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  X, Image as ImageIcon, Film, Sparkles, Library, Upload, Loader2,
  ExternalLink, Check,
} from 'lucide-react'
import { pagesApi } from '@/api/pages'
import './section-editor.css'

export type MediaSlotKind = 'video' | 'image' | 'logo' | 'any'

interface Props {
  open: boolean
  tokenName: string
  /** What media types the slot accepts. Hides irrelevant tabs. */
  slotKind: MediaSlotKind
  currentValue: string | null | undefined
  onClose: () => void
  onPick: (newValue: string) => void
}

type Tab = 'video' | 'image' | 'stock' | 'ai'

export default function MediaPickerModal({
  open, tokenName, slotKind, currentValue, onClose, onPick,
}: Props) {
  // Default tab depends on slot kind. VIDEO_URL → video; IMAGE_URL → image.
  const initialTab: Tab = slotKind === 'video' ? 'video' : 'image'
  const [tab, setTab] = useState<Tab>(initialTab)
  const [videoUrl, setVideoUrl] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) {
      setTab(initialTab)
      setVideoUrl('')
      setImageUrl('')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const uploadMut = useMutation({
    mutationFn: (file: File) =>
      pagesApi.uploadMedia(file) as Promise<{ data: { url: string } }>,
    onSuccess: (resp) => {
      toast.success('Uploaded')
      onPick(resp.data.url)
    },
    onError: (e: any) => toast.error(`Upload failed: ${e?.message || 'unknown'}`),
  })

  const handleFile = (file: File | null) => {
    if (!file) return
    uploadMut.mutate(file)
  }

  const handleSaveVideo = () => {
    const v = videoUrl.trim()
    if (!v) return
    onPick(v)  // Server-side normalizes YouTube URLs
  }
  const handleSaveImage = () => {
    const v = imageUrl.trim()
    if (!v) return
    onPick(v)
  }

  if (!open) return null

  const showVideoTab = slotKind === 'video' || slotKind === 'any'
  const showImageTab = slotKind !== 'video'

  return (
    <div
      className="se-root fixed inset-0 z-[60] flex items-center justify-center p-4 se-picker-backdrop"
      onClick={onClose}
    >
      <div
        className="se-picker-surface w-full max-w-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <div>
            <h2 className="text-base font-semibold text-white/96">
              Choose media
            </h2>
            <p className="text-xs text-white/46 mt-0.5">
              Slot: <span className="font-mono">{tokenName}</span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-white/8 text-white/68 hover:text-white/96 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 px-4 pt-3 border-b border-white/10">
          {showVideoTab && (
            <TabButton active={tab === 'video'} onClick={() => setTab('video')}>
              <Film className="h-3.5 w-3.5" /> Video
            </TabButton>
          )}
          {showImageTab && (
            <TabButton active={tab === 'image'} onClick={() => setTab('image')}>
              <ImageIcon className="h-3.5 w-3.5" /> Image
            </TabButton>
          )}
          <TabButton active={tab === 'stock'} onClick={() => setTab('stock')}>
            <Library className="h-3.5 w-3.5" /> Stock
          </TabButton>
          <TabButton active={tab === 'ai'} onClick={() => setTab('ai')}>
            <Sparkles className="h-3.5 w-3.5" /> AI
          </TabButton>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {tab === 'video' && showVideoTab && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-white/86 mb-2">
                  YouTube or direct video URL
                </label>
                <textarea
                  value={videoUrl}
                  onChange={(e) => setVideoUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=... or https://example.com/video.mp4"
                  rows={3}
                  autoFocus
                  className="w-full px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white/96 placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                />
                <p className="text-xs text-white/46 mt-1.5">
                  YouTube watch / youtu.be / embed URLs are all accepted —
                  we normalize to a looping autoplay embed automatically.
                  Direct mp4 URLs work for self-hosted video.
                </p>
              </div>
              <div className="flex items-center justify-between">
                {currentValue && (
                  <a
                    href={currentValue}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-white/46 hover:text-white/86"
                  >
                    <ExternalLink className="h-3 w-3" /> Current
                  </a>
                )}
                <button
                  onClick={handleSaveVideo}
                  disabled={!videoUrl.trim()}
                  className="ml-auto inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-40"
                >
                  <Check className="h-3.5 w-3.5" /> Use this video
                </button>
              </div>
            </div>
          )}

          {tab === 'image' && showImageTab && (
            <div className="space-y-5">
              {/* Upload */}
              <div>
                <label className="block text-sm font-medium text-white/86 mb-2">
                  Upload from your computer
                </label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadMut.isPending}
                  className="w-full flex flex-col items-center justify-center gap-2 py-8 border-2 border-dashed border-white/15 rounded-lg text-white/68 hover:border-indigo-400/60 hover:bg-indigo-500/5 transition disabled:opacity-50"
                >
                  {uploadMut.isPending ? (
                    <><Loader2 className="h-6 w-6 animate-spin" /> <span className="text-sm">Uploading…</span></>
                  ) : (
                    <><Upload className="h-6 w-6" /> <span className="text-sm">Click to upload (max 25 MB)</span></>
                  )}
                </button>
                <p className="text-xs text-white/46 mt-1.5">
                  Uploads land in R2 and are referenced directly from the page.
                </p>
              </div>

              {/* Or paste a URL */}
              <div>
                <label className="block text-sm font-medium text-white/86 mb-2">
                  Or paste a direct image URL
                </label>
                <input
                  type="text"
                  value={imageUrl}
                  onChange={(e) => setImageUrl(e.target.value)}
                  placeholder="https://example.com/image.jpg"
                  className="w-full px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white/96 placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <div className="flex justify-end mt-2">
                  <button
                    onClick={handleSaveImage}
                    disabled={!imageUrl.trim()}
                    className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-40"
                  >
                    <Check className="h-3.5 w-3.5" /> Use this URL
                  </button>
                </div>
              </div>
            </div>
          )}

          {tab === 'stock' && (
            <EmptyState
              icon={<Library className="h-8 w-8" />}
              title="Stock images — coming soon"
              detail={
                <>
                  Add an <span className="font-mono">UNSPLASH_ACCESS_KEY</span>{' '}
                  to the VPS <span className="font-mono">.env</span> to enable
                  the Unsplash stock search here. Free tier is 50 requests/hour;
                  plenty for editing.
                </>
              }
            />
          )}

          {tab === 'ai' && (
            <EmptyState
              icon={<Sparkles className="h-8 w-8" />}
              title="AI-generated images — coming soon"
              detail={
                <>
                  Ships after Imagen auth is sorted. Either via a Gemini API
                  key with Imagen access, or via Vertex AI service auth.
                  Tracked for Commit 4.
                </>
              }
            />
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Local helpers
// ---------------------------------------------------------------------------

function TabButton({
  active, onClick, children,
}: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={
        'inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ' +
        (active
          ? 'border-indigo-400 text-white/96'
          : 'border-transparent text-white/46 hover:text-white/86')
      }
    >
      {children}
    </button>
  )
}

function EmptyState({
  icon, title, detail,
}: { icon: React.ReactNode; title: string; detail: React.ReactNode }) {
  return (
    <div className="text-center py-12">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-white/5 border border-white/10 text-white/46 mb-3">
        {icon}
      </div>
      <h3 className="text-base font-semibold text-white/86 mb-2">{title}</h3>
      <p className="text-xs text-white/46 max-w-md mx-auto leading-relaxed">
        {detail}
      </p>
    </div>
  )
}
