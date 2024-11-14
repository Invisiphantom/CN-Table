#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR" || exit

# python -c "import requests; r = requests.get('https://dlcdn.apache.org/hadoop/common/hadoop-3.3.6/hadoop-3.3.6.tar.gz'); open('hadoop-3.3.6.tar.gz', 'wb').write(r.content); print('下载完成！')"

# 下载客户端数据
cd code/data
wget https://dldir1v6.qq.com/weixin/Windows/WeChatSetup.exe
head -c 100M WeChatSetup.exe > 100M.send
head -c 50M WeChatSetup.exe > 50M.send
head -c 20M WeChatSetup.exe > 20M.send
head -c 10M WeChatSetup.exe > 10M.send
head -c 5M WeChatSetup.exe > 5M.send
head -c 1M WeChatSetup.exe > 1M.send
head -c 500K WeChatSetup.exe > 500K.send
head -c 200K WeChatSetup.exe > 200K.send
head -c 100K WeChatSetup.exe > 100K.send
head -c 10K WeChatSetup.exe > 10K.send

