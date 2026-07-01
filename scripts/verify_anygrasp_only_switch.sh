#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash "$ROOT_DIR/scripts/verify_anygrasp_active_defaults.sh"
bash "$ROOT_DIR/scripts/verify_anygrasp_only_active_path.sh"
bash "$ROOT_DIR/scripts/verify_anygrasp_require_current_joints.sh"
bash "$ROOT_DIR/scripts/verify_find_anygrasp_alignment_runs.sh"
bash "$ROOT_DIR/scripts/verify_print_latest_anygrasp_alignment_run.sh"
bash "$ROOT_DIR/scripts/verify_anygrasp_binding_config_helper.sh"
bash "$ROOT_DIR/scripts/verify_anygrasp_adapter_in_container.sh"
bash "$ROOT_DIR/scripts/verify_anygrasp_pipeline_outputs.sh"
bash "$ROOT_DIR/scripts/verify_analyze_anygrasp_output_dir.sh"
bash "$ROOT_DIR/scripts/verify_anygrasp_pick_attempt_modes.sh"

echo "AnyGrasp-only switch verification passed."
