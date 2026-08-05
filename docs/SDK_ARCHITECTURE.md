# A1Z Control SDK 架构基线

本文定义自有 A1Z SDK 的第一版边界。目标不是给官方 SDK 打补丁，也不是维护一份官方仓库的 fork，而是在固定的官方驱动之上提供稳定、可验证、同时服务 CLI 与 GUI 的控制产品。

## 1. 核心决定

- 当前产品只面向真机。仿真不是公共 SDK 的后端选项。
- 官方 `a1z` 包是只读的底层依赖，不是我们的公共 API。
- 自有包使用 `a1z_sdk` 导入名，发行名为 `a1z-control-sdk`，避免与官方 `a1z` 冲突。
- 一个控制服务进程独占 CAN 和机械臂。GUI、CLI 以及其他应用都只是客户端。
- GUI 是 SDK 单仓库中的官方应用，但核心 SDK 不依赖 Electron、React 或 GUI 生命周期。
- 宿主机和 Docker 只是部署位置差异，不能改变控制命令及返回语义。

## 2. 运行时边界

```text
官方 a1z 子模块（只读）
          │
          ▼
真机适配与控制循环（a1z_ext，过渡期内部实现）
          │  仅此进程持有 SocketCAN / 电机对象
          ▼
控制服务 ── 唯一目标控制器 / 安全互锁 / 模式原子切换 / 明确错误状态
          │
          ▼
公共 Python API（a1z_sdk.A1ZClient）
          ├────────► 独立 CLI（a1z ...）
          ├────────► Console V2 的薄适配层
          └────────► 用户自己的 Python 程序
```

依赖方向只能自上而下。GUI 不得直接导入官方驱动、打开 CAN、维护第二套控制状态，也不得把按钮是否点亮当作机械臂真实状态。

## 3. 仓库布局

| 路径 | 定位 | 稳定性 |
| --- | --- | --- |
| `a1z_sdk/` | 自有公共 Python API、数据模型、结构化错误和 CLI | 对外稳定 |
| `a1z_ext/` | 现有真机适配器、控制服务及待逐步迁移的实现 | 内部接口 |
| `console_v2/` | SDK 随附的图形控制台 | 应用层 |
| `vendor/GALAXEA-A1Z/` | 官方仓库 Git 子模块，禁止本地改写 | 只读上游 |
| `tools/a1zctl` | 旧入口，迁移期间保留 | 兼容层 |
| `tests/` | 公共契约、控制语义和回归测试 | 质量门禁 |

## 4. 官方 SDK 管理

官方仓库为 `https://github.com/userguide-galaxea/GALAXEA-A1Z.git`，MIT License。当前项目需要 G1Z，因此子模块选择官方 `gripper` 分支并固定在提交：

```text
e931ecd0e25ad35df251097ba42921b3d2fa7224
```

首次获取：

```bash
git submodule update --init --recursive
```

上游升级必须显式评审，不能在构建或启动时自动跟随远端：

```bash
git -C vendor/GALAXEA-A1Z fetch origin gripper
git -C vendor/GALAXEA-A1Z checkout <reviewed-commit>
git add vendor/GALAXEA-A1Z vendor/GALAXEA-A1Z_UPSTREAM
```

升级评审至少覆盖：控制频率、关节符号、软限位、启动模式、停止序列、G1Z 行程映射、反馈字段和异常行为。任何修正都写入我们的适配层；确需改官方代码时先形成独立补丁和上游议题，不在子模块中产生未提交改动。

## 5. 公共控制语义

### 5.1 模式是二选一状态

`ControlMode` 只有两个值：

- `position_hold`：位置保持，可执行位置运动。
- `gravity_comp_effort`：零力/重力补偿模式，不接受位置运动。

模式由真机控制服务维护，客户端只读取或请求原子切换。启动默认 `position_hold`；选择零力必须显式传入 `--start-mode zero-force`。

### 5.2 服务端唯一维护最新目标

机械臂最终目标只能来自控制服务内的 `LatestTargetMotionController`。它以单工作线程完成“读取关节反馈 →
关节空间到达判定 → 原子提交最新目标”；GUI、CLI、舞蹈和轨迹回放都只能向同一个最新目标槽提交目标，
不能各自维护队列或直接调用官方运动方法。SocketCAN 后端的唯一 250 Hz 硬件循环持有 Ruckig 状态，
每 4 ms 生成同一帧的参考位置、速度和加速度，并在该帧内完成 RNEA 前馈、MIT 阻抗命令和 CAN 写入。
服务端 50 Hz 工作线程只监视反馈和到达状态，不再生成阶梯式微帧。

新的合法目标会在当前原子帧完成后替换旧目标，并继承上一帧的位置、速度和加速度状态平滑转向。非法
目标会在替换前完整拒绝，不影响正在执行的目标。模式切换、急停解除等控制边界会清空旧规划参考，
下一次运动从真机当前参考重新起步。

公共结果语义：

- `accepted`：`set_joint_target()` 已异步交给服务端；不表示已经到达，客户端可立即提交更新目标。
- `superseded`：该目标被更新的合法目标替换；阻塞调用抛出 `A1ZCommandSuperseded`。
- `feedback_verified`：修正后的关节参考已经发送，六轴实测误差分别不超过 `0.5°`、最大实测关节
  速度不超过 `0.02 rad/s`，并连续 5 个 50 Hz 样本满足。
- `already_at_target`：提交时已经稳定满足同一组条件，全程不发送冗余运动帧。
- `submitted_unverified`：已经可能发生运动，但超时、堵转、反馈或运行时故障导致无法确认。
- `rejected`：命令在运动前被拒绝。

到达后服务端继续保持该目标并监视漂移；名义轨迹结束后，250 Hz 硬件循环把静态关节残差积分成有界
力矩偏置，而不再移动位置参考。默认等效积分增益为 `0.6 s^-1`、等效修正速度不超过 `0.5°/s`、
等效修正量不超过 `3° × Kp`，并在总力矩饱和处抗积分饱和。总前馈力矩还在发送前经过可配置的变化率
限制。GUI 只展示服务端状态，不能在界面定时器里做回读、判断或补发。

`grasp_tcp` 正运动学位置/姿态误差仍随结果返回，但仅作诊断，不再参与关节目标的到达判定。机械零点、
URDF、工具坐标、减速器回差和结构柔顺性仍需实机标定与验收。

`set_gripper_opening()` 仍独立等待 G1Z 实测开度反馈；它不进入六轴机械臂的位置目标控制器。

## 6. CLI 与 Python 使用

初始化开发环境：

```bash
git submodule update --init --recursive
python -m pip install -e '.[hardware,dev]'
```

启动真机服务：

```bash
a1z serve --can can0 --with-gripper --start-mode hold
```

另一个终端可完全不启动 GUI，直接控制：

```bash
a1z status
a1z mode hold
a1z move '0,60,-60,0,0,0' --speed 0.5
a1z gripper 0.5
a1z grasp close
```

Python 程序使用同一条链路：

```python
from a1z_sdk import A1ZClient

robot = A1ZClient()
state = robot.status()
result = robot.move_joints([0, 60, -60, 0, 0, 0], speed_rad_s=0.5)
assert result.feedback_verified
```

## 7. GUI 集成规则

Console V2 保留为 SDK 自带 GUI，但只增加一个调用 `A1ZClient` 等价接口的薄适配层：

- GUI 和 CLI 必须得到同一种状态、完成语义和错误。
- 当前只读状态由 `python -m a1z_sdk.telemetry` 以逐行 JSON 提供；宿主机与
  Docker 只改变该进程的部署位置，不改变字段和新鲜度语义。
- GUI 刷新只能读取测量状态，不能重复下发上一次目标。
- 长动作的执行状态必须持续存在，直到用户确认或下一次明确动作覆盖。
- 控件锁定依据服务端模式和进行中的互斥操作，不依据页面分类。
- GUI 退出不能绕过服务端的安全停止序列；控制服务也不依赖 GUI 存活。

## 8. 迁移顺序

1. 以 `a1z_sdk` 冻结公共数据模型、错误模型和 CLI。
2. Console V2 改为只通过公共客户端契约读取和控制。
3. 将 `a1z_ext` 中通用控制服务逐步移入私有实现包，保留兼容导入。
4. 为每个动作增加可配置反馈策略、遥测时间戳和控制循环健康指标。
5. 上游更新只通过子模块提交变更和契约回归测试进入主线。
