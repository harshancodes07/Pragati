import { useEffect, useId, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { SPEAK_PROMPT, api } from '../api'
import * as player from '../speech'

/**
 * Hold-free mic: click to start, click to stop. On stop the clip goes to
 * /api/stt and the transcript is handed back via onText.
 */
export function MicButton({ onText, language, disabled }) {
  const [state, setState] = useState('idle') // idle | recording | sending
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState(null)
  const recorder = useRef(null)
  const chunks = useRef([])
  const timer = useRef(null)

  // A component unmounting mid-recording must not leave the mic light on.
  useEffect(() => {
    return () => {
      clearInterval(timer.current)
      const rec = recorder.current
      if (rec && rec.state !== 'inactive') {
        rec.stop()
        rec.stream.getTracks().forEach((t) => t.stop())
      }
    }
  }, [])

  async function start() {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      chunks.current = []

      rec.ondataavailable = (e) => e.data.size > 0 && chunks.current.push(e.data)
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        clearInterval(timer.current)
        const blob = new Blob(chunks.current, { type: rec.mimeType || 'audio/webm' })
        if (!blob.size) {
          setState('idle')
          return
        }
        setState('sending')
        try {
          const res = await api.stt({ blob: await player.toWav(blob), language })
          if (res.text) onText(res.text)
          else setError("Didn't catch that — try again.")
        } catch (e) {
          setError(e.message)
        } finally {
          setState('idle')
        }
      }

      recorder.current = rec
      rec.start()
      setSeconds(0)
      setState('recording')
      timer.current = setInterval(() => setSeconds((s) => s + 1), 1000)
    } catch (e) {
      setError(
        e.name === 'NotAllowedError'
          ? 'Microphone blocked — allow it in your browser settings.'
          : 'No microphone found.',
      )
      setState('idle')
    }
  }

  function stopRecording() {
    if (recorder.current?.state === 'recording') recorder.current.stop()
  }

  const recording = state === 'recording'

  return (
    <div className="flex flex-col items-start gap-1">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={recording ? stopRecording : start}
          disabled={disabled || state === 'sending'}
          title={recording ? 'Stop and transcribe' : 'Speak your answer'}
          className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm transition
            disabled:cursor-not-allowed disabled:opacity-40 ${
              recording
                ? 'border-saffron bg-saffron/10 text-saffron'
                : 'border-line text-muted hover:border-muted hover:text-slate-200'
            }`}
        >
          {recording ? (
            <motion.span
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 1.2, repeat: Infinity }}
              className="h-2.5 w-2.5 rounded-full bg-saffron"
            />
          ) : (
            <span>🎙</span>
          )}
          {state === 'sending'
            ? 'Transcribing…'
            : recording
              ? `Stop · ${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(
                  seconds % 60,
                ).padStart(2, '0')}`
              : 'Speak'}
        </button>

        {recording && (
          <span className="text-xs text-muted">{SPEAK_PROMPT[language]}</span>
        )}
      </div>

      {error && <span className="text-xs text-alert">{error}</span>}
    </div>
  )
}

/** Reads a piece of AI text aloud. Clicking while it plays stops it. */
export function SpeakButton({ text, language, label = 'Listen', autoPlay = false }) {
  const id = useId()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [playingFor, setPlayingFor] = useState(null)

  useEffect(() => player.subscribe(setPlayingFor), [])

  const playing = playingFor === id

  async function speak() {
    if (playing) {
      player.stop()
      return
    }
    setError(null)
    setBusy(true)
    try {
      const res = await api.tts({ text, language })
      player.play(res.clips, id)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  // Auto-speak: fires once per distinct piece of text when the toggle is on.
  useEffect(() => {
    if (autoPlay && text) speak()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoPlay, text])

  if (!text) return null

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={speak}
        disabled={busy}
        title={playing ? 'Stop' : 'Read this aloud'}
        className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs transition
          disabled:opacity-50 ${
            playing
              ? 'bg-saffron/15 text-saffron'
              : 'text-muted hover:bg-raised hover:text-slate-200'
          }`}
      >
        {busy ? (
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-line border-t-saffron" />
        ) : (
          <span>{playing ? '■' : '🔊'}</span>
        )}
        {busy ? 'Loading…' : playing ? 'Stop' : label}
      </button>
      {error && <span className="text-xs text-alert">{error}</span>}
    </div>
  )
}
