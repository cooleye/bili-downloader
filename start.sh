#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# WSL2 gateway IP (Windows host)
GATEWAY=$(ip route | grep default | awk '{print $3}')
# Common proxy ports to try
PROXY_PORTS=(7891 7890 1080 7897 8080 8899)

# Set proxy if gateway found (WSL2 environment)
if [ -n "$GATEWAY" ]; then
    for port in "${PROXY_PORTS[@]}"; do
        if timeout 1 bash -c "echo > /dev/tcp/$GATEWAY/$port" 2>/dev/null; then
            export HTTP_PROXY="http://$GATEWAY:$port"
            export HTTPS_PROXY="http://$GATEWAY:$port"
            echo "  检测到代理: $GATEWAY:$port"
            break
        fi
    done
fi

# Get WSL2 IP for display
WSL_IP=$(ip addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "127.0.0.1")

echo "========================================"
echo "  Bilibili / YouTube 视频下载器"
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
