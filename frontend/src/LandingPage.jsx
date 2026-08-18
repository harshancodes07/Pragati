import { motion } from 'framer-motion'
import { FloatingLanguageLetters } from './components/FloatingLanguageLetters'
import { LANGUAGES } from './api'

/**
 * Marketing entry point, shown before the student ever touches the study
 * app. Deliberately a separate light-themed surface from the dark tutor UI
 * in App.jsx — that UI is preserved untouched; this page's only job is to
 * get a visitor to click "Start Learning".
 */

const fadeUp = {
  initial: { opacity: 0, y: 18 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-80px' },
  transition: { duration: 0.6, ease: 'easeOut' },
}

function Eyebrow({ children }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-[#E5E5EA] bg-[#F5F5F7] px-4 py-1.5 text-xs font-medium text-[#6E6E73]">
      {children}
    </span>
  )
}

function SectionHeader({ eyebrow, title, subtitle }) {
  return (
    <motion.div {...fadeUp} className="mx-auto max-w-2xl text-center">
      {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      <h2 className="mt-4 text-3xl font-semibold tracking-tight text-[#1D1D1F] sm:text-4xl">
        {title}
      </h2>
      {subtitle && <p className="mt-3 text-[15px] leading-relaxed text-[#6E6E73]">{subtitle}</p>}
    </motion.div>
  )
}

function StepCard({ index, icon, title, text, delay }) {
  return (
    <motion.div
      {...fadeUp}
      transition={{ ...fadeUp.transition, delay }}
      className="rounded-2xl border border-[#E5E5EA] bg-white p-7 shadow-[0_1px_2px_rgba(0,0,0,0.04)]"
    >
      <div className="flex items-center justify-between">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#F5F5F7] text-xl">
          {icon}
        </div>
        <span className="text-xs font-semibold tracking-wide text-[#6E6E73]">{index}</span>
      </div>
      <h3 className="mt-5 text-lg font-semibold text-[#1D1D1F]">{title}</h3>
      <p className="mt-2 text-[14px] leading-relaxed text-[#6E6E73]">{text}</p>
    </motion.div>
  )
}

function FeatureCard({ icon, title, text, delay }) {
  return (
    <motion.div
      {...fadeUp}
      transition={{ ...fadeUp.transition, delay }}
      className="rounded-2xl border border-[#E5E5EA] bg-white p-6 transition hover:shadow-[0_4px_20px_rgba(0,0,0,0.06)]"
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#007AFF]/10 text-lg">
        {icon}
      </div>
      <h3 className="mt-4 text-[15px] font-semibold text-[#1D1D1F]">{title}</h3>
      <p className="mt-1.5 text-[13.5px] leading-relaxed text-[#6E6E73]">{text}</p>
    </motion.div>
  )
}

function DemoCard({ tag, tagColor, title, children, delay }) {
  return (
    <motion.div
      {...fadeUp}
      transition={{ ...fadeUp.transition, delay }}
      className="flex-1 rounded-2xl border border-[#E5E5EA] bg-white p-6"
    >
      <span
        className="inline-block rounded-full px-2.5 py-1 text-[11px] font-medium"
        style={{ backgroundColor: `${tagColor}1A`, color: tagColor }}
      >
        {tag}
      </span>
      <h4 className="mt-3 text-sm font-semibold text-[#1D1D1F]">{title}</h4>
      <p className="mt-2 text-[13.5px] leading-relaxed text-[#6E6E73]">{children}</p>
    </motion.div>
  )
}

const DEMO_ARROW = (
  <div className="flex items-center justify-center px-1 text-[#6E6E73] sm:rotate-0 max-sm:rotate-90">
    →
  </div>
)

const SUPPORTED_LANGUAGES = LANGUAGES.filter((l) => l.id !== 'tanglish')

export function LandingPage({ onStart }) {
  return (
    <div className="min-h-screen bg-white text-[#1D1D1F] antialiased">
      {/* Nav */}
      <header className="sticky top-0 z-30 border-b border-[#E5E5EA]/70 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2.5">
            <img src="/logo-512.png" alt="Pragati" className="h-9 w-9 rounded-xl object-contain" />
            <div className="leading-tight">
              <div className="text-[15px] font-semibold tracking-tight">Pragati</div>
              <div className="text-[11px] text-[#6E6E73]">பிரகதி</div>
            </div>
          </div>

          <nav className="hidden items-center gap-8 text-sm text-[#6E6E73] sm:flex">
            <a href="#how" className="transition hover:text-[#1D1D1F]">How it works</a>
            <a href="#demo" className="transition hover:text-[#1D1D1F]">Demo</a>
            <a href="#features" className="transition hover:text-[#1D1D1F]">Features</a>
          </nav>

          <button
            onClick={onStart}
            className="rounded-full bg-[#007AFF] px-5 py-2 text-sm font-medium text-white
              transition hover:brightness-110"
          >
            Start Learning
          </button>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden px-6 pb-28 pt-24 text-center sm:pt-32">
        <FloatingLanguageLetters />

        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: 'easeOut' }}
          className="relative mx-auto max-w-3xl"
        >
          <Eyebrow>🇮🇳 Built for India's regional-language students</Eyebrow>

          <h1 className="mt-6 text-[2.75rem] font-semibold leading-[1.08] tracking-tight text-[#1D1D1F] sm:text-6xl">
            Learn in your language.
            <br />
            Understand without limits.
          </h1>

          <p className="mx-auto mt-6 max-w-xl text-[17px] leading-relaxed text-[#6E6E73]">
            AI-powered explanations that make complex concepts easy to understand in the
            language that feels natural to you.
          </p>

          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <button
              onClick={onStart}
              className="rounded-full bg-[#007AFF] px-7 py-3.5 text-[15px] font-medium text-white
                shadow-lg shadow-[#007AFF]/20 transition hover:brightness-110"
            >
              Start Learning
            </button>
            <a
              href="#how"
              className="rounded-full border border-[#E5E5EA] bg-white px-7 py-3.5 text-[15px]
                font-medium text-[#1D1D1F] transition hover:bg-[#F5F5F7]"
            >
              See How It Works
            </a>
          </div>
        </motion.div>
      </section>

      {/* How it works */}
      <section id="how" className="mx-auto max-w-6xl px-6 py-24">
        <SectionHeader
          eyebrow="How it works"
          title="Three steps to understanding"
          subtitle="No setup, no account juggling — upload a page and start learning in minutes."
        />
        <div className="mt-14 grid gap-6 sm:grid-cols-3">
          <StepCard
            index="01"
            icon="📤"
            title="Upload"
            text="A photo of a page, a PDF, or pasted text — straight from your own textbook."
            delay={0}
          />
          <StepCard
            index="02"
            icon="🧠"
            title="Understand"
            text="Pragati explains the concept clearly, grounded strictly in what you uploaded."
            delay={0.1}
          />
          <StepCard
            index="03"
            icon="💬"
            title="Ask"
            text="Follow up with doubts anytime and get an answer in your own language, instantly."
            delay={0.2}
          />
        </div>
      </section>

      {/* AI Explanation Demo */}
      <section id="demo" className="bg-[#F5F5F7] px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <SectionHeader
            eyebrow="See it in action"
            title="From textbook to your language"
            subtitle="The same page transforms into something you actually understand."
          />
          <div className="mt-14 flex flex-col items-stretch gap-3 sm:flex-row">
            <DemoCard tag="Textbook content" tagColor="#6E6E73" title="Original passage" delay={0}>
              "Photosynthesis is the process by which green plants synthesise food using
              sunlight, water and carbon dioxide, releasing oxygen as a by-product."
            </DemoCard>
            {DEMO_ARROW}
            <DemoCard tag="Simple AI explanation" tagColor="#007AFF" title="In plain English" delay={0.1}>
              Plants make their own food using sunlight. They take in water and carbon
              dioxide, and give out oxygen — the same oxygen we breathe.
            </DemoCard>
            {DEMO_ARROW}
            <DemoCard tag="Regional language" tagColor="#34C759" title="தமிழ் விளக்கம்" delay={0.2}>
              செடிகள் சூரிய ஒளியை பயன்படுத்தி தானாகவே உணவை உற்பத்தி செய்கின்றன. இதை
              ஒளிச்சேர்க்கை என்கிறோம்.
            </DemoCard>
          </div>
        </div>
      </section>

      {/* One platform, many languages */}
      <section className="mx-auto max-w-6xl px-6 py-24">
        <SectionHeader
          eyebrow="One platform"
          title="One Platform. Many Languages."
          subtitle="Pick the language that feels natural — every explanation, follow-up and
            practice question adapts to it."
        />
        <motion.div {...fadeUp} className="mt-12 flex flex-wrap items-center justify-center gap-3">
          {SUPPORTED_LANGUAGES.map((l) => (
            <span
              key={l.id}
              className="flex items-center gap-2 rounded-full border border-[#E5E5EA] bg-white
                px-4 py-2 text-sm font-medium text-[#1D1D1F] shadow-[0_1px_2px_rgba(0,0,0,0.04)]"
            >
              <span>{l.flag}</span>
              {l.label}
            </span>
          ))}
          <span className="rounded-full border border-dashed border-[#D2D2D7] px-4 py-2 text-sm text-[#6E6E73]">
            கன்னடம் · বাংলা · मराठी · ગુજરાતી — more on the way
          </span>
        </motion.div>
      </section>

      {/* Key features */}
      <section id="features" className="bg-[#F5F5F7] px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <SectionHeader eyebrow="Key features" title="Everything built around how you actually learn" />
          <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <FeatureCard
              icon="💡"
              title="AI Explanations"
              text="Concepts broken down clearly, grounded strictly in your own textbook."
              delay={0}
            />
            <FeatureCard
              icon="🌐"
              title="Regional Languages"
              text="Tamil, Hindi, Telugu, Malayalam and more — explained the way a real teacher would."
              delay={0.08}
            />
            <FeatureCard
              icon="💬"
              title="Follow-up AI Chat"
              text="Still confused? Ask a doubt right on the explanation and get an instant answer."
              delay={0.16}
            />
            <FeatureCard
              icon="📖"
              title="Textbook Understanding"
              text="Upload a photo, PDF or text — Pragati reads and teaches from exactly that."
              delay={0.24}
            />
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="px-6 py-28 text-center">
        <motion.div {...fadeUp} className="mx-auto max-w-2xl">
          <h2 className="text-3xl font-semibold tracking-tight text-[#1D1D1F] sm:text-4xl">
            Your language. Your learning.
            <br />
            Your Pragati.
          </h2>
          <button
            onClick={onStart}
            className="mt-8 rounded-full bg-[#007AFF] px-8 py-3.5 text-[15px] font-medium text-white
              shadow-lg shadow-[#007AFF]/20 transition hover:brightness-110"
          >
            Start Learning
          </button>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#E5E5EA] px-6 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 text-xs text-[#6E6E73] sm:flex-row">
          <span>Pragati · பிரகதி</span>
          <span>Learn. Understand. Grow.</span>
        </div>
      </footer>
    </div>
  )
}
