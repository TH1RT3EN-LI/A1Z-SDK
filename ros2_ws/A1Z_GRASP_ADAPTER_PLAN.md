# A1Z Grasp Adapter 规划

本文档只描述 A1-Z 抓取适配层的设计计划，不修改 ROS motion 或抓取执行代码。

## 问题

当前 motion 栈只有一个低层末端位姿 action：

- `/a1z/move_ee`
- 输入：一个 `geometry_msgs/PoseStamped`
- 行为：对一个目标位姿求一次 IK，然后下发一个关节空间命令

这个接口不适合直接承接 OWG 或三维目标点。一个 3D 点只定义末端位置，
没有定义腕部姿态；如果直接把 XYZ 或任意完整 pose 发给 IK，J4/J5/J6
可能会被解到接近限位、发生腕部翻转，或者得到不连续的多圈解。

## 设计目标

在感知/OWG 输出和 `/a1z/move_ee` 之间增加一个 grasp adapter。adapter
负责生成抓取姿态候选、筛选 IK 解、选择轨迹 waypoint；`/a1z/move_ee`
继续作为低层运动原语。

```text
Object3DDescriptor / OWG grasp candidate
  -> A1Z grasp adapter
  -> 多个 6D grasp pose 候选
  -> IK 筛选和评分
  -> pregrasp / descend / close / lift waypoint
  -> 低层运动执行
```

## 输入

第一版直接复用现有 perception descriptor：

- `centroid_xyz`
- `top_point_xyz`
- `support_plane_normal_xyz`
- `local_surface_normal_xyz`
- `principal_axes`
- `bbox_extent_xyz_m`
- 可选 OWG 风格 `grasp_angle`
- 可选夹爪开口提示

## 第一版模式

先只支持保守桌面俯抓。

- approach 方向：在 `robot_base_frame` 下近似竖直向下
- gripper yaw：来自物体主轴或 OWG `grasp_angle`
- roll/pitch：使用固定俯抓姿态模板
- yaw 采样：在首选 yaw 附近采样 `0, +/-30, +/-60, 90` 度
- waypoint：
  - pregrasp：物体上方
  - descend：下降到抓取高度
  - close：闭合夹爪
  - lift：竖直抬起

不要把原始 3D 点直接发给 IK。

## 候选过滤

任一 waypoint 出现以下情况就拒绝该候选：

- IK 不收敛
- 超过软关节限位
- 软限位余量太小
- 相对当前关节角跳变太大
- J4/J5/J6 跳变过大
- J5 太接近腕部 pitch 限位
- waypoint 之间关节轨迹不连续
- 后续接入 planning scene 后，碰撞检测失败

## 初始评分

分数越低越好。

```text
score =
  1.0 * total_joint_motion
  + 3.0 * wrist_joint_motion
  + 5.0 * soft_limit_penalty
  + 5.0 * j5_limit_penalty
  + 3.0 * waypoint_discontinuity_penalty
  + 100.0 * ik_failure_or_residual_penalty
  + 100.0 * collision_penalty
```

第一版可以先对 IK 失败做硬拒绝，collision penalty 等有 planning scene 后再接。

## 后续接口

推荐新增 ROS action：

- action：`/a1z/pick_object`
- 输入：object descriptor ID 或显式 object pose descriptor
- 输出：选中的 grasp pose、关节 waypoint、执行结果

也可以先做非 ROS Python helper：

- 目录：`a1z_ext/grasping/`
- 用于脚本和 open-vocabulary pipeline 调用

## 实施顺序

1. 验证 Isaac 中 J1-J6 的坐标方向一致性，重点看 J3/J5。
2. 用 position-only Target EE 稳定调试工作空间。
3. 增加纯 Python grasp candidate generator。
4. 使用现有 control URDF 增加 IK 筛选和评分。
5. 增加 dry-run CLI，只打印候选和分数，不移动机械臂。
6. 稳定后再通过 `/a1z/move_ee` 或直接关节命令执行。
7. top-down 模式稳定后，再接碰撞检测和更丰富的抓取模式。

## 第一版不做

- 通用 6D grasp synthesis
- 学习式抓取生成
- 让 VLM 自由输出腕部姿态
- 自动碰撞感知轨迹规划
- 修改现有 `/a1z/move_ee` action contract
