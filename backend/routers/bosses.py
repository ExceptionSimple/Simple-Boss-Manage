from fastapi import APIRouter, Query
from pydantic import BaseModel
from ..database import get_db

router = APIRouter()


ALLOWED_SORTS = {"first_msg_time", "last_msg_time"}

@router.get("/bosses")
def list_bosses(
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
    where = []
    params = []

    if city:
        where.append("(job_city LIKE ? OR location_name LIKE ?)")
        params.extend([f"%{city}%", f"%{city}%"])
    if position:
        where.append("position_name LIKE ?")
        params.append(f"%{position}%")
    if keyword:
        where.append("(brand_name LIKE ? OR job_name LIKE ?)")
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

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    sort_col = sort_by if sort_by in ALLOWED_SORTS else "last_msg_time"
    direction = "DESC" if order.lower() == "desc" else "ASC"

    offset = (page - 1) * size

    total_row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM bosses {where_clause}", params
    ).fetchone()
    total = total_row["cnt"]

    rows = conn.execute(
        f"SELECT * FROM bosses {where_clause} ORDER BY {sort_col} {direction} LIMIT ? OFFSET ?",
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
def boss_detail(encrypt_boss_id: str):
    conn = get_db()
    boss = conn.execute(
        "SELECT * FROM bosses WHERE encrypt_boss_id = ?", (encrypt_boss_id,)
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
def update_boss(encrypt_boss_id: str, body: BossUpdate):
    conn = get_db()
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
        params.append(encrypt_boss_id)
        conn.execute(
            f"UPDATE bosses SET {', '.join(updates)} WHERE encrypt_boss_id = ?",
            params,
        )
        conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/bosses")
def delete_all_bosses():
    conn = get_db()
    conn.execute("DELETE FROM chat_messages")
    conn.execute("DELETE FROM bosses")
    deleted = conn.total_changes
    conn.commit()
    conn.close()
    return {"ok": True, "deleted": deleted}


@router.get("/bosses/{encrypt_boss_id}/messages")
def boss_messages(
    encrypt_boss_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    conn = get_db()
    offset = (page - 1) * size

    total_row = conn.execute(
        "SELECT COUNT(*) as cnt FROM chat_messages WHERE encrypt_boss_id = ?",
        (encrypt_boss_id,),
    ).fetchone()

    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE encrypt_boss_id = ? ORDER BY time ASC LIMIT ? OFFSET ?",
        (encrypt_boss_id, size, offset),
    ).fetchall()
    conn.close()

    return {
        "total": total_row["cnt"] if total_row else 0,
        "page": page,
        "size": size,
        "items": [dict(r) for r in rows],
    }
