import { useEffect, useState } from 'react'
import { api, LANGUAGES } from '../api'

function timeAgo(iso) {
  // SQLite datetime('now') is UTC without a zone suffix — mark it explicitly
  // so the browser doesn't parse it as local time and skew the delta.
  const then = new Date(`${iso}Z`).getTime()
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000))
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.round(hrs / 24)}d ago`
}

/**
 * Sidebar list of saved doubt-chat threads. Reuses api.listChats and hands
 * the clicked chat's id up to the parent, which fetches the full thread and
 * restores it in RestoredChatModal — this component only ever needs titles.
 */
export function RecentChats({ sessionId, refreshKey, onSelect }) {
  const [chats, setChats] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .listChats(sessionId)
      .then((res) => { if (!cancelled) setChats(res.chats) })
      .catch(() => { if (!cancelled) setChats([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [sessionId, refreshKey])

  if (!loading && chats.length === 0) return null

  return (
    <div className="mt-8 space-y-2 border-t border-line pt-6">
      <label className="block text-xs font-semibold uppercase tracking-wide text-muted">
        Recent Chats
      </label>

      {loading && <p className="text-xs text-muted">Loading…</p>}

      <div className="max-h-64 space-y-1 overflow-y-auto">
        {chats.map((c) => (
          <button
            key={c.id}
            onClick={() => onSelect(c.id)}
            className="block w-full rounded-lg px-3 py-2 text-left text-xs transition
              hover:bg-raised"
          >
            <div className="truncate font-medium text-[#1D1D1F]">{c.title}</div>
            <div className="mt-0.5 flex items-center gap-1.5 text-muted">
              <span>{LANGUAGES.find((l) => l.id === c.language)?.flag}</span>
              <span>{timeAgo(c.updated_at)}</span>
              <span>· {c.message_count} msg{c.message_count === 1 ? '' : 's'}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
