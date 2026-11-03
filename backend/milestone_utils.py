"""里程碑领域逻辑：查询、创建、保存、只读校验。"""

import re

from fastapi import HTTPException


def get_milestone(conn, milestone_id: int):
    """按 ID 查询里程碑，不存在时返回 404"""
    row = conn.execute("SELECT * FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="里程碑不存在")
    return row


def require_editable(conn, milestone_id: int):
    """校验里程碑存在且处于编辑中，否则抛出 404 / 409"""
    row = get_milestone(conn, milestone_id)
    if row["status"] != "active":
        raise HTTPException(status_code=409, detail=f"{row['name']} 已保存，只读不可修改")
    return row


def next_milestone_name(conn) -> str:
    """返回下一个里程碑名称，例如 M3"""
    names = [row["name"] for row in conn.execute("SELECT name FROM milestones").fetchall()]
    nums = [int(m.group(1)) for name in names if (m := re.match(r"^M(\d+)$", name))]
    return f"M{max(nums, default=0) + 1}"


def create_milestone(conn) -> dict:
    """冻结当前 active 里程碑（如有），创建并返回下一个里程碑"""
    conn.execute(
        "UPDATE milestones SET status = 'frozen', frozen_at = datetime('now', 'localtime') "
        "WHERE status = 'active'"
    )
    name = next_milestone_name(conn)
    cur = conn.execute(
        "INSERT INTO milestones (name, status) VALUES (?, 'active')", (name,)
    )
    conn.commit()
    return dict(
        conn.execute("SELECT * FROM milestones WHERE id = ?", (cur.lastrowid,)).fetchone()
    )


def save_milestone(conn, milestone_id: int) -> dict:
    """保存（冻结）里程碑；已保存时返回 409"""
    row = get_milestone(conn, milestone_id)
    if row["status"] != "active":
        raise HTTPException(status_code=409, detail=f"{row['name']} 已保存，只读不可修改")
    conn.execute(
        "UPDATE milestones SET status = 'frozen', frozen_at = datetime('now', 'localtime') "
        "WHERE id = ?",
        (milestone_id,),
    )
    conn.commit()
    return dict(
        conn.execute("SELECT * FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
    )
