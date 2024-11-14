#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR" || exit

MODE="${1}"
INPUT="${2}"
LOSS="${3}"
DELAY="${4}"

echo "丢包率: $LOSS, 延迟: $DELAY"

sudo tc qdisc del dev veth1 root
sudo tc qdisc add dev veth1 root netem loss "$LOSS" delay "$DELAY"

python3 code/Client.py \
    -mode "$MODE" \
    -vegas False \
    -host 10.0.5.2 \
    -port 12340 \
    -input "$INPUT" \
    -mss 1400
