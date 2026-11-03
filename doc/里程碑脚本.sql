-- 里程碑功能 SQL 脚本
-- 日期：2026-10-27
-- 操作人：lovexiaoling
-- 说明：服务启动时由 backend/database.py 的 init_db() 自动执行迁移，本文件用于查阅和手工恢复。

-- 1. 里程碑表
CREATE TABLE IF NOT EXISTS milestones (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT UNIQUE NOT NULL,
    status     TEXT NOT NULL DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    frozen_at  TEXT
);

-- 2. 业务表增加 milestone_id（新库直接按下列结构建表）

CREATE TABLE IF NOT EXISTS bosses (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    encrypt_boss_id  TEXT NOT NULL,
    milestone_id     INTEGER NOT NULL,
    boss_id          INTEGER,
    name             TEXT,
    boss_title       TEXT,
    avatar_url       TEXT,
    location_name    TEXT,
    has_interview    INTEGER,
    is_resume_sent   INTEGER DEFAULT 0,
    has_written_test INTEGER DEFAULT 0,
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
    id            TEXT NOT NULL,
    milestone_id  INTEGER NOT NULL,
    name          TEXT,
    city          TEXT,
    salary_desc   TEXT,
    job_type_desc TEXT,
    position_name TEXT,
    detail        TEXT,
    company_url   TEXT,
    company_name  TEXT,
    created_at    TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at    TEXT DEFAULT (datetime('now', 'localtime')),
    PRIMARY KEY (id, milestone_id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id              INTEGER NOT NULL,
    milestone_id    INTEGER NOT NULL,
    encrypt_boss_id TEXT NOT NULL,
    received        INTEGER,
    body_type       INTEGER,
    body_content    TEXT,
    push_text       TEXT,
    side            TEXT DEFAULT 'right',
    status          INTEGER,
    time            INTEGER,
    from_name       TEXT,
    to_name         TEXT,
    created_at      TEXT DEFAULT (datetime('now', 'localtime')),
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
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    milestone_id    INTEGER NOT NULL,
    boss_name       TEXT NOT NULL,
    encrypt_boss_id TEXT,
    message         TEXT NOT NULL,
    error           TEXT,
    retry_count     INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 3. 索引
CREATE INDEX IF NOT EXISTS idx_bosses_milestone ON bosses(milestone_id);
CREATE INDEX IF NOT EXISTS idx_job_info_milestone ON job_info(milestone_id);
CREATE INDEX IF NOT EXISTS idx_messages_boss ON chat_messages(milestone_id, encrypt_boss_id);
CREATE INDEX IF NOT EXISTS idx_messages_time ON chat_messages(milestone_id, time);
CREATE INDEX IF NOT EXISTS idx_sync_logs_milestone ON sync_logs(milestone_id);
CREATE INDEX IF NOT EXISTS idx_failed_queue_milestone ON message_failed_queue(milestone_id);

-- 4. 存量数据迁移逻辑（由 init_db 执行，等价步骤）
-- 4.1 若业务表有数据且 milestones 为空，插入 M1：
-- INSERT INTO milestones (name, status) VALUES ('M1', 'active');
-- 4.2 重建 bosses / job_info / chat_messages，补充 milestone_id 并调整约束；
-- 4.3 sync_logs / message_failed_queue 增加 milestone_id；
-- 4.4 所有存量行 milestone_id 指向 M1。
