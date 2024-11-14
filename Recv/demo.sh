#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR" || exit

OUTPUT="data/recv.gz"
# OUTPUT="data/recv.jpg"

# python3 GBN_server.py \
#     -port 12345 \
#     -output "$OUTPUT" \
#     -mss 2048


python3 SR_server.py \
    -port 12345 \
    -output "$OUTPUT" \
    -mss 2048 \
    -window 2048