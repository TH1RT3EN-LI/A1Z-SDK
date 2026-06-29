# Scripts

当前只保留这套工作流真正需要的脚本，并按用途分成三类：用户入口、容器/环境入口、内部辅助。

## 1. 用户入口

这些是日常直接用的脚本。

- `verify_a1z_control_stack.sh`
  - 一次性跑 SDK / mock / server contract / Isaac / SocketCAN preflight。
- `open_a1z_webrtc_host.sh`
  - 从宿主机启动或复用 Isaac WebRTC streaming，并可选打开本地客户端。
- `open_a1z_webrtc_ee_drag_host.sh`
  - 从宿主机启动带“3D 末端拖拽目标”的 Isaac WebRTC 会话；在视口里直接拖目标 prim，机械臂连续 IK 跟随。
- `stop_a1z_webrtc_streaming_host.sh`
  - 从宿主机停止当前 streaming 会话。
- `a1z_runtime_status.sh`
  - 查看当前容器、streaming、socket、backend 状态。
- `a1zctl_in_container.sh`
  - 在容器内运行 `a1zctl`，用于 `info/status/move/gripper/stop`。
- `a1z_ee_teleop_tk.py`
  - 宿主机 Tk 微调面板；支持笛卡尔末端 `+/-X/Y/Z`、`Roll/Pitch/Yaw` 增量 IK 控制，也支持每个关节 `J1..J6` 按软限位做 `+/-` 微调。
- `d405_mosaic_preview.py`
  - 宿主机单窗口 D405 实时拼图预览；当前把 RGB 和 depth 并排显示在一个 Tk 窗口里，适合快速检查真机成像效果。
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
- `create_a1z_ros2_container.sh`
  - 创建独立 ROS 2 Humble 容器，用于运行 `ros2_ws/`。
- `create_a1z_vision_gpu_container.sh`
  - 创建独立 GPU 视觉容器，用于运行 SAM / AnyGrasp。
- `run_a1z_ros2_motion_in_container.sh`
  - 在 ROS 2 容器里构建并启动 `a1z_motion`。
- `setup_a1z_vision_in_container.sh`
  - 在 GPU 视觉容器里创建 vision venv，安装 PyTorch / SAM2 / AnyGrasp 运行时依赖。
- `setup_anygrasp_sdk_in_container.sh`
  - 在 GPU 视觉容器里为当前 Python 版本铺好 AnyGrasp 二进制、license 和 checkpoint 链接。
- `bootstrap_anygrasp_assets.sh`
  - 把 `vendor/vision/anygrasp_sdk` 里的本机 license zip 和两个 checkpoint 落到 `runtime/` 约定路径。
- `run_grconvnet_inference_in_container.sh`
  - 在 GPU 视觉容器里运行 `GR-ConvNet`，输入 `RGB-D + selected mask`，输出 grasp quality/angle/width maps。
- `run_grconvnet_adapter_in_container.sh`
  - 在 SDK 容器里把 `GR-ConvNet` grasp maps 适配成 A1Z grasp adapter 结果。
- `verify_grconvnet_adapter_in_container.sh`
  - 用当前仓库里的 ROS 抓图样例和目标 mask，对 `GR-ConvNet inference -> A1Z adapter` 做一次跨容器离线 smoke verify。
  - 会优先使用 `capture/extrinsic_camera_to_base.npy`；如果旧抓图目录里还没有这个文件，会在 ROS 容器里通过 TF 解析 `d405_color_optical_frame -> robot_base_frame` 后补出来。
- `verify_a1z_vision_stack_in_container.sh`
  - 验证 GPU 视觉容器里的 Torch / SAM2 / AnyGrasp import 与 checkpoint 可见性。
- `verify_anygrasp_sdk_in_container.sh`
  - 单独验证 AnyGrasp，包含官方 detection demo 和 A1Z adapter 侧 preflight/smoke test。
- `a1z_vision_shell_in_container.sh`
  - 进入 GPU 视觉容器并自动激活 vision venv。
- `a1z_sdk_python_in_container.sh`
  - 用 SDK venv Python 在容器里执行命令。
- `a1z_isaac_python_in_container.sh`
  - 用 Isaac Python 在容器里执行命令。
- `load_a1z_container_env.sh`
  - 为其他脚本加载 `config/a1z_container.env`。
- `fetch_vision_vendor_repos.sh`
  - 拉取并固定 SAM2 / SAM3 / AnyGrasp 上游仓库版本。
- `download_sam2_checkpoints.sh`
  - 下载固定的 SAM2.1 checkpoint 到 `runtime/models/sam2/`。

## 3. 验证脚本

这些脚本是更细粒度的专项验证。

- `verify_a1z_sdk_in_container.sh`
- `verify_a1z_mock_control_in_container.sh`
- `verify_a1z_server_contract_in_container.sh`
- `verify_a1z_isaac_control_in_container.sh`
- `verify_a1z_socketcan_preflight_in_container.sh`
- `verify_open_vocab_data_loop_in_container.sh`
- `verify_open_vocab_data_loop_from_isaac_in_container.sh`

通常优先跑 `verify_a1z_control_stack.sh`，只有定位问题时才单独跑这些。

其中：

- `verify_open_vocab_data_loop_in_container.sh`
  - 验证“开放词汇感知数据闭环”的最小链路。
  - 当前只覆盖：
    - 指令解释
    - grounding 候选
    - segmentation 候选
    - mask + depth 恢复 3D descriptor
  - 当前**不包含抓取**。

- `verify_open_vocab_data_loop_from_isaac_in_container.sh`
  - 验证“Isaac D405 真采帧 -> 非抓取版开放词汇 bundle”的链路。
  - 当前覆盖：
    - 打开世界 USD
    - 挂接 D405 运行时资产
    - 采集 color/depth
    - 提取 intrinsics / camera pose
    - 跑通 `TaskSpec -> GroundingCandidate[] -> MaskCandidate[] -> Object3DDescriptor[]`
  - 当前**仍不包含抓取**。

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
- `open_a1z_world_with_a1z_sdk.py`
- `run_open_vocab_data_loop.py`
- `run_open_vocab_data_loop_from_isaac.py`

说明：

- `prepare_a1z_urdfs.py` 不是控制脚本，而是“派生资产生成脚本”。
  它会基于仓库里的基础 URDF/SDK URDF，生成当前项目实际使用的
  `A1Z_G1Z_isaac.urdf`、`A1Z_G1Z_control.urdf`，并把 D405 机械安装链
  固化进去。
- `rebuild_a1z_world.sh` 会先运行 `prepare_a1z_urdfs.py`，再把准备好的
  Isaac URDF 重新导入成 USD，所以它是“从 URDF 到 USD/world”的重建入口。
- `open_a1z_world_with_a1z_sdk.py` 现在主要负责启动编排，并直接使用
  `a1z_ext.runtime.d405` 挂接 Isaac 内的 D405 和 TCP 帧采集后端。
- `run_open_vocab_data_loop.py` 是当前开放词汇 pipeline 的非抓取版入口，
  用统一 schema 跑通：
  `TaskSpec -> GroundingCandidate[] -> MaskCandidate[] -> Object3DDescriptor[]`，
  并把结果 bundle 落到 `runtime/`。
- `run_open_vocab_data_loop_from_isaac.py` 会直接在 Isaac 内打开当前世界、
  挂接 D405 相机 prim、采集一帧 RGB-D、提取内外参，并走同一套
  非抓取版 bundle 流水线。

ROS2 D405 bridge：

- 标准 ROS2 图像接口在 `ros2_ws/src/a1z_d405`。
- Isaac 侧只负责挂接仿真 D405 并通过 A1Z TCP server 暴露 `camera_status`
  和 `camera_capture`。
- `a1z_motion.launch.py` 会启动 `a1z_d405` 的 `d405_bridge`，由 ROS2 工作区发布
  `/a1z/d405/color/*` 和 `/a1z/d405/depth/*` topic。
- `scripts/capture_ros_rgbd.py` 现在默认把抓图目标帧设为 `robot_base_frame`，
  并在可解析 TF 时同时写出：
  - `extrinsic_camera_to_target.npy`
  - `extrinsic_camera_to_base.npy`

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

5. 末端 IK 微调 GUI：

先在容器内启动控制服务，例如：

```bash
./scripts/a1zctl_in_container.sh serve --backend isaacsim --with-gripper --control-freq 60
```

或离线调试：

```bash
./scripts/a1zctl_in_container.sh serve --backend mock --with-gripper
```

然后在宿主机启动 Tk 面板：

```bash
python3 scripts/a1z_ee_teleop_tk.py
```

默认由宿主机 Tk 面板调用容器内的 `a1z_ee_ik_helper.py` 做 FK/IK。

5.1 D405 单窗口预览：

```bash
python3 scripts/d405_mosaic_preview.py
```

默认读取：

- RGB: `/dev/video4`
- Depth: `/dev/video0`

6. 3D 末端拖拽跟随：

启动带 3D 拖拽目标的 Isaac WebRTC：

```bash
./scripts/open_a1z_webrtc_ee_drag_host.sh --restart --no-client
```

启动后，场景里会生成一个目标 prim：

- `/World/A1Z_EE_Target`

它会被自动选中；在 WebRTC 视口里用 Isaac 自带的平移/旋转 gizmo 直接拖它，
机械臂会持续根据该目标做 IK 跟随。

状态文件：

```bash
runtime/logs/a1z-ee-drag-target.json
```

## 7. Docker 内独立 ROS 2 工作区

仓库现在新增了一个独立 ROS 2 工作区：

- `ros2_ws/`

它的定位是：

- 在单独的 ROS 2 容器里运行
- 通过 A1Z TCP server 连接 Isaac 容器里的机器人后端
- 不直接依赖 Isaac Python API

当前包含：

- `a1z_msgs`
  - `MoveEndEffector.action`
- `a1z_motion`
  - `robot_state`
  - `motion_executor`

最小运行形态：

1. Isaac 容器已运行，并已启动 A1Z server
2. `A1Z_TCP_PORT=18080` 可从 ROS 容器访问
3. 在 ROS 容器里执行：

```bash
cd /workspace/A1Z/ros2_ws
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
ros2 launch a1z_motion a1z_motion.launch.py
```

说明：

- `robot_state` 负责发布 `/joint_states` 和最小 TF 树
- `motion_executor` 提供 `/a1z/move_ee` action
- 当前阶段只做 IK + 关节约束检查，不做碰撞约束
