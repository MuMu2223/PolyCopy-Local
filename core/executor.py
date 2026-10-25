# core/executor.py (更新执行逻辑)
from typing import Dict, Any
from config import settings
from utils.logger import logger
from database.db import get_db
from database.models import record_trade, add_system_log
from risk.manager import risk_mgr
from core.api_client import poly_client
from core.simulator import sandbox


class TradeExecutor:
    def __init__(self):
        pass

    def update_position_record(self, trade_plan: Dict[str, Any]):
        condition_id = trade_plan["condition_id"]
        outcome_index = trade_plan["outcome_index"]
        token_id = trade_plan.get("token_id")
        action_type = trade_plan["action_type"]
        shares = float(trade_plan["copy_shares"])
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
                """, (condition_id, outcome_index, token_id, shares, price, amount_usd, price))

            elif action_type == "CLOSE":
                cursor.execute("DELETE FROM positions WHERE condition_id = ? AND outcome_index = ?", (condition_id, outcome_index))

    def execute(self, trade_plan: Dict[str, Any]) -> bool:
        tx_hash = trade_plan["tx_hash"]
        side = trade_plan["side"]
        token_id = trade_plan["token_id"]
        price = trade_plan["price"]
        shares = trade_plan["copy_shares"]
        action = trade_plan["action_type"]
        copy_usd = trade_plan["copy_amount_usd"]

        # 1. 模拟模式下资金校验
        if settings.DRY_RUN:
            if action in ["OPEN", "ADD"]:
                if not sandbox.simulate_buy(copy_usd):
                    add_system_log("WARNING", "executor", f"沙盒虚拟资金不足，跳过跟单 ${copy_usd:.2f}")
                    return False
            elif action == "CLOSE":
                # 简单估算平仓回款
                return_usd = shares * price
                sandbox.simulate_sell(return_usd, copy_usd)

            trade_plan["status"] = "DRY_RUN"
            trade_plan["error_msg"] = None
            record_trade(trade_plan)
            self.update_position_record(trade_plan)
            log_msg = f"[沙盒模拟] 成功复刻交易: {action} | 标的: {token_id[:10]}... | 虚拟金额: ${copy_usd:.2f}"
            logger.info(log_msg)
            add_system_log("INFO", "executor", log_msg)
            return True

        # 2. 实盘模式检查（必须有私钥与风控审核）
        if not settings.WALLET_PRIVATE_KEY:
            logger.error("未配置 WALLET_PRIVATE_KEY，无法开启实盘交易！已自动拦截。")
            return False

        passed, reason = risk_mgr.validate_trade_execution(trade_plan)
        if not passed:
            logger.warning(f"实盘风控拦截 [Tx: {tx_hash[:10]}...]: {reason}")
            trade_plan["status"] = "SKIPPED"
            trade_plan["error_msg"] = reason
            record_trade(trade_plan)
            add_system_log("WARNING", "executor", f"实盘风控拦截: {reason}")
            return False

        try:
            resp = poly_client.place_order(token_id=token_id, price=price, size=shares, side=side)
            status = "FILLED" if resp.get("status") in ["matched", "FILLED"] else "PENDING"
            trade_plan["status"] = status
            record_trade(trade_plan)
            self.update_position_record(trade_plan)
            logger.info(f"实盘跟单已广播至 CLOB [{status}]: 金额 ${copy_usd:.2f}")
            return True
        except Exception as e:
            trade_plan["status"] = "FAILED"
            trade_plan["error_msg"] = str(e)
            record_trade(trade_plan)
            return False


trade_executor = TradeExecutor()
