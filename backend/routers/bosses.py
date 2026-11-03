from fastapi import APIRouter, Query
from pydantic import BaseModel
from ..database import get_db
from ..milestone_utils import require_editable

router = APIRouter()


ALLOWED_SORTS = {"first_msg_time", "last_msg_time"}

@router.get("/bosses")
def list_bosses(
    milestone_id: int = Query(..., description="里程碑 ID"),
    city: str = Query("", description="城市筛选"),
    position: str = Query("", description="职位筛选"),
    keyword: str = Query("", description="公司名/岗位名搜索"),
    has_interview: int | None = Query(None, description="面试筛选: 0/1"),
    is_resume_sent: int | None = Query(None, description="简历筛选: 0/1"),
    has_written_test: int | None = Query(None, description="笔试筛选: 0/1"),
    sort_by: str = Query("last_msg_time", description="排序字段"),
    order: str = Query("desc", description="asc/desc"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    conn = get_db()
    where = ["b.milestone_id = ?"]
    params = [milestone_id]

    if city:
        where.append("(j.city LIKE ? OR b.location_name LIKE ?)")
        params.extend([f"%{city}%", f"%{city}%"])
    if position:
        where.append("j.position_name LIKE ?")
        params.append(f"%{position}%")
    if keyword:
        where.append("(b.company_name LIKE ? OR j.name LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    if has_interview is not None:
        where.append("has_interview = ?")
        params.append(has_interview)
    if is_resume_sent is not None:
        where.append("is_resume_sent = ?")
        params.append(is_resume_sent)
    if has_written_test is not None:
        where.append("has_written_test = ?")
        params.append(has_written_test)

    where_clause = "WHERE " + " AND ".join(where)

    sort_col = sort_by if sort_by in ALLOWED_SORTS else "last_msg_time"
    sort_col = f"b.{sort_col}"  # fully qualified
    direction = "DESC" if order.lower() == "desc" else "ASC"

    offset = (page - 1) * size

    join_clause = "LEFT JOIN job_info j ON b.job_id = j.id AND j.milestone_id = b.milestone_id"

    total_row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM bosses b {join_clause} {where_clause}", params
    ).fetchone()
    total = total_row["cnt"]

    rows = conn.execute(
        f"""SELECT b.*, j.name as job_name, j.city as job_city, j.salary_desc,
                   j.position_name, j.job_type_desc, j.detail as job_detail,
                   j.company_url
            FROM bosses b {join_clause} {where_clause}
            ORDER BY {sort_col} {direction} LIMIT ? OFFSET ?""",
        params + [size, offset],
    ).fetchall()

    conn.close()
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [dict(r) for r in rows],
    }


@router.get("/bosses/{encrypt_boss_id}")
def boss_detail(encrypt_boss_id: str, milestone_id: int = Query(..., description="里程碑 ID")):
    conn = get_db()
    boss = conn.execute(
        """SELECT b.*, j.name as job_name, j.city as job_city, j.salary_desc,
                  j.position_name, j.job_type_desc, j.detail as job_detail,
                  j.company_url
           FROM bosses b
           LEFT JOIN job_info j ON b.job_id = j.id AND j.milestone_id = b.milestone_id
           WHERE b.encrypt_boss_id = ? AND b.milestone_id = ?""",
        (encrypt_boss_id, milestone_id),
    ).fetchone()
    conn.close()
    if not boss:
        return {"error": "not found"}, 404
    return dict(boss)


class BossUpdate(BaseModel):
    has_interview: bool | None = None
    is_resume_sent: bool | None = None
    has_written_test: bool | None = None
    send_resume_datetime: int | None = None


@router.patch("/bosses/{encrypt_boss_id}")
def update_boss(
    encrypt_boss_id: str,
    body: BossUpdate,
    milestone_id: int = Query(..., description="里程碑 ID"),
):
    conn = get_db()
    try:
        require_editable(conn, milestone_id)
        updates = []
        params = []
        if body.has_interview is not None:
            updates.append("has_interview = ?")
            params.append(1 if body.has_interview else 0)
        if body.is_resume_sent is not None:
            updates.append("is_resume_sent = ?")
            params.append(1 if body.is_resume_sent else 0)
        if body.has_written_test is not None:
            updates.append("has_written_test = ?")
            params.append(1 if body.has_written_test else 0)
        if body.send_resume_datetime is not None:
            updates.append("send_resume_datetime = ?")
            params.append(body.send_resume_datetime)
        if updates:
            updates.append("updated_at = datetime('now', 'localtime')")
            params.extend([encrypt_boss_id, milestone_id])
            conn.execute(
                f"UPDATE bosses SET {', '.join(updates)} "
                f"WHERE encrypt_boss_id = ? AND milestone_id = ?",
                params,
            )
            conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.delete("/bosses")
def delete_all_bosses(milestone_id: int = Query(..., description="里程碑 ID")):
    conn = get_db()
    try:
        require_editable(conn, milestone_id)
        conn.execute("DELETE FROM chat_messages WHERE milestone_id = ?", (milestone_id,))
        conn.execute("DELETE FROM bosses WHERE milestone_id = ?", (milestone_id,))
        deleted = conn.total_changes
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "deleted": deleted}


@router.get("/bosses/{encrypt_boss_id}/messages")
def boss_messages(
    encrypt_boss_id: str,
    milestone_id: int = Query(..., description="里程碑 ID"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    conn = get_db()
    offset = (page - 1) * size

    total_row = conn.execute(
        "SELECT COUNT(*) as cnt FROM chat_messages "
        "WHERE encrypt_boss_id = ? AND milestone_id = ?",
        (encrypt_boss_id, milestone_id),
    ).fetchone()

    rows = conn.execute(
        "SELECT * FROM chat_messages "
        "WHERE encrypt_boss_id = ? AND milestone_id = ? "
        "ORDER BY time ASC LIMIT ? OFFSET ?",
        (encrypt_boss_id, milestone_id, size, offset),
    ).fetchall()
    conn.close()

    return {
        "total": total_row["cnt"] if total_row else 0,
        "page": page,
        "size": size,
        "items": [dict(r) for r in rows],
    }
