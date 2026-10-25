# core/monitor.py
import asyncio
import time
from typing import List
from config import settings
from utils.logger import logger
from database.models import get_all_tracked_addresses, is_tx_already_copied, add_system_log
from core.api_client import poly_client
from core.leaderboard import leaderboard_mgr
from core.matcher import trade_matcher
from core.executor import trade_executor


class TradeMonitor:
    """非同步交易監控器：持續監聽前 100 名玩家動態並觸發自動跟單"""

    def __init__(self):
        self.poll_interval = settings.POLL_INTERVAL_SECONDS
        self.is_running = False
        self.last_leaderboard_sync = 0
        self.leaderboard_sync_interval = 3600  # 預設每 1 小時重新同步一次排行榜

    async def sync_leaderboard_if_needed(self):
        """定期更新前 100 名玩家排行榜快取"""
        now = time.time()
        if now - self.last_leaderboard_sync > self.leaderboard_sync_interval:
            logger.info("定時任務觸發：開始同步前 100 名高勝率玩家名單...")
            # 在背景非同步執行更新
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, leaderboard_mgr.update_local_leaderboard)
            if success:
                self.last_leaderboard_sync = now

    async def scan_trader_trades(self, address: str):
        """非同步掃描單一玩家的最新成交訂單"""
        loop = asyncio.get_event_loop()
        # 呼叫 API 獲取該地址最近的交易
        trades = await loop.run_in_executor(None, poly_client.get_trader_recent_trades, address, 5)
        if not trades:
            return

        for trade in trades:
            tx_hash = trade.get("transactionHash") or trade.get("hash")
            if not tx_hash:
                continue

            # 1. 檢查是否已處理過該筆交易
            if is_tx_already_copied(tx_hash):
                continue

            logger.info(f"偵測到目標玩家 [{address[:8]}...] 發起新交易 (Tx: {tx_hash[:10]}...)")
            add_system_log("INFO", "monitor", f"偵測到玩家 {address[:8]}... 新動作")

            # 2. 意圖識別與金額換算
            trade_plan = trade_matcher.process_target_trade(trade)
            if not trade_plan:
                continue

            # 3. 提交訂單執行模組
            await loop.run_in_executor(None, trade_executor.execute, trade_plan)

    async def start(self):
        """啟動常駐監控循環"""
        self.is_running = True
        logger.info(f"🚀 PolyCopy 監控引擎已啟動，輪詢間隔: {self.poll_interval} 秒")
        add_system_log("INFO", "monitor", "監控服務已啟動")

        # 啟動時先確保有第一批排行榜名單
        await self.sync_leaderboard_if_needed()

        while self.is_running:
            try:
                # 檢查排行榜更新
                await self.sync_leaderboard_if_needed()

                # 讀取本地監控地址列表
                tracked_addresses: List[str] = get_all_tracked_addresses()
                if not tracked_addresses:
                    logger.warning("目前未獲取到任何監控玩家地址，等待下一次重試...")
                    await asyncio.sleep(5)
                    continue

                # 依序/批次檢查目標玩家交易
                for address in tracked_addresses:
                    if not self.is_running:
                        break
                    await self.scan_trader_trades(address)
                    # 避免頻繁發送 API 請求造成 rate limit
                    await asyncio.sleep(0.05)

                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.info("監控任務收到終止信號...")
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"監控循環異常: {e}")
                add_system_log("ERROR", "monitor", f"循環異常: {e}")
                await asyncio.sleep(self.poll_interval)

    def stop(self):
        """停止監控"""
        self.is_running = False
        logger.info("正在停止監控引擎...")


# 匯出單例物件
trade_monitor = TradeMonitor()
