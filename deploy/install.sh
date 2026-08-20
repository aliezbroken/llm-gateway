#!/usr/bin/env bash
#
# LLM Gateway 一键部署脚本 (Ubuntu 20.04 / 22.04, amd64)
#
# 用法:
#   sudo bash deploy/install.sh                 # 默认安装到 /opt/llm-gateway, 端口 8000(冲突自动切8001)
#   GW_PORT=8000 sudo bash deploy/install.sh    # 指定端口
#   NODE_SKIP=1 sudo bash deploy/install.sh     # 跳过前端 node 安装/构建（已有 dist）
#
# 设计说明: 本项目是"请求转发网关"本身（接收请求并转发到上游 vLLM），
#   不需要独立的 nginx 反代 —— FastAPI 同时托管前端静态页面(web/dist)、
#   /v1 网关面与 /api 管理面，单进程单端口即可运行。
#
# 安装内容:
#   - Python3 venv + 后端依赖 (FastAPI/SQLAlchemy, 见 server/requirements.txt)
#   - Node.js 20 (NodeSource) + 前端构建 (vite build -> web/dist)
#   - systemd 服务 llm-gateway (uvicorn :$GW_PORT)
#   - SQLite 首次启动自动建库并创建管理员 admin/admin123 (部署后请立即修改)

set -euo pipefail

# ---------------- 配置 ----------------
APP_NAME="llm-gateway"
INSTALL_DIR="${INSTALL_DIR:-/opt/llm-gateway}"
GW_PORT="${GW_PORT:-8000}"                      # 默认 8000；若与现有服务冲突自动改用 8001
RUN_USER="${RUN_USER:-llm-gateway}"
RUN_GROUP="${RUN_GROUP:-llm-gateway}"
SYSTEMD_UNIT="/etc/systemd/system/${APP_NAME}.service"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin123}"            # 只用于首次建库，之后在后台改密
UPSTREAM_URL="${UPSTREAM_URL:-}"    # 必填示例: http://<vllm-ip>:8000；勿在脚本/仓库中写死真实地址

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_ROOT="$(dirname "$SCRIPT_DIR")"             # 项目根（含 server/ web/ 等）

log()  { echo -e "\033[1;32m[install]\033[0m $*"; }
warn() { echo -e "\033[1;33m[warn]\033[0m $*"; }
die()  { echo -e "\033[1;31m[error]\033[0m $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "请以 root 运行: sudo bash $0"

# ---------------- 0. 端口检查 ----------------
if ss -tlnp 2>/dev/null | grep -q ":$GW_PORT "; then
  if [ "$GW_PORT" = "8000" ]; then
    warn "端口 8000 已被占用（可能是现有的 vLLM nginx），自动改用 8001"
    GW_PORT=8001
  else
    die "端口 $GW_PORT 已被占用，请用 GW_PORT=<port> 重新指定"
  fi
fi
log "网关端口: $GW_PORT"

# ---------------- 1. 系统依赖 ----------------
export DEBIAN_FRONTEND=noninteractive
log "安装系统依赖 (python3/venv/curl)..."
apt-get update -y
apt-get install -y python3 python3-venv python3-pip curl git rsync

# ---------------- 2. Node.js (NodeSource 20 LTS) ----------------
if [ "${NODE_SKIP:-0}" = "1" ]; then
  warn "NODE_SKIP=1，跳过 node 安装与前端构建（请确保 INSTALL_DIR/web/dist 已存在）"
elif ! command -v node >/dev/null 2>&1 || [ "$(node -v 2>/dev/null | cut -d. -f1 | tr -d v)" -lt 18 ]; then
  log "安装 Node.js 20 (NodeSource)..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
else
  log "Node.js 已安装: $(node -v)"
fi

# ---------------- 3. 运行账号与目录 ----------------
log "创建运行账号 $RUN_USER 与目录 $INSTALL_DIR ..."
id "$RUN_USER" &>/dev/null || useradd -r -s /usr/sbin/nologin -m -d "$INSTALL_DIR" "$RUN_USER"
mkdir -p "$INSTALL_DIR"

log "复制项目文件 (保留已构建的 web/dist，排除 venv/node_modules/.git)..."
rsync -a --delete \
  --exclude 'server/.venv' --exclude 'web/node_modules' \
  --exclude '.git' --exclude '*.db' --exclude '__pycache__' \
  "$SRC_ROOT/" "$INSTALL_DIR/" 2>/dev/null || {
    # rsync 不可用时退化为 cp
    mkdir -p "$INSTALL_DIR"
    cp -r "$SRC_ROOT/server" "$SRC_ROOT/web" "$SRC_ROOT/deploy" "$SRC_ROOT/docs" "$SRC_ROOT/README.md" "$INSTALL_DIR/" 2>/dev/null || true
    rm -rf "$INSTALL_DIR/server/.venv" "$INSTALL_DIR/web/node_modules" "$INSTALL_DIR/server/gateway.db"
  }

# ---------------- 4. 后端虚拟环境 ----------------
log "创建 Python 虚拟环境并安装后端依赖..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip -q
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/server/requirements.txt" -q

# ---------------- 5. 配置文件 (.env) ----------------
log "生成 .env (随机 JWT secret, 上游 $UPSTREAM_URL)..."
JWT_SECRET="$(head -c 32 /dev/urandom | base64 | tr -d '=+/' | head -c 48)"
cat > "$INSTALL_DIR/server/.env" <<EOF
JWT_SECRET=$JWT_SECRET
SEED_ADMIN_USERNAME=$ADMIN_USER
SEED_ADMIN_PASSWORD=$ADMIN_PASS
EOF
if [ -n "$UPSTREAM_URL" ]; then
  echo "UPSTREAM_URL=$UPSTREAM_URL" >> "$INSTALL_DIR/server/.env"
fi

# ---------------- 6. 前端构建 ----------------
if [ "${NODE_SKIP:-0}" != "1" ] && command -v node >/dev/null 2>&1; then
  log "构建前端 (npm install + vite build)..."
  cd "$INSTALL_DIR/web"
  npm_config_yes=true npm install --no-audit --no-fund
  npm run build
  log "前端产物: $INSTALL_DIR/web/dist"
else
  warn "跳过前端构建，请确认 $INSTALL_DIR/web/dist 存在"
fi
[ -f "$INSTALL_DIR/web/dist/index.html" ] || warn "未发现前端产物 index.html！部署后 80 端口将无法打开面板"

# ---------------- 7. 权限 ----------------
chown -R "$RUN_USER":"$RUN_GROUP" "$INSTALL_DIR" 2>/dev/null || true
chmod -R g+rwX "$INSTALL_DIR"

# ---------------- 8. systemd 服务 ----------------
log "写入 systemd 单元 ($SYSTEMD_UNIT)..."
cat > "$SYSTEMD_UNIT" <<EOF
[Unit]
Description=LLM Gateway (FastAPI, /v1 OpenAI proxy + /api admin)
After=network.target

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_GROUP
WorkingDirectory=$INSTALL_DIR/server
Environment=PYTHONUNBUFFERED=1
ExecStart=$INSTALL_DIR/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port $GW_PORT
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only
PrivateDevices=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "$APP_NAME"

# ---------------- 9. 启动（单进程单端口，前端由 FastAPI 直接托管，无需 nginx） ----------------
log "启动 llm-gateway 服务 (端口 $GW_PORT)..."
systemctl restart "$APP_NAME"
sleep 3
systemctl --no-pager --lines=20 status "$APP_NAME" || true

# ---------------- 10. 自检 ----------------
log "健康检查:"
set +e
for i in 1 2 3 4 5; do
  if curl -fsS "http://127.0.0.1:$GW_PORT/api/health" >/dev/null 2>&1; then
    echo "  -> 后端 OK (http://127.0.0.1:$GW_PORT/api/health)"; break
  fi
  sleep 2
done
if [ -f "$INSTALL_DIR/web/dist/index.html" ]; then
  code="$(curl -fsS -o /dev/null -w '%{http_code}' "http://127.0.0.1:$GW_PORT/" 2>/dev/null || echo 'N/A')"
  echo "  -> 前端(SPA) HTTP $code (由网关直接托管)"
fi
set -e

# ---------------- 完成 ----------------
echo ""
echo "======================================================================"
echo " 安装完成！（单服务即可运行，无需 nginx）"
echo "  面板地址 : http://<本机IP>:$GW_PORT/          (前端，FastAPI 托管)"
echo "  API 入口 : http://<本机IP>:$GW_PORT/v1/       (OpenAI 兼容, Bearer sk-xxx)"
echo "  管理地址 : http://<本机IP>:$GW_PORT/api/      (管理面 REST)"
echo "  默认账号 : ${ADMIN_USER} / ${ADMIN_PASS}   <- 请立即登录后台修改密码"
echo "  端口     : $GW_PORT (systemd: llm-gateway)"
echo "  项目目录 : $INSTALL_DIR"
echo "  日志     : journalctl -u llm-gateway -f"
echo "  上游地址 : $UPSTREAM_URL (可在面板-系统设置修改)"
echo "  JWT密钥  : 已随机生成于 $INSTALL_DIR/server/.env"
echo "  如需 80/443 或 HTTPS: 可自行套一层 nginx/caddy，参考 deploy/nginx-gateway.conf"
echo "======================================================================"
