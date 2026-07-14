import sqlite3
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = os.path.join(PROJECT_ROOT, "data.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
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
            boss_title       TEXT,
            avatar_url       TEXT,
            location_name    TEXT,
            has_interview      INTEGER,
            is_resume_sent     INTEGER DEFAULT 0,
            has_written_test     INTEGER DEFAULT 0,
            send_resume_datetime INTEGER,
            first_msg_time   INTEGER,
            last_msg_time    INTEGER,
            update_time      INTEGER,
            created_at       TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at       TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS job_info (
            id               TEXT PRIMARY KEY,
            name             TEXT,
            city             TEXT,
            salary_desc      TEXT,
            job_type_desc    TEXT,
            position_name    TEXT,
            detail           TEXT,
            company_url      TEXT,
            company_name     TEXT,
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
            created_at       TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_messages_boss ON chat_messages(encrypt_boss_id);
        CREATE INDEX IF NOT EXISTS idx_messages_time ON chat_messages(time);

        CREATE TABLE IF NOT EXISTS sync_logs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_time    TEXT DEFAULT (datetime('now', 'localtime')),
            sync_days    INTEGER DEFAULT 0,
            friends      INTEGER DEFAULT 0,
            new_messages INTEGER DEFAULT 0,
            updated      INTEGER DEFAULT 0,
            skipped      INTEGER DEFAULT 0,
            errors       TEXT
        );

        CREATE TABLE IF NOT EXISTS message_failed_queue (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            boss_name        TEXT NOT NULL,
            encrypt_boss_id  TEXT,
            message          TEXT NOT NULL,
            error            TEXT,
            retry_count      INTEGER DEFAULT 0,
            created_at       TEXT DEFAULT (datetime('now', 'localtime'))
        );
    """)
    conn.commit()

    # migrations
    boss_cols = [row[1] for row in conn.execute("PRAGMA table_info(bosses)").fetchall()]
    msg_cols = [row[1] for row in conn.execute("PRAGMA table_info(chat_messages)").fetchall()]
    log_cols = [row[1] for row in conn.execute("PRAGMA table_info(sync_logs)").fetchall()]

    # legacy migrations (chat_messages)
    if "side" not in msg_cols:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN side TEXT DEFAULT 'right'")
        conn.commit()

    # legacy migrations (bosses) — add cols if missing
    if "first_msg_time" not in boss_cols:
        conn.execute("ALTER TABLE bosses ADD COLUMN first_msg_time INTEGER")
        conn.execute("ALTER TABLE bosses ADD COLUMN last_msg_time INTEGER")
        conn.commit()
    if "has_written_test" not in boss_cols:
        conn.execute("ALTER TABLE bosses ADD COLUMN has_written_test INTEGER DEFAULT 0")
        conn.commit()
    if "boss_title" not in boss_cols:
        conn.execute("ALTER TABLE bosses ADD COLUMN boss_title TEXT")
        conn.commit()
    if "send_resume_datetime" not in boss_cols:
        conn.execute("ALTER TABLE bosses ADD COLUMN send_resume_datetime INTEGER")
        conn.commit()

    # migration: job_id + company_name + company_url on bosses
    if "job_id" not in boss_cols:
        conn.execute("ALTER TABLE bosses ADD COLUMN job_id TEXT")
        conn.execute("ALTER TABLE bosses ADD COLUMN company_name TEXT")
        conn.execute("ALTER TABLE bosses ADD COLUMN company_url TEXT")
        conn.commit()

    # migration: drop old job-related columns from bosses (SQLite 3.35+)
    for old_col in ("brand_name", "job_name", "job_city", "salary_desc", "job_type_desc", "position_name"):
        if old_col in boss_cols:
            try:
                conn.execute(f"ALTER TABLE bosses DROP COLUMN {old_col}")
                conn.commit()
            except Exception:
                pass  # sqlite version doesn't support DROP COLUMN

    # migration: add updated column to sync_logs
    if "updated" not in log_cols:
        conn.execute("ALTER TABLE sync_logs ADD COLUMN updated INTEGER DEFAULT 0")
        conn.commit()

    # migration: remove foreign key from chat_messages (SQLite 不支持 DROP CONSTRAINT，需重建)
    fks = conn.execute("PRAGMA foreign_key_list(chat_messages)").fetchall()
    if fks:
        conn.executescript("""
            CREATE TABLE chat_messages_new (
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
                created_at       TEXT DEFAULT (datetime('now', 'localtime'))
            );
            INSERT INTO chat_messages_new SELECT * FROM chat_messages;
            DROP TABLE chat_messages;
            ALTER TABLE chat_messages_new RENAME TO chat_messages;
            CREATE INDEX IF NOT EXISTS idx_messages_boss ON chat_messages(encrypt_boss_id);
            CREATE INDEX IF NOT EXISTS idx_messages_time ON chat_messages(time);
        """)
        conn.commit()

    conn.close()
