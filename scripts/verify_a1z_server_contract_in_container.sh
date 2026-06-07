#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
VERIFY_SOCKET_PATH="${A1Z_VERIFY_SERVER_SOCKET_PATH:-/tmp/a1z-server-contract.sock}"
SERVER_LOG="$(mktemp)"
SERVER_PID=""

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

echo "Starting mock A1Z server contract verification..."
A1Z_BACKEND=mock \
A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" \
  "$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" \
  /workspace/A1Z/vendor/GALAXEA-A1Z/tools/a1zctl \
  serve \
  --backend mock \
  --with-gripper >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 40); do
  if A1Z_BACKEND=mock A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" \
    "$ROOT_DIR/scripts/a1zctl_in_container.sh" --json info >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if ! A1Z_BACKEND=mock A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" \
  "$ROOT_DIR/scripts/a1zctl_in_container.sh" --json info >/dev/null 2>&1; then
  echo "Mock contract server did not become ready."
  cat "$SERVER_LOG"
  exit 1
fi

A1Z_BACKEND=mock A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" \
  "$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c '
import json
import os
import socket

SOCKET_PATH = os.environ["A1Z_SOCKET_PATH"]

def call(cmd, args=None):
    payload = json.dumps({"cmd": cmd, "args": args or {}}) + "\n"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(30.0)
    sock.connect(SOCKET_PATH)
    sock.sendall(payload.encode())
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    sock.close()
    return json.loads(data.split(b"\n", 1)[0].decode())

info = call("info")
assert info["ok"], info
idata = info["data"]
assert idata["backend"] == "mock", idata
assert idata["control_mode"] == "position_hold", idata
assert idata["gripper_range"] == [0.0, 1.0], idata

bad = call("command", {})
assert (not bad["ok"]) and "command requires '\''joints'\''" in bad["error"], bad

bad_gripper = call("gripper", {"value": 1.5})
assert (not bad_gripper["ok"]) and "value must be in [0.0, 1.0]" in bad_gripper["error"], bad_gripper

move = call("move", {"preset": "ready", "speed": 1.2})
assert move["ok"], move

command = call("command", {"joints": [5, 15, -20, 0, 10, 5], "gripper": 0.6})
assert command["ok"], command
assert abs(command["data"]["gripper"] - 0.6) <= 1e-9, command

status = call("status")
assert status["ok"], status
sdata = status["data"]
assert len(sdata["pos_deg"]) == 6, sdata
assert len(sdata["vel_rad_s"]) == 6, sdata
assert len(sdata["torque_nm"]) == 6, sdata
assert abs(sdata["gripper"] - 0.6) <= 1e-6, sdata

unknown = call("does_not_exist")
assert (not unknown["ok"]) and "Unknown command" in unknown["error"], unknown

stop = call("stop")
assert stop["ok"], stop

print("server contract verification passed")
'

for _ in $(seq 1 20); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    break
  fi
  sleep 0.2
done

wait "$SERVER_PID" 2>/dev/null || true
SERVER_PID=""

echo "A1Z server contract verification passed."
