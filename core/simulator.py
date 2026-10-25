# core/simulator.py
from typing import Dict, Any
from config import settings
from utils.logger import logger
from database.models import add_system_log


class SimulationSandbox:
    """内置虚拟资金沙盒运行引擎 ($100 - $1,000,000 USD)"""

    def __init__(self):
        self.initial_balance: float = settings.SIMULATION_CAPITAL
        self.available_balance: float = self.initial_balance
        self.total_pnl: float = 0.0

    def set_capital(self, amount: float):
        """动态调整虚拟本金 ($100 - $1,000,000)"""
        amount = max(100.0, min(1000000.0, amount))
        self.initial_balance = amount
        self.available_balance = amount
        self.total_pnl = 0.0
        msg = f"沙盒虚拟资金已重置为: ${self.initial_balance:,.2f} USD"
        logger.info(msg)
        add_system_log("INFO", "simulator", msg)

    def get_status(self) -> Dict[str, Any]:
        """获取沙盒资产概览"""
        return {
            "initial_balance": round(self.initial_balance, 2),
            "available_balance": round(self.available_balance, 2),
            "total_pnl": round(self.total_pnl, 2),
            "roi_pct": round((self.total_pnl / self.initial_balance) * 100, 2) if self.initial_balance else 0.0
        }

    def simulate_buy(self, amount_usd: float) -> bool:
        """模拟买入/开仓扣款"""
        if self.available_balance < amount_usd:
            logger.warning(f"[沙盒警告] 虚拟余额不足 (当前: ${self.available_balance:.2f}, 需扣除: ${amount_usd:.2f})")
            return False
        self.available_balance -= amount_usd
        return True

    def simulate_sell(self, return_usd: float, cost_usd: float):
        """模拟卖出/平仓收益结算"""
        profit = return_usd - cost_usd
        self.available_balance += return_usd
        self.total_pnl += profit
        logger.info(f"[沙盒结算] 平仓回款: ${return_usd:.2f} | 盈亏: ${profit:+.2f}")


# 导出全局单例沙盒
sandbox = SimulationSandbox()
