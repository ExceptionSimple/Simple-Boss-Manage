"""
数据库单元测试：验证 schema 迁移和 CRUD 操作。

- schema 测试：直接在真实 data.db 上运行（只读）
- CRUD 测试：在独立临时库上运行，事务回滚，不影响真实数据
"""

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import get_db, init_db, DB_PATH

MILESTONE_ID = 1


def _copy_db(src: str, dst: str):
    """复制数据库 — 先 checkpoint WAL 确保数据完整"""
    c = sqlite3.connect(src)
    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    c.close()
    shutil.copy2(src, dst)
    for suffix in ("-wal", "-shm"):
        sp, dp = src + suffix, dst + suffix
        if os.path.exists(dp):
            os.remove(dp)


def _new_rw_conn(path: str) -> sqlite3.Connection:
    """打开 WAL 模式的读写连接"""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


class TestDatabaseSchema(unittest.TestCase):
    """只读验证真实数据库 schema"""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(DB_PATH):
            raise FileNotFoundError(f"数据库不存在: {DB_PATH}")
        init_db()  # 确保迁移已执行
        cls.conn = get_db()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_all_tables_exist(self):
        tables = {r[0] for r in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()}
        expected = {"bosses", "chat_messages", "config", "job_info",
                    "message_failed_queue", "sync_logs", "milestones"}
        self.assertTrue(expected.issubset(tables),
                        f"缺少表: {expected - tables}")

    def test_bosses_new_columns(self):
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(bosses)").fetchall()}
        for col in ("job_id", "company_name", "company_url"):
            self.assertIn(col, cols, f"bosses 缺少列: {col}")

    def test_bosses_old_columns_dropped(self):
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(bosses)").fetchall()}
        for col in ("brand_name", "job_name", "job_city", "salary_desc",
                    "job_type_desc", "position_name"):
            self.assertNotIn(col, cols, f"bosses 仍存在旧列: {col}")

    def test_job_info_columns(self):
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(job_info)").fetchall()}
        expected = {"id", "milestone_id", "name", "city", "salary_desc", "job_type_desc",
                    "position_name", "detail", "company_url", "company_name",
                    "created_at", "updated_at"}
        self.assertEqual(expected, cols, f"job_info 列不匹配: {cols}")

    def test_job_info_pk(self):
        pks = [r[1] for r in self.conn.execute("PRAGMA table_info(job_info)").fetchall() if r[5]]
        self.assertIn("id", pks, f"job_info 主键不是 id: {pks}")

    def test_chat_messages_no_fk(self):
        fks = self.conn.execute("PRAGMA foreign_key_list(chat_messages)").fetchall()
        self.assertEqual(len(fks), 0, f"chat_messages 存在外键: {fks}")

    def test_init_db_idempotent(self):
        init_db()
        init_db()
        tables = {r[0] for r in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("bosses", tables)

    def test_real_data_counts(self):
        """真实数据库应该有基础数据（WAL checkpoint 后查询）"""
        cnt = self.conn.execute("SELECT COUNT(*) as c FROM bosses").fetchone()["c"]
        self.assertGreater(cnt, 0, "bosses 表应有数据 —— 请确保之前同步过")
        cnt = self.conn.execute("SELECT COUNT(*) as c FROM chat_messages").fetchone()["c"]
        self.assertGreater(cnt, 0, "chat_messages 表应有数据")


# ═══════════════════════════════════════════════════════════════════
# 以下测试使用独立临时数据库，先 copy 真实 DB（获取 schema + 基础数据）
# 再在事务内做写操作，teardown 时回滚，不污染临时库
# ═══════════════════════════════════════════════════════════════════

class _TempDBTestCase(unittest.TestCase):
    """基类：提供临时数据库 + 事务回滚"""
    tmpdir: str = None
    tmpdb: str = None

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.tmpdb = os.path.join(cls.tmpdir, "test.db")
        if os.path.exists(DB_PATH):
            _copy_db(DB_PATH, cls.tmpdb)
        # init_db on temp copy
        import database
        cls._orig_path = database.DB_PATH
        database.DB_PATH = cls.tmpdb
        init_db()
        database.DB_PATH = cls._orig_path
        conn = sqlite3.connect(cls.tmpdb)
        conn.execute(
            "INSERT OR IGNORE INTO milestones (id, name, status) VALUES (?, 'M-TEST', 'active')",
            (MILESTONE_ID,),
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        self.conn = _new_rw_conn(self.tmpdb)
        self.conn.execute("BEGIN")

    def tearDown(self):
        try:
            self.conn.execute("ROLLBACK")
        except Exception:
            pass
        self.conn.close()


class TestJobInfoCRUD(_TempDBTestCase):
    """job_info 表 CRUD"""

    def test_insert(self):
        self.conn.execute(
            "INSERT OR REPLACE INTO job_info (id, milestone_id, name, city, salary_desc, job_type_desc, position_name, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))",
            ("test_001", MILESTONE_ID, "后端开发", "北京", "15-25K", "全职", "Java工程师"),
        )
        row = self.conn.execute("SELECT * FROM job_info WHERE id=?", ("test_001",)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["city"], "北京")

    def test_upsert(self):
        self.conn.execute(
            "INSERT OR REPLACE INTO job_info (id, milestone_id, name, city, updated_at) VALUES (?, ?, ?, ?, datetime('now', 'localtime'))",
            ("test_002", MILESTONE_ID, "旧名称", "上海"),
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO job_info (id, milestone_id, name, city, salary_desc, updated_at) VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))",
            ("test_002", MILESTONE_ID, "新名称", "深圳", "20-30K"),
        )
        row = self.conn.execute("SELECT * FROM job_info WHERE id=?", ("test_002",)).fetchone()
        self.assertEqual(row["name"], "新名称")
        self.assertEqual(row["city"], "深圳")

    def test_update_detail(self):
        self.conn.execute(
            "INSERT OR REPLACE INTO job_info (id, milestone_id, name, updated_at) VALUES (?, ?, ?, datetime('now', 'localtime'))",
            ("test_003", MILESTONE_ID, "测试岗"),
        )
        self.conn.execute(
            "UPDATE job_info SET detail=?, company_url=?, company_name=? WHERE id=?",
            ("描述...", "https://www.zhipin.com/c/123", "测试科技", "test_003"),
        )
        row = self.conn.execute("SELECT * FROM job_info WHERE id=?", ("test_003",)).fetchone()
        self.assertEqual(row["detail"], "描述...")
        self.assertEqual(row["company_name"], "测试科技")

    def test_city_from_body_type8(self):
        self.conn.execute(
            "INSERT OR REPLACE INTO job_info (id, milestone_id, name, city, updated_at) VALUES (?, ?, ?, ?, datetime('now', 'localtime'))",
            ("test_004", MILESTONE_ID, "PM", ""),
        )
        self.conn.execute("UPDATE job_info SET city=? WHERE id=?", ("杭州", "test_004"))
        row = self.conn.execute("SELECT city FROM job_info WHERE id=?", ("test_004",)).fetchone()
        self.assertEqual(row["city"], "杭州")

    def test_delete(self):
        self.conn.execute(
            "INSERT OR REPLACE INTO job_info (id, milestone_id, name, updated_at) VALUES (?, ?, ?, datetime('now', 'localtime'))",
            ("test_del", MILESTONE_ID, "待删除"),
        )
        self.conn.execute("DELETE FROM job_info WHERE id=?", ("test_del",))
        self.assertIsNone(self.conn.execute("SELECT * FROM job_info WHERE id=?", ("test_del",)).fetchone())


class TestBossJobRelation(_TempDBTestCase):
    """bosses ↔ job_info LEFT JOIN + COALESCE 逻辑"""

    def setUp(self):
        super().setUp()
        # 插入一条测试 boss（确保有数据可测）
        self.test_eid = "test_boss_relation_001"
        self.conn.execute(
            "INSERT OR REPLACE INTO bosses (encrypt_boss_id, milestone_id, boss_id, name, update_time) VALUES (?, ?, 999, ?, 0)",
            (self.test_eid, MILESTONE_ID, "测试BOSS"),
        )

    def test_join_with_job_id(self):
        self.conn.execute(
            "INSERT OR REPLACE INTO job_info (id, milestone_id, name, city, salary_desc, updated_at)"
            " VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))",
            ("job_r1", MILESTONE_ID, "全栈", "广州", "18-25K"),
        )
        self.conn.execute(
            "UPDATE bosses SET job_id=?, company_name=? WHERE encrypt_boss_id=?",
            ("job_r1", "广州科技", self.test_eid),
        )
        row = self.conn.execute(
            """SELECT b.name, b.company_name, j.name as job_name, j.city as job_city
               FROM bosses b LEFT JOIN job_info j ON b.job_id=j.id
               WHERE b.encrypt_boss_id=?""", (self.test_eid,)
        ).fetchone()
        self.assertEqual(row["company_name"], "广州科技")
        self.assertEqual(row["job_name"], "全栈")
        self.assertEqual(row["job_city"], "广州")

    def test_left_join_null(self):
        self.conn.execute("UPDATE bosses SET job_id='' WHERE encrypt_boss_id=?", (self.test_eid,))
        row = self.conn.execute(
            """SELECT b.name, j.name as job_name
               FROM bosses b LEFT JOIN job_info j ON b.job_id=j.id
               WHERE b.encrypt_boss_id=?""", (self.test_eid,)
        ).fetchone()
        self.assertIsNone(row["job_name"])

    def test_coalesce_keeps_existing(self):
        self.conn.execute("UPDATE bosses SET job_id=? WHERE encrypt_boss_id=?", ("existing_999", self.test_eid))
        self.conn.execute(
            "UPDATE bosses SET job_id=COALESCE(NULLIF(bosses.job_id,''), ?) WHERE encrypt_boss_id=?",
            ("new_001", self.test_eid),
        )
        row = self.conn.execute("SELECT job_id FROM bosses WHERE encrypt_boss_id=?", (self.test_eid,)).fetchone()
        self.assertEqual(row["job_id"], "existing_999")

    def test_coalesce_sets_new(self):
        self.conn.execute("UPDATE bosses SET job_id='' WHERE encrypt_boss_id=?", (self.test_eid,))
        self.conn.execute(
            "UPDATE bosses SET job_id=COALESCE(NULLIF(bosses.job_id,''), ?) WHERE encrypt_boss_id=?",
            ("fresh_002", self.test_eid),
        )
        row = self.conn.execute("SELECT job_id FROM bosses WHERE encrypt_boss_id=?", (self.test_eid,)).fetchone()
        self.assertEqual(row["job_id"], "fresh_002")


class TestMessageFailedQueue(_TempDBTestCase):
    """发送失败队列 CRUD"""

    def test_insert(self):
        self.conn.execute(
            "INSERT INTO message_failed_queue (boss_name, message, error, milestone_id) VALUES (?, ?, ?, ?)",
            ("测试", "你好", "超时", MILESTONE_ID),
        )
        row = self.conn.execute(
            "SELECT * FROM message_failed_queue ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(row["boss_name"], "测试")
        self.assertEqual(row["retry_count"], 0)

    def test_retry_increment(self):
        self.conn.execute(
            "INSERT INTO message_failed_queue (boss_name, message, error, milestone_id) VALUES (?, ?, ?, ?)",
            ("重试", "msg", "err", MILESTONE_ID),
        )
        rid = self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        self.conn.execute(
            "UPDATE message_failed_queue SET retry_count=retry_count+1 WHERE id=?", (rid,)
        )
        row = self.conn.execute(
            "SELECT retry_count FROM message_failed_queue WHERE id=?", (rid,)
        ).fetchone()
        self.assertEqual(row["retry_count"], 1)

    def test_delete_on_success(self):
        self.conn.execute(
            "INSERT INTO message_failed_queue (boss_name, message, error, milestone_id) VALUES (?, ?, ?, ?)",
            ("ok", "msg", "err", MILESTONE_ID),
        )
        rid = self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        self.conn.execute("DELETE FROM message_failed_queue WHERE id=?", (rid,))
        self.assertIsNone(
            self.conn.execute("SELECT * FROM message_failed_queue WHERE id=?", (rid,)).fetchone()
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
