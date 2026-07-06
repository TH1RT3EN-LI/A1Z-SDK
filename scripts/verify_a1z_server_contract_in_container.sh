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
  /workspace/A1Z/tools/a1zctl \
  serve \
  --backend mock \
  --with-gripper \
  --tcp-port 0 >"$SERVER_LOG" 2>&1 &
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

grasp_status_before = call("grasp_status")
assert grasp_status_before["ok"], grasp_status_before
gs_before = grasp_status_before["data"]
assert gs_before["has_attached_object"] is False, gs_before
assert gs_before["grasp_state"] == "idle", gs_before
assert gs_before["attached_object_path"] is None, gs_before

grasp_contacts_before = call("grasp_contacts", {
    "target_prim_path": "/World/TrashSet/mock_target",
    "require_bilateral_contact": True,
})
assert grasp_contacts_before["ok"], grasp_contacts_before
gc_before = grasp_contacts_before["data"]
assert gc_before["target_body_path"] == "/World/TrashSet/mock_target", gc_before
assert gc_before["target_prim_path"] == "/World/TrashSet/mock_target", gc_before
assert gc_before["selected_body_contact_ready"] is False, gc_before
assert gc_before["snapshot_ok"] is False, gc_before
assert gc_before["left_contact_details"] == [], gc_before
assert gc_before["right_contact_details"] == [], gc_before

grasp_attach = call("grasp_attach", {
    "target_prim_path": "/World/TrashSet/mock_target",
    "timeout_s": 2.0,
    "contact_window_s": 0.15,
    "require_bilateral_contact": True,
})
assert grasp_attach["ok"], grasp_attach
gattach = grasp_attach["data"]
assert gattach["success"] is True, gattach
assert gattach["target_prim_path"] == "/World/TrashSet/mock_target", gattach
assert gattach["target_body_path"] == "/World/TrashSet/mock_target", gattach
assert gattach["attached_object_path"] == "/World/TrashSet/mock_target", gattach
assert gattach["attachment_joint_path"] is None, gattach
cs = gattach["contact_summary"]
assert cs["target_body_path"] == "/World/TrashSet/mock_target", cs
assert cs["chosen_body_path"] == "/World/TrashSet/mock_target", cs
assert cs["selected_body_contact_ready"] is True, cs
assert cs["ground_contact_present"] is False, cs
for legacy_key in [
    "proximity_summary",
    "used_proximity_shell",
    "sensor_contact_summary",
    "sensor_contact_match",
    "left_has_target_proximity",
    "right_has_target_proximity",
    "bilateral_shell_ready",
]:
    assert legacy_key not in cs, (legacy_key, cs)

grasp_status_after = call("grasp_status")
assert grasp_status_after["ok"], grasp_status_after
gs_after = grasp_status_after["data"]
assert gs_after["has_attached_object"] is True, gs_after
assert gs_after["attached_object_path"] == "/World/TrashSet/mock_target", gs_after
assert gs_after["target_prim_path"] == "/World/TrashSet/mock_target", gs_after
assert gs_after["target_body_path"] == "/World/TrashSet/mock_target", gs_after
assert gs_after["grasp_state"] == "attached", gs_after

grasp_release = call("grasp_release", {"open_gripper": True, "timeout_s": 2.0})
assert grasp_release["ok"], grasp_release
grelease = grasp_release["data"]
assert grelease["success"] is True, grelease
assert grelease["released"] is True, grelease
assert grelease["attached_object_path"] is None, grelease

grasp_status_final = call("grasp_status")
assert grasp_status_final["ok"], grasp_status_final
gs_final = grasp_status_final["data"]
assert gs_final["has_attached_object"] is False, gs_final
assert gs_final["attached_object_path"] is None, gs_final
assert gs_final["grasp_state"] == "idle", gs_final

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
