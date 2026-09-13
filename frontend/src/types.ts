export type TaskStatus = 'pending' | 'completed'

export interface Task {
  id: number
  title: string
  description: string | null
  due_at: string | null
  recurrence: string | null
  status: TaskStatus
  starred: boolean
  link: string | null
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

export interface Conversation {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export interface Message {
  id: number
  role: 'user' | 'bot'
  content: string
  intent: string | null
  created_at: string
}
