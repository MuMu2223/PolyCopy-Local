# core/executor.py
from typing import Dict, Any
from config import settings
from utils.logger import logger
from database.db import get_db
from database.models import record_trade, add_system_log
from risk.manager import risk_mgr
from core.api_client import poly_client
from core.simulator import sandbox


class TradeExecutor:
    def update_position_record(self, trade_plan: Dict[str, Any]):
        """精确支持开仓、加仓、部分平仓与全额平仓"""
        condition_id = trade_plan["condition_id"]
        outcome_index = trade_plan["outcome_index"]
        token_id = trade_plan.get("token_id")
        action_type = trade_plan["action_type"]
        trade_shares = float(trade_plan["copy_shares"])
        price = float(trade_plan["price"])
        amount_usd = float(trade_plan["copy_amount_usd"])

        with get_db() as conn:
            cursor = conn.cursor()

            if action_type in ["OPEN", "ADD"]:
                cursor.execute("""
                    INSERT INTO positions (
                        condition_id, outcome_index, token_id, shares,
                        avg_cost, total_invested_usd, current_price, unrealized_pnl, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, CURRENT_TIMESTAMP)
                    ON CONFLICT(condition_id) DO UPDATE SET
                        shares = shares + excluded.shares,
                        total_invested_usd = total_invested_usd + excluded.total_invested_usd,
                        avg_cost = (total_invested_usd + excluded.total_invested_usd) / (shares + excluded.shares),
                        current_price = excluded.current_price,
                        updated_at = CURRENT_TIMESTAMP
                """, (condition_id, outcome_index, token_id, trade_shares, price, amount_usd, price))

            elif action_type == "CLOSE":
                # 查询当前持仓
                cursor.execute("SELECT * FROM positions WHERE condition_id = ? AND outcome_index = ?", (condition_id, outcome_index))
                pos = cursor.fetchone()
                if pos:
                    current_shares = float(pos["shares"])
                    current_cost = float(pos["total_invested_usd"])

                    # 判断是部分平仓还是全部平仓
                    if trade_shares >= (current_shares - 0.001):
                        # 全额平仓：彻底清除记录
                        cursor.execute("DELETE FROM positions WHERE condition_id = ? AND outcome_index = ?", (condition_id, outcome_index))
                    else:
                        # 部分平仓：按比例扣除成本与份额
                        ratio = trade_shares / current_shares
                        remaining_shares = current_shares - trade_shares
                        remaining_cost = current_cost * (1.0 - ratio)
                        avg_cost = remaining_cost / remaining_shares if remaining_shares > 0 else 0.0

                        cursor.execute("""
                            UPDATE positions SET
                                shares = ?,
                                total_invested_usd = ?,
                                avg_cost = ?,
                                current_price = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE condition_id = ? AND outcome_index = ?
                        """, (remaining_shares, remaining_cost, avg_cost, price, condition_id, outcome_index))

    def execute(self, trade_plan: Dict[str, Any]) -> bool:
        tx_hash = trade_plan["tx_hash"]
        side = trade_plan["side"]
        token_id = trade_plan["token_id"]
        price = trade_plan["price"]
        shares = trade_plan["copy_shares"]
        action = trade_plan["action_type"]
        copy_usd = trade_plan["copy_amount_usd"]

        # 1. 沙盒模拟模式
        if settings.DRY_RUN:
            if action in ["OPEN", "ADD"]:
                if not sandbox.simulate_buy(copy_usd):
                    add_system_log("WARNING", "executor", f"沙盒虚拟资金不足，跳过跟单 ${copy_usd:.2f}")
                    return False
            elif action == "CLOSE":
                return_usd = shares * price
                sandbox.simulate_sell(return_usd, copy_usd)

            trade_plan["status"] = "DRY_RUN"
            trade_plan["error_msg"] = None
            record_trade(trade_plan)
            self.update_position_record(trade_plan)
            add_system_log("INFO", "executor", f"[沙盒] {action} 成交: ${copy_usd:.2f} ({shares:.1f} shares)")
            return True

        # 2. 实盘模式
        if not settings.WALLET_PRIVATE_KEY or settings.WALLET_PRIVATE_KEY.startswith("0x_your_"):
            logger.error("未配置真实 WALLET_PRIVATE_KEY，拒绝执行实盘下单！")
            return False

        passed, reason = risk_mgr.validate_trade_execution(trade_plan)
        if not passed:
            trade_plan["status"] = "SKIPPED"
            trade_plan["error_msg"] = reason
            record_trade(trade_plan)
            return False

        try:
            # 引入 2% 滑点容差价格保护
            execution_price = min(0.99, price * 1.02) if side == "BUY" else max(0.01, price * 0.98)
            resp = poly_client.place_order(token_id=token_id, price=execution_price, size=shares, side=side)

            # 校验成交响应
            if resp.get("status") in ["matched", "FILLED"]:
                trade_plan["status"] = "FILLED"
            elif resp.get("orderID"):
                trade_plan["status"] = "SUBMITTED"
            else:
                trade_plan["status"] = "REJECTED"

            record_trade(trade_plan)
            self.update_position_record(trade_plan)
            return True
        except Exception as e:
            trade_plan["status"] = "FAILED"
            trade_plan["error_msg"] = str(e)
            record_trade(trade_plan)
            return False


trade_executor = TradeExecutor()
