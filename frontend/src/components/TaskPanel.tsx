import { useMemo, useState } from 'react'
import type { Task } from '../types'
import { CalendarView } from './CalendarView'
import { TaskDetailModal } from './TaskDetailModal'

type StatusFilter = 'all' | 'pending' | 'completed'
type View = 'list' | 'calendar'

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

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function toDateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

interface Props {
  tasks: Task[]
  onRefresh: () => void
  onComplete: (id: number) => void
  onDelete: (id: number) => void
  onToggleStar: (id: number, starred: boolean) => void
}

export function TaskPanel({ tasks, onRefresh, onComplete, onDelete, onToggleStar }: Props) {
  const [view, setView] = useState<View>('list')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [starredOnly, setStarredOnly] = useState(false)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)

  const filtered = useMemo(() => {
    let result = tasks
    if (statusFilter !== 'all') result = result.filter((t) => t.status === statusFilter)
    if (starredOnly) result = result.filter((t) => t.starred)
    if (selectedDate) result = result.filter((t) => t.due_at && toDateKey(new Date(t.due_at)) === selectedDate)
    return [...result].sort((a, b) => Number(b.starred) - Number(a.starred))
  }, [tasks, statusFilter, starredOnly, selectedDate])

  return (
    <div className="flex h-full flex-col bg-panel">
      <header className="flex items-center justify-between border-b border-border px-4 py-3.5 font-semibold">
        Tasks
        <div className="flex gap-1.5">
          <button
            onClick={() => setView(view === 'list' ? 'calendar' : 'list')}
            className="rounded-md border border-border px-2 py-1 text-xs font-normal text-muted hover:bg-white/5"
          >
            {view === 'list' ? 'Calendar' : 'List'}
          </button>
          <button
            onClick={onRefresh}
            className="rounded-md border border-border px-2 py-1 text-xs font-normal text-muted hover:bg-white/5"
          >
            Refresh
          </button>
        </div>
      </header>

      {view === 'calendar' && (
        <CalendarView tasks={tasks} selectedDate={selectedDate} onSelectDate={setSelectedDate} />
      )}

      <div className="flex flex-wrap items-center gap-1.5 border-b border-border px-3 py-2">
        {(['all', 'pending', 'completed'] as StatusFilter[]).map((f) => (
          <button
            key={f}
            onClick={() => setStatusFilter(f)}
            className={`rounded-md px-2 py-1 text-xs capitalize ${
              statusFilter === f ? 'bg-accent text-white' : 'border border-border text-muted hover:bg-white/5'
            }`}
          >
            {f}
          </button>
        ))}
        <button
          onClick={() => setStarredOnly((v) => !v)}
          className={`ml-auto rounded-md px-2 py-1 text-xs ${
            starredOnly ? 'bg-accent text-white' : 'border border-border text-muted hover:bg-white/5'
          }`}
        >
          ★ Starred
        </button>
        {selectedDate && (
          <button
            onClick={() => setSelectedDate(null)}
            className="rounded-md border border-border px-2 py-1 text-xs text-muted hover:bg-white/5"
          >
            Clear date ✕
          </button>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-2 overflow-y-auto p-3">
        {filtered.length === 0 && (
          <div className="p-3 text-sm text-muted">No matching tasks.</div>
        )}
        {filtered.map((t) => (
          <div
            key={t.id}
            className={`flex items-start justify-between gap-2 rounded-lg border border-border p-3 ${
              t.status === 'completed' ? 'opacity-55' : ''
            }`}
          >
            <button
              onClick={() => onToggleStar(t.id, !t.starred)}
              className={`mt-0.5 flex-shrink-0 text-base ${t.starred ? 'text-yellow-400' : 'text-muted opacity-40 hover:opacity-100'}`}
              title={t.starred ? 'Unstar' : 'Star as important'}
            >
              {t.starred ? '★' : '☆'}
            </button>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1.5 text-sm font-medium">
                <button
                  onClick={() => setSelectedTask(t)}
                  className={`text-left hover:underline ${t.status === 'completed' ? 'line-through' : ''}`}
                >
                  {t.title}
                </button>
                <span className="whitespace-nowrap rounded-full bg-border px-1.5 py-0.5 text-[10px] text-muted">
                  {t.status}
                </span>
                {t.recurrence && (
                  <span className="whitespace-nowrap rounded-full bg-accent/20 px-1.5 py-0.5 text-[10px] text-accent">
                    ↻ {t.recurrence}
                  </span>
                )}
              </div>
              <div className="mt-0.5 text-xs text-muted">
                {formatDue(t.due_at)} · created {timeAgo(t.created_at)}
              </div>
              {t.link && (
                <a
                  href={t.link.startsWith('http') ? t.link : `https://${t.link}`}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block rounded-md bg-accent/15 px-2 py-1 text-xs text-accent hover:bg-accent/25"
                >
                  🎥 Join Meet
                </a>
              )}
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

      {selectedTask && (
        <TaskDetailModal
          task={tasks.find((t) => t.id === selectedTask.id) ?? selectedTask}
          onClose={() => setSelectedTask(null)}
          onComplete={onComplete}
          onDelete={onDelete}
          onToggleStar={onToggleStar}
        />
      )}
    </div>
  )
}
