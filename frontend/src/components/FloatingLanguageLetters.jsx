import { useEffect, useRef } from 'react'
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'

/**
 * Signature hero decoration: regional-language words drifting gently in
 * layered 3D, tilting toward the cursor. Built on framer-motion springs
 * rather than a 3D engine — "lightweight" was explicit in the brief, and a
 * handful of floating words doesn't need WebGL.
 *
 * Depth controls both how far a word travels under parallax and how long its
 * independent float loop takes, so nearer words feel snappier and farther
 * ones feel slower — the layering that reads as depth.
 */
const WORDS = [
  { text: 'தமிழ்', top: '14%', left: '9%', size: 'text-3xl sm:text-4xl', depth: 16, accent: true },
  { text: 'हिन्दी', top: '66%', left: '7%', size: 'text-2xl sm:text-3xl', depth: 26 },
  { text: 'తెలుగు', top: '18%', left: '84%', size: 'text-2xl sm:text-3xl', depth: 20, accent: true },
  { text: 'ಕನ್ನಡ', top: '74%', left: '85%', size: 'text-xl sm:text-2xl', depth: 32 },
  { text: 'മലയാളം', top: '46%', left: '3%', size: 'text-lg sm:text-xl', depth: 36 },
  { text: 'বাংলা', top: '9%', left: '52%', size: 'text-lg sm:text-xl', depth: 22 },
  { text: 'मराठी', top: '86%', left: '46%', size: 'text-lg sm:text-xl', depth: 30 },
  { text: 'ગુજરાતી', top: '52%', left: '93%', size: 'text-base sm:text-lg', depth: 28 },
]

function Letter({ text, top, left, size, depth, accent, sx, sy }) {
  const x = useTransform(sx, (v) => v * depth)
  const y = useTransform(sy, (v) => v * depth)
  const rotateY = useTransform(sx, (v) => v * 8)
  const rotateX = useTransform(sy, (v) => v * -8)

  return (
    <motion.div
      style={{ top, left, x, y, rotateX, rotateY }}
      className={`absolute select-none font-semibold ${size} ${
        accent ? 'text-[#007AFF]/[0.14]' : 'text-[#1D1D1F]/[0.08]'
      }`}
    >
      <motion.span
        className="block"
        animate={{ y: [0, -14, 0] }}
        transition={{
          duration: 4.5 + (depth % 5),
          repeat: Infinity,
          ease: 'easeInOut',
          delay: (depth % 3) * 0.4,
        }}
      >
        {text}
      </motion.span>
    </motion.div>
  )
}

export function FloatingLanguageLetters() {
  const containerRef = useRef(null)
  const mx = useMotionValue(0)
  const my = useMotionValue(0)
  const sx = useSpring(mx, { stiffness: 45, damping: 20, mass: 0.6 })
  const sy = useSpring(my, { stiffness: 45, damping: 20, mass: 0.6 })

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (prefersReducedMotion) return

    function handleMove(e) {
      const el = containerRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      // Normalised to roughly -0.5..0.5 so `depth` reads directly as pixels.
      mx.set((e.clientX - rect.left) / rect.width - 0.5)
      my.set((e.clientY - rect.top) / rect.height - 0.5)
    }
    window.addEventListener('mousemove', handleMove)
    return () => window.removeEventListener('mousemove', handleMove)
  }, [mx, my])

  return (
    <div
      ref={containerRef}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 overflow-hidden [perspective:1400px]"
    >
      {WORDS.map((w) => (
        <Letter key={w.text} {...w} sx={sx} sy={sy} />
      ))}
    </div>
  )
}
