import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { ChatPanel } from './components/ChatPanel'
import { TaskPanel } from './components/TaskPanel'
import { ToastContainer } from './components/ToastContainer'
import { loadBotName, saveBotName } from './storage'
import type { Task } from './types'

export default function App() {
  const [botName, setBotName] = useState(loadBotName)
  const [tasks, setTasks] = useState<Task[]>([])

  const refreshTasks = useCallback(() => {
    void api.listTasks().then(setTasks)
  }, [])

  useEffect(() => {
    refreshTasks()
  }, [refreshTasks])

  useEffect(() => {
    document.title = botName
  }, [botName])

  function handleBotNameChange(name: string) {
    setBotName(name)
    saveBotName(name)
  }

  async function handleComplete(id: number) {
    await api.completeTask(id)
    refreshTasks()
  }

  async function handleDelete(id: number) {
    await api.deleteTask(id)
    refreshTasks()
  }

  return (
    <div className="flex h-screen bg-bg text-text">
      <ToastContainer onTaskCompleted={refreshTasks} />
      <div className="flex-[1.3]">
        <ChatPanel botName={botName} onBotNameChange={handleBotNameChange} onExchange={refreshTasks} />
      </div>
      <div className="flex-1">
        <TaskPanel
          tasks={tasks}
          onRefresh={refreshTasks}
          onComplete={handleComplete}
          onDelete={handleDelete}
        />
      </div>
    </div>
  )
}
