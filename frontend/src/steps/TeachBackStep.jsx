import { useState } from 'react'
import { api, isIndicScript } from '../api'
import { Badge, Button, Card, ErrorNote, Reveal, Skeleton } from '../components/common'
import { DifficultyShift } from '../components/DifficultyShift'
import { DoubtChat } from '../components/DoubtChat'
import { ScoreDashboard } from '../components/ScoreDashboard'
import { MicButton, SpeakButton } from '../components/VoiceButton'

const VERDICTS = {
  correct: { tone: 'good', label: 'Got it', icon: '✓' },
  partial: { tone: 'warn', label: 'Almost there', icon: '◐' },
  misconception: { tone: 'bad', label: 'Misconception found', icon: '!' },
  incorrect: { tone: 'bad', label: 'Not quite', icon: '✕' },
}

// Who the student is explaining to. This changes the grading rubric on the
// backend, not just the placeholder text — a stiff textbook recital scores
// well in Exam mode and badly in Friend mode, by design.
const MODES = [
  {
    id: 'simple',
    dot: '🟢',
    label: 'Simple',
    tagline: 'Explain it to a 10-year-old',
    placeholder: 'Say it like you would to your younger sibling…',
  },
  {
    id: 'exam',
    dot: '🔵',
    label: 'Exam',
    tagline: 'Explain it as a 5-mark answer',
    placeholder: 'Write it the way you would in the exam hall…',
  },
  {
    id: 'friend',
    dot: '🟣',
    label: 'Friend',
    tagline: 'Explain it to a beginner',
    placeholder: 'Explain it to a friend who has never heard of this…',
  },
]

export function TeachBackStep({
  doc,
  language,
  concept,
  voice,
  autoSpeak,
  onEvaluated,
  onChatSaved,
}) {
  const [topic, setTopic] = useState(concept || '')
  const [mode, setMode] = useState('simple')
  const [explanation, setExplanation] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const activeMode = MODES.find((m) => m.id === mode) ?? MODES[0]

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
        mode,
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
  const indic = isIndicScript(language)

  return (
    <Reveal className="space-y-6">
      <header>
        <h2 className="text-3xl font-semibold tracking-tight">Teach it back</h2>
        <p className="mt-1 text-sm text-muted">
          Explain the concept in your own words{voice && ' — type it or just say it out loud'}.
          Any language, any grammar. Pragati grades the idea, never the wording.
        </p>
      </header>

      <div className="grid gap-2 sm:grid-cols-3">
        {MODES.map((m) => {
          const active = m.id === mode
          return (
            <button
              key={m.id}
              onClick={() => setMode(m.id)}
              className={`rounded-xl border px-4 py-3 text-left transition ${
                active
                  ? 'border-saffron bg-saffron/10'
                  : 'border-line hover:border-muted hover:bg-raised/50'
              }`}
            >
              <div
                className={`flex items-center gap-2 text-sm font-medium ${
                  active ? 'text-saffron' : 'text-[#1D1D1F]'
                }`}
              >
                <span>{m.dot}</span>
                {m.label}
              </div>
              <div className="mt-0.5 text-xs text-muted">{m.tagline}</div>
            </button>
          )
        })}
      </div>

      <Card className="space-y-3">
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="Which concept? e.g. photosynthesis"
          className="w-full rounded-xl border border-line bg-white px-4 py-3 text-sm
            outline-none placeholder:text-muted focus:border-saffron"
        />
        <textarea
          value={explanation}
          onChange={(e) => setExplanation(e.target.value)}
          rows={5}
          placeholder={activeMode.placeholder}
          className="w-full resize-none rounded-xl border border-line bg-white p-4 text-sm
            outline-none placeholder:text-muted focus:border-saffron"
        />
        <div className="flex items-center justify-between gap-3">
          {voice ? (
            <MicButton
              language={language}
              disabled={busy}
              onText={(t) => setExplanation((e) => (e ? `${e} ${t}` : t))}
            />
          ) : (
            <span />
          )}
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
          {result.scores && (
            <ScoreDashboard
              scores={result.scores}
              marks={result.mode === 'exam' ? result.marks_out_of_5 : null}
              misconceptions={result.misconceptions}
              indic={indic}
            />
          )}

          <DoubtChat
            concept={topic}
            explanation={result.feedback}
            language={language}
            documentId={doc.document_id}
            sessionId={doc.session_id}
            onChatSaved={onChatSaved}
          >
            <Card className="space-y-4">
              <div className="flex items-center gap-3">
                <span className="text-xl">{verdict.icon}</span>
                <Badge tone={verdict.tone}>{verdict.label}</Badge>
              </div>

              {result.feedback && (
                <>
                  <p className={`text-[15px] leading-relaxed ${indic ? 'script-indic' : ''}`}>
                    {result.feedback}
                  </p>
                  {voice && (
                    <SpeakButton
                      text={result.feedback}
                      language={language}
                      autoPlay={autoSpeak}
                    />
                  )}
                </>
              )}
            </Card>
          </DoubtChat>

          <div className="grid gap-4 sm:grid-cols-2">
            {result.did_well?.length > 0 && (
              <Card>
                <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-leaf">
                  You got this right
                </h4>
                <ul className="space-y-2">
                  {result.did_well.map((p, i) => (
                    <li
                      key={i}
                      className={`flex gap-2 text-sm text-[#1D1D1F] ${
                        indic ? 'script-indic' : ''
                      }`}
                    >
                      <span className="shrink-0 text-leaf">✓</span> {p}
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            {result.improve?.length > 0 && (
              <Card>
                <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-saffron">
                  Improve this
                </h4>
                <ul className="space-y-2">
                  {result.improve.map((p, i) => (
                    <li
                      key={i}
                      className={`flex gap-2 text-sm text-[#1D1D1F] ${
                        indic ? 'script-indic' : ''
                      }`}
                    >
                      <span className="shrink-0 text-saffron">→</span> {p}
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </div>

          {result.misconceptions?.length > 0 && (
            <Card className="border-alert/40 bg-alert/5">
              <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-alert">
                Exactly where it went wrong
              </h4>
              <div className="space-y-4">
                {result.misconceptions.map((m, i) => (
                  <div key={i} className="space-y-2 text-sm">
                    {m.student_claim && (
                      <p className="rounded-lg bg-raised p-3 italic text-muted">
                        “{m.student_claim}”
                      </p>
                    )}
                    {m.problem && (
                      <p className="text-[#1D1D1F]">
                        <span className="text-alert">Why that's wrong — </span>
                        {m.problem}
                      </p>
                    )}
                    {m.correct_concept && (
                      <p className="text-[#1D1D1F]">
                        <span className="text-leaf">Actually — </span>
                        {m.correct_concept}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {result.improved_explanation && (
            <Card className="space-y-3 border-saffron/30 bg-saffron/5">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-saffron">
                One way to say it better
              </h4>
              <p
                className={`text-[15px] leading-relaxed text-[#1D1D1F] ${
                  indic ? 'script-indic' : ''
                }`}
              >
                {result.improved_explanation}
              </p>
              {voice && (
                <SpeakButton text={result.improved_explanation} language={language} />
              )}
            </Card>
          )}

          <DifficultyShift shift={result.difficulty} />
        </Reveal>
      )}
    </Reveal>
  )
}
