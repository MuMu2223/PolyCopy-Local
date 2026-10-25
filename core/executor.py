# core/executor.py
from typing import Dict, Any
from config import settings
from utils.logger import logger
from database.db import get_db
from database.models import record_trade, add_system_log
from risk.manager import risk_mgr
from core.api_client import poly_client


class TradeExecutor:
    """負責實際訂單發送、重試防護與本地倉位更新"""

    def __init__(self):
        self.dry_run = settings.DRY_RUN

    def update_position_record(self, trade_plan: Dict[str, Any]):
        """下單成功後更新本地持倉資料表"""
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
                # 開倉或加倉
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
                # 平倉：全數清除或扣減倉位
                cursor.execute("DELETE FROM positions WHERE condition_id = ? AND outcome_index = ?", (condition_id, outcome_index))

    def execute(self, trade_plan: Dict[str, Any]) -> bool:
        """
        執行跟單交易流程
        """
        tx_hash = trade_plan["tx_hash"]
        side = trade_plan["side"]
        token_id = trade_plan["token_id"]
        price = trade_plan["price"]
        shares = trade_plan["copy_shares"]
        action = trade_plan["action_type"]

        # 1. 執行前置風控審核
        passed, reason = risk_mgr.validate_trade_execution(trade_plan)
        if not passed:
            logger.warning(f"風控攔截 [Tx: {tx_hash[:10]}...]: {reason}")
            trade_plan["status"] = "SKIPPED"
            trade_plan["error_msg"] = reason
            record_trade(trade_plan)
            add_system_log("WARNING", "executor", f"跟單略過: {reason}")
            return False

        # 2. 發送訂單至 Polymarket CLOB
        try:
            logger.info(f"開始執行跟單 => 動作: {action} | 標的: {token_id} | 價格: {price} | 份額: {shares}")
            resp = poly_client.place_order(
                token_id=token_id,
                price=price,
                size=shares,
                side=side
            )

            # 3. 處理訂單回報狀態
            status = "FILLED" if (self.dry_run or resp.get("status") in ["matched", "FILLED", "DRY_RUN"]) else "PENDING"
            trade_plan["status"] = status
            trade_plan["error_msg"] = None

            # 記錄至資料庫
            record_trade(trade_plan)
            self.update_position_record(trade_plan)

            log_msg = f"跟單執行成功 [{status}]! 動作: {action}, 金額: ${trade_plan['copy_amount_usd']:.2f}, 標的: {token_id}"
            logger.info(log_msg)
            add_system_log("INFO", "executor", log_msg)
            return True

        except Exception as e:
            err_msg = f"下單失敗: {str(e)}"
            logger.error(f"跟單下單異常 [Tx: {tx_hash}]: {err_msg}")
            trade_plan["status"] = "FAILED"
            trade_plan["error_msg"] = err_msg
            record_trade(trade_plan)
            add_system_log("ERROR", "executor", err_msg)
            return False


# 匯出單例物件
trade_executor = TradeExecutor()
