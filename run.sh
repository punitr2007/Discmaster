#!/usr/bin/env bash
# DiscMaster Linux Launcher

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 is required but not installed." >&2
    exit 1
fi

exec python3 "$SCRIPT_DIR/discmaster.py" "$@"
