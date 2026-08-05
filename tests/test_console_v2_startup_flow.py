from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "console_v2" / "frontend"


def test_console_v2_exposes_environment_detection_and_deployment_selection() -> None:
    assistant = (FRONTEND / "src" / "components" / "StartupAssistant.tsx").read_text()
    preload = (FRONTEND / "electron" / "preload.cjs").read_text()
    main = (FRONTEND / "electron" / "main.mjs").read_text()

    assert 'type StartupStep = "environment" | "connection" | "service"' in assistant
    assert 'className="startup-environment-options"' in assistant
    assert "onDeploymentModeChange(option.value)" in assistant
    assert "desktop.inspectStartupEnvironments()" in assistant
    assert 'ipcRenderer.invoke("startup:inspect-environments")' in preload
    assert 'ipcMain.handle("startup:inspect-environments"' in main
    assert "A1Z_HOST_MISSING" in main
    assert 'dockerCode = "repair_required"' in main
    assert "legacyDevicePaths.join" in main
    assert "hasDynamicDeviceAccess" in main
    assert "检查 SocketCAN 通道" in assistant
    assert "六轴反馈将在启动服务后验证" in assistant
    assert 'runStartupCheckCommand("docker", ["info", "--format", "{{.ServerVersion}}"]' in main or (
        'runStartupCheckCommand("docker", [' in main
        and '"{{.ServerVersion}}"' in main
    )


def test_console_v2_starts_and_verifies_service_before_entering_control() -> None:
    assistant = (FRONTEND / "src" / "components" / "StartupAssistant.tsx").read_text()
    preload = (FRONTEND / "electron" / "preload.cjs").read_text()
    main = (FRONTEND / "electron" / "main.mjs").read_text()

    service_flow = assistant.split("const runControlService", 1)[1].split(
        "useEffect", 1
    )[0]
    assert "await desktop.startControlService(deploymentMode, parameters)" in service_flow
    assert service_flow.index("await desktop.startControlService") < service_flow.rindex(
        "onComplete();"
    )
    assert 'serviceState === "running"' in assistant
    assert '"启动并进入"' in assistant
    assert 'ipcRenderer.invoke("startup:start-control-service"' in preload
    assert 'ipcMain.handle("startup:start-control-service"' in main
    assert "await readRobotInfo(deploymentMode)" in main
    assert 'info.backend !== "socketcan"' in main
    assert "info.control_mode !== expectedMode" in main
    assert "Math.abs(actualGravityFactor - gravityFactor)" in main


def test_control_service_manager_supports_host_without_changing_docker_default() -> None:
    manager_path = ROOT / "scripts" / "manage_a1z_control_server.sh"
    manager = manager_path.read_text()

    assert 'SERVICE_DEPLOYMENT="${A1Z_SERVICE_DEPLOYMENT:-docker}"' in manager
    assert 'PYTHONPATH="$ROOT_DIR/vendor/GALAXEA-A1Z:$ROOT_DIR' in manager
    assert '"${A1Z_PYTHON:-python3}" "$ROOT_DIR/tools/a1zctl" serve' in manager
    assert "Host SocketCAN '$can_channel' must already be UP" in manager
    assert 'docker exec "$container_name" ip link set "$can_channel" up' in manager
    subprocess.run(["bash", "-n", str(manager_path)], check=True)


def test_real_container_creation_rejects_legacy_fixed_device_mappings() -> None:
    creator = (ROOT / "scripts" / "create_a1z_ros2_container.sh").read_text()

    assert 'EXISTING_DEVICES="$(docker inspect' in creator
    assert '"$EXISTING_DEVICES" != "null"' in creator
    assert "legacy fixed host device mappings" in creator
    assert "-v /dev:/dev" in creator
    assert '--device "$node:$node"' not in creator
