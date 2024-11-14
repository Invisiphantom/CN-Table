#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR" || exit

MODE="${1}"   # 传输模式 (匹配send.sh)
OUTPUT="${2}" # 输出文件

# 示例用法: ./recv.sh GBN data/10M.recv
# 示例用法: ./recv.sh SR  data/100M.recv

python3 code/Server.py \
    -mode "$MODE" \
    -port 12340 \
    -output "$OUTPUT" \
    -mss 2048
