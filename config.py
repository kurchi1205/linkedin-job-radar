import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

LINKEDIN_COOKIE = os.getenv("LINKEDIN_COOKIE", "")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

JOB_LOCATION = os.getenv("JOB_LOCATION", "Singapore")
SCRAPE_INTERVAL_MINUTES = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "10"))

# Comma-separated Google Docs links (must be shared as "anyone with link can view")
RESUME_LINKS = [
    link.strip()
    for link in os.getenv("RESUME_LINKS", "").split(",")
    if link.strip()
]
DB_PATH = os.getenv("DB_PATH", "data/jobs.db")
