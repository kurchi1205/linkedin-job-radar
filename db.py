import sqlite3
import os
from datetime import datetime

import config


def _get_conn():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_text TEXT NOT NULL,
            parsed_profile TEXT NOT NULL,
            keywords TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def get_profile():
    conn = _get_conn()
    row = conn.execute("SELECT * FROM profile ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row


def save_profile(raw_text, parsed_profile, keywords):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO profile (raw_text, parsed_profile, keywords) VALUES (?, ?, ?)",
        (raw_text, parsed_profile, keywords),
    )
    conn.commit()
    conn.close()


def job_exists(job_id):
    """Returns True only if job is viewed or ignored. Pending jobs are NOT skipped."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT 1 FROM jobs WHERE job_id = ? AND status IN ('viewed', 'ignored')",
        (job_id,),
    ).fetchone()
    conn.close()
    return row is not None


def insert_job(job_id, title, company, location, url, status="pending"):
    conn = _get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO jobs
           (job_id, title, company, location, url, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (job_id, title, company, location, url, status),
    )
    conn.commit()
    conn.close()


def update_job_status(job_id, status):
    conn = _get_conn()
    conn.execute("UPDATE jobs SET status = ? WHERE job_id = ?", (status, job_id))
    conn.commit()
    conn.close()


def get_setting(key):
    conn = _get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key, value):
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()
    conn.close()

if __name__=="__main__":
    init_db()