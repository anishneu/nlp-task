const DEFAULT_BOT_NAME = 'Custom To-Do Bot'

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function safeSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Best-effort only — localStorage can be unavailable (private mode, etc.)
  }
}

export function loadConversationId(): string {
  const existing = safeGet('conversationId')
  if (existing) return existing
  const fresh = crypto.randomUUID()
  safeSet('conversationId', fresh)
  return fresh
}

export function saveConversationId(id: string): void {
  safeSet('conversationId', id)
}

export function loadBotName(): string {
  return safeGet('botName') || DEFAULT_BOT_NAME
}

export function saveBotName(name: string): void {
  safeSet('botName', name)
}
