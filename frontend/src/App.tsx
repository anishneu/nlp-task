import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { ChatPanel } from './components/ChatPanel'
import { LandingPage } from './components/LandingPage'
import { Sidebar } from './components/Sidebar'
import { TaskPanel } from './components/TaskPanel'
import { ToastContainer } from './components/ToastContainer'
import { loadBotName, loadConversationId, saveBotName, saveConversationId } from './storage'
import type { Conversation, Message, Task } from './types'

export default function App() {
  const [started, setStarted] = useState(false)
  const [botName, setBotName] = useState(loadBotName)
  const [tasks, setTasks] = useState<Task[]>([])
  const [conversationId, setConversationId] = useState(loadConversationId)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [messages, setMessages] = useState<Message[]>([])

  const refreshTasks = useCallback(() => {
    void api.listTasks().then(setTasks)
  }, [])

  const refreshConversations = useCallback(() => {
    void api.listConversations().then(setConversations)
  }, [])

  useEffect(() => {
    if (!started) return
    refreshTasks()
    refreshConversations()
    void api.listMessages(conversationId).then(setMessages)
    // Only reload history when the app first mounts into the chat view —
    // switching conversations afterwards is handled by handleSelectConversation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [started])

  useEffect(() => {
    document.title = started ? botName : 'Custom To-Do Bot'
  }, [started, botName])

  function handleBotNameChange(name: string) {
    setBotName(name)
    saveBotName(name)
  }

  async function handleSend(text: string) {
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: 'user', content: text, intent: null, created_at: new Date().toISOString() },
    ])
    try {
      const data = await api.chat(text, conversationId, botName)
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: 'bot',
          content: data.reply,
          intent: data.intent,
          created_at: new Date().toISOString(),
        },
      ])
      if (data.bot_name) handleBotNameChange(data.bot_name)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 2,
          role: 'bot',
          content: `Error reaching the server: ${message}`,
          intent: null,
          created_at: new Date().toISOString(),
        },
      ])
    }
    refreshTasks()
    refreshConversations()
  }

  function handleNewChat() {
    const id = crypto.randomUUID()
    setConversationId(id)
    saveConversationId(id)
    setMessages([])
  }

  async function handleSelectConversation(id: string) {
    setConversationId(id)
    saveConversationId(id)
    const history = await api.listMessages(id)
    setMessages(history)
  }

  async function handleDeleteConversation(id: string) {
    await api.deleteConversation(id)
    refreshConversations()
    if (id === conversationId) handleNewChat()
  }

  async function handleComplete(id: number) {
    await api.completeTask(id)
    refreshTasks()
  }

  async function handleDelete(id: number) {
    await api.deleteTask(id)
    refreshTasks()
  }

  async function handleToggleStar(id: number, starred: boolean) {
    await api.setStarred(id, starred)
    refreshTasks()
  }

  async function handleUpdateDueDate(id: number, dueAt: string | null) {
    await api.setDueDate(id, dueAt)
    refreshTasks()
  }

  if (!started) {
    return <LandingPage onGetStarted={() => setStarted(true)} />
  }

  return (
    <div className="flex h-screen bg-bg text-text">
      <ToastContainer onTaskCompleted={refreshTasks} />
      <Sidebar
        conversations={conversations}
        activeId={conversationId}
        onSelect={handleSelectConversation}
        onNewChat={handleNewChat}
        onDelete={handleDeleteConversation}
      />
      <div className="flex-[1.3]">
        <ChatPanel
          botName={botName}
          onBotNameChange={handleBotNameChange}
          messages={messages}
          onSend={handleSend}
        />
      </div>
      <div className="flex-1">
        <TaskPanel
          tasks={tasks}
          onRefresh={refreshTasks}
          onComplete={handleComplete}
          onDelete={handleDelete}
          onToggleStar={handleToggleStar}
          onUpdateDueDate={handleUpdateDueDate}
        />
      </div>
    </div>
  )
}
