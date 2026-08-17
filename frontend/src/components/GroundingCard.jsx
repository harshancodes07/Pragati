import { motion, AnimatePresence } from 'framer-motion'
import { Badge } from './common'

/**
 * The grounding card is the single most important UI element in the product:
 * it is what makes "this came from YOUR book" visible to a judge. Judge mode
 * additionally exposes the retrieval scores and the threshold decision.
 */
export function GroundingCard({ sources, retrieval, grounded, judgeMode }) {
  const hasSources = sources && sources.length > 0

  if (!grounded) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="rounded-xl border border-warn/40 bg-warn/10 p-4"
      >
        <div className="flex items-center gap-2 text-sm font-medium text-warn">
          <span>⚠</span> Not in your textbook
        </div>
        <p className="mt-1 text-sm text-muted">
          Bodhi only answers from the book you uploaded, so it refused this one.
        </p>
        {judgeMode && retrieval && (
          <ScoreDetail retrieval={retrieval} refused />
        )}
      </motion.div>
    )
  }

  if (!hasSources) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-leaf/30 bg-leaf/5 p-4"
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium text-leaf">
          <span>📖</span> From your textbook
        </div>
        <Badge tone="good">grounded</Badge>
      </div>

      <div className="space-y-2.5">
        {sources.map((s) => (
          <div key={s.chunk_id} className="rounded-lg bg-ink/50 p-3">
            <div className="mb-1.5 flex items-center gap-2 text-xs text-muted">
              <span className="font-semibold text-slate-300">Page {s.page}</span>
              {judgeMode && <span className="font-mono">score {s.score}</span>}
            </div>
            <p className="text-sm leading-relaxed text-slate-300">
              “{s.text.slice(0, 260)}
              {s.text.length > 260 ? '…' : ''}”
            </p>
          </div>
        ))}
      </div>

      <AnimatePresence>
        {judgeMode && retrieval && <ScoreDetail retrieval={retrieval} />}
      </AnimatePresence>
    </motion.div>
  )
}

function ScoreDetail({ retrieval, refused }) {
  const { max_score, threshold, reason } = retrieval
  const pct = Math.min(Math.max(max_score / Math.max(threshold * 2, 0.01), 0), 1) * 100
  const markerPct = 50 // threshold sits at the midpoint of the scale above

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="mt-3 overflow-hidden border-t border-line pt-3"
    >
      <div className="mb-2 flex justify-between font-mono text-xs text-muted">
        <span>best match {max_score}</span>
        <span>threshold {threshold}</span>
      </div>
      <div className="relative h-2 rounded-full bg-raised">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5 }}
          className={`h-2 rounded-full ${refused ? 'bg-warn' : 'bg-leaf'}`}
        />
        <div
          className="absolute top-[-3px] h-3.5 w-0.5 bg-slate-400"
          style={{ left: `${markerPct}%` }}
        />
      </div>
      <p className="mt-2 font-mono text-xs text-muted">
        {refused
          ? `below threshold → refused without spending an LLM call (${reason})`
          : `above threshold → sent to NIM (${reason})`}
      </p>
    </motion.div>
  )
}
