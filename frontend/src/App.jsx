import { useEffect, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { AUTH_EVENT, LANGUAGES, api, setAuthToken } from './api'
import { Badge, Card } from './components/common'
import { LanguageModal } from './components/LanguageModal'
import { RecentChats } from './components/RecentChats'
import { RestoredChatModal } from './components/DoubtChat'
import { LandingPage } from './LandingPage'
import { LoginPage } from './LoginPage'
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

function StudyApp({ user, onLogout }) {
  const [step, setStep] = useState('upload')
  const [language, setLanguage] = useState('tanglish')
  const [languageChosen, setLanguageChosen] = useState(false)
  const [languageModalOpen, setLanguageModalOpen] = useState(false)
  const [judgeMode, setJudgeMode] = useState(false)
  const [doc, setDoc] = useState(null)
  const [concept, setConcept] = useState('')
  const [difficulty, setDifficulty] = useState('medium')
  const [health, setHealth] = useState(null)
  const [autoSpeak, setAutoSpeak] = useState(
    () => localStorage.getItem('pragati.autoSpeak') === '1',
  )
  const [chatsRefresh, setChatsRefresh] = useState(0)
  const [restoredChat, setRestoredChat] = useState(null)

  async function openChat(chatId) {
    try {
      setRestoredChat(await api.getChat(chatId))
    } catch { /* chat may have expired; silently ignore */ }
  }

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: 'down' }))
  }, [])

  useEffect(() => {
    localStorage.setItem('pragati.autoSpeak', autoSpeak ? '1' : '0')
  }, [autoSpeak])

  // No Sarvam key on the backend means no mic and no speaker anywhere — the app
  // falls back to exactly what it was before voice existed.
  const voice = !!health?.speech?.configured

  const unlocked = (id) => id === 'upload' || !!doc

  return (
    <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-4 py-6
      sm:px-6 lg:flex-row lg:gap-10 lg:px-8 lg:py-12">
      {/* Step rail */}
      <aside className="w-full lg:w-64 lg:shrink-0">
        <div className="glass-strong space-y-5 rounded-2xl p-5 sm:p-6 lg:sticky lg:top-12 lg:space-y-6">
          <div className="flex items-center gap-3">
            <img src="/logo-512.png" alt="Pragati" className="h-10 w-10 rounded-xl object-contain" />
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">
                Pragati <span className="text-saffron">·</span> பிரகதி
              </h1>
              <p className="mt-1.5 text-sm text-muted">Your textbook, your language</p>
            </div>
          </div>

          {user && (
            <div className="flex items-center justify-between gap-2 rounded-xl border border-line
              bg-raised px-3 py-2">
              <div className="flex min-w-0 items-center gap-2">
                {user.picture ? (
                  <img src={user.picture} alt="" className="h-7 w-7 shrink-0 rounded-full" />
                ) : (
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full
                    bg-saffron/15 text-xs font-semibold text-saffron">
                    {(user.name || user.email || '?')[0].toUpperCase()}
                  </span>
                )}
                <span className="truncate text-sm text-[#1D1D1F]">{user.name || user.email}</span>
              </div>
              <button
                onClick={onLogout}
                title="Sign out"
                className="shrink-0 text-xs text-muted transition hover:text-alert"
              >
                Sign out
              </button>
            </div>
          )}

          {/* Horizontal scrolling pills on mobile (a full vertical stack would push
              everything else below the fold); reverts to a normal vertical list
              once there's room for a sidebar. */}
          <nav className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1
            lg:mx-0 lg:flex-col lg:gap-1.5 lg:overflow-visible lg:px-0 lg:pb-0">
            {STEPS.map((s) => {
              const active = step === s.id
              const open = unlocked(s.id)
              return (
                <button
                  key={s.id}
                  disabled={!open}
                  onClick={() => setStep(s.id)}
                  className={`flex shrink-0 items-center gap-3 rounded-xl px-4 py-3 text-[15px]
                    transition lg:w-full lg:shrink
                    ${
                      active
                        ? 'bg-saffron/15 font-medium text-saffron'
                        : open
                          ? 'text-muted hover:bg-raised hover:text-[#1D1D1F]'
                          : 'cursor-not-allowed text-line'
                    }`}
                >
                  <span className={`text-lg ${open ? '' : 'opacity-30'}`}>{s.icon}</span>
                  {s.label}
                </button>
              )
            })}
          </nav>

          <div className="space-y-3 border-t border-line pt-6">
            <label className="block text-xs font-semibold uppercase tracking-wide text-muted">
              Language
            </label>
            {languageChosen ? (
              <button
                onClick={() => setLanguageModalOpen(true)}
                className="flex w-full items-center justify-between rounded-xl border border-line
                  bg-raised px-4 py-3 text-sm transition hover:border-saffron"
              >
                <span>
                  {LANGUAGES.find((l) => l.id === language)?.flag}{' '}
                  {LANGUAGES.find((l) => l.id === language)?.label}
                </span>
                <span className="text-xs font-medium text-saffron">Change</span>
              </button>
            ) : (
              <p className="text-xs text-muted">Chosen right after you upload.</p>
            )}

            {voice && (
              <button
                onClick={() => setAutoSpeak((v) => !v)}
                className={`w-full rounded-xl border px-4 py-2.5 text-xs transition ${
                  autoSpeak
                    ? 'border-saffron bg-saffron/10 text-saffron'
                    : 'border-line text-muted hover:text-[#1D1D1F]'
                }`}
              >
                {autoSpeak ? '🔊 Read answers aloud' : '🔇 Read answers aloud'}
              </button>
            )}

            <button
              onClick={() => setJudgeMode((v) => !v)}
              className={`w-full rounded-xl border px-4 py-2.5 text-xs transition ${
                judgeMode
                  ? 'border-saffron bg-saffron/10 text-saffron'
                  : 'border-line text-muted hover:text-[#1D1D1F]'
              }`}
            >
              {judgeMode ? '● Judge mode on' : '○ Judge mode'}
            </button>
          </div>

          {health && (
            <div className="space-y-1.5 border-t border-line pt-5 text-xs text-muted">
              <div className="flex items-center gap-1.5">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    health.status === 'ok' ? 'bg-leaf' : 'bg-alert'
                  }`}
                />
                NIM {health.status === 'ok' ? 'connected' : 'not connected'}
              </div>
              {judgeMode && health.nim?.model && (
                <div className="font-mono text-[10px] leading-tight">{health.nim.model}</div>
              )}
              <div className="flex items-center gap-1.5">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    voice ? 'bg-leaf' : 'bg-line'
                  }`}
                />
                Voice {voice ? 'ready' : 'off'}
              </div>
              {judgeMode && voice && health.speech?.detail && (
                <div className="font-mono text-[10px] leading-tight">{health.speech.detail}</div>
              )}
            </div>
          )}

          <RecentChats refreshKey={chatsRefresh} onSelect={openChat} />
        </div>
      </aside>

      {/* Content column */}
      <main className="min-w-0 flex-1">
        {doc && (
          <div className="mb-6 flex flex-wrap items-center gap-3 text-sm text-muted">
            <Badge tone="brand">{doc.title}</Badge>
            <span>
              {doc.file_count > 1 && `${doc.file_count} files · `}
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
                setLanguageModalOpen(true)
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
              onChatSaved={() => setChatsRefresh((n) => n + 1)}
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
              onChatSaved={() => setChatsRefresh((n) => n + 1)}
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

      <LanguageModal
        open={languageModalOpen}
        current={language}
        dismissible={languageChosen}
        onSelect={(id) => {
          setLanguage(id)
          setLanguageChosen(true)
          setLanguageModalOpen(false)
        }}
        onClose={() => setLanguageModalOpen(false)}
      />

      {restoredChat && (
        <RestoredChatModal chat={restoredChat} onClose={() => setRestoredChat(null)} />
      )}
    </div>
  )
}

// landing (marketing) -> login (Google sign-in) -> app (the study tools).
// A restored token skips straight to 'app'; a 401 from any API call (expired
// or invalid token) drops back to 'login', wherever the student was.
export default function App() {
  const [screen, setScreen] = useState('landing')
  const [user, setUser] = useState(null)

  useEffect(() => {
    const savedToken = localStorage.getItem('pragati.authToken')
    const savedUser = localStorage.getItem('pragati.authUser')
    if (savedToken && savedUser) {
      setAuthToken(savedToken)
      setUser(JSON.parse(savedUser))
      setScreen('app')
    }
  }, [])

  useEffect(() => {
    function handleUnauthorized() {
      localStorage.removeItem('pragati.authToken')
      localStorage.removeItem('pragati.authUser')
      setAuthToken(null)
      setUser(null)
      setScreen('login')
    }
    window.addEventListener(AUTH_EVENT, handleUnauthorized)
    return () => window.removeEventListener(AUTH_EVENT, handleUnauthorized)
  }, [])

  function handleLogin({ token, user: signedInUser }) {
    localStorage.setItem('pragati.authToken', token)
    localStorage.setItem('pragati.authUser', JSON.stringify(signedInUser))
    setAuthToken(token)
    setUser(signedInUser)
    setScreen('app')
  }

  function handleLogout() {
    localStorage.removeItem('pragati.authToken')
    localStorage.removeItem('pragati.authUser')
    setAuthToken(null)
    setUser(null)
    setScreen('landing')
  }

  if (screen === 'landing') {
    return <LandingPage onStart={() => setScreen('login')} />
  }

  if (screen === 'login') {
    return <LoginPage onLogin={handleLogin} onBack={() => setScreen('landing')} />
  }

  return <StudyApp user={user} onLogout={handleLogout} />
}
