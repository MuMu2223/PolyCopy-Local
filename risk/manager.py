# risk/manager.py
import datetime
from typing import Dict, Any, Tuple
from config import settings
from utils.logger import logger
from database.db import get_db
from database.models import add_system_log
from core.api_client import poly_client


class RiskManager:
    """即時風控與熔斷防護引擎"""

    def __init__(self):
        self.max_daily_loss = settings.MAX_DAILY_LOSS_USD
        self.is_circuit_breaker_triggered = False

    def get_today_realized_pnl(self) -> float:
        """從本地交易紀錄計算今日累計的已實現損益（USD）"""
        today_str = datetime.date.today().isoformat()
        with get_db() as conn:
            cursor = conn.cursor()
            # 統計今日所有已成交的平倉單損益
            cursor.execute("""
                SELECT SUM(copy_amount_usd) as total_loss
                FROM copy_trades
                WHERE status = 'FILLED'
                  AND action_type = 'CLOSE'
                  AND error_msg LIKE '%LOSS%'
                  AND DATE(created_at) = DATE(?)
            """, (today_str,))
            row = cursor.fetchone()
            return float(row["total_loss"] or 0.0)

    def check_circuit_breaker(self) -> bool:
        """檢查是否觸發每日虧損熔斷線"""
        today_loss = abs(self.get_today_realized_pnl())
        if today_loss >= self.max_daily_loss:
            if not self.is_circuit_breaker_triggered:
                msg = f"【風控警報】今日累計虧損已達 ${today_loss:.2f}，觸發每日最大虧損熔斷線 (${self.max_daily_loss:.2f})！系統已自動停止所有開倉跟單。"
                logger.error(msg)
                add_system_log("ERROR", "risk_manager", msg)
                self.is_circuit_breaker_triggered = True
            return True
        return False

    def validate_trade_execution(self, trade_plan: Dict[str, Any]) -> Tuple[bool, str]:
        """
        在下單前進行多維度綜合風控審核
        :return: (是否放行, 原因說明)
        """
        # 1. 熔斷線檢查（僅限制開倉與加倉，不阻攔平倉止損）
        action_type = trade_plan.get("action_type")
        if action_type in ["OPEN", "ADD"] and self.check_circuit_breaker():
            return False, "今日虧損已觸發熔斷，拒絕開倉"

        # 2. 極端價格過濾（價格接近 0 或 1 時流動性差且賠率失真）
        price = trade_plan.get("price", 0.0)
        if price <= 0.02 or price >= 0.98:
            return False, f"價格過於極端 ({price})，不在安全交易價格區間 (0.02 ~ 0.98)"

        # 3. 自有資金充足度檢查（僅開倉/加倉需消耗 USDC）
        if action_type in ["OPEN", "ADD"]:
            required_usd = trade_plan.get("copy_amount_usd", 0.0)
            if not settings.DRY_RUN:
                available_balance = poly_client.get_balance_allowance()
                if available_balance < required_usd:
                    return False, f"帳戶可用餘額不足 (可用: ${available_balance:.2f}, 所需: ${required_usd:.2f})"

        return True, "風控審核通過"


# 匯出單例物件
risk_mgr = RiskManager()
