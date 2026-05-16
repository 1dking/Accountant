import { useState, useRef, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Mic, Square, Trash2, Upload, Type } from 'lucide-react'
import {
  getVoicemailGreeting,
  uploadVoicemailGreeting,
  deleteVoicemailGreeting,
  updateVoicemailMode,
  type VoicemailMode,
} from '@/api/auth'
import { useAuthStore } from '@/stores/authStore'

const MAX_UPLOAD_BYTES = 5 * 1024 * 1024
const MAX_RECORD_SECONDS = 30
const WARN_AT_SECONDS = 25

const MODE_OPTIONS: { value: VoicemailMode; label: string; note?: string }[] = [
  { value: 'cell_then_voicemail', label: 'Cell phone, then voicemail', note: 'Recommended' },
  { value: 'voicemail_only', label: 'Voicemail only (skip cell)' },
  { value: 'cell_only', label: 'Cell phone only (no voicemail)' },
]

export default function VoicemailGreetingEditor() {
  const { user, fetchMe } = useAuthStore()
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<VoicemailMode>(
    user?.voicemail_mode ?? 'cell_then_voicemail',
  )
  const [activeTab, setActiveTab] = useState<'record' | 'type' | 'upload'>('record')

  useEffect(() => {
    if (user?.voicemail_mode && user.voicemail_mode !== mode) {
      setMode(user.voicemail_mode)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.voicemail_mode])

  const { data: greeting, isLoading: greetingLoading } = useQuery({
    queryKey: ['voicemail-greeting'],
    queryFn: () => getVoicemailGreeting(),
  })

  const modeMutation = useMutation({
    mutationFn: updateVoicemailMode,
    onSuccess: () => {
      toast.success('Voicemail mode updated')
      fetchMe()
    },
    onError: (e: any) => toast.error(`Failed to update mode: ${e.message}`),
  })

  const handleModeChange = (newMode: VoicemailMode) => {
    setMode(newMode)
    modeMutation.mutate(newMode)
  }

  // ─── Recording state ───
  const [isRecording, setIsRecording] = useState(false)
  const [recordingSeconds, setRecordingSeconds] = useState(0)
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const recordingTimerRef = useRef<number | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const cleanupRecordingTimer = () => {
    if (recordingTimerRef.current !== null) {
      window.clearInterval(recordingTimerRef.current)
      recordingTimerRef.current = null
    }
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : 'audio/mp4'
      const recorder = new MediaRecorder(stream, { mimeType })
      chunksRef.current = []
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        streamRef.current = null
        setRecordedBlob(new Blob(chunksRef.current, { type: mimeType }))
        cleanupRecordingTimer()
      }
      recorder.start()
      mediaRecorderRef.current = recorder
      setIsRecording(true)
      setRecordingSeconds(0)
      recordingTimerRef.current = window.setInterval(() => {
        setRecordingSeconds((s) => {
          const next = s + 1
          if (next >= MAX_RECORD_SECONDS) {
            stopRecording()
            return MAX_RECORD_SECONDS
          }
          return next
        })
      }, 1000)
    } catch (e: any) {
      toast.error('Microphone access denied or unavailable')
    }
  }

  const stopRecording = () => {
    mediaRecorderRef.current?.stop()
    setIsRecording(false)
  }

  useEffect(() => {
    return () => {
      // Cleanup on unmount
      cleanupRecordingTimer()
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  const uploadMutation = useMutation({
    mutationFn: uploadVoicemailGreeting,
    onSuccess: () => {
      toast.success('Greeting saved')
      setRecordedBlob(null)
      setSelectedFile(null)
      queryClient.invalidateQueries({ queryKey: ['voicemail-greeting'] })
      fetchMe()
    },
    onError: (e: any) => toast.error(`Save failed: ${e.message}`),
  })

  const saveRecording = () => {
    if (!recordedBlob) return
    const fd = new FormData()
    fd.append('greeting_type', 'audio')
    fd.append('audio_file', recordedBlob, 'greeting.webm')
    uploadMutation.mutate(fd)
  }

  // ─── Type state ───
  const [textGreeting, setTextGreeting] = useState('')
  useEffect(() => {
    if (greeting?.data?.type === 'text' && greeting.data.text) {
      setTextGreeting(greeting.data.text)
    }
  }, [greeting])

  const saveText = () => {
    if (!textGreeting.trim()) return
    const fd = new FormData()
    fd.append('greeting_type', 'text')
    fd.append('text', textGreeting.trim())
    uploadMutation.mutate(fd)
  }

  // ─── Upload state ───
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const saveUpload = () => {
    if (!selectedFile) return
    if (selectedFile.size > MAX_UPLOAD_BYTES) {
      toast.error('File exceeds 5MB limit')
      return
    }
    const fd = new FormData()
    fd.append('greeting_type', 'audio')
    fd.append('audio_file', selectedFile)
    uploadMutation.mutate(fd)
  }

  const deleteMutation = useMutation({
    mutationFn: deleteVoicemailGreeting,
    onSuccess: () => {
      toast.success('Greeting removed — using default')
      queryClient.invalidateQueries({ queryKey: ['voicemail-greeting'] })
      fetchMe()
    },
    onError: (e: any) => toast.error(`Delete failed: ${e.message}`),
  })

  const handleDelete = () => deleteMutation.mutate()

  return (
    <section className="bg-white dark:bg-gray-900 border rounded-lg p-6 space-y-6">
      <div>
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-3">
          Voicemail
        </h2>

        {/* Mode radio group */}
        <div className="space-y-2 mb-6">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
            Call routing
          </label>
          {MODE_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-start gap-2 cursor-pointer">
              <input
                type="radio"
                name="voicemail_mode"
                value={opt.value}
                checked={mode === opt.value}
                onChange={() => handleModeChange(opt.value)}
                className="mt-1"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">
                {opt.label}
                {opt.note && (
                  <span className="ml-2 text-xs text-gray-400">{opt.note}</span>
                )}
              </span>
            </label>
          ))}
        </div>

        {mode !== 'cell_only' && (
          <>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Greeting
            </label>
            <div className="mb-4 text-xs text-gray-500 dark:text-gray-400">
              {greetingLoading ? (
                'Loading…'
              ) : greeting?.data?.type === 'audio' ? (
                <span className="flex items-center gap-2 flex-wrap">
                  Custom audio greeting
                  <audio
                    controls
                    src={`/api/communication/voicemail-greeting/${user?.id}.mp3?cb=${
                      greeting.data.storage_key ?? ''
                    }`}
                    className="h-7"
                  />
                  <button
                    type="button"
                    onClick={handleDelete}
                    className="text-red-600 hover:underline text-xs flex items-center gap-1"
                  >
                    <Trash2 className="h-3 w-3" /> Reset to default
                  </button>
                </span>
              ) : greeting?.data?.type === 'text' ? (
                <span>
                  Custom text greeting:&nbsp;
                  <span className="italic">"{greeting.data.text}"</span>
                  <button
                    type="button"
                    onClick={handleDelete}
                    className="ml-2 text-red-600 hover:underline text-xs"
                  >
                    <Trash2 className="h-3 w-3 inline" /> Reset to default
                  </button>
                </span>
              ) : (
                <span>Using default Polly.Joanna greeting</span>
              )}
            </div>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700 mb-3">
              {(
                [
                  ['record', Mic, 'Record'],
                  ['type', Type, 'Type'],
                  ['upload', Upload, 'Upload'],
                ] as const
              ).map(([key, Icon, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setActiveTab(key)}
                  className={`px-3 py-2 text-sm flex items-center gap-1 border-b-2 ${
                    activeTab === key
                      ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                      : 'border-transparent text-gray-500'
                  }`}
                >
                  <Icon className="h-4 w-4" /> {label}
                </button>
              ))}
            </div>

            {activeTab === 'record' && (
              <div className="space-y-2">
                {!isRecording && !recordedBlob && (
                  <button
                    type="button"
                    onClick={startRecording}
                    className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded flex items-center gap-2 text-sm"
                  >
                    <Mic className="h-4 w-4" /> Record
                  </button>
                )}
                {isRecording && (
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={stopRecording}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-800 text-white rounded flex items-center gap-2 text-sm"
                    >
                      <Square className="h-4 w-4" /> Stop
                    </button>
                    <span
                      className={`font-mono text-sm ${
                        recordingSeconds >= WARN_AT_SECONDS
                          ? 'text-red-600'
                          : 'text-gray-700 dark:text-gray-300'
                      }`}
                    >
                      {recordingSeconds}s / {MAX_RECORD_SECONDS}s
                      {recordingSeconds >= WARN_AT_SECONDS && (
                        <span className="ml-2 text-xs">⚠ approaching limit</span>
                      )}
                    </span>
                  </div>
                )}
                {recordedBlob && !isRecording && (
                  <div className="space-y-2">
                    <audio
                      controls
                      src={URL.createObjectURL(recordedBlob)}
                      className="h-8"
                    />
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={saveRecording}
                        disabled={uploadMutation.isPending}
                        className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm disabled:opacity-50"
                      >
                        {uploadMutation.isPending ? 'Saving…' : 'Save'}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setRecordedBlob(null)
                          startRecording()
                        }}
                        className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm"
                      >
                        Re-record
                      </button>
                      <button
                        type="button"
                        onClick={() => setRecordedBlob(null)}
                        className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'type' && (
              <div className="space-y-2">
                <textarea
                  value={textGreeting}
                  onChange={(e) => setTextGreeting(e.target.value.slice(0, 500))}
                  placeholder="Hi, this is [your name], I'm not available right now…"
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded resize-none text-sm bg-white dark:bg-gray-900"
                />
                <div className="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400">
                  <span>
                    Spoken in Polly.Joanna voice. We'll append "Please leave a message
                    after the beep…"
                  </span>
                  <span>{textGreeting.length}/500</span>
                </div>
                <button
                  type="button"
                  onClick={saveText}
                  disabled={!textGreeting.trim() || uploadMutation.isPending}
                  className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm disabled:opacity-50"
                >
                  {uploadMutation.isPending ? 'Saving…' : 'Save'}
                </button>
              </div>
            )}

            {activeTab === 'upload' && (
              <div className="space-y-2">
                <input
                  type="file"
                  accept="audio/mpeg,audio/mp4,audio/wav,audio/x-wav,.mp3,.m4a,.wav"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
                  className="text-sm"
                />
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  Max 5 MB. .mp3, .m4a, .wav supported.
                </div>
                {selectedFile && (
                  <div className="space-y-2">
                    <audio
                      controls
                      src={URL.createObjectURL(selectedFile)}
                      className="h-8"
                    />
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={saveUpload}
                        disabled={uploadMutation.isPending}
                        className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm disabled:opacity-50"
                      >
                        {uploadMutation.isPending ? 'Saving…' : 'Confirm'}
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedFile(null)}
                        className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}
