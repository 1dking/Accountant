import { useState, useRef, useEffect } from 'react'
import { streamOfficeAiAssist } from '@/api/office'
import { Sparkles, X, Loader2, Check, Copy } from 'lucide-react'

interface AiAssistPopoverProps {
  docId: string
  selectedText: string
  isOpen: boolean
  onClose: () => void
  onReplaceSelection: (text: string) => void
  onInsert: (text: string) => void
}

const SUGGESTIONS_WITH_SELECTION = [
  'Make this more concise',
  'Make this more professional',
  'Fix grammar and spelling',
  'Continue writing from here',
]

const SUGGESTIONS_NO_SELECTION = [
  'Suggest a one-sentence executive summary',
  'Draft an opening paragraph for this document',
  'What is this document missing?',
]

export default function AiAssistPopover({
  docId,
  selectedText,
  isOpen,
  onClose,
  onReplaceSelection,
  onInsert,
}: AiAssistPopoverProps) {
  const [instruction, setInstruction] = useState('')
  const [response, setResponse] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (isOpen) {
      setInstruction('')
      setResponse('')
      setError(null)
      setTimeout(() => textareaRef.current?.focus(), 50)
    }
  }, [isOpen])

  if (!isOpen) return null

  const suggestions = selectedText ? SUGGESTIONS_WITH_SELECTION : SUGGESTIONS_NO_SELECTION

  const runAssist = (text: string) => {
    if (!text.trim() || streaming) return
    setInstruction(text)
    setResponse('')
    setError(null)
    setStreaming(true)
    streamOfficeAiAssist(
      docId,
      text.trim(),
      selectedText || null,
      (chunk) => setResponse((prev) => prev + chunk),
      () => setStreaming(false),
      (err) => {
        setError(err)
        setStreaming(false)
      }
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-24">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-full max-w-lg mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-blue-500" />
            Ask AI
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-gray-400 dark:text-gray-500 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-3">
          {selectedText && (
            <div className="text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 rounded px-3 py-2 max-h-20 overflow-y-auto">
              <span className="font-medium">Selected text: </span>
              {selectedText.length > 200 ? `${selectedText.slice(0, 200)}…` : selectedText}
            </div>
          )}

          {/* Instruction input */}
          <div className="flex items-start gap-2">
            <textarea
              ref={textareaRef}
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  runAssist(instruction)
                }
              }}
              placeholder={selectedText ? 'What should I do with the selection?' : 'Ask a question about this document...'}
              className="flex-1 text-sm border border-gray-300 dark:border-gray-600 rounded-md px-3 py-2 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              rows={2}
              disabled={streaming}
            />
            <button
              onClick={() => runAssist(instruction)}
              disabled={!instruction.trim() || streaming}
              className="px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
            >
              {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Ask'}
            </button>
          </div>

          {/* Suggestions */}
          {!response && !streaming && (
            <div className="flex flex-wrap gap-1.5">
              {suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => runAssist(s)}
                  className="text-xs px-2.5 py-1 rounded-full border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Error */}
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}

          {/* Response */}
          {(response || streaming) && (
            <div className="border border-gray-200 dark:border-gray-700 rounded-md p-3 max-h-64 overflow-y-auto">
              <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
                {response}
                {streaming && <span className="inline-block w-1.5 h-3.5 bg-gray-400 ml-0.5 animate-pulse align-middle" />}
              </p>
            </div>
          )}
        </div>

        {/* Footer actions */}
        {response && !streaming && (
          <div className="px-5 py-3 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-950 rounded-b-lg flex items-center justify-end gap-2">
            <button
              onClick={() => navigator.clipboard.writeText(response)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
            >
              <Copy className="h-3.5 w-3.5" />
              Copy
            </button>
            {selectedText && (
              <button
                onClick={() => {
                  onReplaceSelection(response)
                  onClose()
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
              >
                <Check className="h-3.5 w-3.5" />
                Replace selection
              </button>
            )}
            <button
              onClick={() => {
                onInsert(response)
                onClose()
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
            >
              <Check className="h-3.5 w-3.5" />
              Insert at cursor
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
