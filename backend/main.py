import logging
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .database import init_db
from .routers import cookie, sync, bosses, stats, messenger

AVATAR_DIR = os.path.join(Path(__file__).parent.parent, "avatar")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

app = FastAPI(title="Simple Boss Manage")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cookie.router, prefix="/api", tags=["Cookie"])
app.include_router(sync.router, prefix="/api", tags=["Sync"])
app.include_router(bosses.router, prefix="/api", tags=["Bosses"])
app.include_router(stats.router, prefix="/api", tags=["Stats"])
app.include_router(messenger.router, prefix="/api", tags=["Messenger"])


@app.on_event("startup")
def startup():
    logger.info("正在初始化数据库...")
    init_db()
    logger.info("服务启动完成")


os.makedirs(AVATAR_DIR, exist_ok=True)
app.mount("/avatar", StaticFiles(directory=AVATAR_DIR), name="avatar")


@app.get("/api/health")
def health():
    return {"status": "ok"}
