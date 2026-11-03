import logging
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from ..database import get_db
from ..milestone_utils import require_editable
from ..services.sync_service import sync_all

logger = logging.getLogger("sync")
router = APIRouter()


@router.get("/sync/logs")
def get_sync_logs(
    milestone_id: int = Query(..., description="里程碑 ID"),
    limit: int = Query(10, ge=1, le=100),
):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM sync_logs WHERE milestone_id = ? ORDER BY id DESC LIMIT ?",
        (milestone_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/sync")
async def trigger_sync(milestone_id: int = Query(..., description="里程碑 ID")):
    logger.info("收到同步请求（SSE 流）")
    conn = get_db()
    try:
        require_editable(conn, milestone_id)
    finally:
        conn.close()
    return StreamingResponse(
        sync_all(milestone_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
