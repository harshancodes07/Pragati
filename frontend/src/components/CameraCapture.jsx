import { useEffect, useRef, useState } from 'react'

/**
 * Native browser camera capture (getUserMedia) — no third-party camera or
 * OCR service. The captured frame becomes a plain File, handed to the same
 * upload pipeline that already runs vision-model OCR on photo uploads, so
 * nothing downstream of this component needs to know a photo came from a
 * live camera instead of a file picker.
 *
 * Camera and device-upload stay side by side at every stage — the camera
 * only opens once the student picks it, so no permission prompt fires
 * before they've chosen that path, and "Upload a photo" is never buried.
 */
export function CameraCapture({ onCapture, onCancel }) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const fileInputRef = useRef(null)

  const [stage, setStage] = useState('choose') // choose | live | preview
  const [ready, setReady] = useState(false)
  const [error, setError] = useState(null)
  const [captured, setCaptured] = useState(null) // { blob, url }

  useEffect(() => () => streamRef.current?.getTracks().forEach((t) => t.stop()), [])

  function stopStream() {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }

  async function openCamera() {
    setError(null)
    setReady(false)
    setStage('live')

    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Camera not available on this device — use "Upload a photo" instead.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setReady(true)
    } catch {
      setError('Could not access the camera — check permissions, or upload a photo instead.')
    }
  }

  function takePhoto() {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas) return

    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)
    canvas.toBlob(
      (blob) => {
        if (!blob) return
        setCaptured({ blob, url: URL.createObjectURL(blob) })
        stopStream()
        setStage('preview')
      },
      'image/jpeg',
      0.92,
    )
  }

  function retake() {
    if (captured) URL.revokeObjectURL(captured.url)
    setCaptured(null)
    openCamera()
  }

  function confirm() {
    if (!captured) return
    const file = new File([captured.blob], `scan-${Date.now()}.jpg`, { type: 'image/jpeg' })
    onCapture(file)
  }

  function handleDeviceFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    stopStream()
    setCaptured({ blob: file, url: URL.createObjectURL(file) })
    setStage('preview')
  }

  function cancel() {
    stopStream()
    if (captured) URL.revokeObjectURL(captured.url)
    onCancel()
  }

  const chooseDeviceFile = () => fileInputRef.current?.click()

  return (
    <div className="space-y-4">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={handleDeviceFile}
      />

      {stage !== 'choose' && (
        <div className="relative overflow-hidden rounded-2xl border border-line bg-[#1D1D1F]">
          {captured ? (
            <img src={captured.url} alt="Captured page" className="max-h-[28rem] w-full object-contain" />
          ) : (
            <video
              ref={videoRef}
              playsInline
              muted
              className={`max-h-[28rem] w-full object-contain transition-opacity ${
                ready ? 'opacity-100' : 'opacity-0'
              }`}
            />
          )}

          {stage === 'live' && !ready && !error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <p className="text-sm text-white/70">Opening camera…</p>
            </div>
          )}
        </div>
      )}

      {error && (
        <p className="rounded-xl border border-alert/40 bg-alert/10 px-4 py-3 text-sm text-alert">
          {error}
        </p>
      )}

      <canvas ref={canvasRef} className="hidden" />

      {stage === 'choose' && (
        <div className="grid gap-3 sm:grid-cols-2">
          <button
            onClick={openCamera}
            className="glass flex flex-col items-center gap-2 rounded-2xl px-6 py-8 text-center
              transition hover:border-saffron hover:bg-saffron/5"
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-saffron/15 text-2xl">
              📷
            </span>
            <span className="text-sm font-medium text-[#1D1D1F]">Use Camera</span>
            <span className="text-xs text-muted">Point at a page and capture it live</span>
          </button>
          <button
            onClick={chooseDeviceFile}
            className="glass flex flex-col items-center gap-2 rounded-2xl px-6 py-8 text-center
              transition hover:border-saffron hover:bg-saffron/5"
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-saffron/15 text-2xl">
              🖼️
            </span>
            <span className="text-sm font-medium text-[#1D1D1F]">Upload a Photo</span>
            <span className="text-xs text-muted">Pick an existing photo from your device</span>
          </button>
        </div>
      )}

      {stage !== 'choose' && (
        <div className="flex flex-wrap items-center justify-center gap-3">
          {captured ? (
            <>
              <button
                onClick={retake}
                className="rounded-xl border border-line px-5 py-2.5 text-sm text-[#1D1D1F]
                  transition hover:bg-raised"
              >
                Retake
              </button>
              <button
                onClick={confirm}
                className="rounded-xl bg-saffron px-5 py-2.5 text-sm font-semibold text-white
                  transition hover:brightness-110"
              >
                Use this photo
              </button>
            </>
          ) : (
            <>
              <button
                onClick={takePhoto}
                disabled={!ready}
                className="flex h-14 w-14 items-center justify-center rounded-full bg-saffron
                  text-2xl text-white shadow-lg shadow-saffron/30 transition hover:brightness-110
                  disabled:cursor-not-allowed disabled:opacity-40"
                title="Capture"
              >
                ●
              </button>
              <button
                onClick={chooseDeviceFile}
                className="rounded-xl border border-line px-5 py-2.5 text-sm text-[#1D1D1F]
                  transition hover:bg-raised"
              >
                Upload a photo instead
              </button>
            </>
          )}
          <button onClick={cancel} className="text-sm text-muted transition hover:text-[#1D1D1F]">
            Cancel
          </button>
        </div>
      )}

      {stage === 'choose' && (
        <div className="text-center">
          <button onClick={cancel} className="text-sm text-muted transition hover:text-[#1D1D1F]">
            Cancel
          </button>
        </div>
      )}
    </div>
  )
}
