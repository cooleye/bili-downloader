#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# 手动指定代理（取消注释并修改为实际地址）
# export YT_DLP_PROXY="http://127.0.0.1:7890"

# 如果没有手动指定代理，自动检测
if [ -z "$YT_DLP_PROXY" ] && [ -z "$HTTP_PROXY" ]; then
    PROXY_PORTS=(7890 7891 1080 7897)
    for host in 127.0.0.1 $(ip route 2>/dev/null | grep default | awk '{print $3}'); do
        for port in "${PROXY_PORTS[@]}"; do
            if timeout 1 bash -c "echo > /dev/tcp/$host/$port" 2>/dev/null; then
                export YT_DLP_PROXY="http://$host:$port"
                break
            fi
        done
        [ -n "$YT_DLP_PROXY" ] && break
    done
fi

# 显示代理状态
if [ -n "$YT_DLP_PROXY" ]; then
    echo "  代理: $YT_DLP_PROXY"
elif [ -n "$HTTP_PROXY" ]; then
    echo "  代理: $HTTP_PROXY"
else
    echo "  [警告] 未检测到代理，YouTube 可能无法访问"
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
