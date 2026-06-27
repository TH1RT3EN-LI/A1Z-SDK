# 开放词汇 Pipeline 工作包与退出条件

本文档把当前路线落实成工作包，而不是继续停留在总架构层。

目标是回答四个问题：

- 现在先做什么
- 每项工作归谁
- 做完算什么叫完成
- 哪些工作可以在 Isaac 里完成，哪些必须为真机预留

## 1. 当前基线

截至 2026-06-09，当前真实基线是：

- sample 非抓取闭环稳定通过
- Isaac D405 非抓取专项 verify 已通过
- Isaac 端 `Object3DDescriptor` 已恢复为非空
- 真实 grounding / SAM2 尚未接入
- 抓取后半段尚未开始实现

因此当前工作包不应该从“抓取动作设计”开始，而应该从“稳定共享输入与中间层”开始。

## 2. 工作包总览

| 编号 | 工作包 | 目标层 | 是否共享 | 当前优先级 |
| --- | --- | --- | --- | --- |
| WP0 | Isaac 观测基线收口 | 观测层 | 否，后端专有 | P0 |
| WP1 | 真机 RGB-D adapter | 观测层 | 接口共享 | P0 |
| WP2 | 任务解释层硬化 | 任务层 | 共享 | P1 |
| WP3 | GroundingDINO 接入 | 感知层 | 共享 | P1 |
| WP4 | SAM2 接入 | 感知层 | 共享 | P1 |
| WP5 | 3D 几何增强 | 几何层 | 共享 | P1 |
| WP6 | top-down grasp MVP | 抓取层 | 共享 | P2 |
| WP7 | executability filter | 规划层 | 共享 | P2 |
| WP8 | grasp FSM 与抓后验证 | 执行层 | 共享 | P2 |
| WP9 | 学习式 grasp / 任务导向增强 | 增强层 | 共享 | P3 |

## 3. WP0：Isaac 观测基线收口

### 目标

让 Isaac D405 路径从“能产出过 bundle”提升到“可重复产出可用几何输入”。

### 归属

- `exts/a1z.d405.runtime`
- `a1z_ext/runtime/frame_sources/isaac_rgbd.py`
- `scripts/verify_open_vocab_data_loop_from_isaac_in_container.sh`

### 必须完成

- 收敛 D405 optical frame 定义
- 收敛 streaming-hosted 采帧时序
- 保证单实例运行约束
- 保证 RGB 画面与有效 depth 区域对齐

### 退出条件

- `observation.json` 稳定产出
- `bundle.json` 稳定产出
- `object_descriptors` 连续多次非空
- 结果不依赖手工调一次就停

### 不该做的事

- 不用 Isaac 真值目标 pose 填补主链
- 不把相机私有修补逻辑写进 `a1z_ext/perception`

## 4. WP1：真机 RGB-D adapter

### 目标

新增一个与 Isaac adapter 同构的真机采帧层。

### 归属

- `a1z_ext/runtime/frame_sources/realsense_rgbd.py`
- 未来 `a1z_ext/runtime/calibration.py`

### 必须完成

- 真机 RGB + depth 同步采帧
- intrinsics 读取
- `camera -> robot_base` 外参版本化
- 设备健康检查
- 产出同结构 `RGBDFrameCapture`

### 退出条件

- 真机路径与 Isaac 路径都能写出同结构 `observation.json`
- `source_backend` 不同，但 schema 不分叉
- 标定版本可追踪

### 风险

- 真机深度空洞
- 标定漂移
- 深度和彩色帧不同步

## 5. WP2：任务解释层硬化

### 目标

把当前轻量 `TaskSpec` 入口固化成稳定任务协议。

### 归属

- `a1z_ext/interfaces/schemas.py`
- `a1z_ext/perception/task_interpreter.py`

### 必须完成

- 明确 `action_type`
- 明确 `target_object`
- 明确 `preferred_grasp_mode`
- 明确 `timeout_s`
- 明确 `safety_profile`

### 退出条件

- mock / Isaac / 真机共用同一 `TaskSpec`
- 后续替换 LLM 只换解释实现，不改 schema

## 6. WP3：GroundingDINO 接入

### 目标

替换当前 heuristic grounding stub。

### 归属

- `a1z_ext/perception/grounding.py`

### 必须完成

- 文本到 top-k bbox 候选
- grounding score 标准化
- 候选可视化保存
- 失败结构化输出

### 退出条件

- `GroundingCandidate[]` schema 不变
- sample / Isaac / 真机统一调用同一包装层
- 歧义输入保留多个候选

### 风险

- 开放词汇类别召回不足
- 长尾描述不稳定

## 7. WP4：SAM2 接入

### 目标

替换当前 box-to-mask stub。

### 归属

- `a1z_ext/perception/segmentation.py`

### 必须完成

- box prompt
- point prompt
- mask 质量分数
- 可回放 mask 产物

### 退出条件

- `MaskCandidate[]` schema 不变
- mask 与 depth 有效区域具备可量化重合
- 低质量 mask 可被过滤

## 8. WP5：3D 几何增强

### 目标

把当前 MVP 几何恢复提升到可支撑抓取候选生成的程度。

### 归属

- `a1z_ext/perception/object_3d.py`

### 必须完成

- 点云去噪
- 桌面平面估计
- 法向估计
- 点云质量评分
- workspace / keepout 基础检查

### 退出条件

- `Object3DDescriptor[]` 在 sample 路径稳定非空
- `Object3DDescriptor[]` 在 Isaac 路径稳定非空
- centroid / top surface / normal 可用于 top-down grasp

### 依赖

- WP0
- WP4

## 9. WP6：top-down grasp MVP

### 目标

在共享语义里第一次把“3D 描述”变成“抓取候选”。

### 归属

- `a1z_ext/grasping/proposal_topdown.py`
- `a1z_ext/interfaces/execution.py` 或等价 schema 文件

### 必须完成

- `GraspCandidate`
- `pregrasp_pose`
- `grasp_pose`
- `lift_pose`
- `approach_vector`
- `gripper_opening_m`

### 退出条件

- 单桌面单目标场景能稳定生成候选
- 候选字段足以送入 IK 与状态机

### 当前策略

先做：

- 规则式 top-down parallel jaw

暂不做：

- 学习式 6-DoF grasp 主路径

## 10. WP7：executability filter

### 目标

把几何候选筛成可执行计划。

### 归属

- `a1z_ext/grasping/executability.py`

### 必须完成

- pregrasp IK
- grasp IK
- lift IK
- retreat IK
- joint margin 检查
- 当前姿态连续性检查
- 桌面 / 相机 / 支架 keepout

### 退出条件

- 输出 `ExecutablePlan`
- 拒绝原因结构化
- mock / Isaac / 真机只换 backend，不换筛选语义

### 关键原则

这一层是把 SDK 的 IK 变成任务系统能力的地方。  
如果没有它，SDK 只能算控制底座，不算抓取系统。

## 11. WP8：grasp FSM 与抓后验证

### 目标

把可执行计划跑成任务结果。

### 归属

- `a1z_ext/task/grasp_fsm.py`
- `a1z_ext/task/verification.py`

### 必须完成

- 状态机
- 超时控制
- backend 异常提升
- 夹爪结果检查
- 目标是否被抬离检查
- 结构化 `ExecutionResult`

### 退出条件

- mock 中 100% 跑通状态迁移
- Isaac 中能完成整套任务链
- 真机中失败能落到明确 stage / reason

## 12. WP9：学习式 grasp 与任务导向增强

### 目标

在 MVP 稳定后增强抓取质量，而不是替代基础结构。

### 候选

- Contact-GraspNet
- GPD
- GraspNet 系方法
- OVAL-Grasp / OWG 风格的 task-oriented grasp

### 前提

只有在 WP0 到 WP8 完成后，这一层才值得开始。

## 13. 依赖顺序

当前合理顺序应固定成：

1. WP0
2. WP1
3. WP2
4. WP3
5. WP4
6. WP5
7. WP6
8. WP7
9. WP8
10. WP9

这里面最容易做错的是：

- 跳过 WP0 直接做 grasp
- 跳过 WP1 直接假设 Isaac 可以零改上真机
- 跳过 WP7 直接把 IK 解送进执行

## 14. 每个工作包的统一交付物

每个 WP 都至少应留下三类产物：

1. 代码模块
2. 可回放产物
3. 验证脚本或回归入口

不能只留下：

- 一段 notebook
- 一个 demo 脚本
- 一次人工截图

## 15. 结论

如果按工作包来排，现在最应该做的是：

- 先把 Isaac 观测基线收口
- 同时为真机补同构 frame source
- 然后再替换 grounding / segmentation

这条顺序看起来保守，但和你当前项目的真实瓶颈是对齐的。
