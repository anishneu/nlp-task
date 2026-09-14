import os

from dotenv import load_dotenv

load_dotenv()

# An IANA timezone name (e.g. "America/New_York") for resolving "now" —
# every due date, timestamp, and overdue check in the app is computed in
# this timezone. Leave unset to fall back to the server process's own
# system timezone, which only matches you if the machine running the
# backend is actually configured for where you live.
APP_TIMEZONE = os.getenv("APP_TIMEZONE")

HF_TOKEN = os.getenv("HF_TOKEN")
HF_INTENT_MODEL = os.getenv("HF_INTENT_MODEL", "facebook/bart-large-mnli")
HF_REPLY_MODEL = os.getenv("HF_REPLY_MODEL", "google/gemma-2-2b-it:featherless-ai")
# Tried only when HF_REPLY_MODEL fails for a reason other than quota
# exhaustion (timeout, connection error, a provider-specific capacity
# error) — HF's free third-party quota is one pool shared across every
# provider, so this is NOT a second quota, just resilience against a
# single provider having a bad moment.
HF_REPLY_FALLBACK_MODEL = os.getenv("HF_REPLY_FALLBACK_MODEL", "meta-llama/Llama-3.1-8B-Instruct:novita")
