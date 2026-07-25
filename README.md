# Investment News · 投资资讯

**中文** · [English](README.en.md)

<p align="center">
  <b>为 A股投资者追踪全球产业链领先信号 —— 12 大赛道一一对应 A股板块，覆盖 100+ 权威源，AI 每日提炼为中文要点，全程本地、零 API key。</b><br>
  Tracking the global industry signals behind China A-share sectors — 12 sectors mapped to A-share themes, 100+ authoritative sources, distilled into daily Chinese key points by your own AI, fully local, zero API key.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.1-blue.svg" alt="version 1.0.1">
  <img src="https://img.shields.io/badge/python-3.7+-blue.svg" alt="Python 3.7+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT">
  <img src="https://img.shields.io/badge/赛道-12_大方向-orange.svg" alt="12 sectors">
  <img src="https://img.shields.io/badge/信息源-100+_权威媒体-red.svg" alt="100+ sources">
  <img src="https://img.shields.io/badge/依赖-纯标准库-lightgrey.svg" alt="stdlib">
  <img src="https://img.shields.io/badge/大模型-订阅_or_API-purple.svg" alt="LLM">
</p>

---

## 这是什么

**Investment News 是为 A股投资者打造的全球产业链资讯看板。** 半导体、AI、机器人、新能源车、航天…这 12 大赛道一一对应 A股板块，而真正驱动板块的领先信号，往往先出现在全球英文源里。本工具覆盖全球 100+ 权威信息源，调用你自己的大模型，将各赛道最新动向每日提炼为中文「今日要点」并完成翻译，统一呈现在一个本地浏览器看板中。

区别于信息过载的新闻聚合器，其核心在于**由 AI 完成阅读与提炼**：每个赛道置顶 3–5 条「今日要点」，跨源聚合去重，便于快速把握各赛道全貌，并可下钻至原文核实。抓取过程由 Python 后端完成，AI 使用**你自己**的 Claude 订阅（$0）或任意 API key，结果存入 MySQL 并通过只读 API 提供给看板。

适用场景：

- A股投资者跟踪半导体、AI、新能源车、机器人等板块的全球先行信号，但海外资讯多为英文、且分散在上百个源——本工具把它们汇成一屏中文要点。
- 需同时跟踪多个投资赛道，但资讯庞杂、难以尽读，且多为英文。
- 门户与聚合器提供的是离散信息流；真正需要的是「该赛道当日的核心进展」—— 这正是 AI 要点层的职责。

> 📊 **本工具呈现的是行业动向与领先信号，并非行情数据，更不构成投资建议。** Industry trends, **not financial advice**.

## ✨ 能力 Features

| 能力 | 说明 |
|---|---|
| **今⁠日⁠要⁠点** | 每个赛道置顶 3–5 条中文要点，跨源聚合去重、提炼核心公司与数据，由本地大模型生成 |
| **双⁠语⁠呈⁠现** | 英文标题自动译为中文，中文为主、原文备查，无需英文阅读能力即可掌握 |
| **覆⁠盖⁠赛⁠道** | AI/大模型 · 半导体/芯片 · 机器人/自动化 · 汽车/新能源车 · 能源/新能源 · 生物医药/健康 · 航天/太空 · 网络安全 · 科技/互联网 · 消费电子/数码 · 财经/宏观 · 科学/前沿 |
| **要⁠点⁠溯⁠源** | 每条要点附原文链接，可一键回溯至主要信息来源 |
| **自⁠动⁠刷⁠新** | 服务启动后自动抓取与摘要，此后每 6 小时后台更新，无需手动操作 |
| **引⁠擎⁠双⁠选** | 支持本机 Claude 订阅（`claude-cli`，$0）与任意 OpenAI 兼容 API 两种接入，单一配置项切换 |
| **MySQL 数据源** | 新闻与公众号文章统一存入 MySQL，前端通过 Python 后端 API 实时读取 |
| **合⁠规⁠过⁠滤** | 内置关键词过滤，自动剔除博彩、预测市场、加密货币、色情类内容；时政、财经正常收录 |

## 📸 截图 Screenshot

![dashboard](docs/screenshot.png)

> **本工具的核心交付物是这个浏览器看板。** 运行后访问 `http://localhost:8793/news` 查看产业资讯，访问 `http://localhost:8793/analysis` 查看产业分析。

## 🚀 快速开始

**环境要求**：Node.js 20+、Python 3.7+、MySQL 5.7+/8.0+ 和一个大模型（下方二选一）。

```bash
git clone https://github.com/simonlin1212/investment-news.git
cd investment-news

# 1) 配置大模型(见下「配置」)，默认使用本机 Claude 订阅，零成本
# 2) 安装前后端依赖、构建 React 页面并初始化数据库
npm install
npm run build
python3 -m pip install -r requirements.txt
python3 scripts/import_mysql.py
# 3) 启动看板服务
./scripts/start.sh           # 默认端口 8793，保持运行
# 也可指定端口：./scripts/start.sh 8080
# 4) 在浏览器打开产业资讯（产业分析路由为 /analysis）
open http://localhost:8793/news   # Windows 使用 start，Linux 使用 xdg-open
# 5) 服务启动后会自动刷新一次，此后每 6 小时在后台自动更新
```

## ⚙️ 工作原理

```
sources.json  (108 个源 / 12 赛道)
       │
       ▼  scripts/fetch.py    抓取 + 合规过滤 + 最近 N 天 + 北京时间归一
  data.js  (原始条目)
       │
       ▼  scripts/digest.py   调用你的大模型 → 各赛道「今日要点」+ 中文翻译 + 溯源链接
  data.js  (含 AI 要点，刷新过程的中间文件)
       │
       ▼  scripts/import_mysql.py
     MySQL
       │
       ▼  server.py API       /api/news + /api/wechat-articles
  React + HeroUI 看板（Vite 构建至 dist）
```

数据访问使用 PyMySQL。`claude-cli` 模式下，`digest` 调用本机 `claude -p`（订阅鉴权、禁用全部工具、仅处理文本），**仅本地可用、零成本**。

## 🤖 配置大模型（订阅 / API 二选一）

复制环境变量模板并编辑 `.env`：

| provider | 说明 | 成本 |
|---|---|---|
| **`claude-cli`（默认）** | 使用本机已登录的 **Claude Code 订阅**（仅需 `claude login` 一次），本地可用 | **$0** |
| **`api`** | 任意 **OpenAI 兼容 API**（DeepSeek / OpenAI / 硅基流动 / OpenRouter…），任意环境可用 | 按量计费 |

```bash
cp .env.example .env

# 使用本机 Claude 订阅
LLM_PROVIDER="claude-cli"

# 或使用 OpenAI 兼容 API
LLM_PROVIDER="api"
LLM_BASE_URL="https://api.deepseek.com"
LLM_API_KEY="sk-..."
LLM_MODEL="deepseek-chat"
```

`.env` 已被 Git 忽略；`llm.config.json` 只保存环境变量映射，不再保存密钥。

## 🐳 Docker 运行

Docker 使用 Node + Python 多阶段构建：Node 阶段生成 React 生产资源，最终镜像仅保留 Python 后端和 `dist`。运行配置通过本地 `.env` 注入，`.env` 不会被复制进镜像。

```bash
# 构建镜像（可选参数为标签，默认 latest）
./scripts/docker-build.sh
./scripts/docker-build.sh v1.0.0

# 启动服务
docker compose up -d

# 查看运行日志 / 停止服务
docker compose logs -f
docker compose down
```

打开 `http://localhost:8793/news`（产业资讯）或 `http://localhost:8793/analysis`（产业分析）。Compose 会读取 `.env`，并使用 Docker 命名卷持久化生成的 `data.js`。容器启动后会立即刷新一次，此后每 6 小时自动更新。可通过 `APP_PORT=8080 docker compose up -d` 修改宿主机端口。

生产部署时请在 `.env` 设置公开域名，例如 `PUBLIC_BASE_URL=https://news.example.com`。服务会据此生成各路由的 canonical、Open Graph、JSON-LD、`robots.txt` 和 `sitemap.xml`；根路径会永久重定向到 `/news`。

## 🌐 覆盖赛道与信息源

12 大赛道、108 个精选源，**英文权威媒体与中文垂直媒体并重**，例如：

- **AI/大模型**：OpenAI · Google Research · Hugging Face · 量子位 · 机器之心 · 智东西 · MIT Tech Review
- **半导体/芯片**：DIGITIMES · SemiAnalysis · IEEE Spectrum · EE Times · Semiconductor Engineering
- **机器人 / 汽车 / 能源**：The Robot Report · IEEE Spectrum · Electrek · InsideEVs · CleanTechnica · 国际能源网
- **生物医药 / 航天 / 安全**：STAT · Endpoints · SpaceNews · NASA · Krebs on Security · BleepingComputer
- **科技 / 财经**：TechCrunch · The Verge · Ars Technica · 虎嗅 · 36氪 · 钛媒体 · FT · CNBC · 华尔街见闻 · 东方财富

> 完整清单见 `sources.json`。增删或修复信息源，仅需编辑该文件。

## ➕ 新增信息源 = 增加一行

在 `sources.json` 的 `sources` 数组中增加一行即可，无需改动代码：

```jsonc
{ "name": "某媒体", "hint": "ai", "type": "rss", "url": "https://example.com/feed" }
```

`hint` 为赛道标识（ai / semi / robot / auto / energy / bio / space / security / tech / consumer / macro / science）。
`fetch.recent_days` 控制时间窗口（默认 7 天）；`redline_keywords` 为合规过滤词表。

## 🗂️ 项目结构

```
investment-news/
├── Dockerfile          容器镜像定义
├── docker-compose.yml  容器启动与运行配置
├── .dockerignore       镜像构建忽略规则
├── index.html          Vite HTML 入口
├── src/                React + HeroUI 页面、类型与样式
├── package.json        前端依赖与 Vite 构建命令
├── vite.config.ts      Vite / Tailwind CSS 配置
├── server.py           MySQL API + dist 静态服务 + 每 6 小时后台自动刷新
├── database.py         MySQL 连接与数据查询
├── requirements.txt    Python 依赖
├── sources.json        108 源 / 12 赛道 / 合规词(调整源即编辑此文件)
├── .env                本地大模型配置与密钥(Git 忽略)
├── llm.config.json     环境变量映射(不含密钥)
├── data.js             生成的数据(fetch + digest 产出)
├── scripts/
│   ├── fetch.py        抓取 + 合规过滤 + 时间窗口(纯标准库)
│   ├── digest.py       调用大模型生成「今日要点」与翻译
│   ├── import_mysql.py 创建表并将 JS 数据导入 MySQL
│   ├── llm.py          统一大模型入口(claude-cli / api 双 provider)
│   ├── docker-build.sh Docker 镜像一键构建脚本
│   └── build_sources.py 重建并校验 sources.json(逐源 liveness 实测)
└── docs/screenshot.png
```

## 🧰 技术栈与依赖

- **Python 3.7+**，数据访问依赖 PyMySQL；抓取与摘要部分仍主要使用标准库。
- **React 19 + HeroUI 3 + Tailwind CSS 4 + Vite 8**，构建生产看板。
- **MySQL 5.7+/8.0+**，保存行业资讯、研判要点和公众号文章。
- **一个大模型**：本机 Claude Code 订阅（`claude-cli`，$0），或任意 OpenAI 兼容 API key。
- 需联网访问信息源（部分国际源可能需要代理）。

## ⚖️ 使用边界 / 免责声明

- 数据库凭据仅通过未纳入 Git 的 `.env` 或运行环境变量提供，禁止写入前端代码。
- **仅读取公开 RSS / 接口**，保持低频访问，并遵守各信息源的服务条款。
- **结论仅供参考**：本工具属**资讯聚合**，所呈现的是行业动向与领先信号，**不构成任何投资建议**；据此决策的后果由使用者自行承担。

本软件依 [MIT 许可](LICENSE) 以「现状」提供，不附带任何形式的担保。

## 🙋 作者

**Simon 林** · 抖音「Simon林」· 公众号「硅基世纪」

一个将全球行业资讯提炼为中文要点的本地看板。欢迎提交 PR 补充更多赛道与信息源。

## 📄 License

[MIT](LICENSE)
