# Scripts

当前只保留这套工作流真正需要的脚本，并按用途分成三类：用户入口、容器/环境入口、内部辅助。

## 1. 用户入口

这些是日常直接用的脚本。

- `run_target_mask_to_anygrasp_pick_attempt.sh`
  - 当前推荐的一键抓取入口。
  - 流程是：
    `自然语言目标 -> ROS RGB-D 抓图 -> target mask -> AnyGrasp -> A1Z adapter -> execute`
  - 支持：
    - `--execution-mode best_direct`：执行 `adapter/best_direct/selected_plan.json`；当前默认就是这一档。
    - `--execution-mode adapter_selected`：执行 `adapter/selected_plan.json`
    - `--binding-label <label>`：显式指定本轮 AnyGrasp raw rotation 的列/符号绑定假设。
    - `--camera-correction-label <label>`：显式指定本轮相机坐标系修正假设，当前默认活路径是 `identity`。
    - `--extrinsic-correction-label <label>`：显式指定本轮 `extrinsic_camera_to_base` 内部额外修正假设，当前默认活路径是 `identity`。
    - `--ee-grasp-origin-xyz-m <json>` / `--ee-opening-axis-xyz <json>` / `--ee-approach-axis-xyz <json>`：显式指定本轮 TCP 对齐假设。
    - `--require-current-joints`：要求本轮必须成功落下 `capture/current_joints_rad.json`；否则流程直接失败，不产出不可靠的对齐目录。
  - 对齐机械臂映射时，默认就先走 `--execution-mode best_direct`，先固定 AnyGrasp `rank0`，再根据 `adapter/anygrasp_pose_chain_summary.json` 和 renders 图调整 `camera correction / camera->base / TCP` 绑定。
  - 如果已经从真机观察到“当前 tool 还需要往 base 坐标系的哪边修多少”，可以再用 `rank_anygrasp_binding_hypotheses_in_container.sh` 对 `adapter/mapping_hypotheses.json` 反查，联合缩小 `binding / camera correction / extrinsic correction` 候选；如果旧目录里还没有 `mapping_hypotheses.json`，会退回 `adapter/anygrasp_alignment_report.json` 只排 `binding`。
  - 如果想直接对某一轮输出目录做统一分析，可以用 `analyze_anygrasp_output_dir.sh <pipeline_dir> [--observed-tool-delta-xyz '[dx,dy,dz]']`，它会在该目录下生成 `analysis/analysis_summary.json`；其中 `diagnostic_summary` 会汇总当前 active 配置、best_direct gap 严重度、扫描到的最佳候选以及三层差异。提供观察误差时还会同时生成 `analysis/binding_hypotheses.json`，优先按 `binding / camera correction / extrinsic correction` 三层候选排序。
  - 做“从 0 对齐机械臂映射”时，只在 `capture/current_joints_rad.json` 存在且 `analysis/analysis_summary.json` 里的 `best_direct_reference_state_reliable=true` 时，把该轮 `best_direct gap` 当成有效对齐证据；旧目录如果缺这份抓图时刻关节角，gap 只可用于粗看，不足以下结论。
  - `pipeline_manifest.json` / `analysis/analysis_summary.json` 里的 `active_binding_label`、`active_camera_correction_label`、`active_extrinsic_correction_label` 只表示“这一轮执行时采用的 AnyGrasp frame 假设”，不是已经验证正确的结论。
  - 当前默认 TCP 假设为：`ee_grasp_origin_xyz_m=[0,0,0]`、`ee_opening_axis_xyz=[0,0,1]`、`ee_approach_axis_xyz=[1,0,0]`。配合官方 AnyGrasp 旋转语义 `binding=opening=c1,height=c2,approach=c0` 后，会把目标 TCP 解释成 `tcp_x=approach`、`tcp_y=-height`、`tcp_z=opening`。
  - 当前默认 AnyGrasp `binding_label` 采用 `opening=c1,height=c2,approach=c0`，对应官方 `rotation_matrix` 定义：`column_0=approach`、`column_1=opening`、`column_2=height`。
  - 会在 `runtime/anygrasp_target_pick_attempt_<timestamp>/` 下输出：
    - `capture/`
    - `target_mask/`
    - `anygrasp_from_mask/`
    - `adapter/`
    - `renders/`
    - `execute/`
    - `pipeline_manifest.json`
  - `adapter/` 里当前会固定包含三类调试结果：
    - `anygrasp_adapter_result.json` / `selected_plan.json`
    - `best_direct/anygrasp_best_direct_result.json` / `best_direct/selected_plan.json`
    - `best_vs_selected_summary.json`
    - `anygrasp_pose_chain_summary.json`
    - `anygrasp_frame_binding_analysis.json`
    - `anygrasp_alignment_report.json`
  - `execute/` 里会写：
    - `execution_result.json`
    - `execution_manifest.json`
- `run_target_mask_to_anygrasp_from_ros.sh`
  - 非执行版主入口；会产出 `capture/ target_mask/ anygrasp_from_mask/ adapter/ renders/ analysis/ pipeline_manifest.json`。
  - 同样支持 `--binding-label`、`--camera-correction-label`、`--extrinsic-correction-label`、`--require-current-joints` 和三组 `--ee-*` 参数，适合做“只采集和分析，不执行”的从 0 对齐。
- `replay_anygrasp_from_capture.sh`
  - 对已有抓图目录做 AnyGrasp 重放，适合固定输入后迭代 `binding / camera correction / extrinsic / TCP` 假设。
  - 加 `--require-current-joints` 时，如果源目录没有 `capture/current_joints_rad.json`，会直接拒绝重放，避免继续使用不可靠对齐证据。
- `find_anygrasp_alignment_runs.sh`
  - 扫描 `runtime/` 里的 AnyGrasp 输出目录，并按“是否带抓图时刻关节角、analysis 是否标记为可靠证据”排序。
  - 默认会跳过 `verify / smoke / analysis_input` 这类夹具目录，避免把测试产物误当成真机对齐依据；需要时可加 `--include-fixtures`。
  - 常用法：
    - `bash scripts/find_anygrasp_alignment_runs.sh --require-analysis`
    - `bash scripts/find_anygrasp_alignment_runs.sh --require-analysis --require-current-joints --require-reliable --json`
- `print_latest_anygrasp_alignment_run.sh`
  - 打印“最新且可用于从 0 对齐”的 AnyGrasp 输出目录。
  - 当前如果还没有任何 `best_direct_reference_state_reliable=true` 的目录，会直接报 `no reliable AnyGrasp alignment run found`；这正说明还需要再跑一轮新的真机采集。

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
