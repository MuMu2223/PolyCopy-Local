# 🚀 PolyCopy-Local (Polymarket 智能胜率玩家本地自动跟单系统)

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-teal.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

一个专为 Polymarket 预测市场打造的**本地化、轻量级、支持 Docker 部署、带多功能可视化看板**的自动化跟单机器人系统。

</div>

---

## 🌟 项目特点与多功能板块 (Key Features & Dashboard Modules)

* **🏆 顶尖玩家追踪板块**：自动抓取并维护 Polymarket 综合胜率最高的前 100 名顶尖玩家钱包地址。
* **🧠 智能意图识别引擎**：精准识别目标玩家的**开仓、加仓、完全平仓/卖出**动作，执行镜像操作。
* **💰 动态资金与风控板块**：支持自定义资金缩放比例（Copy Ratio）、每日最大亏损熔断、单笔上限以及 Polymarket CLOB 最小订单限制（$\ge \$1.00$）过滤。
* **💻 多功能可视化 Web 仪表盘 (Dashboard)**：
  * **行情监控区**：实时查看目标市场的盘口与趋势。
  * **排行榜区**：前 100 名胜率玩家实时数据与盈利统计。
  * **持仓与资产板块**：展示自有账户总资产、未实现盈亏与当前活跃跟单。
  * **实时日志终端**：滚动展示系统底层交易与风控拦截记录。
* **🐳 Docker 容器化支持**：完美适配 Docker 与 Docker Compose，支持一键部署与固定端口（`8899`）运行。

---

## 📂 项目目录结构 (Architecture)

```text
polymarket-copy-bot/
├── .env                          # 环境变量配置（私钥、RPC、风控阈值）
├── Dockerfile                    # Docker 镜像构建文件
├── docker-compose.yml            # Docker Compose 编排文件（固定 8899 端口）
├── requirements.txt              # 项目 Python 依赖包
├── config.py                     # 全局配置解析与校验
├── main.py                       # 项目主入口
│
├── core/                         # 核心交易与监控逻辑
│   ├── api_client.py             # Polymarket Gamma API & py-clob-client 封装
│   ├── leaderboard.py            # 前100名胜率玩家数据抓取与本地缓存
│   ├── monitor.py                # 异步轮询/实时监听交易动态
│   ├── matcher.py                # 意图识别与仓位大小计算
│   └── executor.py               # 订单执行引擎
│
├── risk/                         # 风控与安全引擎
│   └── manager.py                # 每日亏损熔断与单笔上限控制
│
├── database/                     # 持久化存储 (SQLite)
│   ├── db.py                     
│   └── models.py                 
│
├── web/                          # 可视化监控仪表盘
│   ├── server.py                 # FastAPI 后端（端口 8899）
│   └── static/                   # 前端静态资源（HTML、Tailwind CSS、Chart.js）
│
└── utils/                        # 辅助工具
    ├── logger.py                 
    └── notifier.py

🛠️ 安装与部署指南 (Installation & Deployment)
方法 A：使用 Docker 部署（推荐，端口固定为 8899）
克隆项目并配置环境变量：

Bash
git clone [https://github.com/your-username/polymarket-copy-bot.git](https://github.com/your-username/polymarket-copy-bot.git)
cd polymarket-copy-bot
# 复制或创建 .env 文件并填写你的私钥与参数
一键构建并启动容器：

Bash
docker-compose up --build -d
访问可视化面板：
打开浏览器访问：http://localhost:8899 即可进入多功能监控看板。

方法 B：本地 Python 直接运行
安装依赖：

Bash
pip install -r requirements.txt
启动服务：

Bash
python main.py
(注：本地开发时可在 web/server.py 中将端口指定为 8899)

⚠️ 免责声明 (Disclaimer)
本项目仅供技术研究、学习与交流使用。加密货币预测市场风险极高，请务必先通过模拟盘（DRY_RUN=True）充分测试。
