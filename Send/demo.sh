#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR" || exit

INPUT="data/send.gz"
# INPUT="data/send.jpg"

python3 GBN_client.py \
    -host 127.0.0.1 \
    -port 12345 \
    -input "$INPUT" \
    -mss 1400 \
    -window 64 \
    -loss 0.00 \
    -corrupt 0.00


# python3 SR_client.py \
#     -host 127.0.0.1 \
#     -port 12345 \
#     -input "$INPUT" \
#     -mss 1400 \
#     -window 64 \
#     -time 0.5 \
#     -loss 0.00 \
#     -corrupt 0.00
