# core/monitor.py
import asyncio
import time
from typing import List, Dict, Any
from config import settings
from utils.logger import logger
from database.db import get_db
from database.models import get_all_tracked_addresses, add_system_log
from core.api_client import poly_client
from core.leaderboard import leaderboard_mgr
from core.matcher import trade_matcher
from core.executor import trade_executor


class TradeMonitor:
    def __init__(self):
        self.poll_interval = settings.POLL_INTERVAL_SECONDS
        self.is_running = False
        self.last_leaderboard_sync = 0
        self.leaderboard_sync_interval = 3600

    def get_last_checkpoint(self, address: str) -> int:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT last_trade_timestamp FROM sync_checkpoints WHERE address = ?", (address.lower(),))
            row = cursor.fetchone()
            return int(row["last_trade_timestamp"]) if row else 0

    def update_checkpoint(self, address: str, timestamp: int):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sync_checkpoints (address, last_trade_timestamp, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(address) DO UPDATE SET
                    last_trade_timestamp = MAX(last_trade_timestamp, excluded.last_trade_timestamp),
                    updated_at = CURRENT_TIMESTAMP
            """, (address.lower(), timestamp))

    def is_trade_processed(self, unique_key: str) -> bool:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM copy_trades WHERE tx_hash = ?", (unique_key,))
            return cursor.fetchone() is not None

    async def scan_trader_trades(self, address: str):
        loop = asyncio.get_event_loop()
        last_ts = self.get_last_checkpoint(address)

        # 获取最多 20 笔（防止高频漏单）
        trades = await loop.run_in_executor(None, poly_client.get_trader_recent_trades, address, 20)
        if not trades:
            return

        # 按时间正序处理（从旧到新，确保开仓->加仓->平仓顺序正确）
        trades.sort(key=lambda x: int(x.get("timestamp", 0) or 0))

        max_seen_ts = last_ts
        for trade in trades:
            trade_ts = int(trade.get("timestamp", 0) or 0)
            tx_hash = trade.get("transactionHash") or trade.get("hash")
            token_id = str(trade.get("asset_id") or trade.get("tokenId") or "")
            order_id = str(trade.get("order_id") or trade.get("id") or "")

            # 复合唯一键，杜绝同 tx 多笔成交被去重过滤
            unique_key = f"{tx_hash}_{token_id}_{order_id}" if tx_hash else None
            if not unique_key:
                continue

            # 检查时间戳与去重记录
            if trade_ts > 0 and trade_ts <= last_ts:
                continue

            if self.is_trade_processed(unique_key):
                continue

            # 记录最大时间戳
            if trade_ts > max_seen_ts:
                max_seen_ts = trade_ts

            logger.info(f"捕获玩家 [{address[:8]}...] 有效动作 (TxKey: {unique_key[:16]}...)")
            trade["composite_key"] = unique_key

            trade_plan = trade_matcher.process_target_trade(trade)
            if not trade_plan:
                continue

            await loop.run_in_executor(None, trade_executor.execute, trade_plan)

        # 更新该地址的检查点位
        if max_seen_ts > last_ts:
            self.update_checkpoint(address, max_seen_ts)

    async def start(self):
        self.is_running = True
        logger.info(f"🚀 PolyCopy 监控引擎已启动 (轮询间隔: {self.poll_interval}s)")
        add_system_log("INFO", "monitor", "监控主循环服务已启动")

        now = time.time()
        if now - self.last_leaderboard_sync > self.leaderboard_sync_interval:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, leaderboard_mgr.update_local_leaderboard)
            self.last_leaderboard_sync = now

        while self.is_running:
            try:
                tracked = get_all_tracked_addresses()
                for addr in tracked:
                    if not self.is_running:
                        break
                    await self.scan_trader_trades(addr)
                    await asyncio.sleep(0.08)  # API 限流缓冲

                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控主循环异常: {e}")
                await asyncio.sleep(self.poll_interval)

    def stop(self):
        self.is_running = False


trade_monitor = TradeMonitor()
