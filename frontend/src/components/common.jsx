import { motion } from 'framer-motion'

export function Card({ children, className = '' }) {
  return (
    <div className={`glass rounded-2xl p-7 sm:p-8 ${className}`}>
      {children}
    </div>
  )
}

export function Button({ children, variant = 'primary', className = '', ...props }) {
  const styles = {
    primary: 'bg-saffron text-white shadow-lg shadow-saffron/25 hover:brightness-110 font-semibold',
    ghost: 'border border-line text-[#1D1D1F] hover:bg-raised',
    subtle: 'text-muted hover:text-[#1D1D1F]',
  }[variant]

  return (
    <button
      className={`rounded-xl px-6 py-3.5 text-[15px] transition disabled:cursor-not-allowed
        disabled:opacity-40 ${styles} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

export function Spinner({ label }) {
  return (
    <div className="flex items-center gap-3 text-sm text-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-saffron" />
      {label}
    </div>
  )
}

export function Skeleton({ lines = 3 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-3 animate-pulse rounded bg-raised"
          style={{ width: `${100 - i * 12}%` }}
        />
      ))}
    </div>
  )
}

export function ErrorNote({ children, onRetry }) {
  if (!children) return null
  return (
    <div className="rounded-xl border border-alert/40 bg-alert/10 px-4 py-3 text-sm text-alert">
      <div>{children}</div>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 underline underline-offset-2">
          Try again
        </button>
      )}
    </div>
  )
}

export function Badge({ children, tone = 'muted' }) {
  const tones = {
    muted: 'bg-raised text-muted',
    good: 'bg-leaf/15 text-leaf',
    warn: 'bg-warn/15 text-warn',
    bad: 'bg-alert/15 text-alert',
    brand: 'bg-saffron/15 text-saffron',
  }[tone]
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${tones}`}>
      {children}
    </span>
  )
}

export const fadeUp = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.25 },
}

export function Reveal({ children, className = '' }) {
  return (
    <motion.div {...fadeUp} className={className}>
      {children}
    </motion.div>
  )
}
