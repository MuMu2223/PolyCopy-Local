# main.py
import os
import sys
import uvicorn
from config import settings
from utils.logger import logger
from database.db import init_db

def print_banner():
    banner = f"""
    ====================================================================
      ____       _         ____                    _                    _ 
     |  _ \ ___ | |_   _  / ___|___  _ __  _   _  | |    ___   ___ __ _| |
     | |_) / _ \| | | | || |   / _ \| '_ \| | | | | |   / _ \ / __/ _` | |
     |  __/ (_) | | |_| || |__| (_) | |_) | |_| | | |__| (_) | (_| (_| | |
     |_|   \___/|_|\__, | \____\___/| .__/ \__, | |_____\___/ \___\__,_|_|
                   |___/            |_|    |___/                          
    ====================================================================
    [*] 運行模式    : {'[模擬盤 DRY RUN]' if settings.DRY_RUN else '[實盤交易 LIVE]'}
    [*] 跟單資金比例: {settings.COPY_RATIO * 100:.1f}%
    [*] 單筆金額上限: ${settings.MAX_TRADE_SIZE_USD:.2f} USD
    [*] 每日熔斷虧損: ${settings.MAX_DAILY_LOSS_USD:.2f} USD
    [*] 監控玩家數量: 前 {settings.TOP_TRADERS_COUNT} 名
    [*] 儀表板位址  : http://{settings.SERVER_HOST if settings.SERVER_HOST != '0.0.0.0' else 'localhost'}:{settings.SERVER_PORT}
    ====================================================================
    """
    print(banner)

def main():
    # 1. 初始化資料庫結構
    logger.info("檢查並初始化本地 SQLite 資料庫...")
    try:
        init_db()
    except Exception as e:
        logger.error(f"資料庫初始化失敗: {e}")
        sys.exit(1)

    # 2. 列印系統狀態橫幅
    print_banner()

    # 3. 啟動 Web 儀表板與後端服務 (端口 8899)
    logger.info(f"正在啟動 Uvicorn 服務，監聽通訊埠 {settings.SERVER_PORT}...")
    try:
        uvicorn.run(
            "web.server:app",
            host=settings.SERVER_HOST,
            port=settings.SERVER_PORT,
            reload=False,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("系統收到使用者手動中止訊號，正在安全退出...")
    except Exception as e:
        logger.error(f"服務運行異常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
