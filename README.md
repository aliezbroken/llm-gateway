# LLM Gateway

> 迷你版 New API：在你自己的 vLLM（OpenAI 兼容上游）前加一层**网关 + 配额计费 + 管理面板**。
> A lightweight OpenAI-compatible gateway with token management, quota billing and a web dashboard - served as a single FastAPI process, no Nginx required.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Language](https://img.shields.io/badge/backend-Python%203.10+-orange.svg)
![Frontend](https://img.shields.io/badge/frontend-Vue3%20%2F%20Vite-green.svg)
![DB](https://img.shields.io/badge/db-SQLite-lightgrey.svg)

## ✨ 特色

- **OpenAI 兼容网关**：`/v1/*` 直接给客户端用（支持 SSE 流式、usage 自动统计、按模型倍率计费），客户端零改造。
- **令牌（API Key）**：`sk-` 密钥，支持额度上限、IP 白名单、并发上限；明文只展示一次，库中仅存哈希。
- **用户 & 配额**：管理员建用户、手动分发配额（带流水审计）；普通用户只能看/管自己的数据。
- **双层并发控制**：用户级 + 令牌级并发同时生效。
- **统计仪表盘**：请求数、Token 趋势、P50/P95/P99 延迟、按 模型/令牌/用户 分布；管理员可看总览或指定用户。
- **请求日志**：来源 IP / 模型 / tokens / 配额消耗 / 延迟 / 状态，多维过滤。
- **单进程部署**：FastAPI 同时托管前端静态页 + 管理面 ` /api/* ` + 网关面 `/v1/*`，**不需要 Nginx**，systemd 一个服务搞定。
- **安全默认**：JWT 密钥首次启动自动生成随机值；生产环境自动关闭 `/docs`、`/openapi.json`。

## 📁 目录结构

```
gateway/
├── docs/
│   ├── REQUIREMENTS.md      # 需求分析
│   ├── ARCHITECTURE.md      # 架构与模块分解（解耦设计/数据模型）
│   └── API.md               # API 设计（管理面 REST + OpenAI 兼容）
├── deploy/
│   ├── install.sh           # 一键部署脚本（Ubuntu 22.04，无 Nginx 依赖）
│   ├── gateway.service      # systemd unit
│   └── nginx-gateway.conf   # 【可选】仅需 80/443/HTTPS 时参考
├── server/                  # 后端 FastAPI（单实例：/v1 + /api + 前端托管）
│   ├── app/
│   │   ├── main.py          # 组装 App、启动钩子（建表/迁移/JWT密钥/健康检查/种子管理员）
│   │   ├── config.py        # Settings（DB、JWT、上游 URL、seed_admin_*）
│   │   ├── models/          # User / ApiToken / UsageLog / SystemSetting / QuotaLedger
│   │   ├── schemas/         # Pydantic 请求/响应模型
│   │   └── modules/         # auth / users / tokens / gateway / logs / stats / system
│   ├── requirements.txt
│   └── run.py               # 开发态启动
└── web/                     # 前端 Vue3 + Vite + Element Plus + ECharts
    └── src/
        ├── router/          # 路由 + admin/user 角色守卫
        ├── stores/          # Pinia（auth）
        ├── api/             # axios 封装（注入 JWT、统一错误）
        └── views/           # Login / Dashboard / Logs / Tokens / Users / Settings
```

## 🚀 快速开始（开发）

**后端**（Python 3.10+）：

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py                                        # 监听 0.0.0.0:8000
```

**前端**（Node 18+）：

```bash
cd web
npm install
npm run dev                                          # http://localhost:5173，/api 代理到 :8000
```

**测试**（pytest，自带 mock 上游，无需真实 vLLM）：

```bash
cd server
pip install -r requirements-dev.txt
python -m pytest                                     # tests/ 目录
```

首次启动自动建库并写入管理员：见下方【默认账号】。

## 🛠 部署（Ubuntu 22.04）

### 一键脚本

```bash
# 把项目传到目标机后：
sudo bash deploy/install.sh                                    # 默认端口 8000（冲突自动切 8001）
GW_PORT=8080 ADMIN_PASS=你的密码 UPSTREAM_URL=http://<vllm>:8000 sudo bash deploy/install.sh
NODE_SKIP=1 sudo bash deploy/install.sh                        # 已带 dist 时跳过前端构建
```

脚本会自动：装系统依赖 → 建 venv 装后端依赖 → （可选）构建前端 → 生成随机 JWT 密钥 → 注册并启动 systemd。**无需 Nginx、无需额外进程。**

### 手动部署（单进程）

1. 后端：`python3 -m venv venv && ./venv/bin/pip install -r requirements.txt`
2. 前端：`cd web && npm install && npm run build`（产出 `web/dist`）
3. systemd：

   ```bash
   sudo useradd -r -s /usr/sbin/nologin -d /opt/llm-gateway llm-gateway
   sudo cp deploy/gateway.service /etc/systemd/system/llm-gateway.service
   sudo systemctl daemon-reload && sudo systemctl enable --now llm-gateway
   ```

4. （可选）需要 `80/443` 或 HTTPS 时再套一层 Nginx/Caddy，参考 `deploy/nginx-gateway.conf`。

### 对外使用

- 面板：`http://<host>:<port>/`
- 管理面：`http://<host>:<port>/api/*`（JWT）
- OpenAI 兼容：`http://<host>:<port>/v1/*`，`Authorization: Bearer sk-...`

## 🔑 默认账号

- 用户名：`admin`
- 密码：`admin123`（来自 `config.py` 的 `seed_admin_*`，**登录后立即修改**）

## ⚙️ 上游与计费

管理后台 → **系统设置**（仅 admin）：

- **上游 URL**：默认占位 `http://127.0.0.1:8000`；可用环境变量 `UPSTREAM_URL` 或后台运行时修改（存 `SystemSetting`，存库不落代码）。
- **模型倍率**：`{"model": {"prompt": x, "completion": y}}`，计费 `cost = round(prompt_tokens*x + completion_tokens*y)`。
- **健康检查**：每 30s 探测 `{upstream}/health`，失败不阻断转发。

## 🔒 安全说明

- JWT 密钥：首次启动自动生成随机值（`server/.env`），无需手工配置。
- `/docs`、`/openapi.json` 仅在 `debug=True` 时暴露，生产默认关闭。
- `sk-` 令牌库中仅存 SHA-256 哈希；记住创建时的明文。
- 默认还会写死一个种子管理员：**上线前必须修改 `SEED_ADMIN_PASSWORD` 或登录后改密**。
- 未内置登录失败限流：如公网暴露 `/api`，建议在前置层加限流或仅内网访问。

## ⚠️ 已知限制

- 并发闸门为**单进程内存计数**：多 worker/多实例需换 Redis（本项目默认单进程）。
- 计费与日志在请求完成后落库，极端崩溃可能丢失最后少量日志。
- **单上游**：只转发到一个 vLLM；无多渠道路由/故障自动切换。

## 🤝 贡献

- 提 Issue / PR 前建议先读 `docs/` 三份文档。
- 代码风格：后端按现有 router → service → model 分层，跨模块只走 service；前端走 `src/api/*` 封装。
- 提交前跑一次：后端 `python -m py_compile app/main.py`、前端 `npm run build`。

## 📄 License

[MIT](LICENSE)
