"""里程碑接口：列表、创建、保存。"""

from fastapi import APIRouter

from ..database import get_db
from .. import milestone_utils

router = APIRouter()


@router.get("/milestones")
def list_milestones():
    conn = get_db()
    rows = conn.execute("""
        SELECT m.*,
            (SELECT COUNT(*) FROM bosses b WHERE b.milestone_id = m.id) AS boss_count,
            (SELECT COUNT(*) FROM chat_messages c WHERE c.milestone_id = m.id) AS message_count
        FROM milestones m
        ORDER BY m.id
    """).fetchall()
    conn.close()
    return {"items": [dict(r) for r in rows]}


@router.post("/milestones")
def create_milestone():
    """创建下一个里程碑；已有编辑中的里程碑会先被自动保存"""
    conn = get_db()
    try:
        return milestone_utils.create_milestone(conn)
    finally:
        conn.close()


@router.post("/milestones/{milestone_id}/save")
def save_milestone(milestone_id: int):
    conn = get_db()
    try:
        row = milestone_utils.save_milestone(conn, milestone_id)
    finally:
        conn.close()
    return {"ok": True, "milestone": row}
