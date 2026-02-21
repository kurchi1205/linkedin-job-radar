from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

import config
import db
import scraper


def _build_message(job):
    return (
        f"\U0001f195 *{_escape_md(job['title'])}*\n"
        f"\U0001f3e2 {_escape_md(job['company'])}, {_escape_md(job['location'])}\n"
        f"\U0001f517 [View Job]({job['url']})"
    )


def _escape_md(text):
    """Escape special characters for Telegram MarkdownV2."""
    special = r"_*[]()~`>#+-=|{}.!"
    for ch in special:
        text = text.replace(ch, f"\\{ch}")
    return text


def _build_keyboard(job_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("\u2705 Viewed", callback_data=f"viewed:{job_id}"),
            InlineKeyboardButton("\u274c Ignore", callback_data=f"ignored:{job_id}"),
        ]
    ])


async def send_job_alert(application, job):
    """Send a job alert message to the configured Telegram chat."""
    message = _build_message(job)
    keyboard = _build_keyboard(job["job_id"])

    await application.bot.send_message(
        chat_id=config.TELEGRAM_CHAT_ID,
        text=message,
        parse_mode="MarkdownV2",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


async def _trigger_scan(application):
    """Run a scan and send results. Called after settings change."""
    keywords_str = db.get_setting("keywords")
    location = db.get_setting("location")
    timeframe = db.get_setting("timeframe") or "r604800"

    if not keywords_str or not location:
        return

    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]

    try:
        new_jobs = scraper.scrape_new_jobs(keywords, location, timeframe)
    except Exception as e:
        await application.bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=f"Scan failed: {e}",
        )
        return

    sent = 0
    for job in new_jobs:
        db.insert_job(
            job_id=job["job_id"],
            title=job["title"],
            company=job["company"],
            location=job["location"],
            url=job["url"],
            status="pending",
        )
        try:
            await send_job_alert(application, job)
            sent += 1
        except Exception:
            pass

    await application.bot.send_message(
        chat_id=config.TELEGRAM_CHAT_ID,
        text=f"Scan complete. Found {len(new_jobs)} new jobs, sent {sent} alerts.",
    )


# --- Timeframe config ---

TIMEFRAME_OPTIONS = {
    "24h": "r86400",
    "48h": "r172800",
    "week": "r604800",
}

TIMEFRAME_LABELS = {
    "r86400": "Past 24 hours",
    "r172800": "Past 48 hours",
    "r604800": "Past week",
}

# --- Preset locations ---

LOCATION_PRESETS = [
    "Singapore",
    "Bangalore",
    "Remote",
    "United States",
    "London",
]


# --- Callback handler ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data

    # Timeframe buttons
    if data.startswith("tf:"):
        value = data.split(":", 1)[1]
        db.set_setting("timeframe", value)
        label = TIMEFRAME_LABELS.get(value, value)
        await query.edit_message_text(f"Timeframe updated: {label}\n\nRunning scan...")
        await _trigger_scan(context.application)
        return

    # Location buttons
    if data.startswith("loc:"):
        location = data.split(":", 1)[1]
        db.set_setting("location", location)
        await query.edit_message_text(f"Location updated: {location}\n\nRunning scan...")
        await _trigger_scan(context.application)
        return

    # Job Viewed/Ignore buttons
    action, job_id = data.split(":", 1)
    db.update_job_status(job_id, action)

    if action == "viewed":
        label = "\u2705 Marked as Viewed"
    else:
        label = "\u274c Ignored"

    await query.edit_message_reply_markup(reply_markup=None)
    await query.edit_message_text(
        text=query.message.text_markdown_v2 + f"\n\n_{_escape_md(label)}_",
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )


# --- Command handlers ---

async def handle_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /keywords command. Show current or update."""
    args = context.args

    if not args:
        current = db.get_setting("keywords")
        if current:
            keywords = current.split(",")
            formatted = ", ".join(keywords)
            await update.message.reply_text(
                f"Current keywords:\n{formatted}\n\n"
                f"To update: /keywords Python, Backend, Django"
            )
        else:
            await update.message.reply_text(
                "No keywords set.\n"
                "Usage: /keywords Python, Backend, Django"
            )
        return

    raw = " ".join(args)
    keywords = [k.strip() for k in raw.split(",") if k.strip()]
    db.set_setting("keywords", ",".join(keywords))

    formatted = ", ".join(keywords)
    await update.message.reply_text(f"Keywords updated:\n{formatted}\n\nRunning scan...")
    await _trigger_scan(context.application)


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /location command. Show buttons or update with text."""
    args = context.args

    if not args:
        current = db.get_setting("location") or "Not set"

        buttons = []
        row = []
        for loc in LOCATION_PRESETS:
            marker = "\u2713 " if loc == current else ""
            row.append(InlineKeyboardButton(f"{marker}{loc}", callback_data=f"loc:{loc}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        keyboard = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(
            f"Current location: {current}\n\nPick one or type: /location Your City",
            reply_markup=keyboard,
        )
        return

    location = " ".join(args).strip()
    db.set_setting("location", location)
    await update.message.reply_text(f"Location updated: {location}\n\nRunning scan...")
    await _trigger_scan(context.application)


async def handle_timeframe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /timeframe command. Show buttons or update with text."""
    args = context.args

    if not args:
        current = db.get_setting("timeframe") or "r604800"

        buttons = []
        for key, value in TIMEFRAME_OPTIONS.items():
            label = TIMEFRAME_LABELS[value]
            marker = "\u2713 " if value == current else ""
            buttons.append(InlineKeyboardButton(f"{marker}{label}", callback_data=f"tf:{value}"))

        keyboard = InlineKeyboardMarkup([buttons])
        await update.message.reply_text(
            f"Current: {TIMEFRAME_LABELS.get(current, current)}\n\nPick a timeframe:",
            reply_markup=keyboard,
        )
        return

    choice = args[0].lower().strip()
    if choice not in TIMEFRAME_OPTIONS:
        await update.message.reply_text(
            "Invalid option. Use: /timeframe 24h, 48h, or week"
        )
        return

    value = TIMEFRAME_OPTIONS[choice]
    db.set_setting("timeframe", value)
    label = TIMEFRAME_LABELS[value]
    await update.message.reply_text(f"Timeframe updated: {label}\n\nRunning scan...")
    await _trigger_scan(context.application)


async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /profile command. Show current profile or re-parse resume."""
    args = context.args

    if not args:
        profile = db.get_profile()
        if profile:
            keywords = profile["keywords"]
            text = (
                f"Current profile:\n\n"
                f"{profile['parsed_profile']}\n\n"
                f"Keywords: {keywords}\n\n"
                f"To re-parse your resume: /profile refresh"
            )
            if len(text) > 4000:
                text = text[:4000] + "..."
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("No profile found. Run /profile refresh to parse your resume.")
        return

    if args[0].lower() == "refresh":
        await update.message.reply_text("Re-parsing resume from Google Docs... This may take a moment.")

        try:
            import resume_parser
            profile, keywords = resume_parser.get_or_create_profile(overwrite=True)
            db.set_setting("keywords", ",".join(keywords))

            await update.message.reply_text(
                f"Profile updated!\n\n"
                f"{profile}\n\n"
                f"New keywords: {', '.join(keywords)}\n\n"
                f"Running scan..."
            )
            await _trigger_scan(context.application)
        except Exception as e:
            await update.message.reply_text(f"Failed to refresh profile: {e}")
        return

    await update.message.reply_text("Usage:\n  /profile — view current\n  /profile refresh — re-parse resume")


def create_application():
    """Create and configure the Telegram bot application."""
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("keywords", handle_keywords))
    app.add_handler(CommandHandler("location", handle_location))
    app.add_handler(CommandHandler("timeframe", handle_timeframe))
    app.add_handler(CommandHandler("profile", handle_profile))
    app.add_handler(CallbackQueryHandler(handle_callback))
    return app
