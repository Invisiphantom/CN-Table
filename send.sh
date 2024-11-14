#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR" || exit

MODE="${1}"  # 传输模式
VEGAS="${2}" # 窗口是否基于延迟
INPUT="${3}" # 输入文件
LOSS="${4}"  # 丢包率
DELAY="${5}" # 延时

# 示例用法: ./send.sh GBN False data/10M.send  0.01 10ms
# 示例用法: ./send.sh SR  True  data/100M.send 0.001 1ms


# 本地模拟测试
# SERVER=127.0.0.1
sudo tc qdisc del dev lo root
sudo tc qdisc add dev lo root netem loss "$LOSS" delay "$DELAY"
sudo tc qdisc show dev lo root

# 真实服务器测试
SERVER=47.254.22.72


python3 code/Client.py \
-mode "$MODE" \
-vegas "$VEGAS" \
-host "$SERVER" \
-port 12340 \
-input "$INPUT" \
-mss 1400
