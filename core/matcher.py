# core/matcher.py
from typing import Dict, Any, Optional
from config import settings
from utils.logger import logger
from database.db import get_db


class TradeMatcher:
    """負責交易意圖判定（開倉/加倉/平倉）與倉位比例計算"""

    def __init__(self, copy_ratio: float = None):
        self.copy_ratio = copy_ratio or settings.COPY_RATIO
        self.min_usd = settings.MIN_TRADE_SIZE_USD
        self.max_usd = settings.MAX_TRADE_SIZE_USD

    def get_local_position(self, condition_id: str, outcome_index: int) -> Optional[Dict[str, Any]]:
        """查詢本地是否已經持有該預測市場選項的倉位"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM positions WHERE condition_id = ? AND outcome_index = ?",
                (condition_id, outcome_index)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def determine_action_type(self, side: str, condition_id: str, outcome_index: int) -> str:
        """
        判斷交易動作意圖：
        - 若目標方向為 BUY：
            - 本地無持倉 -> OPEN (開倉)
            - 本地已有持倉 -> ADD (加倉)
        - 若目標方向為 SELL：
            - CLOSE (平倉/減倉)
        """
        existing_pos = self.get_local_position(condition_id, outcome_index)
        
        if side.upper() == "BUY":
            if existing_pos and existing_pos.get("shares", 0) > 0:
                return "ADD"
            return "OPEN"
        elif side.upper() == "SELL":
            return "CLOSE"
        
        return "UNKNOWN"

    def calculate_copy_amount(self, target_trade_size_usd: float, action_type: str, condition_id: str = None, outcome_index: int = None) -> float:
        """
        計算我方跟單金額（USD）：
        - 平倉時：如果本地持有相應倉位，依比例全部或部分賣出
        - 開倉/加倉時：按 COPY_RATIO 縮放並受限於 MIN/MAX 限制
        """
        if action_type == "CLOSE":
            existing_pos = self.get_local_position(condition_id, outcome_index)
            if not existing_pos or existing_pos.get("shares", 0) <= 0:
                logger.info(f"目標執行平倉，但本地無相關持倉 (condition_id: {condition_id})，略過執行。")
                return 0.0
            # 預設以本地現有倉位依比例釋出
            return float(existing_pos.get("shares", 0.0))

        # 開倉或加倉計算
        raw_copy_usd = target_trade_size_usd * self.copy_ratio

        # 風險與規格過濾
        if raw_copy_usd < self.min_usd:
            logger.info(f"計算金額 ${raw_copy_usd:.2f} 低於系統最小訂單門檻 ${self.min_usd:.2f}，略過該筆交易。")
            return 0.0

        if raw_copy_usd > self.max_usd:
            logger.warning(f"計算金額 ${raw_copy_usd:.2f} 超過單筆最大上限，將截斷為 ${self.max_usd:.2f} 下單。")
            raw_copy_usd = self.max_usd

        return round(raw_copy_usd, 2)

    def process_target_trade(self, raw_trade: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        解析目標訂單並生成跟單執行規劃
        """
        tx_hash = raw_trade.get("transactionHash") or raw_trade.get("hash")
        trader_address = raw_trade.get("maker") or raw_trade.get("proxyWallet") or raw_trade.get("address")
        side = raw_trade.get("side", "").upper()  # BUY 或 SELL
        price = float(raw_trade.get("price", 0.0))
        shares = float(raw_trade.get("size", 0.0))
        target_amount_usd = price * shares

        token_id = raw_trade.get("asset_id") or raw_trade.get("tokenId")
        condition_id = raw_trade.get("conditionId") or raw_trade.get("condition_id")
        outcome_index = int(raw_trade.get("outcomeIndex", 0))

        if not tx_hash or target_amount_usd <= 0 or price <= 0:
            return None

        # 1. 意圖判定
        action_type = self.determine_action_type(side, condition_id, outcome_index)

        # 2. 跟單金額換算
        copy_amount_usd = self.calculate_copy_amount(target_amount_usd, action_type, condition_id, outcome_index)
        if copy_amount_usd <= 0:
            return None

        # 3. 換算預期跟單買賣 Shares
        copy_shares = copy_amount_usd if action_type == "CLOSE" else round(copy_amount_usd / price, 2)

        return {
            "tx_hash": tx_hash,
            "trader_address": trader_address,
            "token_id": token_id,
            "condition_id": condition_id,
            "outcome_index": outcome_index,
            "side": side,
            "action_type": action_type,
            "price": price,
            "target_amount_usd": round(target_amount_usd, 2),
            "copy_amount_usd": copy_amount_usd,
            "copy_shares": copy_shares
        }


# 匯出單例物件
trade_matcher = TradeMatcher()
