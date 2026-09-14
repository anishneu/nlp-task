import { useEffect, useRef, useState } from 'react'

const REPO_URL = 'https://github.com/anishneu/nlp-task'

const DEMO_EXCHANGES = [
  {
    user: 'Remind me to call mom every Sunday at 6pm',
    bot: "Got it — I'll remind you to call mom every Sunday at 6:00 PM.",
  },
  {
    user: "What's on my plate today?",
    bot: "You've got 2 things: submit the report at 3 PM and gym at 6 PM.",
  },
  {
    user: 'Mark the report as done',
    bot: "Nice work! Marked \"submit the report\" as complete.",
  },
]

const TECH_STACK = ['FastAPI', 'React', 'Hugging Face', 'SQLAlchemy', 'APScheduler']

const FEATURES = [
  {
    icon: ChatIcon,
    title: 'Talk, don’t type forms',
    body: '"Remind me to call Mom on Friday at 6 PM" — just say it naturally, no rigid syntax.',
  },
  {
    icon: BrainIcon,
    title: 'ML-backed understanding',
    body: 'Zero-shot intent classification via a Hugging Face model, with semantic matching to find the right task even from vague phrasing.',
  },
  {
    icon: RepeatIcon,
    title: 'Recurring reminders',
    body: 'Daily, weekly, monthly, yearly, or weekday-only tasks that reschedule themselves automatically after each occurrence.',
  },
  {
    icon: CalendarIcon,
    title: 'Calendar & filters',
    body: 'A full month view alongside status, starred, and search filters to cut through a long list fast.',
  },
  {
    icon: HistoryIcon,
    title: 'Full conversation history',
    body: 'Every chat is saved and searchable, so you can pick up right where you left off.',
  },
  {
    icon: OpenSourceIcon,
    title: 'Free & open source',
    body: 'Runs on free Hugging Face models with a rule-based fallback — no paid LLM API required.',
  },
]

const STEPS = [
  {
    title: 'Type it like a message',
    body: 'Tell the bot what you need in plain English — a task, a reminder, or a question about your list.',
  },
  {
    title: 'It understands the intent',
    body: 'An NLP pipeline figures out what you mean, extracts the date/time, and asks a follow-up if anything is missing.',
  },
  {
    title: 'Stay on top of it',
    body: 'Tasks land in a filterable, calendar-aware panel, with in-app notifications the moment something is due.',
  },
]

interface Props {
  onGetStarted: () => void
}

export function LandingPage({ onGetStarted }: Props) {
  return (
    <div className="h-screen overflow-y-auto bg-bg text-text">
      <BackgroundGlow />

      <div className="relative mx-auto flex max-w-5xl flex-col px-6 pb-24 pt-20 sm:pt-28">
        <Reveal>
          <div className="mx-auto flex items-center gap-2 rounded-full border border-border bg-panel/60 px-4 py-1.5 text-xs font-medium text-muted backdrop-blur">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
            </span>
            Open source · no accounts, no paid API keys
          </div>
        </Reveal>

        <Reveal delay={80}>
          <h1 className="mx-auto mt-6 max-w-3xl text-center text-4xl font-bold tracking-tight sm:text-6xl">
            The to-do list that{' '}
            <span className="bg-gradient-to-r from-accent to-sky-300 bg-clip-text text-transparent">
              actually listens
            </span>
          </h1>
        </Reveal>

        <Reveal delay={140}>
          <p className="mx-auto mt-5 max-w-xl text-center text-lg text-muted">
            A conversational task &amp; reminder assistant. Tell it what you need to do, and
            when — it figures out the rest.
          </p>
        </Reveal>

        <Reveal delay={200}>
          <div className="mx-auto mt-9 flex flex-wrap items-center justify-center gap-3">
            <button
              onClick={onGetStarted}
              className="group inline-flex items-center gap-2 rounded-lg bg-accent px-7 py-3 text-base font-semibold text-white shadow-[0_0_0_0_rgba(91,140,255,0.5)] transition-all hover:shadow-[0_0_24px_4px_rgba(91,140,255,0.35)] hover:brightness-110 active:scale-[0.98]"
            >
              Get Started
              <ArrowIcon className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </button>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-panel px-6 py-3 text-base font-medium text-text transition-colors hover:border-accent/50 hover:bg-panel/70"
            >
              <GitHubIcon className="h-4 w-4" />
              View on GitHub
            </a>
          </div>
        </Reveal>

        <Reveal delay={260}>
          <div className="mt-16">
            <ChatDemo />
          </div>
        </Reveal>

        <Reveal delay={100}>
          <div className="mt-16 flex flex-wrap items-center justify-center gap-x-8 gap-y-3">
            {TECH_STACK.map((name) => (
              <span key={name} className="text-sm font-medium text-muted/80">
                {name}
              </span>
            ))}
          </div>
        </Reveal>

        <section className="mt-28">
          <Reveal>
            <h2 className="text-center text-2xl font-bold tracking-tight sm:text-3xl">
              Everything a task assistant should do
            </h2>
          </Reveal>
          <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} delay={i * 60}>
                <div className="group h-full rounded-xl border border-border bg-panel p-5 transition-all hover:-translate-y-1 hover:border-accent/40 hover:shadow-lg hover:shadow-accent/5">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/15 text-accent transition-colors group-hover:bg-accent/25">
                    <f.icon className="h-5 w-5" />
                  </div>
                  <div className="mt-3 text-sm font-semibold">{f.title}</div>
                  <div className="mt-1.5 text-sm leading-relaxed text-muted">{f.body}</div>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        <section className="mt-28">
          <Reveal>
            <h2 className="text-center text-2xl font-bold tracking-tight sm:text-3xl">
              How it works
            </h2>
          </Reveal>
          <div className="relative mt-12 grid grid-cols-1 gap-8 sm:grid-cols-3">
            <div className="pointer-events-none absolute left-0 right-0 top-5 hidden h-px bg-border sm:block" />
            {STEPS.map((s, i) => (
              <Reveal key={s.title} delay={i * 100}>
                <div className="relative text-center">
                  <div className="relative z-10 mx-auto flex h-10 w-10 items-center justify-center rounded-full border border-accent/40 bg-bg text-sm font-bold text-accent">
                    {i + 1}
                  </div>
                  <div className="mt-4 text-sm font-semibold">{s.title}</div>
                  <div className="mt-1.5 text-sm leading-relaxed text-muted">{s.body}</div>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        <Reveal>
          <div className="mt-28 rounded-2xl border border-border bg-panel px-8 py-12 text-center">
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
              Ready to get organized?
            </h2>
            <p className="mx-auto mt-3 max-w-md text-muted">
              No sign-up, no credit card, no tracking. Just start talking to your task list.
            </p>
            <button
              onClick={onGetStarted}
              className="group mt-7 inline-flex items-center gap-2 rounded-lg bg-accent px-7 py-3 text-base font-semibold text-white shadow-[0_0_0_0_rgba(91,140,255,0.5)] transition-all hover:shadow-[0_0_24px_4px_rgba(91,140,255,0.35)] hover:brightness-110 active:scale-[0.98]"
            >
              Get Started
              <ArrowIcon className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </button>
          </div>
        </Reveal>

        <footer className="mt-16 flex flex-col items-center gap-2 text-xs text-muted">
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 hover:text-text"
          >
            <GitHubIcon className="h-3.5 w-3.5" />
            anishneu/nlp-task
          </a>
          <span>MIT Licensed · Built with FastAPI, React &amp; Hugging Face</span>
        </footer>
      </div>
    </div>
  )
}

function BackgroundGlow() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden">
      <div className="animate-blob absolute -left-32 -top-32 h-96 w-96 rounded-full bg-accent/20 blur-[100px]" />
      <div className="animate-blob-slow absolute -right-32 top-40 h-96 w-96 rounded-full bg-sky-400/10 blur-[100px]" />
    </div>
  )
}

function Reveal({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { threshold: 0.15 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      className={`transition-all duration-700 ease-out ${
        visible ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
      }`}
    >
      {children}
    </div>
  )
}

type Phase = 'typing-user' | 'pause-user' | 'typing-bot' | 'pause-bot'

function ChatDemo() {
  const [exchangeIndex, setExchangeIndex] = useState(0)
  const [phase, setPhase] = useState<Phase>('typing-user')
  const [userText, setUserText] = useState('')
  const [botText, setBotText] = useState('')

  useEffect(() => {
    const exchange = DEMO_EXCHANGES[exchangeIndex]
    let timeout: ReturnType<typeof setTimeout>

    if (phase === 'typing-user') {
      if (userText.length < exchange.user.length) {
        timeout = setTimeout(() => setUserText(exchange.user.slice(0, userText.length + 1)), 35)
      } else {
        timeout = setTimeout(() => setPhase('pause-user'), 400)
      }
    } else if (phase === 'pause-user') {
      timeout = setTimeout(() => setPhase('typing-bot'), 500)
    } else if (phase === 'typing-bot') {
      if (botText.length < exchange.bot.length) {
        timeout = setTimeout(() => setBotText(exchange.bot.slice(0, botText.length + 1)), 20)
      } else {
        timeout = setTimeout(() => setPhase('pause-bot'), 2200)
      }
    } else {
      timeout = setTimeout(() => {
        setUserText('')
        setBotText('')
        setPhase('typing-user')
        setExchangeIndex((i) => (i + 1) % DEMO_EXCHANGES.length)
      }, 400)
    }

    return () => clearTimeout(timeout)
  }, [phase, userText, botText, exchangeIndex])

  return (
    <div className="mx-auto max-w-lg rounded-2xl border border-border bg-panel p-4 shadow-2xl shadow-black/20">
      <div className="mb-3 flex items-center gap-1.5 border-b border-border pb-3">
        <span className="h-2.5 w-2.5 rounded-full bg-red-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-yellow-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-green-400/70" />
        <span className="ml-2 text-xs text-muted">Custom To-Do Bot</span>
      </div>

      <div className="flex min-h-[104px] flex-col gap-2.5 text-sm">
        {userText && (
          <div className="ml-auto max-w-[85%] rounded-lg rounded-br-sm bg-accent px-3 py-2 text-white">
            {userText}
            {phase === 'typing-user' && <Cursor />}
          </div>
        )}
        {(phase === 'typing-bot' || phase === 'pause-bot') && (
          <div className="mr-auto max-w-[85%] rounded-lg rounded-bl-sm bg-bubble-bot px-3 py-2">
            {botText || <TypingDots />}
            {phase === 'typing-bot' && botText && <Cursor />}
          </div>
        )}
      </div>
    </div>
  )
}

function Cursor() {
  return <span className="ml-0.5 inline-block h-3.5 w-[2px] animate-pulse bg-current align-middle" />
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-1">
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted [animation-delay:-0.2s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted [animation-delay:-0.1s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted" />
    </span>
  )
}

type IconProps = { className?: string }

function ChatIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 5h16v11H8l-4 4V5Z" />
    </svg>
  )
}

function BrainIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className={className}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 2.8V13a3 3 0 0 0 2 2.8V17a3 3 0 0 0 3 3M9 4a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3M9 4v16m6-16a3 3 0 0 1 3 3 3 3 0 0 1 2 2.8V13a3 3 0 0 1-2 2.8V17a3 3 0 0 1-3 3m0-16a3 3 0 0 0-3 3v10a3 3 0 0 0 3 3m0-16v16"
      />
    </svg>
  )
}

function RepeatIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 2l4 4-4 4M3 11V9a4 4 0 0 1 4-4h14M7 22l-4-4 4-4M21 13v2a4 4 0 0 1-4 4H3" />
    </svg>
  )
}

function CalendarIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className={className}>
      <rect x="3" y="5" width="18" height="16" rx="2" strokeLinecap="round" strokeLinejoin="round" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M8 3v4M16 3v4" />
    </svg>
  )
}

function HistoryIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 12a9 9 0 1 0 3-6.7M3 12V6M3 12h6" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 2" />
    </svg>
  )
}

function OpenSourceIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className={className}>
      <circle cx="12" cy="12" r="9" strokeLinecap="round" strokeLinejoin="round" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v18M3 12h18" />
    </svg>
  )
}

function ArrowIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  )
}

function GitHubIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M12 .5C5.73.5.5 5.73.5 12c0 5.09 3.29 9.4 7.86 10.93.57.1.79-.25.79-.55v-2.16c-3.2.7-3.87-1.36-3.87-1.36-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.7.08-.7 1.17.08 1.78 1.2 1.78 1.2 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.23-1.28-5.23-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.8 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.24 2.76.12 3.05.74.81 1.18 1.84 1.18 3.1 0 4.43-2.68 5.4-5.24 5.69.42.36.78 1.07.78 2.16v3.2c0 .3.21.66.8.55A10.51 10.51 0 0 0 23.5 12C23.5 5.73 18.27.5 12 .5Z" />
    </svg>
  )
}
