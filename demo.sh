#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR" || exit

# 下载客户端数据
cd code/data
wget https://dldir1v6.qq.com/weixin/Windows/WeChatSetup.exe
head -c 100M WeChatSetup.exe > 100M.send
head -c 20M WeChatSetup.exe > 20M.send
head -c 10M WeChatSetup.exe > 10M.send
head -c 5M WeChatSetup.exe > 5M.send
head -c 1M WeChatSetup.exe > 1M.send

