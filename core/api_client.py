# core/api_client.py (仅微调初始化部分，其余查询方法保持不变)
import requests
from typing import List, Dict, Any, Optional
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
from config import settings
from utils.logger import logger

class PolymarketClient:
    GAMMA_API_URL = "https://gamma-api.polymarket.com"
    DATA_API_URL = "https://data-api.polymarket.com"
    CLOB_HOST = "https://clob.polymarket.com"
    CHAIN_ID = 137

    def __init__(self):
        self.clob_client: Optional[ClobClient] = None
        self._init_clob_client()

    def _init_clob_client(self):
        """若提供私钥则初始化实盘客户端，否则仅以只读/模拟模式运行"""
        if not settings.WALLET_PRIVATE_KEY or settings.WALLET_PRIVATE_KEY.startswith("0x_your_"):
            logger.info("未提供有效私钥，系统已安全启动 [虚拟沙盒试运行模式]（只读 Polymarket 公开行情与榜单）")
            return

        try:
            creds = None
            if settings.POLY_API_KEY and settings.POLY_API_SECRET and settings.POLY_API_PASSPHRASE:
                creds = ApiCreds(
                    api_key=settings.POLY_API_KEY,
                    api_secret=settings.POLY_API_SECRET,
                    api_passphrase=settings.POLY_API_PASSPHRASE
                )

            self.clob_client = ClobClient(
                host=self.CLOB_HOST,
                key=settings.WALLET_PRIVATE_KEY,
                chain_id=self.CHAIN_ID,
                creds=creds
            )
            if not creds:
                self.clob_client.set_api_creds(self.clob_client.create_or_derive_api_creds())
            logger.info("Polymarket CLOB 实盘交易客户端就绪")
        except Exception as e:
            logger.warning(f"CLOB 交易客户端未连接 (将以模拟沙盒运行): {e}")

    def fetch_top_traders_raw(self, limit: int = 100) -> List[Dict[str, Any]]:
        url = f"{self.DATA_API_URL}/leaderboard"
        params = {"window": "all", "limit": limit}
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"拉取排行榜异常: {e}")
        return []

    def get_trader_recent_trades(self, address: str, limit: int = 10) -> List[Dict[str, Any]]:
        url = f"{self.DATA_API_URL}/trades"
        params = {"maker_address": address.lower(), "limit": limit}
        try:
            resp = requests.get(url, params=params, timeout=8)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"获取玩家 {address} 动态失败: {e}")
        return []

    def get_balance_allowance(self) -> float:
        if not self.clob_client:
            return 0.0
        try:
            balance_info = self.clob_client.get_balance_allowance()
            return float(balance_info.get("balance", 0)) / 1e6
        except Exception as e:
            logger.error(f"查询实盘余额异常: {e}")
            return 0.0

    def place_order(self, token_id: str, price: float, size: float, side: str) -> Dict[str, Any]:
        if settings.DRY_RUN or not self.clob_client:
            return {"status": "DRY_RUN", "orderID": "mock_order_id"}

        order_args = OrderArgs(token_id=token_id, price=price, size=size, side=side.upper())
        signed_order = self.clob_client.create_order(order_args)
        return self.clob_client.post_order(signed_order, OrderType.FOK)

poly_client = PolymarketClient()
