import { useEffect, useRef, useState } from 'react'
import type { Message } from '../types'

const EXAMPLES = ['Show my tasks', 'Remind me to call Mom on Friday at 6 PM', 'Mark a task as completed']

const LINK_RE = /(https?:\/\/\S+|meet\.google\.com\/\S+|zoom\.us\/\S+)/g

function formatTime(iso: string) {
  const d = new Date(iso)
  const datePart = d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })
  const timePart = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  return `${datePart} · ${timePart}`
}

function linkify(text: string) {
  const parts = text.split(LINK_RE)
  return parts.map((part, i) =>
    LINK_RE.test(part) ? (
      <a
        key={i}
        href={part.startsWith('http') ? part : `https://${part}`}
        target="_blank"
        rel="noreferrer"
        className="underline"
      >
        {part}
      </a>
    ) : (
      <span key={i}>{part}</span>
    ),
  )
}

interface Props {
  botName: string
  onBotNameChange: (name: string) => void
  messages: Message[]
  onSend: (text: string) => void
  isSending: boolean
}

const MAX_INPUT_HEIGHT_PX = 160

function TypingIndicator() {
  return (
    <div className="mr-auto flex max-w-[75%] items-center gap-1 self-start rounded-xl rounded-bl-sm bg-bubble-bot px-3.5 py-3">
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted [animation-delay:-0.2s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted [animation-delay:-0.1s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted" />
    </div>
  )
}

export function ChatPanel({ botName, onBotNameChange, messages, onSend, isSending }: Props) {
  const [input, setInput] = useState('')
  const logRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight })
  }, [messages, isSending])

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_INPUT_HEIGHT_PX)}px`
  }, [input])

  function submitInput() {
    const text = input.trim()
    if (!text || isSending) return
    setInput('')
    onSend(text)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    submitInput()
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submitInput()
    }
  }

  function handleRename() {
    const next = window.prompt('What would you like to call me?', botName)
    if (next === null) return
    onBotNameChange(next.trim() || botName)
  }

  return (
    <div className="flex h-full flex-col border-r border-border">
      <header className="flex items-center justify-between border-b border-border px-4 py-3.5">
        <span className="font-semibold">
          {botName}
          <button
            onClick={handleRename}
            className="ml-2.5 rounded-md border border-border px-2 py-1 text-xs font-normal text-muted hover:bg-white/5"
          >
            Rename
          </button>
        </span>
        <span className="text-xs text-muted">HF intent + rule-based · /chat</span>
      </header>

      <div className="flex flex-wrap gap-1.5 px-3.5 pb-2.5 pt-3.5">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            onClick={() => onSend(example)}
            className="rounded-md border border-border bg-panel px-2.5 py-1.5 text-xs text-muted hover:bg-white/5"
          >
            {example}
          </button>
        ))}
      </div>

      <div ref={logRef} className="chat-scroll flex flex-1 flex-col gap-2.5 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="m-auto flex flex-col items-center gap-1.5 text-center">
            <span className="text-2xl">💬</span>
            <span className="text-sm font-medium">New chat</span>
            <span className="text-xs text-muted">Send a message below, or try one of the examples above.</span>
          </div>
        ) : (
          messages.map((m) => (
            <div
              key={m.id}
              className={`max-w-[75%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'self-end rounded-br-sm bg-accent text-white'
                  : 'self-start rounded-bl-sm bg-bubble-bot'
              }`}
            >
              {linkify(m.content)}
              <span
                className={`mt-1.5 block text-[11px] ${
                  m.role === 'user' ? 'text-white/70' : 'text-muted'
                }`}
              >
                {formatTime(m.created_at)}
              </span>
            </div>
          ))
        )}
        {isSending && <TypingIndicator />}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 border-t border-border p-3.5">
        <textarea
          ref={textareaRef}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={`Message ${botName}… (Shift+Enter for a new line)`}
          className="chat-scroll flex-1 resize-none rounded-lg border border-border bg-panel px-3 py-2.5 text-sm leading-relaxed outline-none focus:ring-1 focus:ring-accent"
          style={{ maxHeight: MAX_INPUT_HEIGHT_PX }}
        />
        <button
          type="submit"
          disabled={isSending}
          className="self-end rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  )
}
