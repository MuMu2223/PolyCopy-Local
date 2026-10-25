# core/api_client.py
import requests
from typing import List, Dict, Any, Optional
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
from config import settings
from utils.logger import logger

class PolymarketClient:
    """Polymarket 数据与交易交互客户端"""
    
    GAMMA_API_URL = "https://gamma-api.polymarket.com"
    DATA_API_URL = "https://data-api.polymarket.com"
    CLOB_HOST = "https://clob.polymarket.com"
    CHAIN_ID = 137  # Polygon Mainnet

    def __init__(self):
        self.clob_client: Optional[ClobClient] = None
        self._init_clob_client()

    def _init_clob_client(self):
        """初始化官方 CLOB 交易客户端"""
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
            # 如果没有显式配置 API Key，尝试从私钥派生 L2 签名凭证
            if not creds:
                self.clob_client.set_api_creds(self.clob_client.create_or_derive_api_creds())
            logger.info("Polymarket CLOB 客户端初始化成功")
        except Exception as e:
            logger.error(f"CLOB 客户端初始化异常: {e}")

    # ==========================================
    # 数据查询相关 (Gamma API / Data API)
    # ==========================================
    def fetch_top_traders_raw(self, limit: int = 100) -> List[Dict[str, Any]]:
        """从 Data API 获取全网交易排行数据"""
        url = f"{self.DATA_API_URL}/leaderboard"
        params = {
            "window": "all",  # 统计周期：all / 30d / 7d
            "limit": limit
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"获取排行榜返回状态码: {resp.status_code}")
        except Exception as e:
            logger.error(f"请求 Leaderboard 异常: {e}")
        return []

    def get_trader_recent_trades(self, address: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取指定玩家地址的最新成交订单记录"""
        url = f"{self.DATA_API_URL}/trades"
        params = {
            "maker_address": address.lower(),
            "limit": limit
        }
        try:
            resp = requests.get(url, params=params, timeout=8)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"获取地址 {address} 交易动态失败: {e}")
        return []

    def get_market_detail(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """查询特定市场的状态与详情（验证是否已结算）"""
        url = f"{self.GAMMA_API_URL}/markets"
        params = {"condition_id": condition_id}
        try:
            resp = requests.get(url, params=params, timeout=8)
            if resp.status_code == 200:
                markets = resp.json()
                return markets[0] if markets else None
        except Exception as e:
            logger.error(f"获取市场详情失败 condition_id={condition_id}: {e}")
        return None

    # ==========================================
    # 订单与资产执行相关 (CLOB API)
    # ==========================================
    def get_balance_allowance(self) -> float:
        """获取自有钱包在 CLOB 的可用 USDC 余额"""
        if not self.clob_client:
            return 0.0
        try:
            balance_info = self.clob_client.get_balance_allowance()
            # 单位换算 (USDC 为 6 位精度)
            balance = float(balance_info.get("balance", 0)) / 1e6
            return balance
        except Exception as e:
            logger.error(f"获取 USDC 余额失败: {e}")
            return 0.0

    def place_order(self, token_id: str, price: float, size: float, side: str) -> Dict[str, Any]:
        """
        向 CLOB 提交市价或限价单
        :param token_id: 合约的 Token ID (YES/NO 代币)
        :param price: 订单价格 (0.01 到 0.99 之间)
        :param size: 买卖份额数 (Shares)
        :param side: 'BUY' 或 'SELL'
        """
        if settings.DRY_RUN:
            logger.info(f"[模拟盘 DRY_RUN] 触发下单: {side} | Token: {token_id} | 价格: {price} | 份额: {size}")
            return {"status": "DRY_RUN", "orderID": "mock_dry_run_id"}

        if not self.clob_client:
            raise RuntimeError("CLOB 客户端尚未就绪")

        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=side.upper()
        )
        # 签名并发送订单
        signed_order = self.clob_client.create_order(order_args)
        resp = self.clob_client.post_order(signed_order, OrderType.FOK)  # 默认 Fill-Or-Kill 避免挂单卡单
        return resp


# 导出全局单例客户端
poly_client = PolymarketClient()
