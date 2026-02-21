# LinkedIn Job Radar

An automated job monitoring agent that scrapes LinkedIn, matches jobs to your resume, and sends alerts to Telegram with interactive buttons.

## How It Works

```
Resume (Google Docs)
    |
    v
Ollama extracts job title keywords (one-time)
    |
    v
Every 10 mins: scrape LinkedIn for each keyword
    |
    v
New job found? (not viewed/ignored)
    |
    v
Send to Telegram with [Viewed] [Ignore] buttons
```

## Features

- **Resume parsing** - Fetches your resume from Google Docs, extracts job title keywords using Ollama (Mistral 7B)
- **LinkedIn scraping** - Scrapes public LinkedIn job listings using requests + BeautifulSoup (no login needed)
- **Telegram alerts** - Sends job cards with title, company, location, and link
- **Interactive buttons** - Mark jobs as Viewed or Ignored directly in Telegram
- **Dedup** - Only pending jobs are shown again; viewed/ignored jobs never resurface
- **Live settings** - Change keywords, location, and timeframe via Telegram commands without restarting
- **Auto scan on change** - Every settings change triggers an immediate scan

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/keywords` | View current keywords |
| `/keywords React, Node.js, Backend` | Update keywords and scan |
| `/location` | Pick location from preset buttons |
| `/location Tokyo` | Set custom location and scan |
| `/timeframe` | Pick timeframe from buttons (24h / 48h / week) |
| `/timeframe 24h` | Set timeframe directly and scan |
| `/profile` | View current parsed profile |
| `/profile refresh` | Re-parse resume from Google Docs and scan |

## Tech Stack

| Component | Technology |
|-----------|------------|
| LLM (resume parsing) | Ollama + Mistral 7B (local, free) |
| LinkedIn scraping | requests + BeautifulSoup (no auth) |
| Database | SQLite |
| Scheduler | APScheduler |
| Notifications | python-telegram-bot |
| Config | python-dotenv |

**Total running cost: $0** - everything runs locally.

## Setup

### 1. Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running

### 2. Install Ollama and pull a model

```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama
ollama serve

# Pull model (in another terminal)
ollama pull mistral
```

### 3. Clone and install dependencies

```bash
git clone <repo-url>
cd linkedin-job-radar
pip install -r requirements.txt
```

### 4. Create a Telegram bot

1. Open Telegram, search for **@BotFather**
2. Send `/newbot`, pick a name and username
3. Copy the **bot token** (looks like `7123456789:AAH...`)
4. Start a chat with your new bot and send any message
5. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in browser
6. Find your **chat ID** from the JSON response: `"chat":{"id":123456789}`

### 5. Prepare your resume

1. Put your resume in Google Docs
2. Share it as **"Anyone with the link can view"**
3. Copy the link(s)

### 6. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Telegram
TELEGRAM_BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=123456789

# Ollama
OLLAMA_MODEL=mistral

# Job Search
JOB_LOCATION=Singapore
JOB_TIMEFRAME=r604800
SCRAPE_INTERVAL_MINUTES=10

# Resume (comma-separated Google Docs links)
RESUME_LINKS=https://docs.google.com/document/d/YOUR_DOC_ID/edit

# Database
DB_PATH=data/jobs.db
```

**Timeframe options:**
- `r86400` - Past 24 hours
- `r172800` - Past 48 hours
- `r604800` - Past week

### 7. Run

```bash
python main.py
```

On first run:
1. Parses your resume via Ollama
2. Extracts job title keywords
3. Seeds settings into the database
4. Runs first LinkedIn scan
5. Sends matching jobs to Telegram
6. Continues scanning every 10 minutes

## Project Structure

```
linkedin-job-radar/
├── config.py              # Settings from .env
├── db.py                  # SQLite: profile, jobs, settings tables
├── resume_parser.py       # Google Docs fetch + Ollama keyword extraction
├── scraper.py             # LinkedIn public page scraper
├── telegram_bot.py        # Bot commands, alerts, inline buttons
├── main.py                # Entry point + scheduler
├── requirements.txt
├── .env.example
├── data/                  # SQLite database (auto-created)
└── tests/
    ├── test_db.py
    ├── test_resume_parser.py
    ├── test_scraper.py
    └── test_telegram_bot.py
```

## Running Tests

```bash
python -m pytest tests/ -v
```

Run specific test files:

```bash
python -m pytest tests/test_db.py tests/test_resume_parser.py -v
```

## Database Schema

**profile** - Parsed resume data (one-time, refreshable via `/profile refresh`)

**jobs** - All scraped jobs with status tracking
| Status | Meaning |
|--------|---------|
| `pending` | Sent to Telegram, shown again until acted on |
| `viewed` | User tapped Viewed, never shown again |
| `ignored` | User tapped Ignore, never shown again |

**settings** - Key-value store for `keywords`, `location`, `timeframe`

## Notes

- LinkedIn public page scraping has no auth requirement, but results are limited compared to logged-in search
- Each keyword is searched independently to avoid zero-result searches
- Ollama must be running in the background (`ollama serve`)
- Resume Google Docs must be shared as "Anyone with the link can view"
