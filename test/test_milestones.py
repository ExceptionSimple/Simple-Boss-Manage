"""里程碑功能测试。

覆盖：
- 旧库迁移：存量数据归入自动创建的 M1，且不丢数据
- 约束：同一里程碑内 encrypt_boss_id / job_info.id / chat_messages.id 唯一
- 隔离：不同里程碑数据互不影响
- 冻结：active 可写，frozen 写入被拒绝
- 编号：M1、M2、M3 连续生成，新建时自动冻结旧的 active
"""

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import backend.database as db
from backend import milestone_utils


# 里程碑功能上线前的旧库结构
OLD_SCHEMA = """
CREATE TABLE config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE bosses (
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
    updated_at       TEXT DEFAULT (datetime('now', 'localtime')),
    job_id           TEXT,
    company_name     TEXT,
    company_url      TEXT
);
CREATE TABLE job_info (
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
CREATE TABLE chat_messages (
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
CREATE INDEX idx_messages_boss ON chat_messages(encrypt_boss_id);
CREATE INDEX idx_messages_time ON chat_messages(time);
CREATE TABLE sync_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_time    TEXT DEFAULT (datetime('now', 'localtime')),
    sync_days    INTEGER DEFAULT 0,
    friends      INTEGER DEFAULT 0,
    new_messages INTEGER DEFAULT 0,
    updated      INTEGER DEFAULT 0,
    skipped      INTEGER DEFAULT 0,
    errors       TEXT
);
CREATE TABLE message_failed_queue (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    boss_name        TEXT NOT NULL,
    encrypt_boss_id  TEXT,
    message          TEXT NOT NULL,
    error            TEXT,
    retry_count      INTEGER DEFAULT 0,
    created_at       TEXT DEFAULT (datetime('now', 'localtime'))
);
"""

OLD_DATA = """
INSERT INTO bosses (encrypt_boss_id, boss_id, name, job_id, company_name)
VALUES ('e1', 1, '张三', 'j1', '甲公司');
INSERT INTO job_info (id, name, city) VALUES ('j1', '后端', '杭州');
INSERT INTO chat_messages (id, encrypt_boss_id, side, time, push_text)
VALUES (1001, 'e1', 'right', 1700000000000, '你好');
INSERT INTO chat_messages (id, encrypt_boss_id, side, time, push_text)
VALUES (1002, 'e1', 'left', 1700000001000, '在的');
INSERT INTO sync_logs (friends) VALUES (1);
INSERT INTO message_failed_queue (boss_name, message) VALUES ('张三', '测试');
"""

DATA_TABLES = ["bosses", "job_info", "chat_messages", "sync_logs", "message_failed_queue"]


class TestMilestoneMigration(unittest.TestCase):
    """旧库启动迁移"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "old.db")
        raw = sqlite3.connect(self.path)
        raw.executescript(OLD_SCHEMA)
        raw.executescript(OLD_DATA)
        raw.commit()
        raw.close()

        self._orig_path = db.DB_PATH
        db.DB_PATH = self.path
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        db.DB_PATH = self._orig_path
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_m1_and_assigns_all_rows(self):
        milestones = self.conn.execute("SELECT * FROM milestones").fetchall()
        self.assertEqual(len(milestones), 1)
        m1 = milestones[0]
        self.assertEqual(m1["name"], "M1")
        self.assertEqual(m1["status"], "active")

        expected_counts = {
            "bosses": 1, "job_info": 1, "chat_messages": 2,
            "sync_logs": 1, "message_failed_queue": 1,
        }
        for table in DATA_TABLES:
            total = self.conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]
            self.assertEqual(total, expected_counts[table], f"{table} 数据丢失")
            other = self.conn.execute(
                f"SELECT COUNT(*) c FROM {table} WHERE milestone_id != ?", (m1["id"],)
            ).fetchone()["c"]
            self.assertEqual(other, 0, f"{table} 存在未归属 M1 的数据")

    def test_all_tables_have_milestone_column(self):
        for table in DATA_TABLES:
            cols = {r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")}
            self.assertIn("milestone_id", cols, f"{table} 缺少 milestone_id")

    def test_bosses_unique_within_milestone_only(self):
        m1_id = self.conn.execute("SELECT id FROM milestones").fetchone()["id"]
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO bosses (encrypt_boss_id, milestone_id, boss_id, name) VALUES (?, ?, 2, '重复')",
                ("e1", m1_id),
            )
        self.conn.rollback()

        m2 = milestone_utils.create_milestone(self.conn)
        self.conn.execute(
            "INSERT INTO bosses (encrypt_boss_id, milestone_id, boss_id, name) VALUES (?, ?, 2, '同 BOSS 新里程碑')",
            ("e1", m2["id"]),
        )
        count = self.conn.execute(
            "SELECT COUNT(*) c FROM bosses WHERE encrypt_boss_id='e1'"
        ).fetchone()["c"]
        self.assertEqual(count, 2)

    def test_chat_and_job_primary_keys_per_milestone(self):
        m2 = milestone_utils.create_milestone(self.conn)
        self.conn.execute(
            "INSERT INTO job_info (id, milestone_id, name) VALUES ('j1', ?, '后端-新')",
            (m2["id"],),
        )
        self.conn.execute(
            "INSERT INTO chat_messages (id, milestone_id, encrypt_boss_id, side, time) VALUES (1001, ?, 'e1', 'right', 1700000000000)",
            (m2["id"],),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO chat_messages (id, milestone_id, encrypt_boss_id) VALUES (1001, ?, 'e1')",
                (m2["id"],),
            )
        self.conn.rollback()

    def test_data_isolated_by_milestone(self):
        m1_id = self.conn.execute("SELECT id FROM milestones").fetchone()["id"]
        m2 = milestone_utils.create_milestone(self.conn)
        self.conn.execute(
            "INSERT INTO bosses (encrypt_boss_id, milestone_id, name) VALUES ('e2', ?, '李四')",
            (m2["id"],),
        )
        m1_count = self.conn.execute(
            "SELECT COUNT(*) c FROM bosses WHERE milestone_id=?", (m1_id,)
        ).fetchone()["c"]
        m2_count = self.conn.execute(
            "SELECT COUNT(*) c FROM bosses WHERE milestone_id=?", (m2["id"],)
        ).fetchone()["c"]
        self.assertEqual((m1_count, m2_count), (1, 1))


class TestMilestoneLifecycle(unittest.TestCase):
    """创建、保存、编号、只读校验"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "life.db")
        raw = sqlite3.connect(self.path)
        raw.executescript(OLD_SCHEMA)
        raw.commit()
        raw.close()

        self._orig_path = db.DB_PATH
        db.DB_PATH = self.path
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        db.DB_PATH = self._orig_path
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_db_has_no_milestone(self):
        rows = self.conn.execute("SELECT * FROM milestones").fetchall()
        self.assertEqual(len(rows), 0)

    def test_sequential_names_and_auto_freeze(self):
        m1 = milestone_utils.create_milestone(self.conn)
        self.assertEqual(m1["name"], "M1")
        self.assertEqual(m1["status"], "active")

        m2 = milestone_utils.create_milestone(self.conn)
        self.assertEqual(m2["name"], "M2")
        self.assertEqual(m2["status"], "active")

        m1_after = milestone_utils.get_milestone(self.conn, m1["id"])
        self.assertEqual(m1_after["status"], "frozen")
        self.assertIsNotNone(m1_after["frozen_at"])

        m3 = milestone_utils.create_milestone(self.conn)
        self.assertEqual(m3["name"], "M3")
        m2_after = milestone_utils.get_milestone(self.conn, m2["id"])
        self.assertEqual(m2_after["status"], "frozen")

    def test_name_uses_max_number(self):
        milestone_utils.create_milestone(self.conn)  # M1
        self.conn.execute(
            "INSERT INTO milestones (name, status) VALUES ('M9', 'frozen')"
        )
        self.conn.commit()
        m = milestone_utils.create_milestone(self.conn)
        self.assertEqual(m["name"], "M10")

    def test_require_editable_rejects_frozen(self):
        m1 = milestone_utils.create_milestone(self.conn)
        milestone_utils.require_editable(self.conn, m1["id"])

        milestone_utils.save_milestone(self.conn, m1["id"])
        with self.assertRaises(HTTPException) as ctx:
            milestone_utils.require_editable(self.conn, m1["id"])
        self.assertEqual(ctx.exception.status_code, 409)

    def test_save_frozen_twice_raises_409(self):
        m1 = milestone_utils.create_milestone(self.conn)
        milestone_utils.save_milestone(self.conn, m1["id"])
        with self.assertRaises(HTTPException) as ctx:
            milestone_utils.save_milestone(self.conn, m1["id"])
        self.assertEqual(ctx.exception.status_code, 409)

    def test_missing_milestone_raises_404(self):
        with self.assertRaises(HTTPException) as ctx:
            milestone_utils.get_milestone(self.conn, 99999)
        self.assertEqual(ctx.exception.status_code, 404)


class TestMilestoneAPI(unittest.TestCase):
    """HTTP 层：必填参数、隔离、冻结写入"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig_path = db.DB_PATH
        db.DB_PATH = os.path.join(self.tmpdir, "api.db")
        from backend.main import app
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        db.DB_PATH = self._orig_path
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_read_requires_milestone_id(self):
        self.assertEqual(self.client.get("/api/bosses").status_code, 422)
        self.assertEqual(self.client.get("/api/stats/overview").status_code, 422)

    def test_isolation_and_frozen_write(self):
        m1 = self.client.post("/api/milestones").json()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO bosses (encrypt_boss_id, milestone_id, boss_id, name) VALUES ('e1', ?, 1, '张三')",
            (m1["id"],),
        )
        conn.commit()
        conn.close()

        self.assertEqual(
            self.client.get(f"/api/bosses?milestone_id={m1['id']}").json()["total"], 1)

        m2 = self.client.post("/api/milestones").json()
        self.assertEqual(
            self.client.get(f"/api/bosses?milestone_id={m2['id']}").json()["total"], 0)
        self.assertEqual(
            self.client.get(f"/api/bosses?milestone_id={m1['id']}").json()["total"], 1)

        statuses = {m["name"]: m["status"]
                    for m in self.client.get("/api/milestones").json()["items"]}
        self.assertEqual(statuses, {"M1": "frozen", "M2": "active"})

        r = self.client.patch(
            f"/api/bosses/e1?milestone_id={m1['id']}", json={"has_interview": 1})
        self.assertEqual(r.status_code, 409)

    def test_save_twice_conflicts(self):
        m1 = self.client.post("/api/milestones").json()
        url = f"/api/milestones/{m1['id']}/save"
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 409)


if __name__ == "__main__":
    unittest.main(verbosity=2)
