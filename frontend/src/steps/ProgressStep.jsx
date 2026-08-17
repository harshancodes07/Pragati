import { useEffect, useState } from 'react'
import { api } from '../api'
import { Badge, Card, Reveal, Skeleton } from '../components/common'

export function ProgressStep({ doc, judgeMode }) {
  const [progress, setProgress] = useState(null)
  const [stats, setStats] = useState(null)

  useEffect(() => {
    api.progress(doc.session_id).then(setProgress).catch(() => {})
    if (judgeMode) api.stats().then(setStats).catch(() => {})
  }, [doc.session_id, judgeMode])

  if (!progress) {
    return (
      <Card>
        <Skeleton lines={4} />
      </Card>
    )
  }

  return (
    <Reveal className="space-y-5">
      <header>
        <h2 className="text-2xl font-semibold">Progress</h2>
        <p className="mt-1 text-sm text-muted">How this session has gone so far.</p>
      </header>

      <div className="grid grid-cols-3 gap-4">
        <Stat label="Answered" value={progress.answered} />
        <Stat label="Correct" value={progress.correct} />
        <Stat
          label="Accuracy"
          value={progress.accuracy === null ? '—' : `${Math.round(progress.accuracy * 100)}%`}
        />
      </div>

      <Card>
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted">Current difficulty</span>
          <Badge tone="brand">{progress.difficulty}</Badge>
        </div>
      </Card>

      {progress.weak_concepts?.length > 0 && (
        <Card className="border-warn/40 bg-warn/5">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-warn">
            Worth revising
          </h4>
          <div className="flex flex-wrap gap-2">
            {progress.weak_concepts.map((c) => (
              <Badge key={c} tone="warn">
                {c}
              </Badge>
            ))}
          </div>
        </Card>
      )}

      {judgeMode && stats && (
        <Card>
          <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">
            NIM usage this session
          </h4>
          <dl className="grid grid-cols-2 gap-y-2 font-mono text-xs">
            <dt className="text-muted">total calls</dt>
            <dd className="text-right">{stats.nim_calls}</dd>
            <dt className="text-muted">avg latency</dt>
            <dd className="text-right">{stats.avg_latency_ms} ms</dd>
            <dt className="text-muted">prompt tokens</dt>
            <dd className="text-right">{stats.prompt_tokens}</dd>
            <dt className="text-muted">completion tokens</dt>
            <dd className="text-right">{stats.completion_tokens}</dd>
            <dt className="text-muted">indexed chunks</dt>
            <dd className="text-right">{stats.indexed_chunks}</dd>
          </dl>
          {stats.by_task && (
            <div className="mt-3 border-t border-line pt-3">
              <p className="mb-2 text-xs text-muted">calls by task</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(stats.by_task).map(([task, n]) => (
                  <Badge key={task}>
                    {task} × {n}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}
    </Reveal>
  )
}

function Stat({ label, value }) {
  return (
    <Card className="text-center">
      <div className="text-2xl font-semibold text-saffron">{value}</div>
      <div className="mt-1 text-xs text-muted">{label}</div>
    </Card>
  )
}
