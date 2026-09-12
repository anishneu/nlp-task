import type { ChatResponse, Task, TaskStatus } from './types'

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`Request failed: ${res.status}`)
  return res.json() as Promise<T>
}

export const api = {
  listTasks: (): Promise<Task[]> => fetch('/tasks').then((r) => json(r)),

  dueReminders: (): Promise<Task[]> => fetch('/reminders/due').then((r) => json(r)),

  completeTask: (id: number): Promise<Task> =>
    fetch(`/tasks/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'completed' satisfies TaskStatus }),
    }).then((r) => json(r)),

  deleteTask: (id: number): Promise<void> =>
    fetch(`/tasks/${id}`, { method: 'DELETE' }).then((r) => {
      if (!r.ok) throw new Error(`Request failed: ${r.status}`)
    }),

  chat: (message: string, sessionId: string, botName: string): Promise<ChatResponse> =>
    fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id: sessionId, bot_name: botName }),
    }).then((r) => json(r)),
}
