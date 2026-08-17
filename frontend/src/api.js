const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options)
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

  upload: ({ file, text, title, language }) => {
    const form = new FormData()
    if (file) form.append('file', file)
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
  practice: (body) => request('/practice', json(body)),
  submitPractice: (body) => request('/practice/submit', json(body)),
  progress: (sessionId) => request(`/progress/${sessionId}`),
}

export const LANGUAGES = [
  { id: 'tanglish', label: 'Tanglish', hint: 'Tamil in English letters' },
  { id: 'tamil', label: 'தமிழ்', hint: 'Tamil script' },
  { id: 'english', label: 'English', hint: 'Simple English' },
  { id: 'hindi', label: 'हिन्दी', hint: 'Hindi' },
  { id: 'telugu', label: 'తెలుగు', hint: 'Telugu' },
  { id: 'malayalam', label: 'മലയാളം', hint: 'Malayalam' },
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
