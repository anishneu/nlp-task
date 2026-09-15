import random

# Local phrasing variety — a few hand-written options per message type,
# picked at random, instead of either (a) one fixed string forever, which
# reads as robotic fast, or (b) an LLM call to reword it every time, which
# reads as natural but costs 2-6s+ of latency and real free-tier quota on
# nearly every message. 3-4 options is enough that the same wording won't
# repeat often in normal use — there's no real gain past that, since a user
# rarely sends the exact same kind of request back-to-back enough times to
# notice a small pool cycling. This runs unconditionally (it's the base
# template layer); HF_REPLY_ENABLED, when on, rephrases *on top* of
# whichever of these gets picked.


def pick(options: list[str], **kwargs) -> str:
    return random.choice(options).format(**kwargs)


CONFIRM_TASK = [
    'Got it — I\'ve scheduled "{title}"{when}{repeats}.{link_note}',
    'Done! "{title}" is on the calendar{when}{repeats}.{link_note}',
    'Alright, I\'ve added "{title}"{when}{repeats}.{link_note}',
    'You\'re all set — "{title}"{when}{repeats}.{link_note}',
]

CONFIRM_MULTI = [
    "Got it — I've scheduled {n} {noun}:\n{lines}",
    "Done! I've added {n} {noun}:\n{lines}",
    "All set — here's what I scheduled:\n{lines}",
]

ASK_TITLE = [
    "What would you like the reminder to be about?",
    "Sure — what should I remind you about?",
    "Happy to help — what's the task?",
]

ASK_TIME = [
    'What time should I remind you to "{title}"?',
    'Got it — what time works for "{title}"?',
    'Sure, what time should that be for "{title}"?',
]

ASK_RESCHEDULE_TIME = [
    'What time should I reschedule "{title}" to?',
    'Got it — what time should "{title}" move to?',
    'Sure, what time works for "{title}"?',
]

ASK_RESCHEDULE_TIME_CHAINED = [
    'Got it, "{title}" — what time should I reschedule it to?',
    'Okay, "{title}" — what time works?',
    '"{title}" it is — what time should that move to?',
]

NO_TASKS = [
    "You have no matching tasks.",
    "Nothing matching that right now.",
    "No tasks match — you're all clear.",
]

LIST_TASKS = [
    "You have {n} task(s):\n{lines}",
    "Here's what's on your list — {n} task(s):\n{lines}",
    "You've got {n} task(s):\n{lines}",
]

MARKED_DONE = [
    'Marked "{title}" as completed.',
    'Nice work — "{title}" is marked done.',
    'Done! "{title}" is checked off.',
]

DELETED = [
    'Deleted "{title}".',
    'Got it — "{title}" is gone.',
    'Removed "{title}" for you.',
]

RESCHEDULED = [
    'Got it — rescheduled "{title}" to {due}.',
    'Done — "{title}" is now set for {due}.',
    'Updated! "{title}" moved to {due}.',
]

NOT_FOUND = [
    'I couldn\'t find a task matching "{query}".',
    'Hmm, nothing matching "{query}" turned up.',
    'I don\'t see a task matching "{query}".',
]

WHICH_TASK = [
    "Which task do you mean?",
    "Which one are you referring to?",
    "Which task should that apply to?",
]

MULTI_MATCH = [
    "I found multiple matching tasks: {titles}. Which one did you mean?",
    "A few tasks match that: {titles}. Which one?",
    "Found more than one match: {titles}. Which did you mean?",
]

GREETING = [
    "{greeting} I'm {name}, your virtual chatbot assistant. How may I help you?",
    "{greeting} I'm {name} — what can I help you with today?",
    "{greeting} {name} here, ready to help with your tasks.",
]

THANKS = [
    "You're welcome!",
    "Happy to help!",
    "Anytime!",
    "No problem — let me know if you need anything else.",
]

SET_NAME_CONFIRM = [
    "Sure, you can call me {name} from now on!",
    "Got it — {name} it is!",
    "Sounds good, I'll go by {name} from now on!",
]

SET_NAME_QUERY = [
    'You can call me {name}. Just say "call me <name>" to rename me.',
    'I\'m {name}! Say "call me <name>" any time to change that.',
]

UNKNOWN = [
    'I didn\'t understand that. Try something like "Remind me to call Mom on Friday at 6 PM."',
    'Sorry, I\'m not sure what you mean. Try something like "Remind me to call Mom on Friday at 6 PM."',
    'Hmm, that didn\'t quite land. Try something like "Remind me to call Mom on Friday at 6 PM."',
]

COMPOUND_ACTION = [
    "Done — {actions}.",
    "All set — {actions}.",
    "Got it — {actions}.",
]
