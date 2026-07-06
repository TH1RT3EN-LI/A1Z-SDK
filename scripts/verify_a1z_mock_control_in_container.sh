#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
SERVER_LOG="$(mktemp)"
SERVER_PID=""
VERIFY_SOCKET_PATH="${A1Z_VERIFY_MOCK_SOCKET_PATH:-/tmp/a1z-mock-verify.sock}"

cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "rm -f '$VERIFY_SOCKET_PATH'" >/dev/null 2>&1 || true
  rm -f "$SERVER_LOG"
}

trap cleanup EXIT

docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "rm -f '$VERIFY_SOCKET_PATH'" >/dev/null 2>&1 || true

echo "Starting mock A1Z control server in container..."
A1Z_BACKEND=mock \
A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" \
  "$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" \
  /workspace/A1Z/tools/a1zctl \
  serve \
  --backend mock \
  --with-gripper >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 40); do
  if A1Z_BACKEND=mock A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" \
    "$ROOT_DIR/scripts/a1zctl_in_container.sh" info >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if ! A1Z_BACKEND=mock A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" \
  "$ROOT_DIR/scripts/a1zctl_in_container.sh" info >/dev/null 2>&1; then
  echo "Mock server did not become ready."
  cat "$SERVER_LOG"
  exit 1
fi

INFO_OUTPUT="$(A1Z_BACKEND=mock A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" "$ROOT_DIR/scripts/a1zctl_in_container.sh" info)"
STATUS_BEFORE="$(A1Z_BACKEND=mock A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" "$ROOT_DIR/scripts/a1zctl_in_container.sh" status)"
MOVE_OUTPUT="$(A1Z_BACKEND=mock A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" "$ROOT_DIR/scripts/a1zctl_in_container.sh" move --preset ready --speed 1.2)"
GRIPPER_OUTPUT="$(A1Z_BACKEND=mock A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" "$ROOT_DIR/scripts/a1zctl_in_container.sh" gripper 0.25)"
STATUS_AFTER="$(A1Z_BACKEND=mock A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" "$ROOT_DIR/scripts/a1zctl_in_container.sh" status)"
GRASP_ATTACH_OUTPUT="$(A1Z_BACKEND=mock A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" "$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c '
import json
import os
import socket

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.settimeout(30.0)
sock.connect(os.environ["A1Z_SOCKET_PATH"])
sock.sendall((json.dumps({
    "cmd": "grasp_attach",
    "args": {
        "target_prim_path": "/World/TrashSet/mock_target",
        "timeout_s": 2.0,
        "contact_window_s": 0.15,
        "require_bilateral_contact": True,
    },
}) + "\n").encode("utf-8"))
data = b""
while b"\n" not in data:
    chunk = sock.recv(4096)
    if not chunk:
        break
    data += chunk
sock.close()
print(data.split(b"\n", 1)[0].decode("utf-8"))
')"
GRASP_STATUS_OUTPUT="$(A1Z_BACKEND=mock A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" "$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c '
import json
import os
import socket

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.settimeout(30.0)
sock.connect(os.environ["A1Z_SOCKET_PATH"])
sock.sendall((json.dumps({"cmd": "grasp_status", "args": {}}) + "\n").encode("utf-8"))
data = b""
while b"\n" not in data:
    chunk = sock.recv(4096)
    if not chunk:
        break
    data += chunk
sock.close()
print(data.split(b"\n", 1)[0].decode("utf-8"))
')"
GRASP_RELEASE_OUTPUT="$(A1Z_BACKEND=mock A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" "$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c '
import json
import os
import socket

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.settimeout(30.0)
sock.connect(os.environ["A1Z_SOCKET_PATH"])
sock.sendall((json.dumps({"cmd": "grasp_release", "args": {"open_gripper": True, "timeout_s": 2.0}}) + "\n").encode("utf-8"))
data = b""
while b"\n" not in data:
    chunk = sock.recv(4096)
    if not chunk:
        break
    data += chunk
sock.close()
print(data.split(b"\n", 1)[0].decode("utf-8"))
')"
STOP_OUTPUT="$(A1Z_BACKEND=mock A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" "$ROOT_DIR/scripts/a1zctl_in_container.sh" stop)"

wait "$SERVER_PID"
SERVER_PID=""

echo "$INFO_OUTPUT"
echo
echo "$STATUS_BEFORE"
echo
echo "$MOVE_OUTPUT"
echo "$GRIPPER_OUTPUT"
echo
echo "$STATUS_AFTER"
echo
echo "$GRASP_ATTACH_OUTPUT"
echo
echo "$GRASP_STATUS_OUTPUT"
echo
echo "$GRASP_RELEASE_OUTPUT"
echo
echo "$STOP_OUTPUT"

grep -q "Backend:      mock" <<<"$INFO_OUTPUT"
grep -q "Gripper set to 0.25" <<<"$GRIPPER_OUTPUT"
grep -q "Gripper: 0.250" <<<"$STATUS_AFTER"
grep -q '"success": true' <<<"$GRASP_ATTACH_OUTPUT"
grep -q '"chosen_body_path": "/World/TrashSet/mock_target"' <<<"$GRASP_ATTACH_OUTPUT"
grep -q '"selected_body_contact_ready": true' <<<"$GRASP_ATTACH_OUTPUT"
grep -q '"ground_contact_present": false' <<<"$GRASP_ATTACH_OUTPUT"
grep -q '"has_attached_object": true' <<<"$GRASP_STATUS_OUTPUT"
grep -q '"grasp_state": "attached"' <<<"$GRASP_STATUS_OUTPUT"
grep -q '"released": true' <<<"$GRASP_RELEASE_OUTPUT"

echo "Mock SDK control verification passed."
