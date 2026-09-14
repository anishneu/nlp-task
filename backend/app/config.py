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

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_TO = os.getenv("SMTP_TO")
