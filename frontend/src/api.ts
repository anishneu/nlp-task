import type { ChatResponse, Conversation, Message, Task, TaskStatus } from './types'

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

  setStarred: (id: number, starred: boolean): Promise<Task> =>
    fetch(`/tasks/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ starred }),
    }).then((r) => json(r)),

  deleteTask: (id: number): Promise<void> =>
    fetch(`/tasks/${id}`, { method: 'DELETE' }).then((r) => {
      if (!r.ok) throw new Error(`Request failed: ${r.status}`)
    }),

  chat: (message: string, conversationId: string, botName: string): Promise<ChatResponse> =>
    fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, conversation_id: conversationId, bot_name: botName }),
    }).then((r) => json(r)),

  listConversations: (): Promise<Conversation[]> => fetch('/conversations').then((r) => json(r)),

  listMessages: (conversationId: string): Promise<Message[]> =>
    fetch(`/conversations/${conversationId}/messages`).then((r) => json(r)),

  deleteConversation: (conversationId: string): Promise<void> =>
    fetch(`/conversations/${conversationId}`, { method: 'DELETE' }).then((r) => {
      if (!r.ok) throw new Error(`Request failed: ${r.status}`)
    }),
}
