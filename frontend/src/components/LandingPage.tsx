const FEATURES = [
  {
    title: 'Talk, don’t type forms',
    body: '"Remind me to call Mom on Friday at 6 PM" — just say it naturally.',
  },
  {
    title: 'ML-backed understanding',
    body: 'Intent classification via a Hugging Face model, with semantic matching to find the right task even from vague phrasing.',
  },
  {
    title: 'Recurring reminders',
    body: 'Daily, weekly, or monthly tasks that reschedule themselves automatically.',
  },
  {
    title: 'Never miss one',
    body: 'In-app notifications the moment something is due, plus optional email delivery.',
  },
]

interface Props {
  onGetStarted: () => void
}

export function LandingPage({ onGetStarted }: Props) {
  return (
    <div className="flex h-screen items-center justify-center bg-bg px-6 text-text">
      <div className="w-full max-w-2xl text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent/15 text-3xl">
          ✅
        </div>
        <h1 className="text-4xl font-bold tracking-tight">Custom To-Do Bot</h1>
        <p className="mt-4 text-lg text-muted">
          A conversational task &amp; reminder assistant. Tell it what you need to do, and when
          &mdash; it figures out the rest.
        </p>

        <button
          onClick={onGetStarted}
          className="mt-8 rounded-lg bg-accent px-8 py-3 text-base font-semibold text-white hover:opacity-90"
        >
          Get Started
        </button>

        <div className="mt-14 grid grid-cols-1 gap-4 text-left sm:grid-cols-2">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-xl border border-border bg-panel p-4">
              <div className="text-sm font-semibold">{f.title}</div>
              <div className="mt-1 text-sm text-muted">{f.body}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
