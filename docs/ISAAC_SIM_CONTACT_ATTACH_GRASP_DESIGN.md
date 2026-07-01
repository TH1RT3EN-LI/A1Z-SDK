# Isaac Sim 接触后 Attach 抓取设计

本文档定义当前 A1Z 项目里，Isaac Sim backend 使用“接触判定后 attach”完成并联夹爪抓取的工程设计。

目标不是构建一套长期共享到真机的抓取物理抽象，而是为当前 Isaac 抓取执行层提供一条：

- 可实现
- 可调试
- 高成功率
- 明确与真机边界隔离

的 sim-only 抓持方案。

结论先行：

- **推荐方案是：低力软闭合 + 目标接触判定 + sim-only fixed joint attach + release 时 detach**
- **attach 逻辑必须留在 Isaac backend 内，不进入共享 perception / grasping 主链**
- **执行层需要把“普通 gripper close”和“sim grasp close”分开建模**

## 1. 问题定义

当前 A1Z Isaac 抓取执行存在下面几个特征：

- 真实夹爪语义接近“开/关”，没有独立力传感闭环
- Isaac 侧夹爪实际上是两个 prismatic finger joint
- 当前控制是 position target 驱动，夹爪增益和最大力较高
- 纯靠手指碰撞与摩擦时，轻小物体容易被闭合过程横向顶走

当前目标不是研究高保真抓持接触力学，而是让系统能稳定完成：

- 接近目标
- 闭合抓持
- 抬升目标
- 继续执行后续搬运动作

因此当前最合理的工程目标是：

- 在闭合阶段仍保留物理接触判定
- 在确认抓住后，不再把搬运稳定性完全押在摩擦上

## 2. 设计边界

## 2.1 必须满足的约束

- 不改真实机器人控制协议
- 不把 Isaac 真值捷径注入共享 perception 主链
- 不要求上层 plan 直接操作 stage / prim
- attach / detach 生命周期必须显式可见、可记录、可恢复

## 2.2 明确的非目标

本设计不解决：

- 真机抓取成功判定
- 真实夹爪力控
- 泛化到所有末端执行器
- 高保真柔顺接触建模
- 多物体同时抓取

## 2.3 sim2real 边界

本设计是明确的 Isaac 专有能力：

- 允许使用 Isaac/PhysX 接触状态
- 允许在接触成立后创建 sim-only 物理约束
- 不要求该约束语义可迁移到真机

这不属于共享 grasping 主链，而属于 backend 专有执行增强。

## 3. 推荐总体方案

推荐流程：

1. 夹爪以低速、低力、软参数开始闭合
2. 运行时轮询目标与左右指的接触状态
3. 当目标满足接触成立条件时，停止继续深度闭合
4. 在目标刚体与夹爪载体 link 之间创建 `UsdPhysics.FixedJoint`
5. attach 成功后将夹爪切入低应力 hold
6. lift / retreat / move 阶段依赖 fixed joint 保持抓持
7. release 阶段删除 fixed joint，并恢复碰撞状态

推荐 attach 的本质是：

- 闭合前半段用物理接触判断“是否抓到”
- 闭合后半段用物理约束保证“搬运不掉”

## 4. 为什么选择 FixedJoint

候选实现主要有三类：

### 4.1 方案 A：FixedJoint attach

做法：

- 目标接触成立后
- 在夹爪 carrier body 与目标 rigid body 间创建 `UsdPhysics.FixedJoint`

优点：

- 目标仍保持 rigid body 身份
- 比每帧手动跟随 pose 更自然
- 可显式 attach / detach
- 后续日志和调试更清晰

缺点：

- 需要处理 attach 后持续接触抖动
- 需要清理 joint 生命周期

### 4.2 方案 B：切为 kinematic 并每帧跟随

优点：

- 最简单
- 最稳

缺点：

- 物理表现太假
- 与环境交互差
- 后续如要评估 grasp quality，价值有限

### 4.3 方案 C：只做软闭合，不 attach

优点：

- 最接近真实纯物理

缺点：

- 当前物体集合和夹爪形态下稳定性不足
- 抬升阶段掉落风险高

结论：

- **当前最优工程方案是 A：FixedJoint attach**

## 5. 系统分层与职责

## 5.1 机器人 backend 层

主实现位置：

- `a1z_ext/robots/isaacsim_robot.py`

职责：

- 管理接触判定
- 管理 attach / detach 生命周期
- 管理 sim-only grasp state
- 屏蔽 stage / prim / joint 细节

不应把这些逻辑放到：

- `execute_a1z_plan.py`
- 通用 plan schema 层
- perception / grasping 模块

## 5.2 CLI / 执行脚本层

主位置：

- `scripts/execute_a1z_plan.py`

职责：

- 在适当阶段调用“普通关闭夹爪”或“sim grasp close”
- 记录结构化执行结果

不负责：

- 直接读接触
- 直接创建 joint
- 直接操作 stage

## 5.3 数据契约层

当前建议只扩充执行结果，不修改 perception 主链对象。

建议新增或补充：

- `ExecutionResult` 中的 sim grasp 字段
- 可选的 `ExecutablePlan.execution_policy`

## 6. 抓取状态机设计

## 6.1 新增状态

建议在 Isaac backend 内部增加下面几个 grasp 子状态：

- `idle`
- `closing_for_grasp`
- `contact_candidate`
- `attached`
- `releasing`
- `failed`

这是一层 backend 局部状态，不要求暴露成上层全局任务状态机。

## 6.2 状态转换

```text
idle
  -> closing_for_grasp
  -> contact_candidate
  -> attached
  -> releasing
  -> idle
```

异常分支：

```text
closing_for_grasp -> failed
contact_candidate -> failed
attached -> failed
releasing -> failed
```

## 6.3 上层任务状态映射

在现有任务层里，仍保持：

- `OpenGripper`
- `Approach`
- `CloseGripper`
- `Lift`
- `Retreat`
- `Verify`

其中 `CloseGripper` 在 Isaac backend 下可映射成：

- `sim_grasp_close_and_attach`

而在真机或 mock 下仍映射成：

- 普通 `command_gripper(close_value)`

## 7. 接触判定设计

## 7.1 推荐判定目标

attach 不应在“任意接触”时触发，而应尽量满足：

- 接触对象是期望抓取目标
- 接触发生在夹爪指部区域
- 接触在短时间窗内稳定持续

## 7.2 接触来源优先级

推荐优先级：

1. 显式 contact sensor
2. 直接读取 PhysX contact pairs
3. 位置停滞近似

当前最优设计目标是：

- **优先使用 Isaac/PhysX 的真实接触信息**

不建议仅靠“夹爪卡住不动”判断抓住，因为这无法区分：

- 抓到目标
- 顶到桌面
- 顶到别的障碍物

## 7.3 最小接触判定规则

建议最小版本使用下面规则：

- 已知本次抓取的 `target_prim_path`
- 在闭合时间窗内，检测到：
  - 左指与目标接触
  - 右指与目标接触
- 且两个接触事件出现在同一短时间窗内

推荐时间窗：

- `contact_window_s = 0.10 ~ 0.25`

推荐稳定计数：

- 连续 `N = 3 ~ 6` 次控制周期满足条件

若暂时拿不到双侧接触，可退化成：

- 一侧指接触目标
- 另一侧指距离目标很近
- 夹爪继续闭合几乎不再收拢

但这只能作为降级策略，不应作为默认主路径。

## 7.4 目标对象识别

attach 必须显式知道当前要抓哪个对象。

建议来源优先级：

1. `ExecutablePlan` 明确给出 `target_prim_path`
2. grasp candidate 关联到 scene object id，再映射到 prim path
3. 运行时根据 grasp pose 邻近目标反查

当前最佳工程方案是：

- **让 plan 显式携带 `target_prim_path`**

这样接触判定、attach、verify、release 都更简单。

## 8. Attach 目标与约束挂点

## 8.1 被 attach 的目标

被 attach 的应是：

- 目标物体的 rigid body 根 prim

而不是：

- 某个子 mesh prim
- 视觉 prim
- 仅几何节点

必须先解析出目标物体真正承载 `RigidBodyAPI` 的 prim。

## 8.2 夹爪侧挂点

不建议把 fixed joint 直接挂在单侧 finger link。

推荐挂点：

- 夹爪公共载体 link
- 当前结构里最合适的是手指的共同父体，也就是 wrist 末端的承载刚体

原因：

- attach 到单侧手指会放大偏载
- 左右手指仍会有独立局部相对运动
- attach 到共同 carrier 更稳定

当前仓库里推荐挂点应解析为：

- `arm_link6` 末端承载刚体
- 或一个明确指定的 `gripper_base_body_path`

最终不要在多处推断，应该在 backend 内集中解析一次并缓存。

## 8.3 Joint Prim 路径

建议在 world 下建立专用容器：

- `/World/SimulationGraspAttachments`

每次 attach 创建：

- `/World/SimulationGraspAttachments/<execution_or_plan_id>_<object_name>`

这样便于：

- 调试
- 日志追踪
- 清理残留 joint

## 9. Attach 成功后的控制策略

attach 一旦建立，必须立刻降低局部应力。

建议顺序：

1. 读取当前 finger DOF
2. 将 gripper target 固定为当前值
3. 切换到低力 hold 参数
4. 记录 `attached_object_path` 与 `attachment_joint_path`

推荐 attach 后的夹爪参数：

- 低 stiffness
- 低 max force
- 不再继续向完全闭合目标推进

目的不是继续“夹紧”，而是避免：

- 手指持续穿挤物体
- fixed joint 与接触求解互相打架

## 10. 碰撞处理策略

## 10.1 为什么要处理

attach 后最常见的问题不是 attach 本身失败，而是：

- 物体已经被 joint 约束住
- 手指和物体仍持续深接触
- 解算器出现 jitter

## 10.2 推荐策略

推荐分两阶段：

### 阶段一：最小可用版本

先只做：

- attach 后冻结当前夹爪开度
- 降低 hold 力

暂不立即做复杂 collision filtering。

### 阶段二：增强稳定性版本

如抖动明显，再加：

- 临时屏蔽“手指 <-> 已抓目标”的碰撞

release 时恢复。

不建议一开始就把所有相关碰撞过滤做复杂化，因为这会显著增加调试难度。

## 11. Release 设计

release 必须是显式状态机动作，不允许只靠“打开夹爪就算释放”。

推荐 release 流程：

1. 若存在 attach joint，则删除 joint
2. 恢复目标与手指的碰撞配置
3. 清空 backend 内部 attached state
4. 执行 gripper open
5. 等待目标重新回到自由动态状态

若当前没有 attached object，则 release 退化成普通 open。

## 12. 失败模式与恢复

## 12.1 闭合超时

条件：

- 规定时间内未形成合法接触

结果：

- 标记 `grasp_contact_not_found`
- 不创建 attach

## 12.2 接触对象错误

条件：

- 接触发生，但接触对象不是目标 prim

结果：

- 标记 `wrong_object_contact`
- 可选择继续短暂等待或直接失败

## 12.3 Attach 创建失败

条件：

- 接触成立，但 fixed joint 创建失败或 body 解析失败

结果：

- 标记 `attach_creation_failed`
- 保留抓取失败结果

## 12.4 Lift 后掉落

条件：

- attach 看似成功，但 lift 期间目标未跟随或 joint 已失效

结果：

- 标记 `attached_object_lost`

## 12.5 残留 joint

条件：

- 上一次异常中断后 joint 未清理

结果：

- 启动 grasp 前先扫 `/World/SimulationGraspAttachments`
- 清理属于当前 backend session 的残留 joint

## 13. 接口设计

## 13.1 IsaacSimArmRobot 新增公开接口

建议新增：

```python
def grasp_close_and_attach(
    self,
    target_prim_path: str,
    *,
    timeout_s: float = 2.0,
    contact_window_s: float = 0.15,
    require_bilateral_contact: bool = True,
) -> dict[str, Any]:
    ...

def release_attached_object(
    self,
    *,
    open_gripper: bool = True,
    timeout_s: float = 2.0,
) -> dict[str, Any]:
    ...
```

返回结果建议至少包含：

- `success`
- `target_prim_path`
- `attached_object_path`
- `attachment_joint_path`
- `contact_summary`
- `failure_reason`
- `timing`

## 13.2 IsaacSimArmRobot 新增状态查询

建议新增：

```python
def get_sim_grasp_status(self) -> dict[str, Any]:
    ...
```

建议字段：

- `has_attached_object`
- `attached_object_path`
- `attachment_joint_path`
- `grasp_state`
- `last_contact_time`
- `last_failure_reason`

## 13.3 服务层接口

若后续要通过 socket server 暴露，建议新增命令而不是复用普通 `gripper`：

- `grasp_attach`
- `grasp_release`
- `grasp_status`

原因：

- 普通 `gripper` 仍保留“仅开合夹爪”的语义
- sim attach 是另一种执行语义，不应混在一个布尔参数里悄悄改变

## 14. Plan 与 ExecutionResult 扩展

## 14.1 ExecutablePlan 扩展建议

当前 [OPEN_VOCAB_GRASPING_DATA_CONTRACTS.md](./OPEN_VOCAB_GRASPING_DATA_CONTRACTS.md) 里的
`ExecutablePlan.gripper_commands` 仍只有：

- `open_before_grasp`
- `close_after_approach`

这对 sim attach 路径不够，因为它无法表达：

- 本次抓取是否要求 sim attach
- 目标 scene object 是谁
- 接触判定策略是什么

建议为 sim-only 执行增加可选字段：

```json
{
  "execution_policy": {
    "grasp_mode": "sim_contact_attach",
    "target_prim_path": "/World/TrashSet/can_upright",
    "require_bilateral_contact": true
  }
}
```

约束：

- 真机 backend 可忽略该字段
- Isaac backend 读取并执行

## 14.2 ExecutionResult 扩展建议

当前 [OPEN_VOCAB_GRASPING_DATA_CONTRACTS.md](./OPEN_VOCAB_GRASPING_DATA_CONTRACTS.md) 里的
`ExecutionResult` 还没有 backend 专有抓持细节字段。

建议记录：

```json
{
  "backend_execution_details": {
    "grasp_mode": "sim_contact_attach",
    "target_prim_path": "/World/TrashSet/can_upright",
    "attached_object_path": "/World/TrashSet/can_upright",
    "attachment_joint_path": "/World/SimulationGraspAttachments/plan123_can_upright",
    "attach_success": true,
    "attach_failure_reason": null
  }
}
```

## 15. 代码改动点

## 15.1 `a1z_ext/robots/isaacsim_robot.py`

新增职责：

- 解析 finger links
- 解析 gripper carrier body
- 解析目标 rigid body root
- 读取接触状态
- 创建 / 删除 fixed joint
- 维护 sim grasp state

建议新增内部方法：

- `_resolve_gripper_carrier_body_path()`
- `_resolve_target_rigid_body_path(target_prim_path)`
- `_poll_grasp_contacts(target_body_path)`
- `_contact_satisfies_attach(...)`
- `_create_attachment_joint(...)`
- `_remove_attachment_joint(...)`
- `_set_gripper_soft_grasp_gains()`
- `_set_gripper_hold_gains()`

## 15.2 `a1z_ext/robots/server.py`

如要通过服务暴露，则新增：

- `grasp_attach`
- `grasp_release`
- `grasp_status`

## 15.3 `scripts/execute_a1z_plan.py`

在 `approach` 段之后：

- 若 backend 为 Isaac 且 `execution_policy.grasp_mode == sim_contact_attach`
- 调用 `grasp_attach`

否则维持现有：

- `gripper_close`

## 15.4 文档与契约

需要补充：

- `OPEN_VOCAB_GRASPING_DATA_CONTRACTS.md`
- `OPEN_VOCAB_SIM2REAL_BOUNDARIES.md`

但这些属于后续文档一致性收口，不阻塞第一版实现。

## 16. 参数建议

第一版建议参数如下：

- 闭合超时：`1.5 ~ 2.0 s`
- 接触稳定窗口：`0.15 s`
- 连续满足次数：`3`
- 软闭合最大速度：低于当前默认值
- 软闭合最大力：显著低于当前默认值
- attach 后 hold 力：低于闭合阶段

当前代码中的夹爪默认参数偏硬，第一版实现前建议同步引入：

- `soft_grasp_kp`
- `soft_grasp_kd`
- `soft_grasp_max_effort`
- `hold_kp`
- `hold_kd`
- `hold_max_effort`

不要复用当前那组高刚度夹爪默认值。

## 17. 验证计划

## 17.1 单元级验证

至少验证：

- 能解析目标 rigid body
- 能创建 attachment joint
- 能删除 attachment joint
- 残留 joint 能被清理

## 17.2 集成验证

至少验证下面三个场景：

1. 正常抓取单个 TrashSet 物体并 lift
2. 接触到错误物体时不 attach
3. attach 后 release，物体重新成为自由刚体

## 17.3 回归关注点

必须重点看：

- attach 后是否抖动
- lift 后是否掉落
- release 后是否残留 joint
- 失败路径是否卡死在 attached state

## 18. 实施顺序

推荐分三步做。

### 第一步：最小 attach 闭环

- backend 内建 attach state
- 指定 `target_prim_path`
- 接触成立后创建 fixed joint
- release 时删除

先不做复杂 collision filtering。

### 第二步：调参和稳定性增强

- 软闭合参数分组
- attach 后 hold 参数分组
- 必要时加入手指与已抓物体的碰撞过滤

### 第三步：契约与日志补齐

- `ExecutablePlan.execution_policy`
- `ExecutionResult.backend_execution_details`
- verify 脚本和专项日志

## 19. 最终建议

当前最优工程设计结论如下：

- **使用 Isaac backend 专有的 `grasp_close_and_attach()` 能力**
- **attach 触发基于目标接触，不基于纯位置停滞**
- **attach 形式使用 `UsdPhysics.FixedJoint`，不使用每帧手动跟随**
- **attach 后立即冻结当前开度并切低力 hold**
- **release 作为显式动作实现**
- **上层 plan 应显式携带 `target_prim_path` 与 `grasp_mode=sim_contact_attach`**

这套方案的主要价值不是“更真实”，而是：

- 在当前夹爪与物体集合条件下更稳定
- 与现有 A1Z 代码结构兼容
- 调试边界清楚
- 不会把 Isaac 专有捷径污染到共享主路径
