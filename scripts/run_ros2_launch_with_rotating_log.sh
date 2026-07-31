#!/usr/bin/env bash

set -euo pipefail

LOG_PATH="${1:?log path is required}"
MAX_BYTES="${2:-67108864}"
BACKUP_COUNT="${3:-3}"

cd /tmp
ros2 launch a1z_motion a1z_stack.launch.py 2>&1 |
  python3 /workspace/A1Z/scripts/rotate_stream_log.py \
    --path "$LOG_PATH" \
    --max-bytes "$MAX_BYTES" \
    --backup-count "$BACKUP_COUNT"
