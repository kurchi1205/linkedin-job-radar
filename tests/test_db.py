import db


# --- profile table ---

def test_get_profile_returns_none_when_empty():
    assert db.get_profile() is None


def test_save_and_get_profile():
    db.save_profile("raw resume text", "parsed summary", "Python,Django,AWS")
    profile = db.get_profile()
    assert profile is not None
    assert profile["raw_text"] == "raw resume text"
    assert profile["parsed_profile"] == "parsed summary"
    assert profile["keywords"] == "Python,Django,AWS"


def test_get_profile_returns_latest():
    db.save_profile("old", "old profile", "Java")
    db.save_profile("new", "new profile", "Python")
    profile = db.get_profile()
    assert profile["parsed_profile"] == "new profile"
    assert profile["keywords"] == "Python"


# --- jobs table ---

def test_job_exists_false_when_empty():
    assert db.job_exists("12345") is False


def test_insert_job_and_exists():
    db.insert_job("12345", "Engineer", "Acme", "Singapore", "https://link", "desc")
    assert db.job_exists("12345") is True


def test_insert_duplicate_job_ignored():
    db.insert_job("12345", "Engineer", "Acme", "SG", "https://link", "desc")
    db.insert_job("12345", "Different", "Other", "US", "https://other", "other")
    # Should still have original data (INSERT OR IGNORE)
    assert db.job_exists("12345") is True


def test_insert_job_default_status_pending():
    db.insert_job("12345", "Engineer", "Acme", "SG", "https://link", "desc")
    import sqlite3, config
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status FROM jobs WHERE job_id = '12345'").fetchone()
    conn.close()
    assert row["status"] == "pending"


def test_update_job_status():
    db.insert_job("12345", "Engineer", "Acme", "SG", "https://link", "desc")
    db.update_job_status("12345", "viewed")
    import sqlite3, config
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status FROM jobs WHERE job_id = '12345'").fetchone()
    conn.close()
    assert row["status"] == "viewed"


def test_update_job_status_to_ignored():
    db.insert_job("99999", "Designer", "Co", "NY", "https://link", "desc")
    db.update_job_status("99999", "ignored")
    import sqlite3, config
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status FROM jobs WHERE job_id = '99999'").fetchone()
    conn.close()
    assert row["status"] == "ignored"


# --- settings table ---

def test_get_setting_returns_none_when_missing():
    assert db.get_setting("nonexistent") is None


def test_set_and_get_setting():
    db.set_setting("keywords", "Python,Django")
    assert db.get_setting("keywords") == "Python,Django"


def test_set_setting_overwrites():
    db.set_setting("location", "Singapore")
    db.set_setting("location", "Bangalore")
    assert db.get_setting("location") == "Bangalore"


def test_multiple_settings_independent():
    db.set_setting("keywords", "Python")
    db.set_setting("location", "NYC")
    assert db.get_setting("keywords") == "Python"
    assert db.get_setting("location") == "NYC"
