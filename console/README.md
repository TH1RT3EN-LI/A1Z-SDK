# A1Z SDK Console

Qt 6 / QML 桌面控制台，参考 `duojin_l1w_control_gui` 的控制器与界面分层，
但针对机械臂改为离散事务模型：

- 控制服务是唯一官方 SDK / CAN 所有者，GUI 不创建第二个 `ArmRobot`；
- `sim` 固定连接 `isaacsim@127.0.0.1:37103`，`real` 固定连接
  `socketcan@127.0.0.1:37104`；
- 所有运动按钮在工作线程的单队列内执行，繁忙期间不会继续排队；
- 软急停使用独立高优先级通道，不会排在阻塞式运动之后；状态回读也不占用运动锁；
- 每次运动前重新读取 `info` 并核对后端身份；
- 运动请求没有自动重试。请求已发出但响应丢失时，GUI 锁定运动，必须现场确认后
  才能人工解除；
- 关节点动每次读取最新角度后只发送一个 `move`；服务端随后只轮询 SDK
  `get_joint_pos()`，达到容差才向界面报告完成；
- 零力补偿 factor 是 SDK 构造参数。界面允许手动配置，但“应用”会重启控制
  服务并以位置保持模式恢复，不在运行中的控制循环里热切换扭矩比例；
- 末端点动使用官方 Pinocchio FK/IK，保留 2° 关节裕量，并拒绝超过 15° 的
  单步 IK 分支跳变；Base/Tool 变换与完整 SDK 能力映射见
  `docs/A1Z_CONSOLE_SDK_COVERAGE.md`；
- AnyGrasp 分为“只计算并审阅”和“执行当前已审阅计划”，两者不是同一个按钮。
- RGB-D 预览统一订阅配置选定的 ROS 主题；GUI 不直接打开 USB 或
  `/dev/video*`，仿真与真机使用同一条相机桥协议。

## 启动

从仓库根目录运行：

```bash
./scripts/run_a1z_console.sh
```

首次运行会把 PySide6 6.8+ 隔离安装到 `runtime/a1z-console-python`，不会修改系统
Python 包目录。
也可显式选择初始配置：

```bash
./scripts/run_a1z_console.sh --profile sim
./scripts/run_a1z_console.sh --profile real
```

正常启动控制台时，会自动检查所选 profile 的 ROS 2 栈：节点和 RGB-D
帧均健康时直接复用，缺失节点或相机帧过期时才重新启动。调试控制台本身、
不希望触碰 ROS 运行态时可加 `--no-ros-autostart`；截图和 smoke test
默认不会自动启动 ROS。

逐页视觉回归可使用 `--page`、`--frame`、`--window-size` 和 `--screenshot`，例如：

```bash
QT_QPA_PLATFORM=offscreen ./scripts/run_a1z_console.sh \
  --page manual --frame tool --window-size 1220x760 --screenshot runtime/manual.png
```

## 安全边界

- 软件急停不能替代现场硬件急停。
- 真机 AnyGrasp 执行不提供“绕过未验证手眼标定”的入口。
- `command_joint_pos` / `command_joint_state` 是高频伺服接口，控制台不会把它们做成
  会产生阶跃的单击按钮；手动运动统一使用带速度约束的 `move_joints`。
- “控制服务在线”不等于“控制循环运行中”；`is_running` 或适配层故障状态异常时，
  所有运动入口都会锁定并提示重启服务。
- 电机扫描、夹爪混控测试和零点标定要求先停止 SDK 服务，避免 CAN 双主。
- 零点标定必须输入 `校零 A1Z`，且当前姿态会被写入电机零点。

## 页面

- 运行总览：连接、后端身份、控制模式、六轴角度/速度/力矩/温度/故障码。
- 手动控制：J1–J6 点动与绝对目标，Base/Tool 末端平移和姿态点动，夹爪控制。
- AnyGrasp：只计算、计划安全审阅、dry-run、显式实际执行。
- SDK 功能：服务生命周期、零力/保持、预置位、动作序列、示教、夹爪，以及
  RGB/Depth 同步预览、链路状态和相机外参。
- 诊断与日志：全链路预检、ROS 管理、官方 CAN 工具和受保护的校零入口。

## 验证

```bash
./scripts/run_a1z_console.sh --smoke-test
PYTHONPATH=runtime/a1z-console-python \
  runtime/a1z-console-python/bin/pyside6-qmllint \
  -I console/qml console/qml/A1ZConsole/*.qml
python3 -m pytest -q tests/test_a1z_console.py
```

## RGB-D 预览链路

相机预览不依赖机械臂控制端点。先启动所选 profile 的 ROS 2 栈：

```bash
A1Z_PROFILE=sim ./scripts/run_a1z_ros2_stack_in_container.sh start
A1Z_PROFILE=real ./scripts/run_a1z_ros2_stack_in_container.sh start
```

设备适配器负责发现/独占物理设备或读取仿真相机，随后发布
`A1Z_RGBD_*_TOPIC` 约定。`camera_console_bridge` 将这组主题提供给 GUI：
SIM 使用 `37203`，REAL 使用 `37204`。两个 profile 的端点隔离，且整个 GUI
链路不引用动态变化的 V4L2 节点编号。

真机 profile 将 librealsense 的控制台阈值设为 `fatal`，避免 USB 断开后
底层 V4L2 错误无节流刷屏。ROS 聚合日志采用 64 MiB × 4（当前文件加三个
备份）的轮转上限；相机是否健康仍由相机桥的新鲜 RGB-D 帧状态判断。当前
640×480×30 真机配置还要求 D405 以至少 5,000 Mb/s 的 USB 3.x 链路枚举，
USB 2.0 回退会在启动前直接报错，不再留下“节点存在但无图像”的假健康状态。
