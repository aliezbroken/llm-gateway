# 架构与模块分解（Architecture）

## 1. 总体架构

```
客户端(OpenAI SDK / opencode)                     浏览器(管理员/普通用户)
        │ Bearer sk-xxx                                │ JWT
        ▼                                              ▼
   Gateway(FastAPI 单实例监听 :8000) ──► 上游 vLLM (UPSTREAM_URL)
        │            │  ▲
        │            │  └─ SQLite(配额/流水/日志)
        │            ├─ /v1/*   (对外网关面)
        │            ├─ /api/*  (管理面 REST + 前端静态页 web/dist 托管)
        │            └─ Everything in ONE process, NO nginx
```

两个流量面由同一进程提供，严格分离：
- **对外网关面**（OpenAI 兼容，`/v1/*`）：`/v1/chat/completions` 等，令牌鉴权 + 计费 + 转发
- **管理后台面**（`/api/*` + 前端静态托管）：JWT 鉴权，REST CRUD + 统计；`web/dist` 由 FastAPI 直接托管（`/` 与 SPA 回退），无需 Web 服务器

## 2. 技术选型

| 层 | 选型 | 理由 |
| --- | --- | --- |
| 后端 | Python 3.10 + FastAPI + uvicorn | asyncio 流式透传；类型化；生态成熟 |
| ORM | SQLAlchemy 2.0 + SQLite | 单文件零运维；后续可平滑切 MySQL |
| 配置 | pydantic-settings（环境变量 + `.env`） | 无状态配置 |
| 认证 | JWT(`pyjwt`或`python-jose`) + `bcrypt/passlib`；令牌 `hashlib.sha256` | 面板与 API 分离鉴权 |
| HTTP 上游 | `httpx` AsyncClient（流式） | 支持 SSE 流式转发 |
| 前端 | Vue3 + Vite + Element Plus + ECharts + Pinia + Vue Router | 管理面板主流组合 |

## 3. 后端模块划分（解耦设计）

依赖方向：**上层(router) → service → model/DB**；**模块间禁止相互 import router**，跨模块能力一律走 service 层。

```
server/app/
├── main.py              # 组装 App：注册路由、启动钩子（建表/健康检查任务/种子管理员）
│
├── core/                # 基础设施，被所有模块依赖
│   ├── config.py        # Settings(pydantic-settings)：DB路径、JWT密钥、上游URL、倍率
│   ├── db.py            # engine / SessionLocal / Base / get_db 依赖
│   ├── security.py      # 密码哈希、JWT 签发与校验、sk- 令牌生成与哈希
│   ├── deps.py          # 通用依赖：get_current_user(admin/user 校验)
│   └── errors.py        # 统一错误码与 HTTP 异常映射（401/403/402/429）
│
├── models/              # ORM 模型（纯数据，无逻辑）
│   ├── user.py          # User
│   ├── token.py         # ApiToken
│   ├── log.py           # UsageLog
│   └── system.py        # SystemSetting(kv)、QuotaLedger
│
├── schemas/             # Pydantic 请求/响应模型（每模块一个文件）
│
└── modules/
    ├── auth/            # 登录、获取当前用户；签发 JWT
    │   ├── router.py  service.py
    ├── users/           # 用户 CRUD、配额分发、启停（仅 admin）
    │   ├── router.py  service.py
    ├── tokens/          # 令牌 CRUD、校验（供 gateway 复用）、配额上限校验
    │   ├── router.py  service.py
    ├── gateway/         # ★ OpenAI 兼容代理：鉴权→限额→转发→usage→扣费→日志
    │   ├── router.py  service.py  upstream.py(httpx流式)  usage.py(SSE解析)
    ├── logs/            # 请求日志查询/过滤
    │   ├── router.py  service.py  repository.py(聚合SQL)
    ├── stats/           # 仪表盘聚合：概览卡、趋势、P50/P95/P99、维度分布
    │   ├── router.py  service.py
    └── system/          # 上游配置(kv)、模型倍率、健康检查(后台任务)、种子数据
        ├── router.py  service.py  health.py
```

### 模块间解耦规则
1. **router 不写业务**：仅参数校验 + 调 service + 返回 schema。
2. **service 不互相 import router**；跨模块调用只允许 `service`（例如 `gateway/service.py` 调 `tokens/service.py: consume/validate`、`logs/service.py: record`、`system/service.py: get_ratios`）。
3. **DB 层单一入口**：所有查询走 `models` + `db.get_db`，模块内 `repository` 封装聚合 SQL。
4. **配置集中**：上游地址、倍率只经 `system` 模块读写，gateway 只读。
5. **错误统一**：`errors.py` 定义错误码枚举，任何模块统一抛出。

## 4. 数据模型

```
User(id, username UNIQUE, password_hash, role[admin|user], status[active|disabled],
     quota INT, created_at, updated_at, remark)

ApiToken(id, user_id FK, name, key_hash UNIQUE, status[active|disabled],
     quota_limit INT NULL,   -- 令牌额度上限（总消耗上限，NULL/0=不限制）
     allowed_ips JSON,       -- IP 白名单（[]=不限制）
     max_concurrency INT,    -- 并发上限（0=不限制）
     created_at, last_used_at)

UsageLog(id, ts INDEX, user_id, token_id, token_name, client_ip, model,
     endpoint, prompt_tokens, completion_tokens, total_tokens,
     quota_cost INT, latency_ms INT, status[ok|rejected|upstream_error|quota_blocked|...],
     error_code, request_id)

SystemSetting(key PK, value TEXT)   -- upstream_url, model_ratios(JSON), ...

QuotaLedger(id, ts, user_id, operator_id, delta INT, balance_after INT,
     reason TEXT)                   -- 管理员手动分发配额审计
```

### 计费模型
- 每模型可配 `{prompt_ratio, completion_ratio}`，默认 `{1, 1}`。
- 单请求消耗：`cost = round(prompt_tokens * prompt_ratio + completion_tokens * completion_ratio)`。
- 扣费：`User.quota -= cost`；`ApiToken` 的 `quota_limit` 为硬顶——累计消耗（SUM UsageLog.quota_cost where token_id）超过时拒绝（402）。
- 流水：配额变动（管理员分发）记 `QuotaLedger`；每次计费记 `UsageLog`。

## 5. 网关请求时序（流式 SSE）

```
客户端 ──POST /v1/chat/completions (Bearer sk-…, stream=true)──► gateway
  1. 校验令牌(sk- 哈希→ApiToken active)          [tokens.service]
  2. IP 白名单校验(client_ip ∈ allowed_ips)        [tokens.service]
  3. 并发闸门(令牌 in-flight < max)                [gateway.limiter]
  4. 额度检查(user.quota>0，且未超令牌上限)          [billing]
  5. 组装上游请求：注入 stream_options.include_usage=true（若缺）
  6. httpx 流式转发上游；边转发边缓冲 SSE 分片
  7. 结束分片 [DONE] 携带 usage → 解析 prompt/completion tokens  [gateway.usage]
  8. 计算 quota_cost（含模型倍率）→ 扣 user.quota + 校验令牌上限
  9. 写入 UsageLog（含 latency_ms）                [logs.service]
  10. 释放并发闸门
向上游请求全程透传，客户端零改造；失败/拒绝时返回标准错误体。
```

非流式（`stream=false`）：读完整响应 JSON 解析 `usage` 后同样走 8/9/10。

## 6. 健康检查
- 后台周期任务（如 30s）`GET {upstream}/health`，结果写入内存 + `SystemSetting` 缓存。
- `/api/system/health` 暴露；管理端"系统"页展示上游在线/延迟/最近检查时间。
- 检查失败不阻断转发（转发仍直连上游，由超时报错）。

## 7. 前端模块划分

```
web/src/
├── main.js / App.vue
├── router/index.js        # 路由 + 角色守卫(admin/user) + 登录拦截
├── stores/                # Pinia: auth(用户/令牌/JWT)、app(全局)
├── api/                   # axios 封装：注入JWT、统一错误处理、模块化 API 函数
├── layouts/AdminLayout.vue# 侧边栏+顶栏框架（按角色渲染菜单）
└── views/
    ├── Login.vue
    ├── Dashboard.vue      # 仪表盘(图表)
    ├── Logs.vue           # 请求日志(过滤表格)
    ├── Tokens.vue         # 令牌管理
    ├── Users.vue          # 用户管理(admin)
    └── Settings.vue       # 上游配置/倍率/健康检查(admin)
```

前端与后端通过 `/api/*` 对接，开发期 Vite proxy 指向 `localhost:8000`；生产由 FastAPI 直接托管 `web/dist`（同一进程、同源），不需要 nginx。

## 8. 部署形态

```
单进程：uvicorn app.main:app --port 8000   (systemd: llm-gateway)
  ├─ /v1/*   对外 OpenAI 网关（令牌鉴权 + 计费 + 转发到 UPSTREAM_URL）
  ├─ /api/*  管理面 REST（JWT 鉴权）
  └─ /       前端静态页 web/dist（SPA 回退，无 nginx）
```

- 健康检查与并发闸门在单进程内天然成立（并发计数为内存态）。
- 端口冲突自动规避（部署脚本 8000 被占时切 8001）。
- 仅当需要 `80/443`（免端口号访问）或 HTTPS 时，可选在外部套一层 Nginx/Caddy（见 `deploy/nginx-gateway.conf` 参考，非必需）。

## 9. 已知边界（README 注明）
- 并发闸门为**单进程内存计数**：多 worker 或多实例需换 Redis（本需求不涉及）。
- 配额扣费与日志写入在请求完成后异步完成，极端崩溃可能丢失最后少量请求日志（影响可控）。
- 令牌 key 哈希存储，忘记即重建。
