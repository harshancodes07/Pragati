import { useState } from 'react'
import { api, isIndicScript } from '../api'
import { Badge, Button, Card, ErrorNote, Reveal, Skeleton } from '../components/common'
import { DifficultyShift } from '../components/DifficultyShift'
import { MicButton, SpeakButton } from '../components/VoiceButton'

export function PracticeStep({ doc, language, concept, difficulty, voice }) {
  const [topic, setTopic] = useState(concept || '')
  const [set, setSet] = useState(null)
  const [answers, setAnswers] = useState({})
  const [graded, setGraded] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const indic = isIndicScript(language)

  async function generate() {
    if (!topic.trim()) return
    setBusy(true)
    setError(null)
    setGraded(null)
    setAnswers({})
    setSet(null)
    try {
      setSet(
        await api.practice({
          document_id: doc.document_id,
          session_id: doc.session_id,
          concept: topic,
          language,
        }),
      )
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      setGraded(
        await api.submitPractice({
          session_id: doc.session_id,
          set_id: set.set_id,
          answers,
          concept: topic,
        }),
      )
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const resultFor = (id) => graded?.results.find((r) => r.id === id)

  return (
    <Reveal className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight">Practice</h2>
          <p className="mt-1 text-sm text-muted">
            5 multiple choice + 2 short answers, generated from your book.
          </p>
        </div>
        <Badge tone="brand">{set?.difficulty ?? difficulty}</Badge>
      </header>

      <Card className="space-y-3">
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="Which concept to practise?"
          className="w-full rounded-xl border border-line bg-white px-4 py-3 text-sm
            outline-none placeholder:text-muted focus:border-saffron"
        />
        <div className="flex justify-end">
          <Button onClick={generate} disabled={busy || !topic.trim()}>
            {busy && !set ? 'Writing questions…' : set ? 'New set' : 'Generate practice'}
          </Button>
        </div>
      </Card>

      <ErrorNote onRetry={generate}>{error}</ErrorNote>

      {busy && !set && (
        <Card>
          <Skeleton lines={6} />
        </Card>
      )}

      {set && (
        <div className="space-y-4">
          {set.questions.map((q, idx) => {
            const res = resultFor(q.id)
            return (
              <Card
                key={q.id}
                className={
                  res?.correct === true
                    ? 'border-leaf/40'
                    : res?.correct === false
                      ? 'border-alert/40'
                      : ''
                }
              >
                <div className="mb-3 flex items-start gap-3">
                  <span className="mt-0.5 text-xs font-mono text-muted">
                    {String(idx + 1).padStart(2, '0')}
                  </span>
                  <p className={`flex-1 text-[15px] ${indic ? 'script-indic' : ''}`}>
                    {q.question}
                  </p>
                  {voice && <SpeakButton text={q.question} language={language} label="" />}
                  {q.type === 'short_answer' && <Badge>written</Badge>}
                </div>

                {q.type === 'mcq' ? (
                  <div className="ml-8 space-y-2">
                    {q.options.map((opt) => {
                      const picked = answers[q.id] === opt
                      const isAnswer = res && opt === res.correct_answer
                      const wrongPick = res && picked && !res.correct
                      return (
                        <button
                          key={opt}
                          disabled={!!graded}
                          onClick={() => setAnswers((a) => ({ ...a, [q.id]: opt }))}
                          className={`w-full rounded-lg border px-4 py-2.5 text-left text-sm transition
                            ${
                              isAnswer
                                ? 'border-leaf bg-leaf/10 text-leaf'
                                : wrongPick
                                  ? 'border-alert bg-alert/10 text-alert'
                                  : picked
                                    ? 'border-saffron bg-saffron/10'
                                    : 'border-line hover:border-muted'
                            } ${indic ? 'script-indic' : ''}`}
                        >
                          {opt}
                        </button>
                      )
                    })}
                  </div>
                ) : (
                  <div className="ml-8 space-y-2">
                    <textarea
                      value={answers[q.id] ?? ''}
                      disabled={!!graded}
                      onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                      rows={3}
                      placeholder="Answer in your own words…"
                      className="w-full resize-none rounded-xl border border-line
                        bg-white p-3 text-sm outline-none placeholder:text-muted focus:border-saffron"
                    />
                    {voice && !graded && (
                      <MicButton
                        language={language}
                        onText={(t) =>
                          setAnswers((a) => ({
                            ...a,
                            [q.id]: a[q.id] ? `${a[q.id]} ${t}` : t,
                          }))
                        }
                      />
                    )}
                  </div>
                )}

                {res && (
                  <div className="ml-8 mt-3 space-y-1.5 border-t border-line pt-3 text-sm">
                    {res.type === 'short_answer' && (
                      <p className="text-[#1D1D1F]">
                        <span className="text-leaf">Model answer — </span>
                        {res.correct_answer}
                      </p>
                    )}
                    {res.explanation && <p className="text-muted">{res.explanation}</p>}
                  </div>
                )}
              </Card>
            )
          })}

          {!graded ? (
            <Button onClick={submit} disabled={busy || Object.keys(answers).length === 0}>
              {busy ? 'Grading…' : 'Submit answers'}
            </Button>
          ) : (
            <Reveal className="space-y-4">
              <Card className="text-center">
                <div className="text-3xl font-semibold text-saffron">
                  {graded.correct} / {graded.total}
                </div>
                <p className="mt-1 text-sm text-muted">
                  multiple choice correct
                  {graded.results.some((r) => r.type === 'short_answer') &&
                    ' · short answers are for self-review'}
                </p>
              </Card>
              <DifficultyShift shift={graded.difficulty} />
              <Button variant="ghost" onClick={generate}>
                Practise again at {graded.difficulty.current}
              </Button>
            </Reveal>
          )}
        </div>
      )}
    </Reveal>
  )
}
