# SDK 与 Isaac Joint Sign 语义缺口

## 问题类型

已知问题，当前暂缓处理。

## 现象

真实机器人 SDK 的关节语义，与当前 Isaac / URDF articulation 的关节语义并不完全一致。

当前已知映射为：

```text
joint_sign = [1, 1, -1, 1, -1, 1]
```

即：

- `J1` 同向
- `J2` 同向
- `J3` 反向
- `J4` 同向
- `J5` 反向
- `J6` 同向

这意味着如果把真机 SDK 的 joint state / joint target 直接当成 Isaac articulation 的 joint coordinate 使用：

- `J3`
- `J5`

会出现语义反向。

## 当前结论

1. `joint_sign` 差异是真实存在的。
2. 如果完全不做映射，真机 SDK 语义**不能严格准确**驱动当前仿真。
3. 但也**不能粗暴地**把 `joint_sign` 直接灌进整个 Isaac 内部控制链。

## 已做实验

之前尝试过把 `joint_sign` 直接接入 Isaac 后端，包括：

- 状态读取
- 位置目标
- drive target
- force arm position
- gravity / effort 相关量

结果是控制表现明显变差：

- 简单 move 会超时
- `J5` 会跑到明显不对的位置
- 整体行为比不改更坏

因此，这条试验已经回退，没有保留为当前默认实现。

## 为什么暂缓

当前主线刚解决的是：

- `J5/J6` 腕部物理不稳定
- 抖动
- 卡滞
- 突变

这类问题属于**物理与驱动稳定性**问题。

如果在这个阶段继续把 `joint_sign` 混进 Isaac 内部控制链，会把两个问题耦合在一起：

1. 物理稳定性
2. SDK 语义对齐

这样会让回归判断变得非常差，难以区分到底是：

- 物理参数又坏了
- 还是语义映射层改错了

所以当前决定是：

**先保持仿真内部控制链稳定，再把 sign 问题单独作为“语义适配层”任务处理。**

## 当前风险

当前配置下：

- 仿真可以稳定运动
- 物理表现已恢复

但如果要求：

- `a1zctl`
- ROS motion
- SDK 风格接口

与真实机器人在关节正方向语义上**完全一致**，那么当前实现仍然存在语义缺口。

换句话说：

- 当前适合做稳定控制和物理验证
- 但还不适合宣称“真机 SDK 关节语义与仿真完全等价”

## 后续正确处理方向

正确做法不是修改整条 Isaac 内部控制链，而是新增一层**边界适配层**：

- 对外：保持 SDK / ROS / `a1zctl` 使用真机语义
- 对内：保持 Isaac articulation 使用自身坐标语义
- 在两者边界做一次 `joint_sign` 映射

建议后续单独实现：

1. `sdk_to_isaac_joint_pos()`
2. `isaac_to_sdk_joint_pos()`
3. `sdk_to_isaac_joint_vel()`
4. `isaac_to_sdk_joint_vel()`
5. 明确哪些 torque / effort 量也要映射

并且只允许在以下边界使用：

- 外部命令进入仿真前
- 仿真状态对外输出前

不应把 sign 直接混入：

- articulation 内部物理参数
- drive stiffness / damping
- solver / inertia 逻辑

## 当前处理建议

在这项工作恢复之前，默认策略应保持为：

- 不把 `joint_sign` 直接注入 Isaac 内部物理控制链
- 把它视为一个单独的 SDK-仿真语义适配任务

## 相关背景

- 腕部物理修复文档：
  - [A1Z_J5_J6_PHYSICS_FIX](../A1Z_J5_J6_PHYSICS_FIX.md)
