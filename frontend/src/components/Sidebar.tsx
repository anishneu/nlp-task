import type { Conversation } from '../types'

interface Props {
  conversations: Conversation[]
  activeId: string
  onSelect: (id: string) => void
  onNewChat: () => void
  onDelete: (id: string) => void
}

export function Sidebar({ conversations, activeId, onSelect, onNewChat, onDelete }: Props) {
  return (
    <div className="flex h-full w-60 flex-shrink-0 flex-col border-r border-border bg-panel">
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          + New Chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {conversations.length === 0 && (
          <div className="px-2 py-3 text-xs text-muted">No conversations yet.</div>
        )}
        {conversations.map((c) => (
          <div
            key={c.id}
            onClick={() => onSelect(c.id)}
            className={`group flex cursor-pointer items-center justify-between gap-1 rounded-md px-2 py-2 text-sm ${
              c.id === activeId ? 'bg-accent/20 text-text' : 'text-muted hover:bg-white/5'
            }`}
          >
            <span className="truncate">{c.title || 'New conversation'}</span>
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDelete(c.id)
              }}
              className="flex-shrink-0 rounded px-1 text-xs opacity-0 hover:bg-white/10 group-hover:opacity-100"
              title="Delete conversation"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
