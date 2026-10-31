#!/bin/bash
# smzdm 一键部署脚本（幂等：已配置则不覆盖 config.txt）
set -e
mkdir -p /opt/smzdm
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -f "$SCRIPT_DIR/smzdm_wecom_pusher.py" /opt/smzdm/
cp -f "$SCRIPT_DIR/keywords.txt" /opt/smzdm/
if [ ! -f /opt/smzdm/config.txt ]; then
  cp -f "$SCRIPT_DIR/config.txt" /opt/smzdm/config.txt
  echo "已创建 /opt/smzdm/config.txt（占位符）。请先填写三项，再重跑本脚本启动。"
  exit 0
fi
# 启动（先停旧进程）
pkill -f smzdm_wecom_pusher.py 2>/dev/null || true
sleep 1
cd /opt/smzdm
nohup python3 smzdm_wecom_pusher.py > smzdm.log 2>&1 &
echo "smzdm 监控已启动。查看日志: tail -f /opt/smzdm/smzdm.log"
