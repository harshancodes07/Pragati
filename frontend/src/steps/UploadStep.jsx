import { useRef, useState } from 'react'
import { api } from '../api'
import { Button, Card, ErrorNote, Reveal, Spinner } from '../components/common'

export function UploadStep({ language, onReady }) {
  const [mode, setMode] = useState('file')
  const [file, setFile] = useState(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  const canSubmit = mode === 'file' ? !!file : text.trim().length > 40

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const res = await api.upload({
        file: mode === 'file' ? file : null,
        text: mode === 'text' ? text : null,
        title: mode === 'file' ? file?.name : 'Pasted text',
        language,
      })
      onReady(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  function pick(f) {
    if (!f) return
    setFile(f)
    setError(null)
  }

  return (
    <Reveal className="space-y-5">
      <header>
        <h2 className="text-2xl font-semibold">Upload your textbook</h2>
        <p className="mt-1 text-sm text-muted">
          A photo of a page, a PDF, or just paste the text. Bodhi will only ever
          teach from what you give it here.
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
              pick(e.dataTransfer.files?.[0])
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
              className="hidden"
              accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.md"
              onChange={(e) => pick(e.target.files?.[0])}
            />
            <div className="text-3xl">{file ? '📄' : '📚'}</div>
            <p className="mt-3 text-sm">
              {file ? (
                <span className="font-medium text-saffron">{file.name}</span>
              ) : (
                <>
                  Drop a page here, or <span className="text-saffron">browse</span>
                </>
              )}
            </p>
            <p className="mt-1 text-xs text-muted">PDF, PNG, JPG or TXT</p>
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
          {busy ? 'Processing…' : 'Start learning'}
        </Button>
        {busy && <Spinner label="Reading the page, then indexing it…" />}
      </div>
    </Reveal>
  )
}
