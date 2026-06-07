# Scripts

当前只保留这套工作流真正需要的脚本，并按用途分成三类：用户入口、容器/环境入口、内部辅助。

## 1. 用户入口

这些是日常直接用的脚本。

- `verify_a1z_control_stack.sh`
  - 一次性跑 SDK / mock / server contract / Isaac / SocketCAN preflight。
- `open_a1z_webrtc_host.sh`
  - 从宿主机启动或复用 Isaac WebRTC streaming，并可选打开本地客户端。
- `stop_a1z_webrtc_streaming_host.sh`
  - 从宿主机停止当前 streaming 会话。
- `a1z_runtime_status.sh`
  - 查看当前容器、streaming、socket、backend 状态。
- `a1zctl_in_container.sh`
  - 在容器内运行 `a1zctl`，用于 `info/status/move/gripper/stop`。
- `a1z_sdk_shell_in_container.sh`
  - 进入容器里的 SDK venv 交互 shell。

## 2. 容器 / 环境入口

这些脚本用于准备和进入当前项目容器环境。

- `create_isaac_sim_dev_container.sh`
  - 创建项目专用 Isaac Sim 5.1 容器。
- `setup_a1z_sdk_in_container.sh`
  - 在容器里准备 SDK venv。
- `setup_a1z_isaac.sh`
  - 初始化容器、解压机器人包并生成世界 USD。
- `a1z_sdk_python_in_container.sh`
  - 用 SDK venv Python 在容器里执行命令。
- `a1z_isaac_python_in_container.sh`
  - 用 Isaac Python 在容器里执行命令。
- `load_a1z_container_env.sh`
  - 为其他脚本加载 `config/a1z_container.env`。

## 3. 验证脚本

这些脚本是更细粒度的专项验证。

- `verify_a1z_sdk_in_container.sh`
- `verify_a1z_mock_control_in_container.sh`
- `verify_a1z_server_contract_in_container.sh`
- `verify_a1z_isaac_control_in_container.sh`
- `verify_a1z_socketcan_preflight_in_container.sh`

通常优先跑 `verify_a1z_control_stack.sh`，只有定位问题时才单独跑这些。

## 4. Streaming 内部辅助

这些脚本仍然有用，但主要被上层入口调用，不建议平时手动直接碰。

- `start_a1z_webrtc_streaming_host.sh`
- `start_a1z_webrtc_streaming.sh`
- `stop_a1z_webrtc_streaming.sh`

推荐入口仍然是：

```bash
./scripts/open_a1z_webrtc_host.sh
./scripts/stop_a1z_webrtc_streaming_host.sh
```

## 5. 构建 / 场景辅助

这些脚本用于场景和 USD 资产准备，不属于日常控制入口。

- `extract_a1z_g1z.sh`
- `prepare_a1z_urdfs.py`
- `rebuild_a1z_world.sh`
- `import_a1z_g1z_to_usd.py`
- `open_a1z_world.py`
- `open_a1z_world_with_a1z_sdk.py`

说明：

- `prepare_a1z_urdfs.py` 不是控制脚本，而是“派生资产生成脚本”。
  它会基于仓库里的基础 URDF/SDK URDF，生成当前项目实际使用的
  `A1Z_G1Z_isaac.urdf`、`A1Z_G1Z_control.urdf`，并把 D405 机械安装链
  固化进去。
- `rebuild_a1z_world.sh` 会先运行 `prepare_a1z_urdfs.py`，再把准备好的
  Isaac URDF 重新导入成 USD，所以它是“从 URDF 到 USD/world”的重建入口。
- `open_a1z_world_with_a1z_sdk.py` 现在主要负责启动编排，并通过 extension 的
  `services.py` 调用 D405 运行时能力。

Extension：

- 仓库现在提供了本地 Isaac Sim extension：
  `exts/a1z.d405.runtime`
- 它现在就是 D405 运行时资产语义和 ROS2 发布的主实现来源。
- extension 对外只保留一个清晰入口：
  `a1z.d405.runtime.services`
- 当前启动脚本会把仓库 `exts/` 目录加入 Isaac 的 extension search path，
  并在启动时启用 `a1z.d405.runtime`。

目录约定：

- 上游 SDK 镜像位于 `vendor/GALAXEA-A1Z`
- 可重建机器人包和 USD 产物位于 `build/`
- 运行日志和 Isaac portable 数据位于 `runtime/`
- 原始压缩包归档位于 `artifacts/`

## 6. 当前推荐最短路径

1. 初始化环境：

```bash
./scripts/create_isaac_sim_dev_container.sh
./scripts/setup_a1z_sdk_in_container.sh
./scripts/setup_a1z_isaac.sh
```

2. 跑整体验证：

```bash
./scripts/verify_a1z_control_stack.sh
```

3. 启动并联调 streaming：

```bash
./scripts/open_a1z_webrtc_host.sh
./scripts/a1z_runtime_status.sh
./scripts/a1zctl_in_container.sh status
```

4. 真机前置检查：

```bash
./scripts/verify_a1z_socketcan_preflight_in_container.sh
```
