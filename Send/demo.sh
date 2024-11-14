#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR" || exit


python3 GBN_client.py \
    -host 127.0.0.1 \
    -port 12345 \
    -input data/send.gz \
    -mss 1400 \
    -window 1024 \
    -time 1.0 \
    -loss 0.00 \
    -corrupt 0.00
