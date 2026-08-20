# API 设计（管理后台 REST + 对外 OpenAI 兼容）

Base URL：管理面 `/api`；对外面与 OpenAI 兼容（`/v1/*`）。

认证方式：
- 管理面：`Authorization: Bearer <JWT>`（登录 `/api/auth/login` 获取）
- 对外面：`Authorization: Bearer <sk-...>`

统一错误体：
```json
{ "error": { "message": "...", "type": "invalid_request_error", "code": 1010 } }
```
常用 HTTP 状态：`400 参数`、`401 未认证/令牌失效`、`403 无权限/IP拒绝`、`402 配额不足`、`404`、`429 并发超限`。

---

## A. 认证 auth

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 公开 | `{username,password}` → `{token, user}` |
| GET | `/api/auth/me` | 登录 | 当前用户信息（含配额余额） |
| PUT | `/api/auth/password` | 登录 | 修改自己密码 |

## B. 用户 users（仅 admin）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/users?page=&size=&keyword=&role=&status=` | 分页查询（支持搜索） |
| POST | `/api/users` | 新增用户 `{username,password,role,quota,remark}` |
| PUT | `/api/users/{id}` | 编辑（启停、备注、重置密码） |
| DELETE | `/api/users/{id}` | 删除（级联停用其令牌） |
| POST | `/api/users/{id}/quota` | 分发配额 `{delta, reason}`，扣减运行负数，记 `QuotaLedger` |
| GET | `/api/users/{id}/ledger` | 该用户配额流水 |

## C. 令牌 tokens（user 仅自己；admin 全量）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/tokens?userId=` | 列表（普通用户只见自己的，admin 可带 userId） |
| POST | `/api/tokens` | 创建 `{name, quota_limit?, allowed_ips?, max_concurrency?}` → 返回**一次**明文 `sk-xx` |
| PUT | `/api/tokens/{id}` | 修改配置/启停 |
| DELETE | `/api/tokens/{id}` | 删除 |
| GET | `/api/tokens/{id}/usage` | 该令牌累计消耗（配额上限使用情况） |

## D. 网关对外接口（OpenAI 兼容，令牌鉴权）

| 路径 | 说明 |
| --- | --- |
| `POST /v1/chat/completions` | 对话补全（支持 stream） |
| `POST /v1/completions` | 补全 |
| `POST /v1/embeddings` | 向量化（如有需要，透传） |
| `GET /v1/models` | 模型列表（透传上游，附加配额信息可选） |

错误示例：
- 401 `invalid_api_key`：令牌不存在/停用
- 403 `ip_not_allowed`：来源 IP 不在白名单
- 429 `concurrency_limit`：超过令牌并发上限
- 402 `insufficient_quota`：用户余额或令牌额度上限用尽

## E. 日志 logs

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/logs?page=&size=&from=&to=&userId=&tokenId=&model=&status=` | admin 全量；user 自动限定本人 | 请求日志分页 |
| GET | `/api/logs/{id}` | 同上 | 单条详情 |

## F. 统计 stats

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/stats/overview?from=&to=` | admin 全量/user 本人 | 卡片：请求数、总token、配额消耗、平均延迟 |
| GET | `/api/stats/trend?from=&to=&granularity=hour` | 同上 | 时间序列（请求量/token/配额） |
| GET | `/api/stats/latency?from=&to=` | 同上 | 响应时间 P50/P95/P99 (ms) |
| GET | `/api/stats/distribution?from=&to=&by=model|token|user` | 同上(维度限权) | 用量占比分布 |

## G. 系统 system（仅 admin）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/system/settings` | 获取配置（上游URL、模型倍率） |
| PUT | `/api/system/settings` | 更新配置 |
| GET | `/api/system/health` | 上游健康检查（在线/延迟/最近检查时间） |
