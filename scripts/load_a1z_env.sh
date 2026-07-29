#!/usr/bin/env bash

# Source common settings and one explicit device profile.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
A1Z_PROFILE_NAME="${A1Z_PROFILE:-sim}"

case "$A1Z_PROFILE_NAME" in
  sim|real) ;;
  *)
    echo "Unsupported A1Z_PROFILE='$A1Z_PROFILE_NAME' (expected sim or real)" >&2
    return 2 2>/dev/null || exit 2
    ;;
esac

load_env_file() {
  local env_file="$1"
  [[ -f "$env_file" ]] || {
    echo "Missing A1Z environment file: $env_file" >&2
    return 1
  }
  while IFS='=' read -r key value; do
    [[ -z "${key// }" ]] && continue
    [[ "$key" =~ ^[[:space:]]*# ]] && continue
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if [[ -z "${!key+x}" ]]; then
      export "$key=$value"
    fi
  done < "$env_file"
}

load_env_file "$ROOT_DIR/config/common.env"
load_env_file "${A1Z_ENV_FILE:-$ROOT_DIR/config/$A1Z_PROFILE_NAME.env}"
export A1Z_PROFILE="$A1Z_PROFILE_NAME"

if [[ "$A1Z_PROFILE" == "real" && (
  "${A1Z_BACKEND:-}" != "socketcan" || "${A1Z_CAMERA_SOURCE:-}" != "realsense"
) ]]; then
  echo "real profile requires A1Z_BACKEND=socketcan and A1Z_CAMERA_SOURCE=realsense" >&2
  return 2 2>/dev/null || exit 2
fi
if [[ "$A1Z_PROFILE" == "sim" && (
  "${A1Z_BACKEND:-}" != "isaacsim" || "${A1Z_CAMERA_SOURCE:-}" != "isaac"
) ]]; then
  echo "sim profile requires A1Z_BACKEND=isaacsim and A1Z_CAMERA_SOURCE=isaac" >&2
  return 2 2>/dev/null || exit 2
fi
