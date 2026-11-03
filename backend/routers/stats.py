import time
from fastapi import APIRouter, Query
from ..database import get_db

router = APIRouter()


def _today_start_ms() -> int:
    now = time.localtime()
    return int(time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, now.tm_isdst))) * 1000


def _start_of_day(offset_days: int = 0) -> int:
    now = time.localtime()
    t = time.mktime((now.tm_year, now.tm_mon, now.tm_mday - offset_days, 0, 0, 0, 0, 0, now.tm_isdst))
    return int(t) * 1000


def _start_of_week(offset_weeks: int = 0) -> int:
    now = time.localtime()
    wday = now.tm_wday  # Python: tm_wday 0=Monday
    t = time.mktime((now.tm_year, now.tm_mon, now.tm_mday - wday - offset_weeks * 7, 0, 0, 0, 0, 0, now.tm_isdst))
    return int(t) * 1000


def _start_of_month(offset_months: int = 0) -> int:
    now = time.localtime()
    m = now.tm_mon - offset_months
    y = now.tm_year
    while m <= 0:
        m += 12; y -= 1
    t = time.mktime((y, m, 1, 0, 0, 0, 0, 0, now.tm_isdst))
    return int(t) * 1000


@router.get("/stats/overview")
def overview(milestone_id: int = Query(..., description="里程碑 ID")):
    conn = get_db()
    total_communications = conn.execute(
        "SELECT COUNT(*) as cnt FROM bosses WHERE milestone_id = ?", (milestone_id,)
    ).fetchone()["cnt"]
    total_messages = conn.execute(
        "SELECT COUNT(*) as cnt FROM chat_messages WHERE milestone_id = ?", (milestone_id,)
    ).fetchone()["cnt"]
    total_resume_sent = conn.execute(
        "SELECT COUNT(*) as cnt FROM bosses WHERE milestone_id = ? AND is_resume_sent = 1",
        (milestone_id,),
    ).fetchone()["cnt"]
    total_interviews = conn.execute(
        "SELECT COUNT(*) as cnt FROM bosses WHERE milestone_id = ? AND has_interview = 1",
        (milestone_id,),
    ).fetchone()["cnt"]
    total_cities = conn.execute(
        """SELECT COUNT(DISTINCT COALESCE(NULLIF(b.location_name,''), j.city)) as cnt
           FROM bosses b
           LEFT JOIN job_info j ON b.job_id = j.id AND j.milestone_id = b.milestone_id
           WHERE b.milestone_id = ?""",
        (milestone_id,),
    ).fetchone()["cnt"]
    total_positions = conn.execute(
        """SELECT COUNT(DISTINCT j.position_name) as cnt
           FROM bosses b
           LEFT JOIN job_info j ON b.job_id = j.id AND j.milestone_id = b.milestone_id
           WHERE b.milestone_id = ? AND j.position_name != ''""",
        (milestone_id,),
    ).fetchone()["cnt"]

    # 今日 vs 昨天（有消息的 BOSS 数）
    today_ms = _start_of_day(0)
    yest_ms_start = _start_of_day(1)
    today_count = conn.execute(
        "SELECT COUNT(DISTINCT encrypt_boss_id) as cnt FROM chat_messages "
        "WHERE milestone_id = ? AND time >= ?",
        (milestone_id, today_ms),
    ).fetchone()["cnt"]
    yest_count = conn.execute(
        "SELECT COUNT(DISTINCT encrypt_boss_id) as cnt FROM chat_messages "
        "WHERE milestone_id = ? AND time >= ? AND time < ?",
        (milestone_id, yest_ms_start, today_ms),
    ).fetchone()["cnt"]

    # 本周 vs 上周
    week_ms = _start_of_week(0)
    last_week_ms_start = _start_of_week(1)
    week_count = conn.execute(
        "SELECT COUNT(DISTINCT encrypt_boss_id) as cnt FROM chat_messages "
        "WHERE milestone_id = ? AND time >= ?",
        (milestone_id, week_ms),
    ).fetchone()["cnt"]
    last_week_count = conn.execute(
        "SELECT COUNT(DISTINCT encrypt_boss_id) as cnt FROM chat_messages "
        "WHERE milestone_id = ? AND time >= ? AND time < ?",
        (milestone_id, last_week_ms_start, week_ms),
    ).fetchone()["cnt"]
    week_resume = conn.execute(
        "SELECT COUNT(*) as cnt FROM bosses "
        "WHERE milestone_id = ? AND is_resume_sent = 1 AND last_msg_time >= ?",
        (milestone_id, week_ms),
    ).fetchone()["cnt"]
    last_week_resume = conn.execute(
        "SELECT COUNT(*) as cnt FROM bosses "
        "WHERE milestone_id = ? AND is_resume_sent = 1 AND last_msg_time >= ? AND last_msg_time < ?",
        (milestone_id, last_week_ms_start, week_ms),
    ).fetchone()["cnt"]

    # 本月 vs 上月
    month_ms = _start_of_month(0)
    last_month_ms_start = _start_of_month(1)
    month_count = conn.execute(
        "SELECT COUNT(DISTINCT encrypt_boss_id) as cnt FROM chat_messages "
        "WHERE milestone_id = ? AND time >= ?",
        (milestone_id, month_ms),
    ).fetchone()["cnt"]
    last_month_count = conn.execute(
        "SELECT COUNT(DISTINCT encrypt_boss_id) as cnt FROM chat_messages "
        "WHERE milestone_id = ? AND time >= ? AND time < ?",
        (milestone_id, last_month_ms_start, month_ms),
    ).fetchone()["cnt"]
    month_resume = conn.execute(
        "SELECT COUNT(*) as cnt FROM bosses "
        "WHERE milestone_id = ? AND is_resume_sent = 1 AND last_msg_time >= ?",
        (milestone_id, month_ms),
    ).fetchone()["cnt"]
    last_month_resume = conn.execute(
        "SELECT COUNT(*) as cnt FROM bosses "
        "WHERE milestone_id = ? AND is_resume_sent = 1 AND last_msg_time >= ? AND last_msg_time < ?",
        (milestone_id, last_month_ms_start, month_ms),
    ).fetchone()["cnt"]

    # Top 3
    top5 = conn.execute("""
        SELECT b.name, b.company_name, COUNT(cm.id) as cnt
        FROM bosses b
        JOIN chat_messages cm ON cm.encrypt_boss_id = b.encrypt_boss_id
                             AND cm.milestone_id = b.milestone_id
        WHERE b.milestone_id = ?
        GROUP BY b.encrypt_boss_id ORDER BY cnt DESC LIMIT 5
    """, (milestone_id,)).fetchall()
    conn.close()
    return {
        "total_communications": total_communications,
        "total_messages": total_messages,
        "total_resume_sent": total_resume_sent,
        "total_interviews": total_interviews,
        "total_cities": total_cities,
        "total_positions": total_positions,
        "today": {"value": today_count, "prev": yest_count},
        "week": {"value": week_count, "prev": last_week_count},
        "week_resume": {"value": week_resume, "prev": last_week_resume},
        "month": {"value": month_count, "prev": last_month_count},
        "month_resume": {"value": month_resume, "prev": last_month_resume},
        "top_chatters": [{"name": r["name"], "brand": r["company_name"], "count": r["cnt"]} for r in top5],
    }


@router.get("/stats/cities")
def city_distribution(milestone_id: int = Query(..., description="里程碑 ID")):
    conn = get_db()
    rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(b.location_name,''), j.city) as city, COUNT(*) as count
        FROM bosses b
        LEFT JOIN job_info j ON b.job_id = j.id AND j.milestone_id = b.milestone_id
        WHERE b.milestone_id = ?
          AND COALESCE(NULLIF(b.location_name,''), j.city) != ''
        GROUP BY city
        ORDER BY count DESC
        """,
        (milestone_id,),
    ).fetchall()
    conn.close()
    return [{"name": r["city"], "value": r["count"]} for r in rows]


@router.get("/stats/daily")
def daily_stats(milestone_id: int = Query(..., description="里程碑 ID")):
    """按天统计沟通的 BOSS 数量（BOSS 时间戳为本地时间，需用 localtime）"""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT DATE(time / 1000, 'unixepoch', 'localtime') as date, COUNT(DISTINCT encrypt_boss_id) as count
        FROM chat_messages
        WHERE milestone_id = ? AND time > 0
        GROUP BY date
        ORDER BY date
        """,
        (milestone_id,),
    ).fetchall()
    conn.close()
    return [{"date": r["date"], "count": r["count"]} for r in rows]


@router.get("/stats/daily-resume")
def daily_resume_stats(milestone_id: int = Query(..., description="里程碑 ID")):
    """按天统计发送简历数量"""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT DATE(send_resume_datetime / 1000, 'unixepoch', 'localtime') as date, COUNT(*) as count
        FROM bosses
        WHERE milestone_id = ? AND is_resume_sent = 1
          AND send_resume_datetime IS NOT NULL AND send_resume_datetime > 0
        GROUP BY date
        ORDER BY date
        """,
        (milestone_id,),
    ).fetchall()
    conn.close()
    return [{"date": r["date"], "count": r["count"]} for r in rows]


@router.get("/stats/recent-resumes")
def recent_resumes(
    milestone_id: int = Query(..., description="里程碑 ID"),
    limit: int = 5,
):
    """最近发简历的前 N 家公司"""
    conn = get_db()
    rows = conn.execute(
        """SELECT b.name, b.company_name, j.name as job_name, b.send_resume_datetime
           FROM bosses b
           LEFT JOIN job_info j ON b.job_id = j.id AND j.milestone_id = b.milestone_id
           WHERE b.milestone_id = ? AND b.is_resume_sent = 1
             AND b.send_resume_datetime IS NOT NULL
           ORDER BY b.send_resume_datetime DESC LIMIT ?""",
        (milestone_id, limit),
    ).fetchall()
    conn.close()
    return [{"name": r["name"], "brand": r["company_name"], "job": r["job_name"], "datetime": r["send_resume_datetime"]} for r in rows]


@router.get("/stats/sync-logs")
def sync_logs(
    milestone_id: int = Query(..., description="里程碑 ID"),
    limit: int = 5,
):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM sync_logs WHERE milestone_id = ? ORDER BY id DESC LIMIT ?",
        (milestone_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/stats/positions")
def position_distribution(milestone_id: int = Query(..., description="里程碑 ID")):
    conn = get_db()
    rows = conn.execute(
        """
        SELECT j.position_name as name, COUNT(*) as count
        FROM bosses b
        LEFT JOIN job_info j ON b.job_id = j.id AND j.milestone_id = b.milestone_id
        WHERE b.milestone_id = ? AND j.position_name != ''
        GROUP BY j.position_name
        ORDER BY count DESC
        """,
        (milestone_id,),
    ).fetchall()
    conn.close()
    return [{"name": r["name"], "value": r["count"]} for r in rows]
