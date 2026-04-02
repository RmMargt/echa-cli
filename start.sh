#!/bin/bash

#####################################################################
# ECHA MCP 服务部署启动脚本（venv + systemd）
#
# 端口：7082 (SSE)
# 部署目录：/home/www/echa_mcp
#####################################################################

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE_NAME="echa-mcp"
VENV_DIR="$SCRIPT_DIR/.venv"

log_info "当前工作目录: $SCRIPT_DIR"

#####################################################################
# 1. 创建/更新 venv 并安装依赖
#####################################################################
if [ ! -d "$VENV_DIR" ]; then
    log_info "创建 Python 虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi

log_info "安装/更新依赖..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -e .

#####################################################################
# 2. 安装 systemd 服务
#####################################################################
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

log_info "配置 systemd 服务..."
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=ECHA MCP Server (SSE on port 7082)
After=network.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
ExecStart=$VENV_DIR/bin/python -m echa_mcp.server
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

#####################################################################
# 3. 重启服务
#####################################################################
log_info "重启 $SERVICE_NAME 服务..."
systemctl restart "$SERVICE_NAME"
systemctl enable "$SERVICE_NAME" 2>/dev/null || true

sleep 3

#####################################################################
# 4. 健康检查
#####################################################################
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log_info "✓ $SERVICE_NAME 运行中"
else
    log_error "× $SERVICE_NAME 启动失败"
    journalctl -u "$SERVICE_NAME" --no-pager -n 20
    exit 1
fi

log_info "=========================================="
log_info "ECHA MCP Server: http://localhost:7082/sse"
log_info "=========================================="
log_info "查看日志: journalctl -u $SERVICE_NAME -f"
log_info "部署完成！"

exit 0
