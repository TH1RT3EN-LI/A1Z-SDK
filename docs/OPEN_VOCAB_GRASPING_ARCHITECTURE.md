# 开放词汇抓取系统架构

本文档定义当前 A1Z 项目上的开放词汇抓取系统架构。

目标不是做一个“大模型直接输出动作”的黑盒，而是做一条可解释、可替换、可验证的模块化 pipeline。

## 1. 设计目标

系统应支持：

- 输入自然语言抓取指令
- 使用单目 RGB-D 观测进行开放词汇目标定位
- 在没有为每个类别专门训练的前提下完成目标分割
- 从深度和 mask 恢复稳定的 3D 抓取描述
- 生成可执行的抓取候选
- 通过 A1Z SDK 驱动 mock / Isaac / 真机后端执行
- 在执行后验证抓取成功与失败

系统不应假设：

- “只要找到了物体中心就能抓”
- “只要 IK 有解就能执行”
- “仿真可行就一定真机可行”
- “夹爪闭合就一定抓成功”

## 2. 关键设计原则

### 2.1 LLM 只负责语义，不直接负责控制

自然语言模型负责：

- 解释用户意图
- 做对象指代消解
- 给下游生成结构化任务目标

自然语言模型不直接负责：

- 输出关节值
- 输出末端位姿
- 输出低层执行时序

### 2.2 视觉、几何、抓取、执行分层

这四件事必须拆开：

- 找到目标
- 恢复目标几何
- 生成抓取候选
- 验证候选是否可执行

任何两层混在一起，后面都会难以调试。

### 2.3 默认使用“候选集 + 重排序”，不做单一路径赌死

系统不应只输出单个：

- box
- point
- mask
- grasp pose

而是应输出：

- top-k grounding candidates
- top-k masks
- top-k grasp candidates

最后再做执行筛选。

### 2.4 执行链必须有闭环

系统必须有：

- 前置可执行性筛选
- 执行状态机
- 抓后验证
- 失败分类与重试策略

否则它只是一个“生成动作命令的感知 demo”。

## 3. 推荐总架构

```text
User Instruction
    ->
Task Interpretation Layer
    ->
Grounding Layer
    ->
Segmentation Layer
    ->
3D Object Recovery Layer
    ->
Grasp Proposal Layer
    ->
Executability Filtering Layer
    ->
Task Execution State Machine
    ->
Post-Grasp Verification Layer
```

## 4. 模块分层

## 4.1 Task Interpretation Layer

职责：

- 解析自然语言任务
- 做语义归一化
- 生成结构化任务对象

输入：

- 用户自然语言
- 当前视觉上下文摘要

输出：

- `TaskSpec`

建议实现：

- 当前阶段使用 LLM/VLM 做结构化抽取
- 输出必须是 schema 约束过的 JSON，而不是自由文本

参考：

- [VIMA](https://arxiv.org/abs/2210.03094)
- [OpenVLA](https://arxiv.org/abs/2406.09246)

为什么只是参考：

- 这两类工作说明“语言 + 视觉 -> 操作任务”是可行方向
- 但它们更适合作为长期统一策略模型参考，不适合当前直接替代你现有 SDK 控制栈

## 4.2 Grounding Layer

职责：

- 在 RGB 图像上根据自然语言找目标
- 输出多候选 box / point，而不是单个结果

输入：

- RGB 图像
- `TaskSpec.target_object`

输出：

- `GroundingCandidate[]`

推荐主方案：

- Grounding DINO

推荐增强方案：

- Grounded SAM 2 的 image pipeline

原因：

- `GroundingDINO` 是稳定的 open-set grounding 基线
- `Grounded-SAM-2` 已经把 grounding + segmentation + tracking 串成可复用流水线

参考：

- [Grounding DINO GitHub](https://github.com/IDEA-Research/GroundingDINO)
- [Grounded SAM 2 GitHub](https://github.com/IDEA-Research/Grounded-SAM-2)

## 4.3 Segmentation Layer

职责：

- 根据 point / box / mask prompt 得到候选 mask
- 为每个 mask 输出质量评分

输入：

- RGB 图像
- `GroundingCandidate`

输出：

- `MaskCandidate[]`

推荐主方案：

- SAM 2 image predictor

推荐实践：

- 同时支持 box prompt 与 point prompt
- 支持把 Grounding DINO 的框作为第一阶段提示
- 保存原始 logits / scores，方便后处理

参考：

- [SAM 2 官方页面](https://ai.meta.com/research/sam2/)
- [SAM 2 论文](https://arxiv.org/abs/2408.00714)

## 4.4 3D Object Recovery Layer

职责：

- 将 mask 投影到深度图
- 恢复目标点云
- 求取支撑面、法向、中心点、顶面点、可抓区域

输入：

- 深度图
- 内参
- `MaskCandidate`
- 相机外参

输出：

- `Object3DDescriptor`

推荐几何工具：

- Open3D

原因：

- 当前阶段你需要的是稳定、透明的几何处理，而不是黑盒 pose net
- Open3D 足够覆盖：
  - 点云恢复
  - 法向估计
  - 平面分割
  - 裁剪与过滤

参考：

- [Open3D 论文](https://open3d.org/paper.pdf)
- [Open3D 点云文档](https://www.open3d.org/docs/latest/jupyter/geometry/pointcloud.html)

## 4.5 Grasp Proposal Layer

职责：

- 从 `Object3DDescriptor` 生成一组抓取候选

输入：

- `Object3DDescriptor`
- 夹爪基础约束
- 任务语义约束

输出：

- `GraspCandidate[]`

建议分两条路线：

### 路线 A：规则式 top-down grasp

用于 MVP。

特点：

- 桌面场景
- 单相机
- 单目标
- 不估尺寸也能先做

输出：

- pregrasp pose
- grasp pose
- lift pose
- approach vector
- gripper opening

### 路线 B：学习式 6-DoF grasp proposal

用于后续增强。

候选参考：

- Contact-GraspNet
- GPD
- GraspNet baseline

注意：

- 这些方法通常假设更完整的点云或特定数据分布
- 不应在你现阶段直接替换规则式 MVP

参考：

- [Contact-GraspNet GitHub](https://github.com/NVlabs/contact_graspnet)
- [GPD GitHub](https://github.com/atenpas/gpd)
- [GraspNet-1Billion 论文](https://openaccess.thecvf.com/content_CVPR_2020/papers/Fang_GraspNet-1Billion_A_Large-Scale_Benchmark_for_General_Object_Grasping_CVPR_2020_paper.pdf)

## 4.6 Executability Filtering Layer

职责：

- 判断抓取候选是否能由 A1Z 后端执行

输入：

- `GraspCandidate[]`
- 当前机器人状态
- 机器人约束模型

输出：

- `ExecutablePlan | failure`

必须检查：

- pregrasp 是否 IK 可达
- grasp 是否 IK 可达
- lift 是否 IK 可达
- retreat 是否 IK 可达
- 关节限位裕量
- 末端桌面碰撞风险
- 相机/支架禁入区
- 与当前姿态的跳变大小

这一层应该调用：

- 上游 `a1z` 的 IK / dynamics 能力
- 本地 `a1z_ext` 的约束和策略逻辑

## 4.7 Task Execution State Machine

职责：

- 执行完整抓取任务

推荐状态：

- `Idle`
- `AcquireTarget`
- `OpenGripper`
- `MoveToPregrasp`
- `Approach`
- `CloseGripper`
- `Lift`
- `Retreat`
- `Verify`
- `Done`
- `Failed`

执行入口应落在：

- `a1z_ext/task/`

执行面不应继续堆在：

- 单个 CLI 文件
- Isaac 启动脚本
- demo 脚本

## 4.8 Post-Grasp Verification Layer

职责：

- 判断抓取是否成功

输入：

- 执行结果
- 夹爪状态
- 抬升后视觉观测

输出：

- `ExecutionResult`

最小可用验证：

- 夹爪闭合后开口是否合理
- 抬升后目标是否离开支撑面
- 原位置是否仍残留同一目标大面积 mask

参考：

- [OK-Robot](https://ok-robot.github.io/)
- [OWG](https://github.com/gtziafas/OWG)

这些工作都强调：真正决定成功率的，不只是 grounding，而是中后段执行与失败恢复。

## 5. 与当前仓库的映射

## 5.1 当前已有模块

- `vendor/GALAXEA-A1Z`
  - 上游 SDK
- `a1z_ext`
  - 本地 backend / server / config 扩展
- `exts/a1z.d405.runtime`
  - D405 运行时 extension

## 5.2 建议新增模块

```text
a1z_ext/
  perception/
    task_interpreter.py
    grounding.py
    segmentation.py
    object_3d.py
  grasping/
    proposal_topdown.py
    proposal_ranker.py
    executability.py
  task/
    grasp_fsm.py
    retry_policy.py
  interfaces/
    schemas.py
```

## 5.3 运行时边界

建议保留三层：

- 感知与任务规划层
- 机器人服务层
- 后端适配层

不要把感知模型推理直接塞进 `a1zctl` 或 `RobotServer`。

## 6. 推荐技术栈

### 6.1 主语言

- Python 3.11

### 6.2 仿真与运行时

- Isaac Sim 5.1
- 独立 SDK venv

### 6.3 几何与机器人学

- NumPy
- Open3D
- Pinocchio
- 上游 `a1z`

### 6.4 模型层

- Grounding DINO
- SAM 2
- 可选 Grounded-SAM-2

### 6.5 后续探索层

仅作为后续，不作为当前主路径：

- OpenVLA
- VIMA
- FoundationPose
- OnePose
- OWG
- OVAL-Grasp

## 7. 为什么当前不建议直接上端到端 VLA

当前阶段不建议把 OpenVLA / VIMA 当主控制系统，原因不是它们不强，而是它们解决的问题和你当前项目边界不完全一致：

- 你已经有可用的 SDK 控制链
- 你需要的是稳定抓取任务闭环，而不是直接学习动作 token
- 真机安全、限位、异常恢复仍然需要可解释的约束层

因此更合理的路径是：

- 先做模块化开放词汇抓取
- 再把 VLA 当成高层策略建议器或未来替代方向

## 8. 核心结论

对于当前 A1Z 项目，最稳妥的方案不是“让一个模型从语言直接输出动作”，而是：

- 用开放词汇模型解决“找什么”
- 用 SAM2 解决“框住什么”
- 用几何恢复解决“它在 3D 的哪里”
- 用规则式或学习式 grasp proposal 解决“怎么抓”
- 用 SDK 约束层解决“能不能抓”
- 用状态机解决“按什么阶段抓”
- 用抓后验证解决“到底抓没抓到”

这条架构与当前仓库的控制栈、仿真栈和工程边界是兼容的。

