# config.py
import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 钱包与网络配置（私钥设为可选，未填时自动仅允许模拟盘试运行）
    WALLET_PRIVATE_KEY: Optional[str] = Field(default=None, description="Polygon钱包私钥，不填则仅运行模拟沙盒")
    RPC_URL: str = Field(default="https://polygon-rpc.com", description="Polygon RPC节点")

    # Polymarket CLOB API 配置 (可选)
    POLY_API_KEY: Optional[str] = Field(default=None, description="API Key")
    POLY_API_SECRET: Optional[str] = Field(default=None, description="API Secret")
    POLY_API_PASSPHRASE: Optional[str] = Field(default=None, description="API Passphrase")

    # 运行模式与端口 (默认固定 8899)
    DRY_RUN: bool = Field(default=True, description="是否为模拟盘模式")
    SERVER_HOST: str = Field(default="0.0.0.0", description="Web仪表盘监听地址")
    SERVER_PORT: int = Field(default=8899, description="Web仪表盘端口")

    # 模拟沙盒资金池配置 (100 到 1000000 USD)
    SIMULATION_CAPITAL: float = Field(default=10000.0, ge=100.0, le=1000000.0, description="内置虚拟初始资金")

    # 跟单与风控参数
    COPY_RATIO: float = Field(default=0.10, ge=0.01, le=1.0, description="跟单资金缩放比例")
    MIN_TRADE_SIZE_USD: float = Field(default=1.0, ge=1.0, description="最小订单金额限制")
    MAX_TRADE_SIZE_USD: float = Field(default=50.0, description="单笔最大跟单限额")
    MAX_DAILY_LOSS_USD: float = Field(default=100.0, description="每日最大亏损熔断线")

    # 监控配置
    TOP_TRADERS_COUNT: int = Field(default=100, le=500, description="监控前N名玩家")
    POLL_INTERVAL_SECONDS: int = Field(default=2, ge=1, description="轮询扫描间隔(秒)")

    # 通知渠道 (可选)
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = 设置()
