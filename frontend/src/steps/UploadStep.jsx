import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { Button, Card, ErrorNote, Reveal, Spinner } from '../components/common'

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
    <Reveal className="space-y-5">
      <header>
        <h2 className="text-2xl font-semibold">Upload your textbook</h2>
        <p className="mt-1 text-sm text-muted">
          One or more page photos, a PDF, or just paste the text. Bodhi will
          only ever teach from what you give it here.
        </p>
      </header>

      <div className="flex gap-2">
        {[
          ['file', 'Photo or PDF'],
          ['text', 'Paste text'],
        ].map(([id, label]) => (
          <button
            key={id}
            onClick={() => setMode(id)}
            className={`rounded-lg px-4 py-2 text-sm transition ${
              mode === id
                ? 'bg-saffron/15 text-saffron'
                : 'text-muted hover:text-slate-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <Card>
        {mode === 'file' ? (
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
            className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center
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
                <div className="text-3xl">📚</div>
                <p className="mt-3 text-sm">
                  Drop pages here, or <span className="text-saffron">browse</span>
                </p>
                <p className="mt-1 text-xs text-muted">
                  PDF, PNG, JPG or TXT — up to {MAX_FILES} pages at once
                </p>
              </>
            ) : (
              <div className="space-y-2 text-left" onClick={(e) => e.stopPropagation()}>
                {files.map((f, i) => (
                  <div
                    key={fileKey(f)}
                    className="flex items-center justify-between gap-3 rounded-lg
                      bg-ink/60 px-3 py-2 text-sm"
                  >
                    <span className="truncate text-slate-200">{f.name}</span>
                    <button
                      onClick={() => removeFile(i)}
                      className="shrink-0 text-muted hover:text-alert"
                      aria-label={`Remove ${f.name}`}
                    >
                      ✕
                    </button>
                  </div>
                ))}
                {files.length < MAX_FILES && (
                  <p
                    onClick={() => inputRef.current?.click()}
                    className="cursor-pointer pt-1 text-center text-xs text-saffron"
                  >
                    + Add another page
                  </p>
                )}
              </div>
            )}
          </div>
        ) : (
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            placeholder="Paste a passage from your textbook…"
            className="w-full resize-none rounded-xl border border-line bg-ink p-4 text-sm
              outline-none placeholder:text-muted focus:border-saffron"
          />
        )}
      </Card>

      <ErrorNote>{error}</ErrorNote>

      <div className="flex items-center gap-4">
        <Button onClick={submit} disabled={!canSubmit || busy}>
          {busy
            ? 'Processing…'
            : files.length > 1
              ? `Start learning from ${files.length} pages`
              : 'Start learning'}
        </Button>
        {busy && <Spinner label={uploadStatus(elapsed, files.length)} />}
      </div>
    </Reveal>
  )
}
