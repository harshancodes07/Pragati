import { useEffect, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { LANGUAGES, api } from './api'
import { Badge, Card } from './components/common'
import { UploadStep } from './steps/UploadStep'
import { LearnStep } from './steps/LearnStep'
import { TeachBackStep } from './steps/TeachBackStep'
import { PracticeStep } from './steps/PracticeStep'
import { ProgressStep } from './steps/ProgressStep'

const STEPS = [
  { id: 'upload', label: 'Upload', icon: '📚' },
  { id: 'learn', label: 'Learn', icon: '💡' },
  { id: 'teachback', label: 'Teach Back', icon: '🗣' },
  { id: 'practice', label: 'Practice', icon: '✏️' },
  { id: 'progress', label: 'Progress', icon: '📈' },
]

export default function App() {
  const [step, setStep] = useState('upload')
  const [language, setLanguage] = useState('tanglish')
  const [judgeMode, setJudgeMode] = useState(false)
  const [doc, setDoc] = useState(null)
  const [concept, setConcept] = useState('')
  const [difficulty, setDifficulty] = useState('medium')
  const [health, setHealth] = useState(null)
  const [autoSpeak, setAutoSpeak] = useState(
    () => localStorage.getItem('bodhi.autoSpeak') === '1',
  )

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: 'down' }))
  }, [])

  useEffect(() => {
    localStorage.setItem('bodhi.autoSpeak', autoSpeak ? '1' : '0')
  }, [autoSpeak])

  // No Sarvam key on the backend means no mic and no speaker anywhere — the app
  // falls back to exactly what it was before voice existed.
  const voice = !!health?.speech?.configured

  const unlocked = (id) => id === 'upload' || !!doc

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl gap-8 px-6 py-8">
      {/* Step rail */}
      <aside className="w-52 shrink-0">
        <div className="mb-8">
          <h1 className="text-xl font-semibold tracking-tight">
            Bodhi <span className="text-saffron">·</span> போதி
          </h1>
          <p className="mt-1 text-xs text-muted">Your textbook, your language</p>
        </div>

        <nav className="space-y-1">
          {STEPS.map((s) => {
            const active = step === s.id
            const open = unlocked(s.id)
            return (
              <button
                key={s.id}
                disabled={!open}
                onClick={() => setStep(s.id)}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition
                  ${
                    active
                      ? 'bg-saffron/15 font-medium text-saffron'
                      : open
                        ? 'text-muted hover:bg-raised hover:text-slate-200'
                        : 'cursor-not-allowed text-line'
                  }`}
              >
                <span className={open ? '' : 'opacity-30'}>{s.icon}</span>
                {s.label}
              </button>
            )
          })}
        </nav>

        <div className="mt-8 space-y-3 border-t border-line pt-6">
          <label className="block text-xs font-semibold uppercase tracking-wide text-muted">
            Language
          </label>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm outline-none
              focus:border-saffron"
          >
            {LANGUAGES.map((l) => (
              <option key={l.id} value={l.id}>
                {l.label}
              </option>
            ))}
          </select>
          <p className="text-xs text-muted">
            {LANGUAGES.find((l) => l.id === language)?.hint}
          </p>

          {voice && (
            <button
              onClick={() => setAutoSpeak((v) => !v)}
              className={`mt-4 w-full rounded-lg border px-3 py-2 text-xs transition ${
                autoSpeak
                  ? 'border-saffron bg-saffron/10 text-saffron'
                  : 'border-line text-muted hover:text-slate-200'
              }`}
            >
              {autoSpeak ? '🔊 Read answers aloud' : '🔇 Read answers aloud'}
            </button>
          )}

          <button
            onClick={() => setJudgeMode((v) => !v)}
            className={`mt-4 w-full rounded-lg border px-3 py-2 text-xs transition ${
              judgeMode
                ? 'border-saffron bg-saffron/10 text-saffron'
                : 'border-line text-muted hover:text-slate-200'
            }`}
          >
            {judgeMode ? '● Judge mode on' : '○ Judge mode'}
          </button>
        </div>

        {health && (
          <div className="mt-6 text-xs text-muted">
            <span
              className={`mr-1.5 inline-block h-2 w-2 rounded-full ${
                health.status === 'ok' ? 'bg-leaf' : 'bg-alert'
              }`}
            />
            NIM {health.status === 'ok' ? 'connected' : 'not connected'}
            {judgeMode && health.nim?.model && (
              <div className="mt-1 font-mono text-[10px] leading-tight">
                {health.nim.model}
              </div>
            )}
            <div className="mt-1.5">
              <span
                className={`mr-1.5 inline-block h-2 w-2 rounded-full ${
                  voice ? 'bg-leaf' : 'bg-line'
                }`}
              />
              Voice {voice ? 'ready' : 'off'}
              {judgeMode && voice && health.speech?.detail && (
                <div className="mt-1 font-mono text-[10px] leading-tight">
                  {health.speech.detail}
                </div>
              )}
            </div>
          </div>
        )}
      </aside>

      {/* Content column */}
      <main className="min-w-0 flex-1">
        {doc && (
          <div className="mb-6 flex flex-wrap items-center gap-3 text-sm text-muted">
            <Badge tone="brand">{doc.title}</Badge>
            <span>
              {doc.pages} page{doc.pages === 1 ? '' : 's'} · {doc.chunk_count} chunks
              {doc.ocr_pages > 0 && ` · ${doc.ocr_pages} OCR'd`}
            </span>
            {judgeMode && doc.timing_ms && (
              <span className="font-mono text-[10px] leading-tight text-line">
                {Object.entries(doc.timing_ms)
                  .map(([stage, ms]) => `${stage}=${ms}ms`)
                  .join(' · ')}
              </span>
            )}
          </div>
        )}

        <AnimatePresence mode="wait">
          {step === 'upload' && (
            <UploadStep
              key="upload"
              language={language}
              onReady={(res) => {
                setDoc(res)
                setStep('learn')
              }}
            />
          )}

          {step === 'learn' && doc && (
            <LearnStep
              key="learn"
              doc={doc}
              language={language}
              judgeMode={judgeMode}
              voice={voice}
              autoSpeak={autoSpeak}
              onTaught={setConcept}
            />
          )}

          {step === 'teachback' && doc && (
            <TeachBackStep
              key="teachback"
              doc={doc}
              language={language}
              concept={concept}
              voice={voice}
              autoSpeak={autoSpeak}
              onEvaluated={(res) => setDifficulty(res.difficulty.current)}
            />
          )}

          {step === 'practice' && doc && (
            <PracticeStep
              key="practice"
              doc={doc}
              language={language}
              concept={concept}
              difficulty={difficulty}
              voice={voice}
            />
          )}

          {step === 'progress' && doc && (
            <ProgressStep key="progress" doc={doc} judgeMode={judgeMode} />
          )}
        </AnimatePresence>

        {!doc && step !== 'upload' && (
          <Card>
            <p className="text-sm text-muted">Upload a textbook page first.</p>
          </Card>
        )}
      </main>
    </div>
  )
}
