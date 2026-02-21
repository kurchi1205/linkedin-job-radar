import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import db
from telegram_bot import (
    _escape_md,
    _build_message,
    _build_keyboard,
    handle_keywords,
    handle_location,
    handle_callback,
)


# --- _escape_md ---

def test_escape_md_plain_text():
    assert _escape_md("hello world") == "hello world"


def test_escape_md_special_chars():
    result = _escape_md("C++ & C#")
    assert "+" in result
    assert "#" in result


def test_escape_md_brackets():
    result = _escape_md("test [value]")
    assert "\\[" in result
    assert "\\]" in result


def test_escape_md_dots_and_dashes():
    result = _escape_md("Sr. Engineer - Backend")
    assert "\\." in result
    assert "\\-" in result


# --- _build_message ---

def test_build_message_contains_job_info():
    job = {
        "title": "Python Dev",
        "company": "Acme",
        "location": "Singapore",
        "url": "https://linkedin.com/jobs/view/123/",
    }
    msg = _build_message(job)
    assert "Python Dev" in msg
    assert "Acme" in msg
    assert "Singapore" in msg
    assert "https://linkedin.com/jobs/view/123/" in msg


# --- _build_keyboard ---

def test_build_keyboard_has_two_buttons():
    kb = _build_keyboard("12345")
    assert len(kb.inline_keyboard) == 1  # one row
    assert len(kb.inline_keyboard[0]) == 2  # two buttons
    assert kb.inline_keyboard[0][0].callback_data == "viewed:12345"
    assert kb.inline_keyboard[0][1].callback_data == "ignored:12345"


# --- /keywords command ---

@pytest.mark.asyncio
async def test_handle_keywords_show_current():
    """When no args, show current keywords."""
    db.set_setting("keywords", "Python,Django,AWS")

    update = MagicMock()
    update.message = AsyncMock()
    context = MagicMock()
    context.args = []

    await handle_keywords(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "Python" in call_text
    assert "Django" in call_text


@pytest.mark.asyncio
async def test_handle_keywords_show_empty():
    """When no args and no keywords set, show usage."""
    update = MagicMock()
    update.message = AsyncMock()
    context = MagicMock()
    context.args = []

    await handle_keywords(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "No keywords set" in call_text


@pytest.mark.asyncio
async def test_handle_keywords_update():
    """When args provided, update keywords in DB."""
    update = MagicMock()
    update.message = AsyncMock()
    context = MagicMock()
    context.args = ["React,", "Node.js,", "TypeScript"]

    await handle_keywords(update, context)

    saved = db.get_setting("keywords")
    assert "React" in saved
    assert "Node.js" in saved
    assert "TypeScript" in saved

    call_text = update.message.reply_text.call_args[0][0]
    assert "updated" in call_text.lower()


# --- /location command ---

@pytest.mark.asyncio
async def test_handle_location_show_current():
    """When no args, show current location."""
    db.set_setting("location", "Bangalore")

    update = MagicMock()
    update.message = AsyncMock()
    context = MagicMock()
    context.args = []

    await handle_location(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "Bangalore" in call_text


@pytest.mark.asyncio
async def test_handle_location_show_empty():
    """When no args and no location set, show usage."""
    update = MagicMock()
    update.message = AsyncMock()
    context = MagicMock()
    context.args = []

    await handle_location(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "No location set" in call_text


@pytest.mark.asyncio
async def test_handle_location_update():
    """When args provided, update location in DB."""
    update = MagicMock()
    update.message = AsyncMock()
    context = MagicMock()
    context.args = ["New", "York"]

    await handle_location(update, context)

    assert db.get_setting("location") == "New York"


# --- callback (Viewed/Ignore buttons) ---

@pytest.mark.asyncio
async def test_handle_callback_viewed():
    """Tapping Viewed updates DB status."""
    db.insert_job("555", "Job", "Co", "SG", "https://link", "desc")

    query = AsyncMock()
    query.data = "viewed:555"
    query.message = MagicMock()
    query.message.text_markdown_v2 = "some message"

    update = MagicMock()
    update.callback_query = query
    context = MagicMock()

    await handle_callback(update, context)

    query.answer.assert_called_once()
    query.edit_message_reply_markup.assert_called_once_with(reply_markup=None)

    import sqlite3, config
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status FROM jobs WHERE job_id = '555'").fetchone()
    conn.close()
    assert row["status"] == "viewed"


@pytest.mark.asyncio
async def test_handle_callback_ignored():
    """Tapping Ignore updates DB status."""
    db.insert_job("666", "Job", "Co", "SG", "https://link", "desc")

    query = AsyncMock()
    query.data = "ignored:666"
    query.message = MagicMock()
    query.message.text_markdown_v2 = "some message"

    update = MagicMock()
    update.callback_query = query
    context = MagicMock()

    await handle_callback(update, context)

    import sqlite3, config
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status FROM jobs WHERE job_id = '666'").fetchone()
    conn.close()
    assert row["status"] == "ignored"
