import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { Badge, Card } from './common'

/**
 * The results dashboard for Teach Back.
 *
 * This is the moment the student finds out whether their thinking held up, so
 * it is deliberately staged rather than dumped: the ring counts up, the bars
 * grow in sequence. It should read as a tutor responding to them, not an exam
 * result appearing.
 */

const BANDS = [
  { min: 85, label: 'Excellent', tone: 'good', color: 'var(--color-leaf)' },
  { min: 70, label: 'Strong', tone: 'good', color: 'var(--color-leaf)' },
  { min: 55, label: 'Good', tone: 'warn', color: 'var(--color-saffron)' },
  { min: 0, label: 'Needs Improvement', tone: 'bad', color: 'var(--color-warn)' },
]

const band = (score) => BANDS.find((b) => score >= b.min) ?? BANDS[BANDS.length - 1]

const METRICS = [
  { key: 'concept', icon: '🧠', label: 'Concept Understanding' },
  { key: 'clarity', icon: '💬', label: 'Clarity' },
  { key: 'completeness', icon: '📚', label: 'Completeness' },
  { key: 'examples', icon: '💡', label: 'Explanation & Examples' },
]

/** Counts from 0 to `value` so the number feels earned rather than stamped. */
function useCountUp(value, duration = 900) {
  const [shown, setShown] = useState(0)

  useEffect(() => {
    let frame
    const start = performance.now()
    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1)
      // ease-out cubic: fast then settling, which reads as "landing" on a score
      setShown(Math.round(value * (1 - Math.pow(1 - t, 3))))
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [value, duration])

  return shown
}

function ScoreRing({ score, marks }) {
  const shown = useCountUp(score)
  const { label, color } = band(score)

  const radius = 66
  const circumference = 2 * Math.PI * radius

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative h-40 w-40">
        <svg className="h-full w-full -rotate-90" viewBox="0 0 160 160">
          <circle
            cx="80" cy="80" r={radius}
            className="stroke-raised" strokeWidth="12" fill="none"
          />
          <motion.circle
            cx="80" cy="80" r={radius}
            stroke={color} strokeWidth="12" fill="none" strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference * (1 - score / 100) }}
            transition={{ duration: 0.9, ease: 'easeOut' }}
          />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-4xl font-semibold tabular-nums">{shown}</span>
          <span className="text-xs text-muted">out of 100</span>
        </div>
      </div>

      <Badge tone={band(score).tone}>{label}</Badge>

      {marks != null && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="rounded-xl border border-line bg-ink/60 px-4 py-2 text-center"
        >
          <div className="text-xl font-semibold text-saffron tabular-nums">
            {marks} / 5
          </div>
          <div className="text-[11px] uppercase tracking-wide text-muted">
            exam marks
          </div>
        </motion.div>
      )}
    </div>
  )
}

function MetricBar({ icon, label, value, delay }) {
  const { color } = band(value)

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 text-slate-300">
          <span>{icon}</span>
          {label}
        </span>
        <span className="font-mono text-xs text-muted tabular-nums">{value}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-raised">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.7, delay, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}

export function ScoreDashboard({ scores, marks, misconceptions, indic }) {
  const hasMisconceptions = misconceptions?.length > 0

  return (
    <Card className="space-y-6">
      <div className="flex flex-col items-center gap-8 sm:flex-row sm:items-center">
        <ScoreRing score={scores.overall} marks={marks} />

        <div className="w-full flex-1 space-y-4">
          {METRICS.map((m, i) => (
            <MetricBar
              key={m.key}
              icon={m.icon}
              label={m.label}
              value={scores[m.key]}
              delay={0.15 + i * 0.1}
            />
          ))}
        </div>
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.7 }}
        className={`flex items-center gap-2.5 rounded-xl border px-4 py-3 text-sm ${
          hasMisconceptions
            ? 'border-alert/40 bg-alert/10 text-alert'
            : 'border-leaf/30 bg-leaf/5 text-leaf'
        }`}
      >
        <span>{hasMisconceptions ? '⚠' : '✓'}</span>
        <span className={indic ? 'script-indic' : ''}>
          {hasMisconceptions
            ? `Misconception detected — ${misconceptions.length} thing${
                misconceptions.length === 1 ? '' : 's'
              } to fix below`
            : 'No major misconceptions'}
        </span>
      </motion.div>
    </Card>
  )
}
