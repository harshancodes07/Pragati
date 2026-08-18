import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { Button, Card, ErrorNote, Reveal, Spinner } from '../components/common'
import { CameraCapture } from '../components/CameraCapture'

const MAX_FILES = 8

// A dense photo can take a vision model 10-15s+ to transcribe, and multiple
// pages run in the same request — a static spinner over that long reads as
// "stuck", so the label changes with elapsed time and file count.
function uploadStatus(seconds, fileCount) {
  const plural = fileCount > 1 ? 's' : ''
  if (seconds < 4) return `Reading the page${plural}…`
  if (seconds < 10) return `Still reading${fileCount > 1 ? ` all ${fileCount} pages` : ''} — dense or busy pages take longer…`
  return `Still working (${seconds}s)${fileCount > 1 ? ` on ${fileCount} pages` : ''}…`
}

function fileKey(f) {
  return `${f.name}:${f.size}`
}

export function UploadStep({ language, onReady }) {
  const [mode, setMode] = useState('file')
  const [files, setFiles] = useState([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [showCamera, setShowCamera] = useState(false)
  const inputRef = useRef(null)

  const canSubmit = mode === 'file' ? files.length > 0 : text.trim().length > 40

  useEffect(() => {
    if (!busy) return
    setElapsed(0)
    const id = setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [busy])

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const res = await api.upload({
        files: mode === 'file' ? files : null,
        text: mode === 'text' ? text : null,
        title: mode === 'file' && files.length === 1 ? files[0].name : undefined,
        language,
      })
      onReady(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  // Accumulates across successive picks/drops, deduped by name+size, so a
  // student can add pages one photo at a time instead of selecting them all
  // in a single dialog.
  function addFiles(fileList) {
    if (!fileList?.length) return
    setFiles((prev) => {
      const seen = new Set(prev.map(fileKey))
      const merged = [...prev]
      for (const f of fileList) {
        const key = fileKey(f)
        if (!seen.has(key)) {
          merged.push(f)
          seen.add(key)
        }
      }
      return merged.slice(0, MAX_FILES)
    })
    setError(null)
  }

  function removeFile(index) {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  return (
    <Reveal className="space-y-6">
      <header>
        <h2 className="text-3xl font-semibold tracking-tight">Upload your textbook</h2>
        <p className="mt-2 text-[15px] leading-relaxed text-muted">
          One or more page photos, a PDF, or just paste the text. Pragati will
          only ever teach from what you give it here.
        </p>
      </header>

      <div className="inline-flex gap-1 rounded-xl border border-line bg-raised p-1">
        {[
          ['file', 'Photo or PDF'],
          ['text', 'Paste text'],
        ].map(([id, label]) => (
          <button
            key={id}
            onClick={() => {
              setMode(id)
              setShowCamera(false)
            }}
            className={`rounded-lg px-5 py-2.5 text-sm font-medium transition ${
              mode === id
                ? 'bg-white text-saffron shadow-[0_1px_2px_rgba(0,0,0,0.08)]'
                : 'text-muted hover:text-[#1D1D1F]'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <Card>
        {mode === 'file' ? (
          showCamera ? (
            <CameraCapture
              onCapture={(file) => {
                addFiles([file])
                setShowCamera(false)
              }}
              onCancel={() => setShowCamera(false)}
            />
          ) : (
            <div
              onDragOver={(e) => {
                e.preventDefault()
                setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragging(false)
                addFiles(e.dataTransfer.files)
              }}
              onClick={() => inputRef.current?.click()}
              className={`cursor-pointer rounded-2xl border-2 border-dashed px-6 py-12 text-center
                sm:px-10 sm:py-20
                transition ${
                  dragging ? 'border-saffron bg-saffron/5' : 'border-line hover:border-muted'
                }`}
            >
              <input
                ref={inputRef}
                type="file"
                multiple
                className="hidden"
                accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.md"
                onChange={(e) => addFiles(e.target.files)}
              />

              {files.length === 0 ? (
                <>
                  <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full
                    bg-saffron/10 text-5xl">
                    📚
                  </div>
                  <p className="mt-6 text-lg font-medium text-[#1D1D1F]">
                    Drop pages here, or <span className="text-saffron">browse</span>
                  </p>
                  <p className="mt-2 text-sm text-muted">
                    PDF, PNG, JPG or TXT — up to {MAX_FILES} pages at once
                  </p>
                  <div className="mx-auto mt-4 w-fit border-t border-line pt-4 text-xs text-muted">
                    or
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setShowCamera(true)
                    }}
                    className="relative z-10 mt-4 inline-flex items-center gap-2 rounded-xl
                      border border-line bg-white px-6 py-3 text-sm font-medium text-[#1D1D1F]
                      shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition hover:border-saffron
                      hover:bg-saffron/5"
                  >
                    📷 Scan & Learn
                  </button>
                </>
              ) : (
                <div className="space-y-2.5 text-left" onClick={(e) => e.stopPropagation()}>
                  {files.map((f, i) => (
                    <div
                      key={fileKey(f)}
                      className="flex items-center justify-between gap-3 rounded-xl
                        bg-raised px-4 py-3 text-sm"
                    >
                      <span className="truncate text-[#1D1D1F]">{f.name}</span>
                      <button
                        onClick={() => removeFile(i)}
                        className="shrink-0 text-muted hover:text-alert"
                        aria-label={`Remove ${f.name}`}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                  <div className="flex flex-wrap items-center justify-center gap-5 pt-2">
                    {files.length < MAX_FILES && (
                      <p
                        onClick={() => inputRef.current?.click()}
                        className="cursor-pointer text-center text-sm font-medium text-saffron"
                      >
                        + Add another page
                      </p>
                    )}
                    {files.length < MAX_FILES && (
                      <p
                        onClick={() => setShowCamera(true)}
                        className="cursor-pointer text-center text-sm font-medium text-saffron"
                      >
                        📷 Scan another page
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        ) : (
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={12}
            placeholder="Paste a passage from your textbook…"
            className="w-full resize-none rounded-xl border border-line bg-white p-5 text-[15px]
              leading-relaxed outline-none placeholder:text-muted focus:border-saffron"
          />
        )}
      </Card>

      {!showCamera && (
        <>
          <ErrorNote>{error}</ErrorNote>

          <div className="flex flex-wrap items-center gap-4">
            <Button onClick={submit} disabled={!canSubmit || busy}>
              {busy
                ? 'Processing…'
                : files.length > 1
                  ? `Start learning from ${files.length} pages`
                  : 'Start learning'}
            </Button>
            {busy && <Spinner label={uploadStatus(elapsed, files.length)} />}
          </div>
        </>
      )}
    </Reveal>
  )
}
