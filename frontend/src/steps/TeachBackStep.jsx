import { useState } from 'react'
import { api, isIndicScript } from '../api'
import { Badge, Button, Card, ErrorNote, Reveal, Skeleton } from '../components/common'
import { DifficultyShift } from '../components/DifficultyShift'

const VERDICTS = {
  correct: { tone: 'good', label: 'Got it', icon: '✓' },
  partial: { tone: 'warn', label: 'Almost there', icon: '◐' },
  misconception: { tone: 'bad', label: 'Misconception found', icon: '!' },
  incorrect: { tone: 'bad', label: 'Not quite', icon: '✕' },
}

export function TeachBackStep({ doc, language, concept, onEvaluated }) {
  const [topic, setTopic] = useState(concept || '')
  const [explanation, setExplanation] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit() {
    if (!topic.trim() || !explanation.trim()) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.teachBack({
        document_id: doc.document_id,
        session_id: doc.session_id,
        concept: topic,
        explanation,
        language,
      })
      setResult(res)
      onEvaluated(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const verdict = result && (VERDICTS[result.understanding] ?? VERDICTS.partial)

  return (
    <Reveal className="space-y-5">
      <header>
        <h2 className="text-2xl font-semibold">Teach it back</h2>
        <p className="mt-1 text-sm text-muted">
          Explain the concept in your own words — any language, any grammar.
          Bodhi grades the idea, never the wording.
        </p>
      </header>

      <Card className="space-y-3">
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="Which concept? e.g. photosynthesis"
          className="w-full rounded-xl border border-line bg-ink px-4 py-3 text-sm
            outline-none placeholder:text-muted focus:border-saffron"
        />
        <textarea
          value={explanation}
          onChange={(e) => setExplanation(e.target.value)}
          rows={5}
          placeholder="Plant sunlight ah use panni food make pannum…"
          className="w-full resize-none rounded-xl border border-line bg-ink p-4 text-sm
            outline-none placeholder:text-muted focus:border-saffron"
        />
        <div className="flex justify-end">
          <Button onClick={submit} disabled={busy || !topic.trim() || !explanation.trim()}>
            {busy ? 'Checking…' : 'Check my understanding'}
          </Button>
        </div>
      </Card>

      <ErrorNote onRetry={submit}>{error}</ErrorNote>

      {busy && (
        <Card>
          <Skeleton lines={5} />
        </Card>
      )}

      {result && (
        <Reveal className="space-y-4">
          <Card className="space-y-4">
            <div className="flex items-center gap-3">
              <span className="text-xl">{verdict.icon}</span>
              <Badge tone={verdict.tone}>{verdict.label}</Badge>
            </div>

            {result.feedback && (
              <p
                className={`text-[15px] leading-relaxed ${
                  isIndicScript(language) ? 'script-indic' : ''
                }`}
              >
                {result.feedback}
              </p>
            )}

            {result.correct_points?.length > 0 && (
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-leaf">
                  What you got right
                </h4>
                <ul className="space-y-1.5">
                  {result.correct_points.map((p, i) => (
                    <li key={i} className="flex gap-2 text-sm text-slate-300">
                      <span className="text-leaf">✓</span> {p}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          {result.misconceptions?.length > 0 && (
            <Card className="border-alert/40 bg-alert/5">
              <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-alert">
                Exactly where it went wrong
              </h4>
              <div className="space-y-4">
                {result.misconceptions.map((m, i) => (
                  <div key={i} className="space-y-2 text-sm">
                    {m.student_claim && (
                      <p className="rounded-lg bg-ink/60 p-3 italic text-slate-400">
                        “{m.student_claim}”
                      </p>
                    )}
                    {m.problem && (
                      <p className="text-slate-300">
                        <span className="text-alert">Why that's wrong — </span>
                        {m.problem}
                      </p>
                    )}
                    {m.correct_concept && (
                      <p className="text-slate-300">
                        <span className="text-leaf">Actually — </span>
                        {m.correct_concept}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          <DifficultyShift shift={result.difficulty} />
        </Reveal>
      )}
    </Reveal>
  )
}
