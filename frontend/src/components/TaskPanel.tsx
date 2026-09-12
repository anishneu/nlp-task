import type { Task } from '../types'

function formatDue(dueAt: string | null): string {
  if (!dueAt) return 'no due date'
  const d = new Date(dueAt)
  return d.toLocaleString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

interface Props {
  tasks: Task[]
  onRefresh: () => void
  onComplete: (id: number) => void
  onDelete: (id: number) => void
}

export function TaskPanel({ tasks, onRefresh, onComplete, onDelete }: Props) {
  return (
    <div className="flex h-full flex-col bg-panel">
      <header className="flex items-center justify-between border-b border-border px-4 py-3.5 font-semibold">
        Tasks
        <button
          onClick={onRefresh}
          className="rounded-md border border-border px-2 py-1 text-xs font-normal text-muted hover:bg-white/5"
        >
          Refresh
        </button>
      </header>

      <div className="flex flex-1 flex-col gap-2 overflow-y-auto p-3">
        {tasks.length === 0 && (
          <div className="p-3 text-sm text-muted">No tasks yet — try the chat panel.</div>
        )}
        {tasks.map((t) => (
          <div
            key={t.id}
            className={`flex items-start justify-between gap-2 rounded-lg border border-border p-3 ${
              t.status === 'completed' ? 'opacity-55' : ''
            }`}
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1.5 text-sm font-medium">
                <span className={t.status === 'completed' ? 'line-through' : ''}>{t.title}</span>
                <span className="whitespace-nowrap rounded-full bg-border px-1.5 py-0.5 text-[10px] text-muted">
                  {t.status}
                </span>
                {t.recurrence && (
                  <span className="whitespace-nowrap rounded-full bg-accent/20 px-1.5 py-0.5 text-[10px] text-accent">
                    ↻ {t.recurrence}
                  </span>
                )}
              </div>
              <div className="mt-0.5 text-xs text-muted">{formatDue(t.due_at)}</div>
            </div>
            <div className="flex flex-shrink-0 gap-1.5">
              {t.status !== 'completed' && (
                <button
                  onClick={() => onComplete(t.id)}
                  className="rounded-md border border-border px-2 py-1 text-xs text-muted hover:bg-white/5"
                >
                  Done
                </button>
              )}
              <button
                onClick={() => onDelete(t.id)}
                className="rounded-md border border-border px-2 py-1 text-xs text-muted hover:bg-white/5"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
