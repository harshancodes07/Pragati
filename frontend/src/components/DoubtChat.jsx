import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { api, LANGUAGES } from '../api'

function TypingDots() {
  return (
    <div className="flex gap-1 px-1 py-1">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-muted"
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
        />
      ))}
    </div>
  )
}

/** The message list + input box shared by the floating popup and the
 * standalone Recent Chats restore panel — same look, same send logic. */
function ChatPanel({ messages, busy, error, input, setInput, onSend, listRef }) {
  return (
    <>
      <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {messages.length === 0 && (
          <p className="text-xs text-muted">
            Confused about something above? Ask here — I'll answer using this
            explanation and your textbook.
          </p>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
                m.role === 'user' ? 'bg-saffron/15 text-[#1D1D1F]' : 'bg-raised text-[#1D1D1F]'
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}

        {busy && (
          <div className="flex justify-start">
            <div className="rounded-xl bg-raised px-1">
              <TypingDots />
            </div>
          </div>
        )}
      </div>

      {error && <p className="px-4 pb-1 text-xs text-alert">{error}</p>}

      <div className="flex items-center gap-2 border-t border-line p-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSend()}
          placeholder="Type your doubt…"
          className="flex-1 rounded-lg border border-line bg-white px-3 py-2 text-sm
            outline-none placeholder:text-muted focus:border-saffron"
        />
        <button
          onClick={onSend}
          disabled={busy || !input.trim()}
          title="Send"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-saffron
            text-white transition hover:brightness-110 disabled:cursor-not-allowed
            disabled:opacity-40"
        >
          ➤
        </button>
      </div>
    </>
  )
}

/**
 * Wraps one generated explanation with a floating doubt-chat bubble anchored
 * to its bottom-right corner. Conversation state lives here and only here —
 * closing the popup "minimizes" it (the thread survives); unmounting the
 * wrapped explanation (a new Ask, a new Teach Back attempt) starts fresh,
 * which is correct: a doubt thread belongs to the explanation it was asked
 * about, not to the page as a whole.
 *
 * Every exchange is persisted server-side under a chat_id (Recent Chats), so
 * `onChatSaved` fires whenever that id is created or a message is appended.
 */
export function DoubtChat({
  children, concept, explanation, language, documentId, sessionId, onChatSaved,
}) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [chatId, setChatId] = useState(null)
  const listRef = useRef(null)

  useEffect(() => {
    if (open && listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages, busy, open])

  async function send() {
    const text = input.trim()
    if (!text || busy) return

    const next = [...messages, { role: 'user', content: text }]
    setMessages(next)
    setInput('')
    setError(null)
    setBusy(true)
    try {
      const res = await api.doubt({
        document_id: documentId,
        session_id: sessionId,
        chat_id: chatId,
        concept,
        explanation,
        language,
        messages: next,
      })
      setMessages((m) => [...m, { role: 'assistant', content: res.answer }])
      setChatId(res.chat_id)
      onChatSaved?.(res.chat_id)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative">
      {children}

      <button
        onClick={() => setOpen((v) => !v)}
        title={open ? 'Minimize' : 'Ask a doubt about this'}
        className="absolute -bottom-3 -right-3 z-30 flex h-11 w-11 items-center justify-center
          rounded-full bg-saffron text-lg text-white shadow-lg shadow-saffron/30 transition
          hover:brightness-110"
      >
        {open ? '✕' : '💬'}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.96 }}
            transition={{ duration: 0.15 }}
            className="glass-strong absolute bottom-12 right-0 z-40 flex h-96 w-[min(22rem,88vw)]
              flex-col overflow-hidden rounded-2xl"
          >
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <span>🤖</span> Ask a doubt
              </div>
              <button
                onClick={() => setOpen(false)}
                title="Minimize"
                className="text-muted hover:text-[#1D1D1F]"
              >
                −
              </button>
            </div>

            <ChatPanel
              messages={messages}
              busy={busy}
              error={error}
              input={input}
              setInput={setInput}
              onSend={send}
              listRef={listRef}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/**
 * Full-screen restore view for a saved Recent Chat: same panel as the
 * floating popup, preloaded with the stored thread and context, so the
 * student can pick a doubt conversation back up from where they left it.
 */
export function RestoredChatModal({ chat, onClose }) {
  const [messages, setMessages] = useState(chat.messages)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const listRef = useRef(null)

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages, busy])

  async function send() {
    const text = input.trim()
    if (!text || busy) return

    const next = [...messages, { role: 'user', content: text }]
    setMessages(next)
    setInput('')
    setError(null)
    setBusy(true)
    try {
      const res = await api.doubt({
        document_id: chat.document_id,
        session_id: chat.session_id,
        chat_id: chat.id,
        concept: chat.concept,
        explanation: chat.explanation,
        language: chat.language,
        messages: next,
      })
      setMessages((m) => [...m, { role: 'assistant', content: res.answer }])
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <motion.div
        initial={{ opacity: 0, y: 10, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.97 }}
        transition={{ duration: 0.15 }}
        className="glass-strong flex h-[32rem] w-full max-w-lg flex-col overflow-hidden rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm font-medium">
              <span>🤖</span> <span className="truncate">{chat.title}</span>
            </div>
            <p className="mt-0.5 text-xs text-muted">
              {LANGUAGES.find((l) => l.id === chat.language)?.label || chat.language}
            </p>
          </div>
          <button onClick={onClose} title="Close" className="text-muted hover:text-[#1D1D1F]">
            ✕
          </button>
        </div>

        <ChatPanel
          messages={messages}
          busy={busy}
          error={error}
          input={input}
          setInput={setInput}
          onSend={send}
          listRef={listRef}
        />
      </motion.div>
    </div>
  )
}
