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
- 关节点动每次读取最新角度后只发送一个 `move`；
- 末端点动使用官方 Pinocchio FK/IK，保留 2° 关节裕量，并拒绝超过 15° 的
  单步 IK 分支跳变；
- AnyGrasp 分为“只计算并审阅”和“执行当前已审阅计划”，两者不是同一个按钮。

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

## 安全边界

- 软件急停不能替代现场硬件急停。
- 真机 AnyGrasp 执行不提供“绕过未验证手眼标定”的入口。
- `command_joint_pos` / `command_joint_state` 是高频伺服接口，控制台不会把它们做成
  会产生阶跃的单击按钮；手动运动统一使用带速度约束的 `move_joints`。
- 电机扫描、夹爪混控测试和零点标定要求先停止 SDK 服务，避免 CAN 双主。
- 零点标定必须输入 `校零 A1Z`，且当前姿态会被写入电机零点。

## 页面

- 运行总览：连接、后端身份、控制模式、六轴角度/速度/力矩/温度/故障码。
- 手动控制：J1–J6 点动与绝对目标，Base/Tool 末端平移和姿态点动，夹爪控制。
- AnyGrasp：只计算、计划安全审阅、dry-run、显式实际执行。
- SDK 功能：服务生命周期、零力/保持、预置位、动作序列、示教、夹爪、D405。
- 诊断与日志：全链路预检、ROS 管理、官方 CAN 工具和受保护的校零入口。

## 验证

```bash
./scripts/run_a1z_console.sh --smoke-test
PYTHONPATH=runtime/a1z-console-python \
  runtime/a1z-console-python/bin/pyside6-qmllint \
  -I console/qml console/qml/A1ZConsole/*.qml
python3 -m pytest -q tests/test_a1z_console.py
```
