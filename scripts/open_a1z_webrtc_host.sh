#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

SERVER_IP="${A1Z_SERVER_IP:-10.66.0.11}"
CLIENT_APP="${A1Z_WEBRTC_CLIENT_APP:-}"
LAUNCH_CLIENT="${A1Z_WEBRTC_LAUNCH_CLIENT:-auto}"
RESTART_ARG=()

# WebRTC is the primary viewport path for this workspace. Enable viewport
# operations by default unless the caller explicitly disables them.
export A1Z_VIEWPORT_ENABLED="${A1Z_VIEWPORT_ENABLED:-1}"

usage() {
  cat <<'EOF'
Usage: ./scripts/open_a1z_webrtc_host.sh [--restart] [--client|--no-client] [server-ip]

Starts the single shared A1Z Isaac Sim WebRTC session. Local and remote viewers
connect to the same target:

  server-ip:49100  signaling
  server-ip:47998  media UDP

Options:
  --restart    Stop any existing stream first, then start a fresh one.
  --client     Launch A1Z_WEBRTC_CLIENT_APP after the stream is ready.
  --no-client  Only start/reuse the stream and print connection details.
  -h, --help   Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --restart)
      RESTART_ARG=(--restart)
      ;;
    --client)
      LAUNCH_CLIENT=1
      ;;
    --no-client)
      LAUNCH_CLIENT=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      SERVER_IP="$1"
      ;;
  esac
  shift
done

echo "Starting or reusing the shared A1Z Isaac Sim WebRTC session..."
echo "Server IP: $SERVER_IP"

"$ROOT_DIR/scripts/start_a1z_webrtc_streaming_host.sh" "${RESTART_ARG[@]}" "$SERVER_IP"

echo
echo "Use the same WebRTC target from local or remote clients:"
echo "  Server IP: $SERVER_IP"
echo "  Signaling: $SERVER_IP:49100/tcp"
echo "  Media:     $SERVER_IP:47998/udp"

if [[ "$LAUNCH_CLIENT" == "0" ]]; then
  exit 0
fi

if [[ -z "$CLIENT_APP" ]]; then
  if [[ "$LAUNCH_CLIENT" == "1" ]]; then
    echo "A1Z_WEBRTC_CLIENT_APP is not set, cannot launch a local client." >&2
    exit 1
  fi
  echo "Set A1Z_WEBRTC_CLIENT_APP=/path/to/isaacsim-webrtc-streaming-client.AppImage to auto-open a local client."
  exit 0
fi

if [[ ! -x "$CLIENT_APP" ]]; then
  echo "Configured A1Z_WEBRTC_CLIENT_APP is not executable: $CLIENT_APP" >&2
  exit 1
fi

echo "Launching local WebRTC client: $CLIENT_APP"
nohup "$CLIENT_APP" --no-sandbox >/tmp/a1z-webrtc-client.log 2>&1 &
echo "Client log: /tmp/a1z-webrtc-client.log"
