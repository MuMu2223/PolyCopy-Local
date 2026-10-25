# core/leaderboard.py
import time
from typing import List, Dict, Any
from config import settings
from utils.logger import logger
from core.api_client import poly_client
from database.models import upsert_top_traders, add_system_log


class LeaderboardManager:
    """管理前 100 名顶尖玩家的数据抓取、胜率计算与本地存储"""

    def __init__(self, target_count: int = None):
        self.target_count = target_count or settings.TOP_TRADERS_COUNT
        self.last_update_timestamp = 0

    def fetch_and_rank_traders(self) -> List[Dict[str, Any]]:
        """从 API 拉取数据并计算综合胜率排名"""
        logger.info(f"开始同步 Polymarket 排行榜数据 (目标数量: {self.target_count})...")
        raw_data = poly_client.fetch_top_traders_raw(limit=max(self.target_count * 2, 200))
        
        if not raw_data:
            logger.warning("未获取到排行榜原始数据，将沿用本地缓存的玩家名单")
            return []

        processed_traders = []
        for item in raw_data:
            # 兼容不同 API 字段返回命名
            address = item.get("address") or item.get("proxyWallet") or item.get("user")
            if not address:
                continue

            # 统计指标
            pnl = float(item.get("pnl", 0.0) or item.get("profit", 0.0))
            volume = float(item.get("volume", 0.0))
            trades_count = int(item.get("trades", 0) or item.get("totalTrades", 0))

            # 过滤掉交易频次过低、偶然获利的噪音样本（至少交易过 5 次）
            if trades_count < 5:
                continue

            # 胜率估算（若接口有直接字段优先使用，否则按盈利订单占比/综合指标计算）
            win_rate = float(item.get("winRate", 0.0) or item.get("win_rate", 0.0))
            if win_rate <= 0 and trades_count > 0 and pnl > 0:
                # 简单平滑胜率估算
                win_rate = min(0.95, round(0.5 + (pnl / (volume + 1e-5)) * 0.5, 4))

            processed_traders.append({
                "address": address.lower(),
                "win_rate": round(win_rate, 4),
                "total_pnl": round(pnl, 2),
                "total_trades": trades_count
            })

        # 按胜率为主、总盈亏为辅进行降序排序
        processed_traders.sort(key=lambda x: (x["win_rate"], x["total_pnl"]), reverse=True)
        top_list = processed_traders[:self.target_count]

        # 赋予排名字段
        for rank, trader in enumerate(top_list, start=1):
            trader["rank"] = rank

        logger.info(f"成功计算并提取前 {len(top_list)} 名优质玩家数据")
        return top_list

    def update_local_leaderboard(self) -> bool:
        """更新本地 SQLite 数据库中的玩家排行榜"""
        try:
            top_traders = self.fetch_and_rank_traders()
            if not top_traders:
                return False

            upsert_top_traders(top_traders)
            self.last_update_timestamp = time.time()
            
            msg = f"本地排行榜更新完毕，当前监控玩家数: {len(top_traders)}"
            logger.info(msg)
            add_system_log("INFO", "leaderboard", msg)
            return True
        except Exception as e:
            err_msg = f"更新玩家排行榜异常: {e}"
            logger.error(err_msg)
            add_system_log("ERROR", "leaderboard", err_msg)
            return False


# 导出全局单例管理对象
leaderboard_mgr = LeaderboardManager()


if __name__ == "__main__":
    # 本地快速测试抓取与写入
    success = leaderboard_mgr.update_local_leaderboard()
    print("排行榜更新结果:", success)
