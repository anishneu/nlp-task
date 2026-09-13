import { useState } from 'react'
import type { Task } from '../types'

interface Props {
  tasks: Task[]
  selectedDate: string | null
  onSelectDate: (date: string | null) => void
}

function toDateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function CalendarView({ tasks, selectedDate, onSelectDate }: Props) {
  const [viewDate, setViewDate] = useState(() => new Date())

  const year = viewDate.getFullYear()
  const month = viewDate.getMonth()
  const firstOfMonth = new Date(year, month, 1)
  const startWeekday = firstOfMonth.getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const todayKey = toDateKey(new Date())

  const tasksByDate = new Map<string, Task[]>()
  for (const t of tasks) {
    if (!t.due_at) continue
    const key = toDateKey(new Date(t.due_at))
    if (!tasksByDate.has(key)) tasksByDate.set(key, [])
    tasksByDate.get(key)!.push(t)
  }

  const cells: (number | null)[] = [
    ...Array(startWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]

  return (
    <div className="border-b border-border p-3">
      <div className="mb-2 flex items-center justify-between">
        <button
          onClick={() => setViewDate(new Date(year, month - 1, 1))}
          className="rounded-md border border-border px-2 py-1 text-xs text-muted hover:bg-white/5"
        >
          ‹
        </button>
        <span className="text-sm font-medium">
          {viewDate.toLocaleString(undefined, { month: 'long', year: 'numeric' })}
        </span>
        <button
          onClick={() => setViewDate(new Date(year, month + 1, 1))}
          className="rounded-md border border-border px-2 py-1 text-xs text-muted hover:bg-white/5"
        >
          ›
        </button>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center text-[10px] text-muted">
        {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
          <div key={i}>{d}</div>
        ))}
      </div>

      <div className="mt-1 grid grid-cols-7 gap-1">
        {cells.map((day, i) => {
          if (day === null) return <div key={i} />
          const key = toDateKey(new Date(year, month, day))
          const dayTasks = tasksByDate.get(key) ?? []
          const isSelected = key === selectedDate
          const isToday = key === todayKey
          return (
            <button
              key={i}
              onClick={() => onSelectDate(isSelected ? null : key)}
              className={`flex aspect-square flex-col items-center justify-center rounded-md text-xs ${
                isSelected
                  ? 'bg-accent text-white'
                  : isToday
                    ? 'border border-accent text-text'
                    : 'text-text hover:bg-white/5'
              }`}
            >
              <span>{day}</span>
              {dayTasks.length > 0 && (
                <span
                  className={`mt-0.5 h-1 w-1 rounded-full ${isSelected ? 'bg-white' : 'bg-accent'}`}
                />
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
