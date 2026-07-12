from fastapi import APIRouter
from ..database import get_db

router = APIRouter()


@router.get("/stats/overview")
def overview():
    conn = get_db()
    total_communications = conn.execute("SELECT COUNT(*) as cnt FROM bosses").fetchone()["cnt"]
    total_resume_sent = conn.execute(
        "SELECT COUNT(*) as cnt FROM bosses WHERE is_resume_sent = 1"
    ).fetchone()["cnt"]
    total_interviews = conn.execute(
        "SELECT COUNT(*) as cnt FROM bosses WHERE has_interview = 1"
    ).fetchone()["cnt"]
    total_cities = conn.execute(
        "SELECT COUNT(DISTINCT COALESCE(NULLIF(location_name,''), job_city)) as cnt FROM bosses"
    ).fetchone()["cnt"]
    total_positions = conn.execute(
        "SELECT COUNT(DISTINCT position_name) as cnt FROM bosses WHERE position_name != ''"
    ).fetchone()["cnt"]
    conn.close()
    return {
        "total_communications": total_communications,
        "total_resume_sent": total_resume_sent,
        "total_interviews": total_interviews,
        "total_cities": total_cities,
        "total_positions": total_positions,
    }


@router.get("/stats/cities")
def city_distribution():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(location_name,''), job_city) as city, COUNT(*) as count
        FROM bosses
        WHERE COALESCE(NULLIF(location_name,''), job_city) != ''
        GROUP BY city
        ORDER BY count DESC
        """
    ).fetchall()
    conn.close()
    return [{"name": r["city"], "value": r["count"]} for r in rows]


@router.get("/stats/daily")
def daily_stats():
    """按天统计消息数量"""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT DATE(time / 1000, 'unixepoch') as date, COUNT(*) as count
        FROM chat_messages
        WHERE time > 0
        GROUP BY date
        ORDER BY date
        """
    ).fetchall()
    conn.close()
    return [{"date": r["date"], "count": r["count"]} for r in rows]


@router.get("/stats/positions")
def position_distribution():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT position_name as name, COUNT(*) as count
        FROM bosses
        WHERE position_name != ''
        GROUP BY position_name
        ORDER BY count DESC
        """
    ).fetchall()
    conn.close()
    return [{"name": r["name"], "value": r["count"]} for r in rows]
