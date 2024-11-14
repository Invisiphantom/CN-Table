#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR" || exit

python3 GBN_server.py \
    -port 12345 \
    -output data/recv.gz \
    -mss 2048