# web/server.py
import os
import asyncio
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from config import settings
from utils.logger import logger
from database.db import get_db, init_db
from core.monitor import trade_monitor
from core.api_client import poly_client
from core.simulator import sandbox
from risk.manager import risk_mgr


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库与后台监控协程"""
    logger.info("正在初始化本地持久化数据库...")
    init_db()

    monitor_task = asyncio.create_task(trade_monitor.start())
    logger.info("交易监控引擎后台任务启动成功")
    yield
    trade_monitor.stop()
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    logger.info("交易监控引擎已安全停止")


app = FastAPI(title="PolyCopy OS Server", lifespan=lifespan)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_dashboard():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "欢迎使用 PolyCopy 看板，请确保 index.html 位于 web/static 目录下。"}


# ==========================================
# API 路由
# ==========================================

class CapitalRequest(BaseModel):
    amount: float = Field(..., ge=100.0, le=1000000.0)


@app.get("/api/status")
def get_system_status():
    is_live = (not settings.DRY_RUN) and bool(settings.WALLET_PRIVATE_KEY)
    sb_status = sandbox.get_status()

    balance = poly_client.get_balance_allowance() if is_live else sb_status["available_balance"]
    today_pnl = abs(risk_mgr.get_today_realized_pnl()) if is_live else sb_status["total_pnl"]

    return {
        "status": "RUNNING" if trade_monitor.is_running else "STOPPED",
        "dry_run": settings.DRY_RUN,
        "has_private_key": bool(settings.WALLET_PRIVATE_KEY and not settings.WALLET_PRIVATE_KEY.startswith("0x_your_")),
        "copy_ratio": settings.COPY_RATIO,
        "balance_usd": balance,
        "sandbox": sb_status,
        "today_loss_usd": today_pnl,
        "is_circuit_breaker_triggered": risk_mgr.is_circuit_breaker_triggered
    }


@app.post("/api/sandbox/capital")
def set_sandbox_capital(req: CapitalRequest):
    sandbox.set_capital(req.amount)
    return {"status": "SUCCESS", "new_balance": sandbox.available_balance}


@app.post("/api/mode/toggle")
def toggle_trading_mode():
    if settings.DRY_RUN:
        if not settings.WALLET_PRIVATE_KEY or settings.WALLET_PRIVATE_KEY.startswith("0x_your_"):
            return JSONResponse(status_code=400, content={"status": "ERROR", "message": "未在 .env 中配置有效私钥，无法切换至实盘！"})
        settings.DRY_RUN = False
        logger.warning("【交易警告】系统已切换为 [实盘交易 LIVE] 模式！")
    else:
        settings.DRY_RUN = True
        logger.info("系统已切回 [模拟盘沙盒] 模式")

    return {"status": "SUCCESS", "dry_run": settings.DRY_RUN}


@app.get("/api/traders")
def get_top_traders():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM top_traders ORDER BY rank ASC LIMIT 100")
        return {"data": [dict(r) for r in cursor.fetchall()]}


@app.get("/api/positions")
def get_positions():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM positions ORDER BY updated_at DESC")
        return {"data": [dict(r) for r in cursor.fetchall()]}


@app.get("/api/trades")
def get_copy_trades(limit: int = 50):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM copy_trades ORDER BY created_at DESC LIMIT ?", (limit,))
        return {"data": [dict(r) for r in cursor.fetchall()]}


@app.get("/api/logs")
def get_system_logs(limit: int = 50):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM system_logs ORDER BY created_at DESC LIMIT ?", (limit,))
        return {"data": [dict(r) for r in cursor.fetchall()]}
