export type TaskStatus = 'pending' | 'completed'

export interface Task {
  id: number
  title: string
  description: string | null
  due_at: string | null
  recurrence: string | null
  status: TaskStatus
  created_at: string
  updated_at: string
}

export interface ChatResponse {
  reply: string
  intent: string
  task: Task | null
  tasks: Task[] | null
  bot_name: string | null
}
