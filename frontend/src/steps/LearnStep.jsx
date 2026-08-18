import { useState } from 'react'
import { api, isIndicScript } from '../api'
import { Button, Card, ErrorNote, Reveal, Skeleton } from '../components/common'
import { DoubtChat } from '../components/DoubtChat'
import { GroundingCard } from '../components/GroundingCard'
import { MicButton, SpeakButton } from '../components/VoiceButton'

export function LearnStep({ doc, language, judgeMode, voice, autoSpeak, onTaught }) {
  const [question, setQuestion] = useState('')
  const [askedQuestion, setAskedQuestion] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function ask(q) {
    const asked = (q ?? question).trim()
    if (!asked) return

    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.ask({
        document_id: doc.document_id,
        session_id: doc.session_id,
        question: asked,
        language,
      })
      setResult(res)
      setAskedQuestion(asked)
      if (res.grounded) onTaught(asked)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Reveal className="space-y-5">
      <header>
        <h2 className="text-2xl font-semibold">Ask about your book</h2>
        <p className="mt-1 text-sm text-muted">
          Ask in Tamil, Tanglish or English — Pragati answers only from your upload.
        </p>
      </header>

      <Card className="space-y-3">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) ask()
          }}
          rows={3}
          placeholder="Photosynthesis-na enna?"
          className="w-full resize-none rounded-xl border border-line bg-ink p-4 text-sm
            outline-none placeholder:text-muted focus:border-saffron"
        />
        <div className="flex items-center justify-between gap-3">
          {voice ? (
            <MicButton
              language={language}
              disabled={busy}
              onText={(t) => setQuestion((q) => (q ? `${q} ${t}` : t))}
            />
          ) : (
            <span className="text-xs text-muted">⌘/Ctrl + Enter to ask</span>
          )}
          <Button onClick={() => ask()} disabled={busy || !question.trim()}>
            {busy ? 'Thinking…' : 'Ask Pragati'}
          </Button>
        </div>
      </Card>

      <ErrorNote onRetry={() => ask()}>{error}</ErrorNote>

      {busy && (
        <Card>
          <Skeleton lines={4} />
        </Card>
      )}

      {result && (
        <div className="space-y-4">
          <DoubtChat
            concept={askedQuestion}
            explanation={result.answer}
            language={language}
            documentId={doc.document_id}
            sessionId={doc.session_id}
          >
            <Card className="space-y-3">
              <p
                className={`whitespace-pre-wrap text-[15px] leading-relaxed ${
                  isIndicScript(language) ? 'script-indic' : ''
                }`}
              >
                {result.answer}
              </p>
              {voice && (
                <div className="border-t border-line pt-3">
                  <SpeakButton
                    text={result.answer}
                    language={language}
                    autoPlay={autoSpeak}
                  />
                </div>
              )}
            </Card>
          </DoubtChat>

          <GroundingCard
            sources={result.sources}
            retrieval={result.retrieval}
            grounded={result.grounded}
            judgeMode={judgeMode}
          />

          {result.grounded && (
            <p className="text-sm text-muted">
              Understood it? Move to <span className="text-saffron">Teach Back</span> and
              explain it in your own words.
            </p>
          )}
        </div>
      )}
    </Reveal>
  )
}
