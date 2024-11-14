#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR" || exit

MODE="${1}"
INPUT="${2}"

python3 code/Client.py \
    -mode "$MODE" \
    -host 127.0.0.1 \
    -port 12345 \
    -input "$INPUT" \
    -mss 1400 \
    -loss 0.00 \
    -corrupt 0.00
