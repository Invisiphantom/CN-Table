#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR" || exit

MODE="${1}"
INPUT="${2}"
LOSS="${3}"
DELAY="${4}"


sudo tc qdisc del dev lo root
sudo tc qdisc add dev lo root netem loss "$LOSS" delay "$DELAY"
sudo tc qdisc show dev lo root

python3 code/Client.py \
    -mode "$MODE" \
    -vegas True \
    -host 127.0.0.1 \
    -port 12340 \
    -input "$INPUT" \
    -mss 1400
