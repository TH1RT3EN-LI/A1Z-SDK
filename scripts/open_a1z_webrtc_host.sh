#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_env.sh"

SERVER_IP="${A1Z_SERVER_IP:-10.66.0.11}"
CLIENT_APP="${A1Z_WEBRTC_CLIENT_APP:-}"
LAUNCH_CLIENT="${A1Z_WEBRTC_LAUNCH_CLIENT:-auto}"
WEBRTC_SIGNAL_PORT="${A1Z_WEBRTC_SIGNAL_PORT:-49100}"
WEBRTC_STREAM_PORT="${A1Z_WEBRTC_STREAM_PORT:-47998}"
RESTART_ARG=()
CLIENT_PREFER_X11="${A1Z_WEBRTC_CLIENT_PREFER_X11:-1}"

detect_display() {
  if [[ -n "${DISPLAY:-}" ]]; then
    printf '%s\n' "$DISPLAY"
    return 0
  fi
  if [[ -n "${GNOME_SETUP_DISPLAY:-}" ]]; then
    case "$GNOME_SETUP_DISPLAY" in
      unix:/tmp/.X11-unix/X*)
        printf ':%s\n' "${GNOME_SETUP_DISPLAY##*X}"
        return 0
        ;;
      :*)
        printf '%s\n' "$GNOME_SETUP_DISPLAY"
        return 0
        ;;
    esac
  fi
  return 1
}

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
echo "  Signaling: $SERVER_IP:$WEBRTC_SIGNAL_PORT/tcp"
echo "  Media:     $SERVER_IP:$WEBRTC_STREAM_PORT/udp"
echo "  Client host field: $SERVER_IP"

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
CLIENT_DISPLAY="$(detect_display || true)"
CLIENT_ENV=()
CLIENT_UNSET_ENV=()
if [[ -n "$CLIENT_DISPLAY" ]]; then
  CLIENT_ENV+=(DISPLAY="$CLIENT_DISPLAY")
fi
if [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then
  CLIENT_ENV+=(XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR")
fi
if [[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]]; then
  CLIENT_ENV+=(DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS")
fi
if [[ -n "$CLIENT_DISPLAY" && "$CLIENT_PREFER_X11" == "1" ]]; then
  CLIENT_UNSET_ENV+=(-u WAYLAND_DISPLAY -u XDG_SESSION_TYPE -u ELECTRON_OZONE_PLATFORM_HINT)
elif [[ -z "$CLIENT_DISPLAY" && -n "${WAYLAND_DISPLAY:-}" ]]; then
  CLIENT_ENV+=(WAYLAND_DISPLAY="$WAYLAND_DISPLAY")
  if [[ -n "${XDG_SESSION_TYPE:-}" ]]; then
    CLIENT_ENV+=(XDG_SESSION_TYPE="$XDG_SESSION_TYPE")
  fi
fi

if [[ ${#CLIENT_ENV[@]} -gt 0 ]]; then
  nohup env "${CLIENT_UNSET_ENV[@]}" "${CLIENT_ENV[@]}" "$CLIENT_APP" --no-sandbox >/tmp/a1z-webrtc-client.log 2>&1 &
else
  nohup env "${CLIENT_UNSET_ENV[@]}" "$CLIENT_APP" --no-sandbox >/tmp/a1z-webrtc-client.log 2>&1 &
fi
echo "Client log: /tmp/a1z-webrtc-client.log"
