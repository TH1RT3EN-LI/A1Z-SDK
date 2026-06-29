#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/load_a1z_container_env.sh"

VISION_CONTAINER_NAME="${A1Z_VISION_CONTAINER_NAME:-a1z-vision-gpu}"
VISION_VENV_DIR="${A1Z_VISION_VENV_DIR:-/opt/venvs/a1z-vision}"
ANYGRASP_SDK_DIR="${A1Z_ANYGRASP_SDK_DIR:-/workspace/A1Z/vendor/vision/anygrasp_sdk}"
ANYGRASP_DETECTION_CKPT="${A1Z_ANYGRASP_DETECTION_CKPT:-/workspace/A1Z/runtime/models/anygrasp/checkpoint_detection.tar}"
ANYGRASP_TRACKING_CKPT="${A1Z_ANYGRASP_TRACKING_CKPT:-/workspace/A1Z/runtime/models/anygrasp/checkpoint_tracking.tar}"
ANYGRASP_LICENSE_DIR="${A1Z_ANYGRASP_LICENSE_DIR:-/workspace/A1Z/runtime/licenses/anygrasp}"
ANYGRASP_IFCONFIG_SNAPSHOT="${A1Z_ANYGRASP_IFCONFIG_SNAPSHOT:-/workspace/A1Z/runtime/anygrasp/ifconfig.snapshot}"
HOST_UID="${A1Z_HOST_UID:-$(id -u)}"
HOST_GID="${A1Z_HOST_GID:-$(id -g)}"

"$ROOT_DIR/scripts/freeze_anygrasp_machine_fingerprint.sh" "${ANYGRASP_IFCONFIG_SNAPSHOT/#\/workspace\/A1Z/$ROOT_DIR}"

if [[ "$(docker inspect -f '{{.State.Running}}' "$VISION_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]]; then
  docker start "$VISION_CONTAINER_NAME" >/dev/null
fi

docker exec \
  -e A1Z_VISION_VENV_DIR="$VISION_VENV_DIR" \
  -e A1Z_ANYGRASP_SDK_DIR="$ANYGRASP_SDK_DIR" \
  -e A1Z_ANYGRASP_DETECTION_CKPT="$ANYGRASP_DETECTION_CKPT" \
  -e A1Z_ANYGRASP_TRACKING_CKPT="$ANYGRASP_TRACKING_CKPT" \
  -e A1Z_ANYGRASP_LICENSE_DIR="$ANYGRASP_LICENSE_DIR" \
  -e A1Z_ANYGRASP_IFCONFIG_SNAPSHOT="$ANYGRASP_IFCONFIG_SNAPSHOT" \
  -e A1Z_HOST_UID="$HOST_UID" \
  -e A1Z_HOST_GID="$HOST_GID" \
  "$VISION_CONTAINER_NAME" \
  bash -lc '
    set -euo pipefail
    source "$A1Z_VISION_VENV_DIR/bin/activate"

    if [[ -f "$A1Z_ANYGRASP_IFCONFIG_SNAPSHOT" ]]; then
      tmp_anygrasp_bin="/tmp/a1z-anygrasp-bin-$(id -u)"
      rm -rf "$tmp_anygrasp_bin"
      mkdir -p "$tmp_anygrasp_bin"
      cat >"$tmp_anygrasp_bin/ifconfig" <<EOF
#!/usr/bin/env bash
cat "$A1Z_ANYGRASP_IFCONFIG_SNAPSHOT"
EOF
      chmod +x "$tmp_anygrasp_bin/ifconfig"
      export PATH="$tmp_anygrasp_bin:$PATH"
      echo "AnyGrasp fingerprint snapshot: $A1Z_ANYGRASP_IFCONFIG_SNAPSHOT"
    fi

    py_tag="$(python - <<'"'"'PY'"'"'
import sys
print(f"{sys.version_info.major}{sys.version_info.minor}")
PY
)"

    case "$py_tag" in
      310) py_so="cpython-310-x86_64-linux-gnu" ;;
      311) py_so="cpython-311-x86_64-linux-gnu" ;;
      312) py_so="cpython-312-x86_64-linux-gnu" ;;
      313) py_so="cpython-313-x86_64-linux-gnu" ;;
      314) py_so="cpython-314-x86_64-linux-gnu" ;;
      *)
        echo "Unsupported AnyGrasp Python ABI tag: $py_tag" >&2
        exit 1
        ;;
    esac

    detection_dir="$A1Z_ANYGRASP_SDK_DIR/grasp_detection"
    tracking_dir="$A1Z_ANYGRASP_SDK_DIR/grasp_tracking"
    license_reg_dir="$A1Z_ANYGRASP_SDK_DIR/license_registration"
    feature_id_path="/workspace/A1Z/runtime/models/anygrasp/feature_id.txt"

    mkdir -p "$detection_dir/log" "$tracking_dir/log" /workspace/A1Z/runtime/models/anygrasp

    cp "$detection_dir/gsnet_versions/gsnet.$py_so.so" "$detection_dir/gsnet.so"
    cp "$tracking_dir/tracker_versions/tracker.$py_so.so" "$tracking_dir/tracker.so"

    if [[ -d "$license_reg_dir/lib_cxx_versions" ]]; then
      cp "$license_reg_dir/lib_cxx_versions/lib_cxx.$py_so.so" "$detection_dir/lib_cxx.so"
      cp "$license_reg_dir/lib_cxx_versions/lib_cxx.$py_so.so" "$tracking_dir/lib_cxx.so"
      cp "$license_reg_dir/lib_cxx_versions/lib_cxx.$py_so.so" "$license_reg_dir/lib_cxx.so"
    fi

    if [[ -f "$A1Z_ANYGRASP_DETECTION_CKPT" ]]; then
      ln -sfn "$A1Z_ANYGRASP_DETECTION_CKPT" "$detection_dir/log/checkpoint_detection.tar"
    else
      echo "Missing AnyGrasp detection checkpoint: $A1Z_ANYGRASP_DETECTION_CKPT"
    fi

    if [[ -f "$A1Z_ANYGRASP_TRACKING_CKPT" ]]; then
      ln -sfn "$A1Z_ANYGRASP_TRACKING_CKPT" "$tracking_dir/log/checkpoint_tracking.tar"
    else
      echo "Missing AnyGrasp tracking checkpoint: $A1Z_ANYGRASP_TRACKING_CKPT"
    fi

    if [[ -d "$A1Z_ANYGRASP_LICENSE_DIR" ]]; then
      rm -rf "$detection_dir/license" "$tracking_dir/license" "$license_reg_dir/license"
      ln -s "$A1Z_ANYGRASP_LICENSE_DIR" "$detection_dir/license"
      ln -s "$A1Z_ANYGRASP_LICENSE_DIR" "$tracking_dir/license"
      ln -s "$A1Z_ANYGRASP_LICENSE_DIR" "$license_reg_dir/license"

      if [[ -x "$license_reg_dir/license_checker" ]]; then
        "$license_reg_dir/license_checker" -c "$license_reg_dir/license/licenseCfg.json" \
          | tee /workspace/A1Z/runtime/models/anygrasp/license_check.txt
      else
        echo "AnyGrasp license directory linked: $A1Z_ANYGRASP_LICENSE_DIR" \
          | tee /workspace/A1Z/runtime/models/anygrasp/license_check.txt
      fi
    else
      echo "AnyGrasp license directory not found yet: $A1Z_ANYGRASP_LICENSE_DIR"
    fi

    python - <<'"'"'PY'"'"'
import os
import sys

sdk_dir = "/workspace/A1Z/vendor/vision/anygrasp_sdk"
feature_id_path = "/workspace/A1Z/runtime/models/anygrasp/feature_id.txt"
sys.path.insert(0, os.path.join(sdk_dir, "grasp_detection"))
sys.path.insert(0, os.path.join(sdk_dir, "grasp_tracking"))

import gsnet  # noqa: F401
import tracker  # noqa: F401

feature_id = None
if hasattr(gsnet, "get_feature_id"):
    feature_id = gsnet.get_feature_id()
    with open(feature_id_path, "w", encoding="utf-8") as f:
        f.write(f"{feature_id}\n")
    print(f"AnyGrasp feature id: {feature_id}")
elif os.path.exists(os.path.join(sdk_dir, "license_registration", "license_checker")):
    print("AnyGrasp runtime imported, but feature id still requires legacy license_checker.")
else:
    print("AnyGrasp runtime imported, but this build does not expose get_feature_id().")

print("AnyGrasp runtime binaries imported successfully.")
PY

    if [[ ! -f "$feature_id_path" && -x "$license_reg_dir/license_checker" ]]; then
      "$license_reg_dir/license_checker" -f | tee "$feature_id_path"
    fi

    chown -R "$A1Z_HOST_UID:$A1Z_HOST_GID" \
      /workspace/A1Z/runtime/models/anygrasp \
      /workspace/A1Z/runtime/licenses/anygrasp \
      /workspace/A1Z/runtime/anygrasp
  '
