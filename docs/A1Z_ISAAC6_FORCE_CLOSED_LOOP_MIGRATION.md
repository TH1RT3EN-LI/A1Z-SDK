# A1Z 迁移到 Isaac Sim 6 与力反馈抓取闭环

本文说明上级 `A1Z` 工程如何迁移到当前 Paw 中已经验证的 Isaac Sim 6.0.1
A1Z 运行模式。目标不是把旧的 Isaac 5.1 启动脚本改到“能打开”，而是统一
运行时、控制协议、D405 数据链路和抓取语义。

当前 Paw 中的参考实现位于工作区 sibling 项目：

- `../Paw/external/A1Z/a1z_ext/robots/isaacsim_robot.py`
- `../Paw/external/A1Z/a1z_ext/robots/server.py`
- `../Paw/external/A1Z/a1z_ext/grasping/physical_types.py`
- `../Paw/external/A1Z/a1z_ext/grasping/physical_fsm.py`
- `../Paw/external/A1Z/a1z_ext/grasping/contact_reducer.py`
- `../Paw/config/grasping/controllers/a1z_physical_gripper_v1.json`

本文是迁移契约和实施顺序；不等同于直接复制 Paw 目录。上级 A1Z 应先在
Isaac Sim 6 独立模式中完成验收，再选择是否挂载到 DOG 的共享 articulation。

## 1. 目标状态

迁移完成后，A1Z 的目标链路应为：

```text
SDK / ROS / Teleop / AnyGrasp
        |
        v
  A1Z RobotServer
  Unix socket（可选）/ TCP 37103
        |
        v
  Isaac Sim 6 A1Z runtime
  Native public API + 60 Hz A1Z control tick
        |
        v
  A1Z articulation + real contact physics
        |
        v
  physical_v2 grasp FSM
  contact impulse -> force estimate -> jaw drive profile -> contact/hold state
```

如果作为独立 A1Z 工程运行，推荐保持：

```text
articulation root: /World/A1Z_G1Z/Geometry
asset geometry:    /World/A1Z_G1Z/Geometry
```

如果最终挂载到 Paw，则使用：

```text
articulation root: /DOG/Geometry/BASE_LINK
asset geometry:    /DOG/A1Z_PAYLOAD_MOUNT/A1Z_G1Z/Geometry
```

两种部署的抓取语义必须完全相同：物体保持动态刚体，夹爪通过真实碰撞和
驱动器产生夹持力，不创建临时固定关节。

## 2. 与旧工程的边界

上级工程当前的旧模式包括：

- Isaac 5.1 风格的 `World`、`SingleArticulation` 和 `ArticulationAction`；
- `/World/A1Z_G1Z/Geometry` 作为独立 articulation；
- TCP `18080`、`/tmp/a1z.sock` 等旧默认端点；
- D405 默认高分辨率、同步读取和旧 ROS publisher；
- `grasp_attach` / `FixedJoint` 作为抓取成功手段；
- 将物体改成 kinematic、关闭重力或直接写位置作为抓取 fallback。

这些内容不能作为新生产路径。旧 `grasp_attach` 可以在迁移期间保留为显式
兼容接口，但不得被 `physical_v2` 调用，也不得出现在新 AnyGrasp 默认策略中。

## 3. Isaac Sim 6 运行时迁移

### 3.1 资产生成

1. 使用 Isaac Sim 6 的 `URDFImporter` 导入 A1Z URDF。
2. 使用 Asset Transformer 生成 Isaac 6 可加载的 USDA/USD 资产。
3. 将材质、碰撞、关节 drive、gripper 两个 prismatic DOF 固化到生成资产。
4. 不把抓取目标、FixedJoint 或物体的运动状态写进 A1Z 机器人资产。
5. 目标物体必须由场景层单独 author，且默认是动态刚体、非 kinematic、受重力影响。

迁移后的资产检查至少应确认：

- 六个 arm DOF 名称仍为 `arm_joint1` 至 `arm_joint6`；
- 夹爪 DOF 仍为 `gripper_finger_left_joint` 和
  `gripper_finger_rIght_joint`；
- 两个夹爪 DOF 都有有效刚体、碰撞和 prismatic drive；
- 夹爪 open/closed DOF 范围与 controller profile 一致；
- 目标物体存在有效 rigid body 和 collision API；
- 没有自动生成的物体—夹爪固定关节。

### 3.2 Native API 适配

`a1z_ext/robots/isaacsim_robot.py` 应把 Isaac 访问集中在一个小的 backend
adapter 中。业务层只依赖以下能力：

- 读取 articulation 的位置、速度、effort 和 DOF 名称；
- 发送有限的关节位置/速度/effort drive command；
- 读取两个夹爪 DOF 的实时位置和速度；
- 读取左右指尖刚体的接触记录；
- 读取物体和夹爪 carrier 的世界位姿；
- 读取并校验 PhysicsScene 的实际 `physics_dt`。

Isaac 6 下禁止依赖旧版内部对象或通过 USD 每个 tick 写入一套重复 drive
target。必须保留一个权威的 live command path；如果为了兼容性保留 USD
mirror，必须是显式 A/B 开关，默认关闭。

### 3.3 时间和线程

- A1Z 控制 tick 默认 60 Hz；
- 所有 Isaac stage、articulation、contact 和 drive 操作在 Kit 主线程完成；
- TCP/Unix server 线程只接收命令、等待事件和返回 JSON；
- server 启动必须等待实际 listener bind/listen 完成后才报告 ready；
- 物理 callback 每次先处理主线程请求，再更新关节、接触和抓取 FSM；
- `process_pending(step_size)` 应支持按实际物理步长累计，并只在到达 A1Z
  控制周期时推进一次控制逻辑。

## 4. 通信和状态协议

推荐新默认值：

```text
A1Z_TCP_HOST=127.0.0.1
A1Z_TCP_PORT=37103
A1Z_SOCKET_PATH=<可选的 Isaac6 专用 Unix socket>
A1Z_ISAAC_CONTROL_FREQ_HZ=60
```

基础命令保持兼容：

```text
status
info
move
command
gripper
camera_status
camera_capture
camera_extrinsic
```

新抓取接口必须增加：

```text
grasp_close_v2
grasp_release_v2
grasp_status_v2
```

`grasp_close_v2` 的关键参数：

```json
{
  "timeout_s": 15.0,
  "minimum_normal_force_n": 0.05,
  "preload_delta_m": null,
  "controller_profile": {}
}
```

`physical_v2` 的正常调用不传 `target_body_path`。backend 在慢速闭合期间
寻找左右指尖共同接触的同一个刚体，连续稳定达到阈值后才锁定该刚体。
`target_body_path` 不再属于 `grasp_close_v2` 请求参数，只在状态响应中报告
自动发现并锁定的刚体。

`grasp_status_v2` 至少应返回：

```json
{
  "contract_version": 2,
  "mode": "physical",
  "success": true,
  "phase": "holding",
  "target_body_path": "/World/TrashSet/target/physics",
  "target_discovery_mode": true,
  "bilateral_contact": true,
  "stable_contact_frames": 5,
  "left_normal_force_n": 2.1,
  "right_normal_force_n": 2.0,
  "filtered_weak_normal_force_n": 2.0,
  "effective_grip_force_n": 2.0,
  "grip_force_source": "contact_normal_force",
  "target_normal_force_n": 2.0,
  "maximum_normal_force_n": 12.0,
  "force_control_active": true,
  "force_target_reached": true,
  "resistance_confirmed": true,
  "measured_width_m": 0.042,
  "hold_width_m": 0.0407,
  "applied_preload_delta_m": 0.0013,
  "constraint_count_delta": 0,
  "target_physics_state_mutated": false,
  "attachment_joint_path": null,
  "attached_object_path": null,
  "failure_reason": null
}
```

`constraint_count_delta != 0`、`target_physics_state_mutated == true`、
`attachment_joint_path != null` 或 `attached_object_path != null` 都必须使
physical grasp 失败，而不是被当作成功。

## 5. 新的力反馈抓取闭环

这里的“力闭环”是基于接触力反馈的闭环抓取控制：当前参考实现用驱动器的
位置/速度/最大 effort profile 执行夹爪动作，用接触冲量反馈决定何时减速、预紧、
保持或失败。它不是简单的 `gripper close -> FixedJoint`，也不是把夹爪或物体
直接 teleport 到目标位置。

### 5.1 力估计

PhysX 接触记录中的 impulse 必须按实际物理步长换算：

```text
normal_force_N = ||contact_impulse|| / physics_dt_seconds
```

左右指尖分别按接触刚体归约接触记录。两侧共同接触候选按较弱侧法向力排序，
同一候选连续稳定后锁定为目标。地面、桌面和工作台属于允许存在的 support
contact：它们会被记录到状态中，但不参与候选排序，也不会单独触发失败。夹爪
carrier 和通过 `A1Z_PHYSICAL_GRASP_BLOCKING_BODY_PATHS` 显式配置的危险体属于
blocking contact，必须触发安全停止；需要防护的其他机器人碰撞体应加入该环境
变量。

接触冲量换算出的左右法向力是闭环主反馈，并分别做滑动窗口中值滤波。
`get_dof_projected_joint_forces()` 的夹爪轴投影载荷和 drive 目标相对实测位置的
滞后提供受限的阻力后备信号：运行时先在无物体接触的自由运动阶段估计载荷
基线，再计算基线扣除后的 residual。只有双侧已经接触同一个目标、左右 residual
都超过阈值、左右命令滞后也都超过阈值时，较弱侧 residual 才能作为
`effective_grip_force_n`；单侧接触或空载阻力不能宣布抓取成功。

必须显式检查：

- `physics_dt` 有效、有限且大于 0；
- 左右指尖都接触同一个自动发现的动态刚体；
- 两侧力分别可读；
- 接触连续稳定达到 `minimum_stable_frames`；
- 接触过程中没有新增物理 constraint；
- 目标物体的 rigid/kinematic/gravity 状态没有被修改。

### 5.2 FSM 状态

新抓取状态机建议固定为：

```text
IDLE
  -> PRECHECK
  -> SOFT_CLOSE
  -> SEARCH                 （软闭合超时后）
  -> PRELOAD                （双侧目标接触稳定）
  -> HOLDING                （弱侧滤波法向力稳定达到目标）
  -> RELEASING
  -> RELEASED
```

任意阶段遇到 blocking contact、目标接触丢失、超时、非法物理状态或新
constraint，进入 `FAILED`/`ABORTED`，夹爪保持当前安全目标宽度，不得继续盲目
闭合。support contact 不属于 blocking contact；只有支撑接触而没有双指动态物体
接触时，FSM 继续低速搜索，最终按正常 search timeout 失败。

各阶段语义：

| 阶段 | drive profile | 结束条件 |
|---|---|---|
| `PRECHECK` | `HOLD`，保持张开 | 机械臂速度和位置误差稳定 |
| `SOFT_CLOSE` | 低 stiffness / 低 max effort | 双侧目标接触稳定，或进入 search |
| `SEARCH` | 中等 stiffness / effort | 双侧目标接触稳定，或超时失败 |
| `PRELOAD` | `HOLD` | 逐步加压，弱侧滤波力连续达到目标；超时或过力则失败 |
| `HOLDING` | 低速、高阻尼 hold | 双侧接触和目标力持续；掉力则有界补压 |
| `RELEASING` | `FREE` | 张开到 open width 且速度稳定 |

接触宽度 `contact_width_m` 只能来自实际两个夹爪 DOF 的 readback。双侧接触
不是停止闭合的终点：它会把控制从搜索切换到有上限的闭环预紧。初始只增加
很小的预紧量，此后以 `preload_step_m` 逐步收紧，直到弱侧滤波法向力达到
`target_normal_force_n`；夹持中力跌破带滞回的下限时继续补压。总预紧量和
法向力都有限制：

```text
initial_hold_width_m = max(closed_width_m,
                           contact_width_m - preload_delta_m)
next_hold_width_m = max(contact_width_m - maximum_preload_delta_m,
                        current_hold_width_m - preload_step_m)
target_normal_force_n <= filtered_force_n <= maximum_normal_force_n
```

短于 `contact_loss_grace_frames` 的接触采样丢失会保持当前目标，不会立即误报
松脱；超过容错仍然失败。这里的容错只处理传感器/接触求解的瞬时空洞，不允许
用单侧接触继续宣布成功。

所有宽度都必须通过 parallel-jaw mapping 转换回两个独立 DOF，不能假设两个
DOF 的符号或方向相同。

夹指碰撞面必须单独绑定高摩擦物理材料；当前标定为静摩擦 `2.0`、动摩擦
`1.5`、`frictionCombineMode=max`。该材料只绑定两个夹指 collider，不修改被抓
物体、地面或支撑面的物理状态。运行时在每次 physical grasp 前重新校验两侧
binding，任意一侧缺失都拒绝进入闭合，避免悄悄退化为低摩擦抓取。

### 5.3 Controller profile

建议把 profile 独立成版本化 JSON，例如：

```json
{
  "schema_version": 1,
  "controller_profile_id": "a1z_physical_gripper_v1",
  "joint_names": [
    "gripper_finger_left_joint",
    "gripper_finger_rIght_joint"
  ],
  "open_dofs_m": [0.048, -0.048],
  "closed_dofs_m": [0.0, 0.0],
  "drive_type": "force",
  "max_close_velocity_m_s": 0.006,
  "max_command_lead_m": 0.003,
  "virtual_coupling": {
    "center_error_gain": 1.0,
    "maximum_center_correction_m": 0.0015
  },
  "contact": {
    "require_bilateral": true,
    "minimum_stable_frames": 5,
    "force_window_frames": 5,
    "minimum_normal_force_n": 0.05
  },
  "preload": {
    "delta_m": 0.0005,
    "maximum_delta_m": 0.008
  },
  "force_control": {
    "target_normal_force_n": 2.0,
    "maximum_normal_force_n": 12.0,
    "force_hysteresis_n": 0.25,
    "confirm_frames": 5,
    "preload_step_m": 0.00008,
    "contact_loss_grace_frames": 3,
    "force_loss_grace_frames": 6,
    "minimum_effort_residual_n": 0.1,
    "minimum_position_lag_m": 0.0005,
    "unilateral_recovery_timeout_s": 1.2
  }
}
```

`max_close_velocity_m_s` 限制动作速度，`max_command_lead_m` 限制 drive target
相对实测位置可积累的跟踪误差，两者不能混为一谈。负载下某根自由夹指持续精确
落后一个 lead cap 时，应在保持低速度的前提下调整经过标定的 lead、stiffness、
damping 和 max effort。当前 force-drive profile 将 soft/search/hold 的单指
最大力限制为 `10/20/30 N`；位置刚度在 3 mm lead 上分别提供
`3/6/9 N` 的名义静态夹持余量。两指还通过虚拟中心耦合保持同步：单侧接触时
冻结接触指，只让自由指以 0.08 mm 小步追赶，避免对称闭合把小物体横向推出。

profile 中的 open/closed width 必须和实际 articulation readback 的范围一致，
否则启动抓取时立即失败。`calibration_status=legacy_baseline` 只能表示
接口迁移完成，不能表示现场夹爪力已经标定完成。

## 6. AnyGrasp / 规划器迁移

规划器输出必须从“创建 attachment”改为“提供物理闭环的目标和策略”：

```json
{
  "execution_policy": {
    "grasp_mode": "physical_v2",
    "target_body_path": "",
    "target_discovery_mode": "bilateral_contact",
    "controller_profile": "a1z_physical_gripper_v1",
    "timeout_s": 15.0,
    "hold_after_lift_s": 1.0,
    "hold_after_retreat_s": 0.3,
    "release_after_retreat": true,
    "minimum_lift_m": 0.03,
    "minimum_hold_ratio": 0.8
  }
}
```

执行顺序：

1. 捕获当前关节和目标物体 debug 状态；
2. 移动到 approach pose，并确认机械臂已稳定；
3. 调用 `grasp_close_v2`；
4. 等待状态进入 `holding`，不能只依据命令返回；
5. lift/retreat 期间周期读取 `grasp_status_v2`；
6. 验证物体实际上升、双侧接触保持比例达标、物体仍为动态状态；
7. 调用 `grasp_release_v2`，确认进入 `released`；
8. 记录完整的 force、width、phase、target pose 和 constraint audit。

抓取成功至少同时满足：

- close 进入 `holding`；
- `constraint_count_delta == 0`；
- 目标物理状态未改变；
- 物体达到最小 lift 高度；
- lift/retreat 期间双侧接触保持比例达标；
- release 进入 `released`；
- release 后无双侧接触、无 attachment joint、无 attached object。

## 7. D405 和 ROS 迁移要求

D405 不应再由 ROS 节点主动触发一次新的同步渲染。推荐：

- Isaac 6 `RtxCamera` + `CameraSensor`；
- 320×240、10 Hz 独立 RenderProduct；
- CUDA annotator buffer；
- RGB/depth 必须来自同一个完成的 render token；
- ROS 只消费最新完整帧，跳过重复 timestamp；
- sensor-data QoS：keep-last=1、best-effort、volatile；
- zlib level 1，RGB/depth 编码使用独立 worker；
- camera capture 与 arm command 不共用同一把长时间持有的锁。

独立 A1Z 模式下 D405 parent 可以是 `/World/A1Z_G1Z/Geometry`；挂载 Paw
模式下必须在 attachment 前设置为实际的
`/DOG/A1Z_PAYLOAD_MOUNT/A1Z_G1Z/Geometry`。不得把旧路径作为隐式 fallback。

## 8. 迁移实施顺序

### P0：冻结旧行为并建立基线

- 保存当前 A1Z 关节顺序、符号、限位、drive gains 和夹爪 DOF 范围；
- 保存旧 D405 外参、frame ID、RGB-D payload schema；
- 统计旧代码中的 FixedJoint、position teleport、gravity/kinematic mutation；
- 把 `grasp_attach` 标记为 legacy，不再作为新测试的成功条件。

### P1：完成 Isaac 6 资产转换

- 生成 Isaac 6 USDA/USD；
- 单独验证 arm motion、gripper motion、碰撞和动态物体；
- 不加入任何抓取 attachment authoring；
- 先用 standalone `/World/A1Z_G1Z/Geometry` 验收。

### P2：替换 runtime backend

- 加入 Native Isaac 6 adapter；
- 将 stage、articulation、contact 和 drive 操作收敛到主线程；
- 实现 listener readiness、health snapshot 和 60 Hz tick；
- 确认命令线程不能直接修改 USD/PhysX。

### P3：接入接触力反馈闭环

- 实现实际 `physics_dt` 读取；
- 实现左右指尖 contact impulse 归约；
- 实现 parallel-jaw mapping；
- 实现 `PhysicalGraspFSM`；
- 实现 soft-close/search/preload/hold/release profiles；
- 几何和时序验收可以临时使用 `minimum_normal_force_n=null`，但生产抓取必须使用已标定的正阈值。A1Z 当前使用每侧 `0.05 N` 的 loaded-touch 门槛，避免零冲量或擦边碰撞过早锁定接触宽度。

### P4：替换 server 和规划协议

- 增加 `grasp_close_v2`、`grasp_release_v2`、`grasp_status_v2`；
- 让 AnyGrasp 默认输出 `physical_v2`；
- 由双指共同接触自动发现并锁定目标刚体，不依赖感知 prim 路径；
- 禁止 physical_v2 调用 `grasp_attach`；
- 增加 constraint delta 和 target physics mutation 的硬失败条件。

### P5：迁移 D405/ROS

- 切换到 Isaac 6 sensor adapter；
- 验证 RGB/depth 同帧、timestamp 单调和低背压；
- 对拍 intrinsics、extrinsics、frame IDs 和 AnyGrasp 输入；
- 确认 D405 失败会让 runtime health 降级，而不是继续复用旧帧报告 ready。

### P6：可选的 Paw 挂载迁移

- 将 A1Z geometry 合入 Paw world；
- 将 articulation root 改为 `/DOG/Geometry/BASE_LINK`；
- 禁用 A1Z 内部 `root_joint`，避免嵌套 articulation；
- 不拆分 DOG+A1Z contact island 到两个物理进程；
- 验证 A1Z arm motion 对 DOG base 的反作用仍在同一个 PhysicsScene 中。

## 9. 验收门槛

### 运行时

- Isaac 6.0.1 / Kit 110 能加载 USDA；
- A1Z listener 实际 bind 后才报告 ready；
- 60 Hz 控制 tick 持续运行，无 tick failure；
- 关节状态、命令和实际 readback 的顺序及单位一致；
- D405 首帧、RGB-D 同帧和 ROS QoS 探针通过。

### 夹爪自由运动

- open/close 不写 joint state；
- 两个 finger DOF 的位置和速度 readback 有限且连续；
- soft-close/search/hold 三套 profile 均能被实际 drive 使用；
- 夹爪与桌面/地面接触会被识别为 support contact，不会被选成目标；
- 夹爪 carrier 或显式配置的危险体会被识别为 blocking contact。

### 物理抓取

至少执行以下场景：

1. 目标不存在：必须失败；
2. 只有左指接触：必须失败；
3. 只有右指接触：必须失败；
4. 单指或双指接触地面/桌面：不得锁定支撑面，也不得立即失败；
5. 一侧接触支撑面、同时两侧接触同一动态物体：锁定动态物体；
6. 只有支撑接触而没有双侧动态物体接触：继续低速搜索并最终超时失败；
7. carrier 或显式危险体接触：立即失败；
8. 双侧目标接触：进入 preload，但弱侧法向力未到目标时不得进入 holding；
9. holding 后 lift：物体实际上升且无 constraint；
10. holding 中短暂掉力：有界补压并恢复；达到最大预紧仍不足则失败；
11. holding 中持续丢失一侧目标接触：超过容错后进入 failed；
12. release：物体重新受重力，状态为 released；
13. 注入 FixedJoint、kinematic 或 gravity mutation：立即失败。

### 机器可读硬条件

```text
physical_v2 success                 == true
phase after close                   == holding
force_control_active                == true
force_target_reached                == true
resistance_confirmed                == true
constraint_count_delta              == 0
target_physics_state_mutated        == false
attachment_joint_path               == null
attached_object_path                == null
minimum_lift_m                      >= configured threshold
bilateral_hold_ratio                >= configured threshold
phase after release                 == released
```

## 10. 禁止事项和迁移风险

- 不要通过 `FixedJoint`、`PhysicsJoint` 或等效 constraint 宣布抓取成功；
- 不要把目标设为 kinematic、关闭重力或保存/恢复物体位姿来模拟抓取；
- 不要在夹爪运动未稳定时把一次接触记录当作成功；
- 不要用接触 impulse 直接当牛顿力，必须除以实际 `physics_dt`；
- 不要把地面/桌面等 support contact、carrier 接触或其他物体接触混入目标力；
- 不要用 gripper position teleport 作为驱动失败 fallback；
- 不要让 AnyGrasp、ROS 或 GUI 直接写 USD/PhysX；
- 不要在 standalone 路径和 Paw mounted 路径之间静默复用 prim path；
- 不要把 `calibration_status=legacy_baseline` 当作现场力标定已完成。

目前最大的实际风险不是接口迁移，而是夹爪的力、摩擦、碰撞几何和物体
质量/惯量尚未完成现场等价标定。接口验收通过后，仍必须分别做空夹爪、不同
质量物体、不同摩擦材质和 lift/retreat 长时间 hold 验收。

## 11. 交付物清单

迁移完成时，上级 A1Z 目录应至少新增或更新：

- Isaac 6 运行时入口和 Native API adapter；
- `grasping/physical_types.py`；
- `grasping/physical_fsm.py`；
- `grasping/contact_reducer.py`；
- `grasping/parallel_jaw.py`；
- 版本化 gripper controller profile；
- server v2 grasp commands；
- AnyGrasp `physical_v2` execution path；
- D405 Isaac 6 sensor/session adapter；
- standalone 和 mounted 两套明确配置；
- 运行时、接触力、抓取、release 和 constraint audit 测试；
- 一份包含 force、width、phase、target pose 和 release 结果的验收 JSON。

最终判定标准是：A1Z 可以仅靠真实接触、夹爪 drive 和力反馈在 Isaac 6 中
完成 close -> preload -> holding -> lift -> release；整个过程中不创建
attachment，不修改目标物理状态，不依赖位姿 teleport，并且失败时能给出
可诊断的 phase 和 failure reason。
