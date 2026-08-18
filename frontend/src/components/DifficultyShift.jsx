import { motion } from 'framer-motion'

const LEVELS = ['easy', 'medium', 'hard']

/**
 * Difficulty adaptation is worth points only if the judge can SEE it happen,
 * so the change is animated and the rule that caused it is stated in words.
 */
export function DifficultyShift({ shift }) {
  if (!shift) return null
  const { previous, current, changed, reason } = shift

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-xl p-4"
    >
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">
          Difficulty
        </span>
        {changed && (
          <motion.span
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="rounded-full bg-saffron/15 px-2.5 py-1 text-xs font-medium text-saffron"
          >
            {LEVELS.indexOf(current) > LEVELS.indexOf(previous) ? '↑ levelled up' : '↓ eased off'}
          </motion.span>
        )}
      </div>

      <div className="flex gap-2">
        {LEVELS.map((level) => {
          const active = level === current
          const was = level === previous && changed
          return (
            <motion.div
              key={level}
              animate={{ scale: active ? 1 : 0.97 }}
              className={`flex-1 rounded-lg border px-3 py-2 text-center text-xs capitalize transition
                ${
                  active
                    ? 'border-saffron bg-saffron/15 font-semibold text-saffron'
                    : was
                      ? 'border-line bg-raised text-muted line-through'
                      : 'border-line text-muted'
                }`}
            >
              {level}
            </motion.div>
          )
        })}
      </div>

      <p className="mt-3 text-sm text-muted">{reason}</p>
    </motion.div>
  )
}
