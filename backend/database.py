import os
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = os.path.join(PROJECT_ROOT, "data.db")

# 里程碑迁移时用于复制数据的完整列清单
BOSS_COLUMNS = [
    "id", "encrypt_boss_id", "boss_id", "name", "boss_title", "avatar_url",
    "location_name", "has_interview", "is_resume_sent", "has_written_test",
    "send_resume_datetime", "first_msg_time", "last_msg_time", "update_time",
    "job_id", "company_name", "company_url", "created_at", "updated_at",
]
JOB_INFO_COLUMNS = [
    "id", "name", "city", "salary_desc", "job_type_desc", "position_name",
    "detail", "company_url", "company_name", "created_at", "updated_at",
]
CHAT_MESSAGE_COLUMNS = [
    "id", "encrypt_boss_id", "received", "body_type", "body_content",
    "push_text", "side", "status", "time", "from_name", "to_name", "created_at",
]

DATA_TABLES = ["bosses", "job_info", "chat_messages", "sync_logs", "message_failed_queue"]


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS milestones (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT UNIQUE NOT NULL,
            status     TEXT NOT NULL DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            frozen_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS bosses (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            encrypt_boss_id  TEXT NOT NULL,
            milestone_id     INTEGER NOT NULL,
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
            job_id           TEXT,
            company_name     TEXT,
            company_url      TEXT,
            created_at       TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at       TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE (encrypt_boss_id, milestone_id)
        );

        CREATE TABLE IF NOT EXISTS job_info (
            id               TEXT NOT NULL,
            milestone_id     INTEGER NOT NULL,
            name             TEXT,
            city             TEXT,
            salary_desc      TEXT,
            job_type_desc    TEXT,
            position_name    TEXT,
            detail           TEXT,
            company_url      TEXT,
            company_name     TEXT,
            created_at       TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at       TEXT DEFAULT (datetime('now', 'localtime')),
            PRIMARY KEY (id, milestone_id)
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id               INTEGER NOT NULL,
            milestone_id     INTEGER NOT NULL,
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
            PRIMARY KEY (id, milestone_id)
        );

        CREATE TABLE IF NOT EXISTS sync_logs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            milestone_id INTEGER NOT NULL,
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
            milestone_id     INTEGER NOT NULL,
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
        """)
        conn.commit()

    _migrate_to_milestones(conn)
    _create_milestone_indexes(conn)
    conn.close()


def _copy_columns(conn: sqlite3.Connection, table: str, columns: list[str]) -> list[str]:
    """返回旧表中实际存在的列，避免老库缺列时复制失败"""
    existing = set(_table_columns(conn, table))
    return [col for col in columns if col in existing]


def _rebuild_bosses(conn: sqlite3.Connection, milestone_id: int):
    cols = _copy_columns(conn, "bosses", BOSS_COLUMNS)
    insert_cols = ", ".join(cols + ["milestone_id"])
    select_cols = ", ".join(cols + [str(int(milestone_id))])
    conn.executescript(f"""
        CREATE TABLE bosses_milestone_new (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            encrypt_boss_id  TEXT NOT NULL,
            milestone_id     INTEGER NOT NULL,
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
            job_id           TEXT,
            company_name     TEXT,
            company_url      TEXT,
            created_at       TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at       TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE (encrypt_boss_id, milestone_id)
        );
        INSERT INTO bosses_milestone_new ({insert_cols})
        SELECT {select_cols} FROM bosses;
        DROP TABLE bosses;
        ALTER TABLE bosses_milestone_new RENAME TO bosses;
    """)


def _rebuild_job_info(conn: sqlite3.Connection, milestone_id: int):
    cols = _copy_columns(conn, "job_info", JOB_INFO_COLUMNS)
    insert_cols = ", ".join(cols + ["milestone_id"])
    select_cols = ", ".join(cols + [str(int(milestone_id))])
    conn.executescript(f"""
        CREATE TABLE job_info_milestone_new (
            id               TEXT NOT NULL,
            milestone_id     INTEGER NOT NULL,
            name             TEXT,
            city             TEXT,
            salary_desc      TEXT,
            job_type_desc    TEXT,
            position_name    TEXT,
            detail           TEXT,
            company_url      TEXT,
            company_name     TEXT,
            created_at       TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at       TEXT DEFAULT (datetime('now', 'localtime')),
            PRIMARY KEY (id, milestone_id)
        );
        INSERT INTO job_info_milestone_new ({insert_cols})
        SELECT {select_cols} FROM job_info;
        DROP TABLE job_info;
        ALTER TABLE job_info_milestone_new RENAME TO job_info;
    """)


def _rebuild_chat_messages(conn: sqlite3.Connection, milestone_id: int):
    cols = _copy_columns(conn, "chat_messages", CHAT_MESSAGE_COLUMNS)
    insert_cols = ", ".join(cols + ["milestone_id"])
    select_cols = ", ".join(cols + [str(int(milestone_id))])
    conn.executescript(f"""
        CREATE TABLE chat_messages_milestone_new (
            id               INTEGER NOT NULL,
            milestone_id     INTEGER NOT NULL,
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
            PRIMARY KEY (id, milestone_id)
        );
        INSERT INTO chat_messages_milestone_new ({insert_cols})
        SELECT {select_cols} FROM chat_messages;
        DROP TABLE chat_messages;
        ALTER TABLE chat_messages_milestone_new RENAME TO chat_messages;
    """)


def _migrate_to_milestones(conn: sqlite3.Connection):
    """给业务表补充 milestone_id；有存量数据时自动创建 M1 并归入"""
    missing = [t for t in DATA_TABLES if "milestone_id" not in _table_columns(conn, t)]
    if not missing:
        return

    row = conn.execute("SELECT id FROM milestones ORDER BY id LIMIT 1").fetchone()
    has_data = any(
        conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
        for table in DATA_TABLES
    )

    if row:
        milestone_id = row["id"]
    elif has_data:
        cur = conn.execute("INSERT INTO milestones (name, status) VALUES ('M1', 'active')")
        milestone_id = cur.lastrowid
    else:
        milestone_id = 0

    if "milestone_id" not in _table_columns(conn, "bosses"):
        _rebuild_bosses(conn, milestone_id)
    if "milestone_id" not in _table_columns(conn, "job_info"):
        _rebuild_job_info(conn, milestone_id)
    if "milestone_id" not in _table_columns(conn, "chat_messages"):
        _rebuild_chat_messages(conn, milestone_id)
    for table in ("sync_logs", "message_failed_queue"):
        if "milestone_id" not in _table_columns(conn, table):
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN milestone_id INTEGER NOT NULL "
                f"DEFAULT {int(milestone_id)}"
            )
    conn.commit()


def _create_milestone_indexes(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_bosses_milestone ON bosses(milestone_id);
        CREATE INDEX IF NOT EXISTS idx_job_info_milestone ON job_info(milestone_id);
        CREATE INDEX IF NOT EXISTS idx_messages_boss ON chat_messages(milestone_id, encrypt_boss_id);
        CREATE INDEX IF NOT EXISTS idx_messages_time ON chat_messages(milestone_id, time);
        CREATE INDEX IF NOT EXISTS idx_sync_logs_milestone ON sync_logs(milestone_id);
        CREATE INDEX IF NOT EXISTS idx_failed_queue_milestone ON message_failed_queue(milestone_id);
    """)
    conn.commit()
