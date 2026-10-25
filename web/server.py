# web/server.py
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from config import settings
from utils.logger import logger
from database.db import get_db, init_db
from core.monitor import trade_monitor
from core.api_client import poly_client
from risk.manager import risk_mgr


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理：啟動時初始化資料庫並掛載監控引擎"""
    logger.info("正在初始化本地資料庫...")
    init_db()

    # 在背景非同步啟動 Polymarket 交易監控任務
    monitor_task = asyncio.create_task(trade_monitor.start())
    logger.info("交易監控引擎背景任務已就緒")
    
    yield
    
    # 關閉服務時停止監控
    trade_monitor.stop()
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    logger.info("交易監控引擎已停止")


app = FastAPI(title="PolyCopy-Local 監控後台", lifespan=lifespan)

# 靜態資源目錄
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_dashboard():
    """首頁直達視覺化儀表板"""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "歡迎使用 PolyCopy 看板，請將 index.html 放入 web/static 目錄下。"}


# ==========================================
# RESTful API 介面提供前端調用
# ==========================================

@app.get("/api/status")
def get_system_status():
    """獲取系統概況與風控狀態"""
    balance = poly_client.get_balance_allowance() if not settings.DRY_RUN else 1000.0
    return {
        "status": "RUNNING" if trade_monitor.is_running else "STOPPED",
        "dry_run": settings.DRY_RUN,
        "copy_ratio": settings.COPY_RATIO,
        "balance_usd": balance,
        "is_circuit_breaker_triggered": risk_mgr.is_circuit_breaker_triggered,
        "today_loss_usd": abs(risk_mgr.get_today_realized_pnl())
    }


@app.get("/api/traders")
def get_top_traders():
    """獲取本地快取的前 100 名高勝率玩家"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM top_traders ORDER BY rank ASC LIMIT 100")
        rows = [dict(r) for r in cursor.fetchall()]
        return {"data": rows}


@app.get("/api/positions")
def get_positions():
    """獲取目前本地活躍持倉"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM positions ORDER BY updated_at DESC")
        rows = [dict(r) for r in cursor.fetchall()]
        return {"data": rows}


@app.get("/api/trades")
def get_copy_trades(limit: int = 50):
    """獲取跟單執行紀錄清單"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM copy_trades ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
        return {"data": rows}


@app.get("/api/logs")
def get_system_logs(limit: int = 50):
    """獲取最新系統日誌"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM system_logs ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
        return {"data": rows}


if __name__ == "__main__":
    import uvicorn
    # 直接執行此檔時以 8899 端口運行
    uvicorn.run("web.server:app", host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=False)
