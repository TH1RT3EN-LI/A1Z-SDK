# 从当前闭环到可执行抓取系统的缺口清单

本文档只回答一个问题：

- 基于当前已经打通的非抓取版 open-vocab RGB-D 闭环，还需要补哪些层，系统才能进入“可执行抓取”阶段

它不是路线图，也不是操作手册。  
它是当前项目的差量清单。

## 1. 当前已经有的基础

当前仓库已经具备：

- `vendor/GALAXEA-A1Z` 上游 SDK 镜像
- `a1z_ext/robots` 统一 backend 分层
- `mock / isaacsim / socketcan` 三类控制后端
- `a1z_ext/interfaces/schemas.py` perception 中间对象
- `a1z_ext/interfaces/observation.py` 统一 RGB-D observation
- `a1z_ext/runtime/frame_sources/*` sample / Isaac 采帧层
- `a1z_ext/perception/*` 非抓取版 bundle 主干
- sample / Isaac 双输入验证脚本

这说明当前已经不是“从零开始搭系统”，而是“补中间层和执行层”。

## 2. 缺口总览

从当前状态到可执行抓取，至少还缺下面六层。

1. 真实 grounding / segmentation
2. 3D 几何增强
3. grasp candidate 层
4. executability filter
5. 抓取状态机
6. 抓后验证与失败分类

## 3. 缺口一：真实 grounding / segmentation

当前状态：

- `grounding.py` 是 deterministic stub
- `segmentation.py` 是 box 派生矩形 mask

必须补齐的内容：

- GroundingDINO 或等价 open-vocab detector
- SAM2 或等价 promptable segmentation
- top-k 候选保留
- score 归一化与筛选
- 失败输出而不是 silent fail

这层的输出仍应保持不变：

- `GroundingCandidate[]`
- `MaskCandidate[]`

否则后续会牵连整个主干返工。

## 4. 缺口二：3D 几何增强

当前状态：

- `object_3d.py` 已能恢复点云、质心、顶部点、主轴和包围盒
- 但仍是 MVP 几何层

必须补齐的内容：

- 稳定支撑面估计
- 法向稳健估计
- 点云去噪与异常值处理
- keepout / 工作空间质量判断
- 低质量点云失败分类

推荐方向：

- 在保留当前 `numpy` 主干的基础上，引入 Open3D 做几何增强

这层输出仍应保持：

- `Object3DDescriptor[]`

## 5. 缺口三：grasp candidate 层

当前状态：

- 仓库里还没有 `GraspCandidate`
- 也没有“从目标 3D 描述生成抓取候选”的模块

必须新增：

- `a1z_ext/grasping/proposal_topdown.py`
- `GraspCandidate` schema

MVP 至少应输出：

- `pregrasp_pose`
- `grasp_pose`
- `lift_pose`
- `approach_axis`
- `gripper_opening_m`
- `score`
- `source_policy`

当前最务实的第一版应是：

- 规则式 top-down grasp

而不是一上来就上学习式 6-DoF grasp 网络。

## 6. 缺口四：executability filter

当前状态：

- 上游 SDK 提供 IK 基础
- 当前本地项目没有独立的任务级可执行性筛选层

必须新增：

- `a1z_ext/grasping/executability.py`
- `ExecutablePlan` schema

至少要检查：

- pregrasp 是否可达
- grasp 是否可达
- lift 是否可达
- retreat 是否可达
- joint margin 是否足够
- 与当前姿态的连续性
- 桌面 / 相机 / 支架 keepout

注意：

- 不能把“IK 有一个解”直接等价成“计划可执行”

## 7. 缺口五：抓取状态机

当前状态：

- 控制后端已存在
- 任务级抓取执行器不存在

必须新增：

- `a1z_ext/task/grasp_fsm.py`

MVP 状态至少应包括：

- `OpenGripper`
- `MoveToPregrasp`
- `Approach`
- `CloseGripper`
- `Lift`
- `Retreat`
- `Verify`
- `Failed`
- `Done`

并且每个状态都要有：

- 进入条件
- 退出条件
- 超时条件
- 错误提升规则

## 8. 缺口六：抓后验证与失败分类

当前状态：

- 没有 `ExecutionResult`
- 没有结构化成功 / 失败判定

必须新增：

- `a1z_ext/task/verification.py`
- `ExecutionResult` schema

至少要有：

- 成功 / 失败
- `failure_stage`
- `failure_reason`
- 是否可重试
- 重试使用哪个下一个候选

最小抓后验证可先依赖：

- 夹爪闭合后开口变化
- 目标是否离开支撑面
- 原位目标是否仍然存在

## 9. 额外缺口：真机 perception adapter

虽然这不属于“抓取执行层”，但如果目标是 sim2real，就还缺：

- `realsense_d405` 或等价真机 RGB-D frame source
- 标定版本管理
- 真机采帧健康检查

否则系统只能在 Isaac 内闭环，不能真正进入“同一上位机迁移真机”的阶段。

## 10. 推荐补齐顺序

最合理的实现顺序是：

1. 收口 Isaac frame source 稳定性
2. 新增真机 RGB-D frame source
3. 替换真实 GroundingDINO / SAM2
4. 增强 `Object3DDescriptor`
5. 新增 `GraspCandidate`
6. 新增 `ExecutablePlan`
7. 新增 grasp FSM
8. 新增 `ExecutionResult`

顺序不要反。

## 11. 当前不该做的事

当前不建议：

- 把 Isaac 真值直接塞进共享抓取主链
- 直接做端到端 VLA 控制
- 先接复杂 grasp 网络，再补基础几何和执行层

因为你现在缺的是：

- 中间对象
- 任务执行边界
- 可执行性与失败语义

不是又一层更黑的模型。

## 12. 结论

当前项目离“可执行抓取系统”并不差在底层控制，而是差在中间层。

最准确的差量表述是：

- perception bundle 主干已存在
- 抓取候选层不存在
- 可执行性层不存在
- 任务执行层不存在
- 抓后验证层不存在

后续开发应该围绕这四层继续推进。
