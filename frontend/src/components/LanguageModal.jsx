import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { LANGUAGES } from '../api'

/**
 * Shown right after a successful upload, and again whenever the student wants
 * to switch languages. Blocks the rest of the app behind a backdrop until a
 * language is confirmed, since every downstream step (Learn, Teach Back,
 * Practice) reads this choice directly.
 */
export function LanguageModal({ open, current, onSelect, onClose, dismissible }) {
  const [picked, setPicked] = useState(current)

  if (!open) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
        onClick={() => dismissible && onClose?.()}
      >
        <motion.div
          initial={{ opacity: 0, y: 12, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 12, scale: 0.98 }}
          transition={{ duration: 0.2 }}
          onClick={(e) => e.stopPropagation()}
          className="w-full max-w-lg rounded-2xl border border-line bg-surface p-6 shadow-2xl"
        >
          <div className="mb-1 text-2xl">🌐</div>
          <h2 className="text-xl font-semibold">Which language would you like to learn in?</h2>
          <p className="mt-1 text-sm text-muted">
            Choose the language for AI explanations, Teach Back and practice.
            Your upload itself stays exactly as you gave it.
          </p>

          <div className="mt-5 grid grid-cols-2 gap-2.5 sm:grid-cols-3">
            {LANGUAGES.map((l) => {
              const active = picked === l.id
              return (
                <button
                  key={l.id}
                  onClick={() => setPicked(l.id)}
                  className={`rounded-xl border p-3 text-left transition ${
                    active
                      ? 'border-saffron bg-saffron/10'
                      : 'border-line hover:border-muted hover:bg-raised/50'
                  }`}
                >
                  <div className="text-lg">{l.flag}</div>
                  <div className={`mt-1 text-sm font-medium ${active ? 'text-saffron' : 'text-[#1D1D1F]'}`}>
                    {l.label}
                  </div>
                  <div className="text-[11px] text-muted">{l.hint}</div>
                </button>
              )
            })}
          </div>

          <div className="mt-6 flex items-center justify-between gap-3">
            {dismissible ? (
              <button onClick={onClose} className="text-sm text-muted hover:text-[#1D1D1F]">
                Cancel
              </button>
            ) : (
              <span />
            )}
            <button
              onClick={() => onSelect(picked)}
              disabled={!picked}
              className="rounded-xl bg-saffron px-6 py-2.5 text-sm font-semibold text-white
                transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Continue
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
