import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from ..services.sync_service import sync_all

logger = logging.getLogger("sync")
router = APIRouter()


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
