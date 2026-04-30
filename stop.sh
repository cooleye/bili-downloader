#!/usr/bin/env bash
fuser -k 8899/tcp 2>/dev/null && echo "服务已停止" || echo "服务未运行"
