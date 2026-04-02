#!/bin/bash

#####################################################################
# ECHA MCP 服务 CI/CD 部署启动脚本
#
# 功能：
#   - 首次部署：构建并启动服务（docker compose up -d --build）
#   - 已部署：重新构建并重启服务
#
# 端口：8005 (SSE)
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

log_info "当前工作目录: $SCRIPT_DIR"

#####################################################################
# 1. 检查必要文件
#####################################################################
if [ ! -f "docker-compose.yml" ]; then
    log_error "未找到 docker-compose.yml"
    exit 1
fi

#####################################################################
# 2. 检查基础镜像
#####################################################################
log_info "检查基础镜像..."
if docker image inspect python:3.11-slim > /dev/null 2>&1; then
    log_info "✓ python:3.11-slim 已存在"
else
    log_warn "拉取 python:3.11-slim..."
    docker pull python:3.11-slim || log_warn "拉取失败，build 时会自动重试"
fi

#####################################################################
# 3. 部署
#####################################################################
CONTAINER_EXISTS=$(docker ps -a --filter "name=echa-mcp-server" --format "{{.Names}}" 2>/dev/null || echo "")

if [ -z "$CONTAINER_EXISTS" ]; then
    log_info "首次部署，构建并启动..."
else
    log_info "检测到已有容器，停止旧版本..."
    docker compose down
fi

docker compose up -d --build

if [ $? -eq 0 ]; then
    log_info "✓ 服务启动成功！"
    sleep 5

    docker compose ps

    log_info "=========================================="
    log_info "ECHA MCP Server: http://localhost:8005/sse"
    log_info "=========================================="
else
    log_error "服务启动失败"
    exit 1
fi

#####################################################################
# 4. 健康检查
#####################################################################
log_info "健康检查..."
sleep 3

if curl -f -s http://localhost:8005/sse > /dev/null 2>&1; then
    log_info "✓ MCP Server (8005) 健康"
else
    log_warn "× 服务可能还在启动中..."
fi

#####################################################################
# 5. 清理
#####################################################################
docker image prune -f > /dev/null 2>&1 || true

log_info "=========================================="
log_info "部署完成！"
log_info "=========================================="

docker compose logs --tail=10

exit 0
