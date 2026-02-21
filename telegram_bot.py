from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

import config
import db


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


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Viewed/Ignore button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data
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


async def handle_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /keywords command. Show current or update."""
    args = context.args

    if not args:
        # Show current keywords
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

    # Update keywords — join all args, split by comma, strip whitespace
    raw = " ".join(args)
    keywords = [k.strip() for k in raw.split(",") if k.strip()]
    db.set_setting("keywords", ",".join(keywords))

    formatted = ", ".join(keywords)
    await update.message.reply_text(f"Keywords updated:\n{formatted}")


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /location command. Show current or update."""
    args = context.args

    if not args:
        current = db.get_setting("location")
        if current:
            await update.message.reply_text(
                f"Current location: {current}\n\n"
                f"To update: /location Bangalore"
            )
        else:
            await update.message.reply_text(
                "No location set.\n"
                "Usage: /location Bangalore"
            )
        return

    location = " ".join(args).strip()
    db.set_setting("location", location)
    await update.message.reply_text(f"Location updated: {location}")


def create_application():
    """Create and configure the Telegram bot application."""
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("keywords", handle_keywords))
    app.add_handler(CommandHandler("location", handle_location))
    app.add_handler(CallbackQueryHandler(handle_callback))
    return app
