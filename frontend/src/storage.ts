export const DEFAULT_BOT_NAME = 'Custom To-Do Bot'

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

export function loadSessionId(): string {
  const existing = safeGet('sessionId')
  if (existing) return existing
  const fresh = crypto.randomUUID()
  safeSet('sessionId', fresh)
  return fresh
}

export function loadBotName(): string {
  return safeGet('botName') || DEFAULT_BOT_NAME
}

export function saveBotName(name: string): void {
  safeSet('botName', name)
}
