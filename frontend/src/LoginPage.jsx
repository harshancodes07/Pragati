import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { api } from './api'

/**
 * Sits between the marketing landing page and the actual study app. Uses
 * Google Identity Services' button flow (loaded via a <script> tag in
 * index.html, not an npm package) — it hands back a signed ID token
 * client-side with no redirect, which the backend verifies and exchanges
 * for the app's own session token.
 */
export function LoginPage({ onLogin, onBack }) {
  const buttonRef = useRef(null)
  const [error, setError] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
    if (!clientId) {
      setError('Sign-in is not configured yet — VITE_GOOGLE_CLIENT_ID is missing.')
      return
    }

    let cancelled = false

    async function handleCredential(response) {
      try {
        const res = await api.loginWithGoogle(response.credential)
        if (!cancelled) onLogin(res)
      } catch (e) {
        if (!cancelled) setError(e.message)
      }
    }

    // The script tag loads async, so poll briefly rather than assuming
    // window.google exists the instant this component mounts.
    let attempts = 0
    const id = setInterval(() => {
      attempts += 1
      if (window.google?.accounts?.id) {
        clearInterval(id)
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: handleCredential,
        })
        if (buttonRef.current) {
          window.google.accounts.id.renderButton(buttonRef.current, {
            type: 'standard',
            theme: 'outline',
            size: 'large',
            shape: 'pill',
            width: 280,
          })
        }
        setReady(true)
      } else if (attempts > 100) {
        clearInterval(id)
        setError('Could not load Google Sign-In. Check your connection and try again.')
      }
    }, 100)

    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [onLogin])

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-6 text-[#1D1D1F] antialiased">
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="w-full max-w-sm rounded-2xl border border-[#E5E5EA] bg-white p-8 text-center
          shadow-[0_1px_2px_rgba(0,0,0,0.04)]"
      >
        <img src="/logo-512.png" alt="Pragati" className="mx-auto h-14 w-14 rounded-xl object-contain" />

        <h1 className="mt-5 text-2xl font-semibold tracking-tight">Sign in to Pragati</h1>
        <p className="mt-2 text-[14px] leading-relaxed text-[#6E6E73]">
          One quick sign-in, then straight into your textbook.
        </p>

        <div className="mt-7 flex min-h-[44px] items-center justify-center">
          {!ready && !error && (
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-[#E5E5EA] border-t-[#007AFF]" />
          )}
          <div ref={buttonRef} />
        </div>

        {error && (
          <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-600">
            {error}
          </p>
        )}

        <button
          onClick={onBack}
          className="mt-6 text-sm text-[#6E6E73] transition hover:text-[#1D1D1F]"
        >
          ← Back
        </button>
      </motion.div>
    </div>
  )
}
