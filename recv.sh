#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR" || exit

MODE="${1}"
OUTPUT="${2}"

python3 code/Server.py \
    -mode "$MODE" \
    -port 12340 \
    -output "$OUTPUT" \
    -mss 2048
