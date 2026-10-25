# 🚀 PolyCopy-Local (Polymarket 智能胜率玩家本地自动跟单系统)

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-teal.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

一个专为 Polymarket 预测市场打造的**本地化、轻量级、支持 Docker 部署、带 Apple 视觉毛玻璃看板**的自动化跟单系统。  
支持免私钥启动沙盒模拟运行（内置 $100 ~ $1,000,000 USD 虚拟资金），并可在验证稳定后一键切换为真实私钥实盘跟单。

</div>

---

## 🌟 项目核心特性 (Key Features)

* **🏆 前 100 名顶尖胜率玩家追踪**：基于 Polymarket Gamma & Data API，自动拉取并维护胜率与盈利最高的前 100 名玩家清单。
* **🎮 内置沙盒试运行（免私钥）**：无需提前填入钱包私钥即可启动！内置 $100 ~ $1,000,000 USD 虚拟资金池，可在网页看板随意拉动滑块调节测试。
* **⚡ 真正实盘跟单支持**：在 `.env` 中配置私钥后，支持一键切换实盘模式，利用 Polymarket CLOB 协议发起链上签名与订单撮合。
* **🧠 精准意图识别与部分平仓**：支持开仓（OPEN）、加仓（ADD）、部分减仓（Partial Close）与全额平仓（Full Close），精确按比例扣减持仓与计算盈亏。
* **🛡️ 断点续传与硬核风控**：引入 SQLite 检查点（`sync_checkpoints`）与复合交易去重键，重启不漏单；内置每日最大亏损熔断、滑点保护与单笔最大金额限制。
* **🍏 Apple 空间拟物毛玻璃看板**：原生固定监听 **`8899`** 端口，采用深色超清磨砂玻璃视觉（Tailwind CSS + 极光光晕），动态展示指标、持仓、榜单与滚动日志。

---

## 📂 项目结构规范 (Architecture)

```text
PolyCopy-Local/
├── .env.example             # 环境变量模板（含模拟资金与风控配置）
├── .gitignore               # 忽略 .env、本地 sqlite 数据库等敏感项
├── Dockerfile               # Docker 镜像构建配置
├── docker-compose.yml       # Docker Compose 一键编排文件 (8899 端口)
├── requirements.txt         # Python 第三方依赖
├── config.py                # Pydantic 强类型配置解析类
├── main.py                  # 系统主启动入口
├── README.md                # 项目全量说明手册
│
├── core/                    # 核心业务逻辑
│   ├── api_client.py        # Polymarket 官方 API & CLOB 交易客户端封装
│   ├── leaderboard.py       # 前 100 名顶尖玩家清洗与本地缓存
│   ├── matcher.py           # 交易意图识别与仓位缩放计算
│   ├── simulator.py         # 虚拟沙盒账户引擎 ($100 ~ $1,000,000)
│   ├── executor.py          # 订单执行器（支持部分平仓与滑点保护）
│   └── monitor.py           # 异步交易轮询、去重与断点续接
│
├── risk/                    # 风控安全层
│   └── manager.py           # 每日亏损熔断线与交易安全审查
│
├── database/                # 本地持久化层 (SQLite)
│   ├── db.py                # 数据库初始化（含 checkpoints 检查点表）
│   └── models.py            # 数据表增删改查封装
│
├── web/                     # 视觉化服务层 (FastAPI)
│   ├── server.py            # Web API 服务端（端口 8899）
│   └── static/
│       └── index.html       # Apple 质感毛玻璃前端仪表盘
│
└── utils/                   # 工具库
    └── logger.py            # 统一彩色日志
