import { useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

/**
 * Scaled-down live render of a block's HTML — the same Tailwind CDN the
 * editor iframe, the Preview tab and compile_page() load, so the
 * thumbnail is what the block actually looks like. Fills its container's
 * width (measured with a ResizeObserver) at a fixed 1200px "design width".
 *
 * Shared by the Visual tab's Section Library and the classic
 * VariantPickerModal (block model v2: both read GET /api/pages/variants
 * and render `preview_html`). Rendered screenshots (S3) replace this for
 * the gallery views; it stays as the zero-infrastructure fallback.
 */
interface Props {
  html: string
  /** Aspect ratio of the thumbnail box, width / height. Default 2. */
  ratio?: number
  className?: string
  /** Fixed width in px; when omitted the thumb fills its container. */
  width?: number
}

const DOC_WIDTH = 1200

export default function SectionThumb({ html, ratio = 2, className = '', width }: Props) {
  const { t } = useTranslation('ui')
  const boxRef = useRef<HTMLDivElement>(null)
  const [measured, setMeasured] = useState(width ?? 0)

  useLayoutEffect(() => {
    if (width) { setMeasured(width); return }
    const el = boxRef.current
    if (!el) return
    const update = () => setMeasured(el.clientWidth)
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [width])

  const scale = measured > 0 ? measured / DOC_WIDTH : 0
  const height = measured > 0 ? Math.round(measured / ratio) : 0
  const docHeight = scale > 0 ? Math.round(height / scale) : 0
  const srcDoc = `<!DOCTYPE html><html><head><script src="https://cdn.tailwindcss.com"></script><style>html,body{margin:0;background:#fff;overflow:hidden}</style></head><body>${html}</body></html>`

  return (
    <div
      ref={boxRef}
      style={{ width: width ? `${width}px` : '100%', height: height || undefined, aspectRatio: height ? undefined : String(ratio) }}
      className={`relative overflow-hidden bg-white ${className}`}
    >
      {scale > 0 && (
        <iframe
          srcDoc={srcDoc}
          title={t('ui:VisualEditor.sectionPreview')}
          scrolling="no"
          tabIndex={-1}
          loading="lazy"
          sandbox="allow-scripts"
          style={{ width: DOC_WIDTH, height: docHeight, border: 'none', transform: `scale(${scale})`, transformOrigin: 'top left', pointerEvents: 'none' }}
        />
      )}
    </div>
  )
}
