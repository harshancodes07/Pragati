/**
 * Recording format conversion.
 *
 * MediaRecorder gives us WebM/Opus in Chrome and MP4 in Safari, and Sarvam
 * accepts neither — its live API takes wav/mp3/aac/pcm only, whatever the docs
 * claim. No browser records those natively, so we decode the clip and re-encode
 * it as 16 kHz mono WAV via the Web Audio API. Speech recognition gains nothing
 * from stereo or a 48 kHz rate, so this also cuts the upload by roughly 6x.
 */

const TARGET_RATE = 16000

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const str = (offset, s) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i))
  }

  str(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  str(8, 'WAVE')
  str(12, 'fmt ')
  view.setUint32(16, 16, true) // PCM header size
  view.setUint16(20, 1, true) // format: PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // byte rate
  view.setUint16(32, 2, true) // block align
  view.setUint16(34, 16, true) // bits per sample
  str(36, 'data')
  view.setUint32(40, samples.length * 2, true)

  let offset = 44
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const clamped = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true)
  }
  return new Blob([view], { type: 'audio/wav' })
}

/** Any recorded blob -> 16 kHz mono WAV that Sarvam will accept. */
export async function toWav(blob) {
  const Ctx = window.AudioContext || window.webkitAudioContext
  const Offline = window.OfflineAudioContext || window.webkitOfflineAudioContext
  if (!Ctx || !Offline) throw new Error('This browser cannot process audio.')

  const ctx = new Ctx()
  let decoded
  try {
    decoded = await ctx.decodeAudioData(await blob.arrayBuffer())
  } finally {
    ctx.close()
  }
  if (!decoded.length) throw new Error('That recording was empty.')

  // Rendering into a 1-channel context downmixes and resamples in one pass.
  const frames = Math.ceil(decoded.duration * TARGET_RATE)
  const offline = new Offline(1, frames, TARGET_RATE)
  const source = offline.createBufferSource()
  source.buffer = decoded
  source.connect(offline.destination)
  source.start()

  const rendered = await offline.startRendering()
  return encodeWav(rendered.getChannelData(0), TARGET_RATE)
}

/**
 * Audio playback singleton.
 *
 * The app has no state library and no context — everything is useState in
 * App.jsx, drilled down as props. Playback is the one thing that genuinely has
 * to be global: two Speak buttons must never talk over each other. A plain
 * module-level object is a smaller price than introducing Context for it.
 */

let audio = null
let queue = []
let index = 0
let owner = null // which SpeakButton is currently playing
const listeners = new Set()

function emit() {
  for (const fn of listeners) fn(owner)
}

export function subscribe(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function stop() {
  if (audio) {
    audio.pause()
    audio.src = ''
    audio = null
  }
  queue = []
  index = 0
  owner = null
  emit()
}

function playNext() {
  if (index >= queue.length) {
    stop()
    return
  }
  audio = new Audio(`data:audio/mpeg;base64,${queue[index]}`)
  audio.onended = () => {
    index += 1
    playNext()
  }
  // A decode failure on one clip shouldn't strand the button in "playing".
  audio.onerror = () => stop()
  audio.play().catch(() => stop())
}

/** Play base64 clips in order. Starting a new one always cancels the old. */
export function play(clips, id) {
  stop()
  if (!clips?.length) return
  queue = clips
  index = 0
  owner = id ?? 'anonymous'
  emit()
  playNext()
}

export const playingId = () => owner
