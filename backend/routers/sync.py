import logging
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from ..database import get_db
from ..services.sync_service import sync_all

logger = logging.getLogger("sync")
router = APIRouter()


@router.get("/sync/logs")
def get_sync_logs(limit: int = Query(10, ge=1, le=100)):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM sync_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/sync")
async def trigger_sync():
    logger.info("收到同步请求（SSE 流）")
    return StreamingResponse(
        sync_all(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
