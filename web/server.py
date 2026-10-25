# 在 web/server.py 中添加以下路由：
from core.simulator import sandbox
from pydantic import BaseModel

class CapitalRequest(BaseModel):
    amount: float

@app.get("/api/status")
def get_system_status():
    """返回系统状态与资产概览（若为模拟盘则返回沙盒虚拟数据）"""
    sb_status = sandbox.get_status()
    is_live = not settings.DRY_RUN and bool(settings.WALLET_PRIVATE_KEY)

    balance = poly_client.get_balance_allowance() if is_live else sb_status["available_balance"]
    today_pnl = abs(risk_mgr.get_today_realized_pnl()) if is_live else sb_status["total_pnl"]

    return {
        "status": "RUNNING" if trade_monitor.is_running else "STOPPED",
        "dry_run": settings.DRY_RUN,
        "has_private_key": bool(settings.WALLET_PRIVATE_KEY),
        "copy_ratio": settings.COPY_RATIO,
        "balance_usd": balance,
        "sandbox": sb_status,
        "today_loss_usd": today_pnl,
        "is_circuit_breaker_triggered": risk_mgr.is_circuit_breaker_triggered
    }

@app.post("/api/sandbox/capital")
def set_sandbox_capital(req: CapitalRequest):
    """前端滑块/输入框动态调整沙盒本金 (100 ~ 1,000,000 USD)"""
    sandbox.set_capital(req.amount)
    return {"status": "SUCCESS", "new_balance": sandbox.available_balance}

@app.post("/api/mode/toggle")
def toggle_trading_mode():
    """切换模拟/实盘（若未提供私钥则禁止切换实盘）"""
    if settings.DRY_RUN:
        if not settings.WALLET_PRIVATE_KEY:
            return {"status": "ERROR", "message": "未在 .env 中配置钱包私钥，无法开启实盘！"}
        settings.DRY_RUN = False
    else:
        settings.DRY_RUN = True
    return {"status": "SUCCESS", "dry_run": settings.DRY_RUN}
