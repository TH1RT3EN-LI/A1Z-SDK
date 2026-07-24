#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"
VISION_IMAGE_TAG="${A1Z_VISION_IMAGE_TAG:-a1z-vision-gpu:local}"
AUTO_REPAIR_MOUNT="${A1Z_VISION_AUTO_REPAIR_MOUNT:-1}"
WORKSPACE_DESTINATION="/workspace/A1Z"

expected_source="$(readlink -f "$ROOT_DIR")"

if ! docker inspect "$VISION_CONTAINER_NAME" >/dev/null 2>&1; then
  echo "Vision container does not exist; creating $VISION_CONTAINER_NAME" >&2
  "$ROOT_DIR/scripts/create_a1z_vision_gpu_container.sh"
fi

actual_source="$(
  docker inspect \
    --format '{{range .Mounts}}{{if eq .Destination "/workspace/A1Z"}}{{.Source}}{{end}}{{end}}' \
    "$VISION_CONTAINER_NAME"
)"
if [[ -n "$actual_source" ]]; then
  actual_source="$(readlink -f "$actual_source" 2>/dev/null || printf '%s' "$actual_source")"
fi

if [[ "$actual_source" != "$expected_source" ]]; then
  if [[ "$AUTO_REPAIR_MOUNT" != "1" ]]; then
    echo "error: $VISION_CONTAINER_NAME mounts '$actual_source' at $WORKSPACE_DESTINATION;" >&2
    echo "       current project requires '$expected_source'." >&2
    echo "       Set A1Z_VISION_AUTO_REPAIR_MOUNT=1 to preserve and repair the container." >&2
    exit 5
  fi

  repair_id="$(date +%Y%m%d_%H%M%S)"
  backup_name="${VISION_CONTAINER_NAME}-workspace-backup-${repair_id}"
  snapshot_image="${VISION_IMAGE_TAG%:*}:workspace-repair-${repair_id}"
  was_running="$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME")"

  echo "Repairing stale vision workspace mount:" >&2
  echo "  old: ${actual_source:-<missing>} -> $WORKSPACE_DESTINATION" >&2
  echo "  new: $expected_source -> $WORKSPACE_DESTINATION" >&2
  echo "Preserving installed environment as image $snapshot_image and container $backup_name" >&2

  docker commit "$VISION_CONTAINER_NAME" "$snapshot_image" >/dev/null
  if [[ "$was_running" == "true" ]]; then
    docker stop "$VISION_CONTAINER_NAME" >/dev/null
  fi
  docker rename "$VISION_CONTAINER_NAME" "$backup_name"

  rollback() {
    docker rm -f "$VISION_CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rename "$backup_name" "$VISION_CONTAINER_NAME" >/dev/null 2>&1 || true
    if [[ "$was_running" == "true" ]]; then
      docker start "$VISION_CONTAINER_NAME" >/dev/null 2>&1 || true
    fi
  }
  trap rollback ERR

  docker create \
    --name "$VISION_CONTAINER_NAME" \
    --gpus all \
    --ipc host \
    --network host \
    -v "$expected_source:$WORKSPACE_DESTINATION" \
    -w "$WORKSPACE_DESTINATION" \
    "$snapshot_image" \
    bash -lc "sleep infinity" >/dev/null
  docker start "$VISION_CONTAINER_NAME" >/dev/null
  trap - ERR
elif [[ "$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME")" != "true" ]]; then
  docker start "$VISION_CONTAINER_NAME" >/dev/null
fi

if ! docker exec "$VISION_CONTAINER_NAME" \
  test -f "$WORKSPACE_DESTINATION/scripts/run_target_mask_pipeline.py"; then
  echo "error: $VISION_CONTAINER_NAME cannot read the current A1Z workspace at $WORKSPACE_DESTINATION" >&2
  exit 5
fi

echo "Vision container ready: $VISION_CONTAINER_NAME ($expected_source -> $WORKSPACE_DESTINATION)"
