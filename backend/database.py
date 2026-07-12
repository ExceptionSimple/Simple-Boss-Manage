import sqlite3
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = os.path.join(PROJECT_ROOT, "data.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bosses (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            encrypt_boss_id  TEXT UNIQUE NOT NULL,
            boss_id          INTEGER,
            name             TEXT,
            avatar_url       TEXT,
            brand_name       TEXT,
            job_name         TEXT,
            position_name    TEXT,
            job_city         TEXT,
            location_name    TEXT,
            salary_desc      TEXT,
            job_type_desc    TEXT,
            has_interview      INTEGER,
            is_resume_sent     INTEGER DEFAULT 0,
            has_written_test   INTEGER DEFAULT 0,
            first_msg_time   INTEGER,
            last_msg_time    INTEGER,
            update_time      INTEGER,
            created_at       TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at       TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id               INTEGER PRIMARY KEY,
            encrypt_boss_id  TEXT NOT NULL,
            received         INTEGER,
            body_type        INTEGER,
            body_content     TEXT,
            push_text        TEXT,
            side             TEXT DEFAULT 'right',
            status           INTEGER,
            time             INTEGER,
            from_name        TEXT,
            to_name          TEXT,
            created_at       TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (encrypt_boss_id) REFERENCES bosses(encrypt_boss_id)
        );

        CREATE INDEX IF NOT EXISTS idx_messages_boss ON chat_messages(encrypt_boss_id);
        CREATE INDEX IF NOT EXISTS idx_messages_time ON chat_messages(time);
    """)
    conn.commit()

    # migrations
    cols = [row[1] for row in conn.execute("PRAGMA table_info(chat_messages)").fetchall()]
    boss_cols = [row[1] for row in conn.execute("PRAGMA table_info(bosses)").fetchall()]

    if "side" not in cols:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN side TEXT DEFAULT 'right'")
        conn.commit()
    if "first_msg_time" not in boss_cols:
        conn.execute("ALTER TABLE bosses ADD COLUMN first_msg_time INTEGER")
        conn.execute("ALTER TABLE bosses ADD COLUMN last_msg_time INTEGER")
        conn.commit()
    if "has_written_test" not in boss_cols:
        conn.execute("ALTER TABLE bosses ADD COLUMN has_written_test INTEGER DEFAULT 0")
        conn.commit()

    conn.close()
