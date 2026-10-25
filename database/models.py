# database/models.py
from typing import List, Dict, Any, Optional
from database.db import get_db


def upsert_top_traders(traders: List[Dict[str, Any]]):
    """批量更新前 100 名高胜率玩家数据"""
    with get_db() as conn:
        cursor = conn.cursor()
        for t in traders:
            cursor.execute("""
                INSERT INTO top_traders (address, rank, win_rate, total_pnl, total_trades, last_updated)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(address) DO UPDATE SET
                    rank=excluded.rank,
                    win_rate=excluded.win_rate,
                    total_pnl=excluded.total_pnl,
                    total_trades=excluded.total_trades,
                    last_updated=CURRENT_TIMESTAMP
            """, (t["address"], t["rank"], t["win_rate"], t["total_pnl"], t["total_trades"]))


def get_all_tracked_addresses() -> List[str]:
    """获取所有正在监控的玩家地址列表"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT address FROM top_traders ORDER BY rank ASC")
        return [row["address"] for row in cursor.fetchall()]


def is_tx_already_copied(tx_hash: str) -> bool:
    """检查该笔交易是否已经执行过跟单（防重）"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM copy_trades WHERE tx_hash = ?", (tx_hash,))
        return cursor.fetchone() is not None


def record_trade(trade_data: Dict[str, Any]):
    """记录一笔新的跟单订单"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO copy_trades (
                tx_hash, trader_address, market_id, condition_id,
                outcome_index, side, action_type, target_amount_usd,
                copy_amount_usd, price, shares, status, error_msg
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_data.get("tx_hash"),
            trade_data.get("trader_address"),
            trade_data.get("market_id"),
            trade_data.get("condition_id"),
            trade_data.get("outcome_index"),
            trade_data.get("side"),
            trade_data.get("action_type"),
            trade_data.get("target_amount_usd"),
            trade_data.get("copy_amount_usd"),
            trade_data.get("price"),
            trade_data.get("shares"),
            trade_data.get("status"),
            trade_data.get("error_msg")
        ))


def add_system_log(level: str, module: str, message: str):
    """写入系统操作日志（供 Web 界面读取）"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO system_logs (level, module, message) VALUES (?, ?, ?)",
            (level, module, message)
        )
