import { useState } from 'react'
import type { Task } from '../types'

function formatFull(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function toDateTimeLocalValue(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const RECURRENCE_LABELS: Record<string, string> = {
  daily: 'Daily',
  weekly: 'Weekly',
  monthly: 'Monthly',
  yearly: 'Yearly',
  weekday: 'Every weekday (Mon–Fri)',
}

interface Row {
  label: string
  value: React.ReactNode
}

function DetailRow({ label, value }: Row) {
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <span className="text-xs font-medium text-muted">{label}</span>
      <span className="text-right text-sm">{value}</span>
    </div>
  )
}

interface Props {
  task: Task
  onClose: () => void
  onComplete: (id: number) => void
  onDelete: (id: number) => void
  onToggleStar: (id: number, starred: boolean) => void
  onUpdateDueDate: (id: number, dueAt: string | null) => void
}

export function TaskDetailModal({
  task,
  onClose,
  onComplete,
  onDelete,
  onToggleStar,
  onUpdateDueDate,
}: Props) {
  const [editingDate, setEditingDate] = useState(false)
  const [dateValue, setDateValue] = useState(() => toDateTimeLocalValue(task.due_at))

  function startEditingDate() {
    setDateValue(toDateTimeLocalValue(task.due_at))
    setEditingDate(true)
  }

  function saveDate() {
    // Sent as-is (no UTC conversion) — the whole app treats due dates as
    // naive wall-clock time in one timezone (see backend/app/clock.py), so
    // .toISOString() here would shift it by the browser's UTC offset.
    onUpdateDueDate(task.id, dateValue ? `${dateValue}:00` : null)
    setEditingDate(false)
  }

  function clearDate() {
    onUpdateDueDate(task.id, null)
    setEditingDate(false)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-border bg-panel p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-base font-semibold leading-snug">{task.title}</h2>
          <button
            onClick={onClose}
            className="flex-shrink-0 rounded-md border border-border px-2 py-1 text-xs text-muted hover:bg-white/5"
          >
            Close
          </button>
        </div>

        <div className="mt-3 divide-y divide-border border-y border-border">
          <DetailRow
            label="Status"
            value={
              <span className="capitalize">
                {task.status}
                {task.starred ? ' · ★ Starred' : ''}
              </span>
            }
          />
          <DetailRow
            label="Due"
            value={
              editingDate ? (
                <div className="flex items-center justify-end gap-1.5">
                  <input
                    type="datetime-local"
                    value={dateValue}
                    onChange={(e) => setDateValue(e.target.value)}
                    className="rounded-md border border-border bg-panel px-1.5 py-1 text-xs outline-none"
                  />
                  <button
                    onClick={saveDate}
                    className="rounded-md border border-border px-2 py-1 text-xs text-accent hover:bg-white/5"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingDate(false)}
                    className="rounded-md border border-border px-2 py-1 text-xs text-muted hover:bg-white/5"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <div className="flex items-center justify-end gap-1.5">
                  <span>{formatFull(task.due_at)}</span>
                  <button
                    onClick={startEditingDate}
                    className="rounded-md border border-border px-1.5 py-0.5 text-[10px] text-muted hover:bg-white/5"
                  >
                    Edit
                  </button>
                  {task.due_at && (
                    <button
                      onClick={clearDate}
                      className="rounded-md border border-border px-1.5 py-0.5 text-[10px] text-muted hover:bg-white/5"
                    >
                      Clear
                    </button>
                  )}
                </div>
              )
            }
          />
          {task.recurrence && (
            <DetailRow label="Repeats" value={RECURRENCE_LABELS[task.recurrence] ?? task.recurrence} />
          )}
          {task.description && <DetailRow label="Description" value={task.description} />}
          {task.link && (
            <DetailRow
              label="Link"
              value={
                <a
                  href={task.link.startsWith('http') ? task.link : `https://${task.link}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-accent underline"
                >
                  {task.link}
                </a>
              }
            />
          )}
          <DetailRow label="Created" value={formatFull(task.created_at)} />
          <DetailRow label="Last updated" value={formatFull(task.updated_at)} />
          <DetailRow label="Task ID" value={`#${task.id}`} />
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={() => onToggleStar(task.id, !task.starred)}
            className="rounded-md border border-border px-3 py-1.5 text-xs text-muted hover:bg-white/5"
          >
            {task.starred ? 'Unstar' : 'Star'}
          </button>
          {task.status !== 'completed' && (
            <button
              onClick={() => {
                onComplete(task.id)
                onClose()
              }}
              className="rounded-md border border-border px-3 py-1.5 text-xs text-muted hover:bg-white/5"
            >
              Mark done
            </button>
          )}
          <button
            onClick={() => {
              onDelete(task.id)
              onClose()
            }}
            className="rounded-md border border-red-900/50 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  )
}
