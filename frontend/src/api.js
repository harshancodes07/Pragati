// In dev, Vite proxies /api to localhost:8000 (see vite.config.js) so a
// relative path works. In production the frontend and backend are deployed
// separately (Vercel + Railway), so VITE_API_URL points at the backend's
// public domain — set it in Vercel's project env vars, no trailing slash.
const BASE = `${import.meta.env.VITE_API_URL || ''}/api`

// Set once at login (and restored from localStorage on load) so every call
// below carries it automatically — callers never pass it explicitly.
let authToken = null
export function setAuthToken(token) {
  authToken = token
}

// Fired when a call comes back 401 — App listens for this to drop back to
// the login screen (an expired/invalid token, not a per-call error to handle).
export const AUTH_EVENT = 'pragati:unauthorized'

async function request(path, options = {}) {
  const headers = { ...options.headers }
  if (authToken) headers.Authorization = `Bearer ${authToken}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (res.status === 401) {
    window.dispatchEvent(new Event(AUTH_EVENT))
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (body.detail) detail = body.detail
    } catch { /* non-JSON error body */ }
    throw new Error(detail)
  }
  return res.json()
}

const json = (body) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  health: () => request('/health'),
  stats: () => request('/stats'),
  loginWithGoogle: (credential) => request('/auth/google', json({ credential })),

  upload: ({ files, text, title, language }) => {
    const form = new FormData()
    if (files?.length) files.forEach((f) => form.append('files', f))
    if (text) form.append('text', text)
    if (title) form.append('title', title)
    form.append('language', language)
    return request('/upload', { method: 'POST', body: form })
  },

  stt: ({ blob, language }) => {
    const form = new FormData()
    // Sarvam validates on the declared type, so the name must match the bytes.
    const ext = (blob.type.split('/')[1] || 'wav').split(';')[0]
    form.append('file', blob, `recording.${ext}`)
    form.append('language', language)
    return request('/stt', { method: 'POST', body: form })
  },
  tts: (body) => request('/tts', json(body)),

  ask: (body) => request('/ask', json(body)),
  teachBack: (body) => request('/teachback', json(body)),
  doubt: (body) => request('/doubt', json(body)),
  practice: (body) => request('/practice', json(body)),
  submitPractice: (body) => request('/practice/submit', json(body)),
  progress: (sessionId) => request(`/progress/${sessionId}`),

  listChats: (sessionId) =>
    request(`/chats${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''}`),
  getChat: (chatId) => request(`/chats/${chatId}`),
}

export const LANGUAGES = [
  { id: 'tanglish', label: 'Tanglish', hint: 'Tamil in English letters', flag: '🔤' },
  { id: 'tamil', label: 'தமிழ்', hint: 'Tamil script', flag: '🇮🇳' },
  { id: 'english', label: 'English', hint: 'Simple English', flag: '🇬🇧' },
  { id: 'hindi', label: 'हिन्दी', hint: 'Hindi', flag: '🇮🇳' },
  { id: 'telugu', label: 'తెలుగు', hint: 'Telugu', flag: '🇮🇳' },
  { id: 'malayalam', label: 'മലയാളം', hint: 'Malayalam', flag: '🇮🇳' },
]

// Indic scripts need looser line height; Tanglish and English do not.
export const isIndicScript = (lang) =>
  ['tamil', 'hindi', 'telugu', 'malayalam'].includes(lang)

// Shown while recording, so the student knows which language to speak.
export const SPEAK_PROMPT = {
  tanglish: 'Speak in Tamil — it comes back in English letters',
  tamil: 'Speak in Tamil',
  english: 'Speak in English',
  hindi: 'Speak in Hindi',
  telugu: 'Speak in Telugu',
  malayalam: 'Speak in Malayalam',
}
