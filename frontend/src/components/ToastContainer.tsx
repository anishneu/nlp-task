import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Task } from '../types'

const POLL_INTERVAL_MS = 15_000

interface Props {
  onTaskCompleted: () => void
}

export function ToastContainer({ onTaskCompleted }: Props) {
  const [toasts, setToasts] = useState<Task[]>([])
  const shownKeys = useRef(new Set<string>())

  useEffect(() => {
    async function poll() {
      try {
        const due = await api.dueReminders()
        const fresh = due.filter((t) => !shownKeys.current.has(`${t.id}:${t.due_at}`))
        if (fresh.length === 0) return
        fresh.forEach((t) => shownKeys.current.add(`${t.id}:${t.due_at}`))
        setToasts((prev) => [...prev, ...fresh])
      } catch {
        // Reminder polling is best-effort; a network hiccup shouldn't break the page.
      }
    }
    void poll()
    const id = setInterval(poll, POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [])

  function dismiss(id: number) {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  async function markDone(id: number) {
    await api.completeTask(id)
    dismiss(id)
    onTaskCompleted()
  }

  if (toasts.length === 0) return null

  return (
    <div className="fixed right-4 top-4 z-10 flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className="flex w-72 flex-col gap-2 rounded-lg border border-accent bg-panel p-3.5 shadow-2xl"
        >
          <div className="text-sm font-semibold">⏰ {t.title}</div>
          <div className="flex justify-end gap-1.5">
            <button
              onClick={() => dismiss(t.id)}
              className="rounded-md border border-border px-2 py-1 text-xs text-muted hover:bg-white/5"
            >
              Dismiss
            </button>
            <button
              onClick={() => void markDone(t.id)}
              className="rounded-md bg-accent px-3 py-1 text-xs font-medium text-white hover:opacity-90"
            >
              Done
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
