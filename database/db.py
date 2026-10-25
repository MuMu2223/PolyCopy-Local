# database/db.py
import sqlite3
import os
from contextlib import contextmanager

# 数据库文件保存在 database/poly_copy.db
DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "poly_copy.db")


def get_connection():
    """获取 SQLite 连接并配置 row_factory 为字典格式"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    """数据库连接上下文管理器，自动提交与关闭"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_db():
    """初始化数据库表结构"""
    with get_db() as conn:
        cursor = conn.cursor()

        # 1. 监控的前 100 名玩家榜单表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS top_traders (
                address TEXT PRIMARY KEY,
                rank INTEGER,
                win_rate REAL,
                total_pnl REAL,
                total_trades INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. 跟单交易记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS copy_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_hash TEXT UNIQUE,
                trader_address TEXT,
                market_id TEXT,
                condition_id TEXT,
                outcome_index INTEGER,
                side TEXT, -- BUY / SELL
                action_type TEXT, -- OPEN / ADD / CLOSE
                target_amount_usd REAL,
                copy_amount_usd REAL,
                price REAL,
                shares REAL,
                status TEXT, -- FILLED / SKIPPED / FAILED / DRY_RUN
                error_msg TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 3. 本地当前活跃持仓表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                condition_id TEXT PRIMARY KEY,
                outcome_index INTEGER,
                token_id TEXT,
                shares REAL,
                avg_cost REAL,
                total_invested_usd REAL,
                current_price REAL,
                unrealized_pnl REAL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. 系统运行日志表（方便 Web 仪表盘实时拉取）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT, -- INFO / WARNING / ERROR
                module TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


if __name__ == "__main__":
    init_db()
    print("数据库初始化成功，文件位于:", DB_PATH)
