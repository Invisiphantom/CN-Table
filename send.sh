#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR" || exit

MODE="${1}"
INPUT="${2}"
LOSS="${3}"

python3 code/Client.py \
    -mode "$MODE" \
    -vegas False \
    -host 127.0.0.1 \
    -port 12340 \
    -input "$INPUT" \
    -mss 1400 
