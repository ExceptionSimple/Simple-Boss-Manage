"""周报/月报生成"""
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, HTMLResponse
from ..database import get_db
from .stats import _start_of_week, _start_of_month, _start_of_day

logger = logging.getLogger("reports")
router = APIRouter()
REPORTS_DIR = os.path.join(Path(__file__).parent.parent.parent, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def _build_html(title: str, date_range: str, prev_label: str,
                stats: dict, daily_data: list, top_chatters: list) -> str:
    daily_json = json.dumps(daily_data, ensure_ascii=False)
    ai_summary = _generate_summary(stats, prev_label)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#f5f6f8; padding:40px; }}
.container {{ max-width:900px; margin:0 auto; }}
.header {{ text-align:center; margin-bottom:30px; }}
.header h1 {{ font-size:28px; color:#1f2937; }}
.header p {{ color:#9ca3af; margin-top:6px; }}
.summary {{ background:#fff; border-radius:12px; padding:20px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,.06); font-size:14px; line-height:1.8; color:#374151; }}
.cards {{ display:flex; gap:12px; margin-bottom:20px; flex-wrap:wrap; }}
.card {{ flex:1; min-width:130px; background:#fff; border-radius:10px; padding:18px 14px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,.04); }}
.card .num {{ font-size:26px; font-weight:700; color:#6366f1; }}
.card .lbl {{ font-size:12px; color:#9ca3af; margin-top:2px; }}
.card .trend {{ font-size:12px; }}
.trend.up {{ color:#10b981; }} .trend.down {{ color:#ef4444; }}
.chart-box {{ background:#fff; border-radius:12px; padding:20px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
.rank-box {{ background:#fff; border-radius:12px; padding:20px; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
.rank-box h3 {{ font-size:16px; color:#374151; margin-bottom:12px; }}
.rank-item {{ display:flex; align-items:center; gap:10px; padding:8px 0; border-bottom:1px solid #f3f4f6; }}
.rank-item:last-child {{ border:none; }}
.rank-emoji {{ font-size:20px; }}
.rank-name {{ font-weight:600; }} .rank-brand {{ color:#9ca3af; font-size:13px; }}
.rank-cnt {{ margin-left:auto; color:#10b981; font-weight:600; }}
.footer {{ text-align:center; color:#d1d5db; font-size:12px; margin-top:30px; }}
</style>
</head>
<body>
<div class="container">
<div class="header">
  <h1>{title}</h1>
  <p>{date_range} · 对比{prev_label}</p>
</div>

<div class="summary">{ai_summary}</div>

<div class="cards">
  <div class="card"><div class="num">{stats['talked']}</div><div class="lbl">沟通人数</div><div class="trend {stats['trend_talked_cls']}">{stats['trend_talked']}</div></div>
  <div class="card"><div class="num">{stats['messages']}</div><div class="lbl">新消息</div><div class="trend {stats['trend_msg_cls']}">{stats['trend_msg']}</div></div>
  <div class="card"><div class="num">{stats['resumes']}</div><div class="lbl">发简历</div><div class="trend {stats['trend_resume_cls']}">{stats['trend_resume']}</div></div>
  <div class="card"><div class="num">{stats['interviews']}</div><div class="lbl">约面</div><div class="trend {stats['trend_interview_cls']}">{stats['trend_interview']}</div></div>
</div>

<div class="chart-box"><div id="chart" style="width:100%;height:320px;"></div></div>

<div class="rank-box">
  <h3>沟通最多</h3>
  {''.join(f'<div class="rank-item"><span class="rank-emoji">{e}</span><span class="rank-name">{n}</span><span class="rank-brand">{b}</span><span class="rank-cnt">{c} 条</span></div>' for e,n,b,c in [(['🥇','🥈','🥉'][i] if i<3 else str(i+1), t["name"], t["brand"], t["count"]) for i,t in enumerate(top_chatters)])}
</div>

<div class="footer">BOSS 管理 · {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
</div>
<script>
var d=echarts.init(document.getElementById('chart'));
d.setOption({{tooltip:{{trigger:'axis'}},xAxis:{{type:'category',data:{daily_json}.map(i=>i.date),axisLabel:{{rotate:45,fontSize:10}}}},yAxis:{{type:'value',name:'消息数',minInterval:1}},series:[{{data:{daily_json}.map(i=>i.count),type:'bar',itemStyle:{{color:'#6366f1'}}}}],grid:{{left:45,bottom:70,right:15,top:10}}}});
</script>
</body>
</html>"""


def _generate_summary(stats: dict, prev_label: str) -> str:
    parts = [f"本周期共与 {stats['talked']} 位 BOSS 沟通，共产生 {stats['messages']} 条消息"]
    if stats['resumes']:
        parts.append(f"发送简历 {stats['resumes']} 份")
    if stats['interviews']:
        parts.append(f"获得面试 {stats['interviews']} 次")
    return "，".join(parts) + "。"


def _calc_trend(curr, prev, label: str) -> tuple[str, str]:
    if prev == 0 and curr == 0:
        return "暂无", ""
    if prev == 0:
        return f"较{label} 0", "up"
    diff = curr - prev
    if diff > 0:
        return f"较{label} +{diff}", "up"
    elif diff < 0:
        return f"较{label} {diff}", "down"
    return f"较{label} →", ""


def _daily_data(start_ms: int, end_ms: int) -> list:
    conn = get_db()
    rows = conn.execute(
        """SELECT DATE(time/1000,'unixepoch') as date, COUNT(*) as cnt
           FROM chat_messages WHERE time >= ? AND time < ? GROUP BY date ORDER BY date""",
        (start_ms, end_ms),
    ).fetchall()
    conn.close()
    return [{"date": r["date"], "count": r["cnt"]} for r in rows]


def _build_stats(period_start: int, period_end: int, prev_start: int, prev_end: int, prev_label: str) -> dict:
    conn = get_db()
    cur_talked = conn.execute("SELECT COUNT(DISTINCT encrypt_boss_id) FROM chat_messages WHERE time >= ? AND time < ?", (period_start, period_end)).fetchone()[0]
    prev_talked = conn.execute("SELECT COUNT(DISTINCT encrypt_boss_id) FROM chat_messages WHERE time >= ? AND time < ?", (prev_start, prev_end)).fetchone()[0]
    cur_msgs = conn.execute("SELECT COUNT(*) FROM chat_messages WHERE time >= ? AND time < ?", (period_start, period_end)).fetchone()[0]
    prev_msgs = conn.execute("SELECT COUNT(*) FROM chat_messages WHERE time >= ? AND time < ?", (prev_start, prev_end)).fetchone()[0]
    cur_resume = conn.execute(
        "SELECT COUNT(*) FROM bosses WHERE is_resume_sent=1 AND send_resume_datetime IS NOT NULL AND send_resume_datetime >= ? AND send_resume_datetime < ?",
        (period_start, period_end)).fetchone()[0]
    prev_resume = conn.execute(
        "SELECT COUNT(*) FROM bosses WHERE is_resume_sent=1 AND send_resume_datetime IS NOT NULL AND send_resume_datetime >= ? AND send_resume_datetime < ?",
        (prev_start, prev_end)).fetchone()[0]
    interviews = conn.execute(
        "SELECT COUNT(*) FROM bosses WHERE has_interview=1 AND first_msg_time >= ? AND first_msg_time < ?",
        (period_start, period_end)).fetchone()[0]
    prev_interviews = conn.execute(
        "SELECT COUNT(*) FROM bosses WHERE has_interview=1 AND first_msg_time >= ? AND first_msg_time < ?",
        (prev_start, prev_end)).fetchone()[0]
    top = conn.execute("""SELECT b.name, b.brand_name, COUNT(cm.id) as cnt FROM bosses b JOIN chat_messages cm ON cm.encrypt_boss_id=b.encrypt_boss_id WHERE cm.time>=? AND cm.time<? GROUP BY b.encrypt_boss_id ORDER BY cnt DESC LIMIT 5""", (period_start, period_end)).fetchall()
    conn.close()

    t_talked, t_cls = _calc_trend(cur_talked, prev_talked, prev_label)
    t_msg, m_cls = _calc_trend(cur_msgs, prev_msgs, prev_label)
    t_res, r_cls = _calc_trend(cur_resume, prev_resume, prev_label)
    t_intv, i_cls = _calc_trend(interviews, prev_interviews, prev_label)

    return {
        "talked": cur_talked, "messages": cur_msgs, "resumes": cur_resume, "interviews": interviews,
        "trend_talked": t_talked, "trend_talked_cls": t_cls,
        "trend_msg": t_msg, "trend_msg_cls": m_cls,
        "trend_resume": t_res, "trend_resume_cls": r_cls,
        "trend_interview": t_intv, "trend_interview_cls": i_cls,
        "top": [{"name": r["name"], "brand": r["brand_name"] or "", "count": r["cnt"]} for r in top],
    }


@router.get("/reports/weekly")
def generate_weekly():
    now = time.localtime()
    end_of_today = int(time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 23, 59, 59, 0, 0, now.tm_isdst))) * 1000
    week_start = _start_of_week(0)
    prev_week_start = _start_of_week(1)
    prev_week_end = week_start - 1  # last Sunday 23:59:59.999

    stats = _build_stats(week_start, end_of_today, prev_week_start, prev_week_end, "上周")
    daily = _daily_data(week_start, end_of_today)
    d1 = datetime.fromtimestamp(week_start/1000).strftime('%m/%d')
    d2 = datetime.fromtimestamp(end_of_today/1000).strftime('%m/%d')

    html = _build_html(f"📊 周报 {d1} - {d2}", f"{d1} - {d2}", "上周", stats, daily, stats["top"])
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = os.path.join(REPORTS_DIR, f"weekly_{ts}.html")
    with open(path, "w") as f:
        f.write(html)
    return {"ok": True, "path": f"weekly_{ts}.html", "url": f"/api/reports/view/weekly_{ts}.html"}


@router.get("/reports/monthly")
def generate_monthly():
    now = time.localtime()
    end_of_today = int(time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 23, 59, 59, 0, 0, now.tm_isdst))) * 1000
    month_start = _start_of_month(0)
    prev_month_start = _start_of_month(1)
    prev_month_end = month_start - 1

    stats = _build_stats(month_start, end_of_today, prev_month_start, prev_month_end, "上月")
    daily = _daily_data(month_start, end_of_today)
    d1 = datetime.fromtimestamp(month_start/1000).strftime('%m/%d')
    d2 = datetime.fromtimestamp(end_of_today/1000).strftime('%m/%d')

    html = _build_html(f"📊 月报 {d1} - {d2}", f"{d1} - {d2}", "上月", stats, daily, stats["top"])
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = os.path.join(REPORTS_DIR, f"monthly_{ts}.html")
    with open(path, "w") as f:
        f.write(html)
    return {"ok": True, "path": f"monthly_{ts}.html", "url": f"/api/reports/view/monthly_{ts}.html"}


@router.get("/reports/list")
def list_reports():
    files = sorted(
        [f for f in os.listdir(REPORTS_DIR) if f.endswith(".html")],
        reverse=True,
    )
    results = []
    for f in files:
        p = os.path.join(REPORTS_DIR, f)
        t = datetime.fromtimestamp(os.path.getmtime(p)).strftime('%Y-%m-%d %H:%M')
        kind = "周报" if f.startswith("weekly") else "月报"
        results.append({"name": f, "type": kind, "time": t, "url": f"/api/reports/view/{f}"})
    return results


@router.get("/reports/view/{filename}", response_class=HTMLResponse)
def view_report(filename: str):
    path = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(path):
        return HTMLResponse("<h2>报告不存在</h2>", status_code=404)
    with open(path) as f:
        return HTMLResponse(f.read())
