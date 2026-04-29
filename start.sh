#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# Get WSL2 IP
WSL_IP=$(ip addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "127.0.0.1")

echo "========================================"
echo "  Bilibili 视频下载器"
echo "========================================"
echo ""
echo "  Windows 访问地址:"
echo "  ->  http://localhost:8899"
echo "  ->  http://$WSL_IP:8899"
echo ""
echo "  按 Ctrl+C 停止服务"
echo "========================================"
echo ""

python3 main.py
