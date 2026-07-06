#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"
CONTAINER_NAME="${ISAAC_SIM_CONTAINER_NAME:-isaac-sim-5-1-dev}"
VERIFY_SOCKET_PATH="${A1Z_VERIFY_SOCKET_PATH:-/tmp/a1z-isaac-verify.sock}"
WORLD_USD="${A1Z_WORLD_USD:-/workspace/A1Z/build/scenes/A1Z_G1Z_world.usd}"
SERVER_IP="${A1Z_SERVER_IP:-10.66.0.11}"
LOG_FILE="/workspace/A1Z/runtime/logs/isaac-a1z-verify.log"
STARTUP_SCRIPT="/workspace/A1Z/scripts/open_a1z_world_with_a1z_sdk.py"

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$CONTAINER_NAME" >/dev/null
fi

RUNNING_PROCS="$(
  docker exec -u ubuntu "$CONTAINER_NAME" bash -lc \
    "ps -ef | grep -E 'isaacsim.exp.full.streaming.kit|/isaac-sim/runheadless.sh' | grep -v grep || true"
)"

if [[ -n "$RUNNING_PROCS" ]]; then
  echo "Another Isaac Sim process is already running in $CONTAINER_NAME." >&2
  echo "Stop it before running verify_a1z_isaac_control_in_container.sh." >&2
  echo "$RUNNING_PROCS" >&2
  exit 1
fi

docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "rm -f '$VERIFY_SOCKET_PATH' '$LOG_FILE'"

VERIFY_PID="$(
  docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "
    export A1Z_WORLD_USD='$WORLD_USD'
    export A1Z_SOCKET_PATH='$VERIFY_SOCKET_PATH'
    export A1Z_WITH_GRIPPER='${A1Z_WITH_GRIPPER:-1}'
    export A1Z_ISAAC_ARTICULATION_ROOT='${A1Z_ISAAC_ARTICULATION_ROOT:-/World/A1Z_G1Z/Geometry}'
    export A1Z_ISAAC_CONTROL_FREQ_HZ='${A1Z_ISAAC_CONTROL_FREQ_HZ:-60}'
    nohup /isaac-sim/runheadless.sh \
      --/app/livestream/publicEndpointAddress='$SERVER_IP' \
      --exec '$STARTUP_SCRIPT' \
      >'$LOG_FILE' 2>&1 &
    echo \$!
  "
)"
KIT_VERIFY_PID="$(
  docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "
    for _ in \$(seq 1 40); do
      pid=\$(ps -o pid= --ppid '$VERIFY_PID' | awk 'NR==1 {print \$1}')
      if [[ -n \"\$pid\" ]]; then
        echo \"\$pid\"
        break
      fi
      sleep 0.5
    done
  "
)"

cleanup() {
  docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "
    if [[ -n '$KIT_VERIFY_PID' ]] && kill -0 '$KIT_VERIFY_PID' 2>/dev/null; then
      kill '$KIT_VERIFY_PID' 2>/dev/null || true
      wait '$KIT_VERIFY_PID' 2>/dev/null || true
    fi
    if [[ -n '$VERIFY_PID' ]] && kill -0 '$VERIFY_PID' 2>/dev/null; then
      kill '$VERIFY_PID' 2>/dev/null || true
      wait '$VERIFY_PID' 2>/dev/null || true
    fi
    rm -f '$VERIFY_SOCKET_PATH'
  " >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in $(seq 1 120); do
  if docker exec -u ubuntu "$CONTAINER_NAME" test -S "$VERIFY_SOCKET_PATH"; then
    break
  fi
  sleep 1
done

if ! docker exec -u ubuntu "$CONTAINER_NAME" test -S "$VERIFY_SOCKET_PATH"; then
  echo "Isaac verify socket did not appear: $VERIFY_SOCKET_PATH" >&2
  docker exec -u ubuntu "$CONTAINER_NAME" tail -n 80 "$LOG_FILE" >&2 || true
  exit 1
fi

A1Z_SOCKET_PATH="$VERIFY_SOCKET_PATH" "$ROOT_DIR/scripts/a1z_sdk_python_in_container.sh" -c '
import json
import socket

SOCKET_PATH = "'"$VERIFY_SOCKET_PATH"'"
READY = [0.0, 30.0, -30.0, 0.0, 45.0, 0.0]

def call(cmd, args=None):
    req = json.dumps({"cmd": cmd, "args": args or {}}) + "\n"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(120.0)
    sock.connect(SOCKET_PATH)
    sock.sendall(req.encode())
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    sock.close()
    resp = json.loads(data.split(b"\n", 1)[0].decode())
    if not resp.get("ok"):
        raise RuntimeError(resp.get("error", "unknown error"))
    return resp.get("data", {})

info = call("info")
if info.get("backend") != "isaacsim":
    raise RuntimeError(f"unexpected backend: {info}")

grasp_status_before = call("grasp_status")
if grasp_status_before.get("has_attached_object") is not False:
    raise RuntimeError(f"unexpected initial grasp status: {grasp_status_before}")
if grasp_status_before.get("grasp_state") != "idle":
    raise RuntimeError(f"unexpected initial grasp state: {grasp_status_before}")

call("move", {"preset": "ready", "speed": 0.7})
call("gripper", {"value": 0.25})
status = call("status")

pos_deg = status["pos_deg"]
for idx, (actual, target) in enumerate(zip(pos_deg, READY), start=1):
    if abs(actual - target) > 2.0:
        raise RuntimeError(f"joint J{idx} out of tolerance: actual={actual} target={target}")

gripper = status.get("gripper")
if gripper is None or abs(gripper - 0.25) > 0.15:
    raise RuntimeError(f"gripper out of tolerance: {gripper}")

attach = call("grasp_attach", {
    "target_prim_path": "",
    "timeout_s": 0.2,
    "contact_window_s": 0.05,
    "require_bilateral_contact": True,
})
required_top_keys = {
    "success",
    "target_prim_path",
    "target_body_path",
    "attached_object_path",
    "attachment_joint_path",
    "contact_summary",
    "failure_reason",
    "timing",
}
missing_top = required_top_keys.difference(attach.keys())
if missing_top:
    raise RuntimeError(f"attach response missing keys: {sorted(missing_top)} -> {attach}")
summary = attach["contact_summary"]
required_summary_keys = {
    "target_body_path",
    "chosen_body_path",
    "selected_body_contact_ready",
    "ground_contact_present",
    "left_has_selected_body_contact",
    "right_has_selected_body_contact",
}
missing_summary = required_summary_keys.difference(summary.keys())
if missing_summary:
    raise RuntimeError(f"attach summary missing keys: {sorted(missing_summary)} -> {summary}")
legacy_keys = [
    "proximity_summary",
    "used_proximity_shell",
    "sensor_contact_summary",
    "sensor_contact_match",
    "left_has_target_proximity",
    "right_has_target_proximity",
    "bilateral_shell_ready",
]
present_legacy = [key for key in legacy_keys if key in summary]
if present_legacy:
    raise RuntimeError(f"attach summary still contains legacy keys: {present_legacy} -> {summary}")

call("stop")
print("isaacsim control verification passed")
'

for _ in $(seq 1 30); do
  if ! docker exec -u ubuntu "$CONTAINER_NAME" bash -lc "kill -0 '${KIT_VERIFY_PID:-$VERIFY_PID}' 2>/dev/null"; then
    break
  fi
  sleep 1
done

echo "Isaac Sim backend verification passed."
echo "Log: $LOG_FILE"
