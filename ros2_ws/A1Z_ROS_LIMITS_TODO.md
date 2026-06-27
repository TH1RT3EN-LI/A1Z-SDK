# A1Z ROS2 Limit Handling TODO

本文档记录 ROS2 侧后续需要补齐的限位工作。当前变更只落实 Isaac backend 与 USD/URDF 资产侧，未修改 ROS2 motion executor 代码。

## 当前边界

- Isaac backend 已作为执行兜底层：
  - 目标关节角按 Galaxea 最新软件控制范围裁剪。
  - 关节速度按额定速度限速。
  - torque feedforward 按 SDK torque clip 裁剪。
  - Isaac/USD articulation 使用 Galaxea 最新硬件限位。
- ROS2 目前仍只做现有 IK 结果检查和 `joint_margin_rad`、`max_joint_step_rad` 约束。
- ROS2 代码没有在本轮改动。

## 后续 ROS2 应做

1. 统一读取限位配置
   - 从 `a1z_ext/config/control_defaults.json` 读取：
     - `arm_soft_joint_limits_deg`
     - `arm_hard_joint_limits_deg`
     - `arm_rated_velocity_rad_s`
     - `arm_peak_velocity_rad_s`
   - 避免 ROS2、URDF、Isaac backend 各自维护一份不同参数。

2. IK 前置检查使用软件限位
   - 当前 ROS2 通过 Pinocchio model lower/upper 做检查。
   - 后续应明确使用 `arm_soft_joint_limits_deg` 加 `joint_margin_rad`。
   - 如果 IK 解接近硬限位但仍在软限位外，应在 ROS2 层直接 reject，不交给 backend clip。

3. 路径与速度约束
   - `MoveEndEffector` 目标应在规划阶段限制单关节速度。
   - 轨迹插值要按 minimum-jerk 峰值速度计算 duration，避免中点瞬时速度超过额定速度。
   - `speed` 字段需要明确语义：全局 joint speed cap，还是任务级缩放系数。

4. 错误语义
   - 区分这些失败原因：
     - IK 不收敛
     - 超出软件限位
     - 过近硬件限位
     - 单步关节变化过大
     - 速度要求过高
   - action result 中应保留具体 joint index、目标角、允许范围。

5. 状态可观测性
   - ROS2 节点应能暴露当前生效限位：
     - software limits
     - hard limits
     - velocity limits
   - 建议通过参数 dump、diagnostics 或 `/a1z/limits` service 暴露。

## 推荐原则

- ROS2 是规划和任务安全层：负责提前 reject 不合理目标。
- Isaac backend 是执行兜底层：负责所有入口最终 clamp/rate-limit。
- USD/URDF 是物理模型层：Isaac 版本使用硬限位，control/IK 版本使用软件限位。

