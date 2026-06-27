# 开放词汇抓取文档集

这组文档服务于当前 A1Z 工作区，目标是把下面这条链路收敛成一套可实施、可迁移、可验收的工程方案：

1. 自然语言指令
2. RGB 画面上的 open-vocabulary grounding / pointing
3. SAM2 或等价分割模块输出 mask
4. mask 与深度融合，恢复目标 3D 描述
5. 抓取候选生成、可执行性筛选与执行

当前仓库的真实状态是：

- 上游 SDK 镜像：`vendor/GALAXEA-A1Z`
- 本地扩展层：`a1z_ext`
- Isaac Sim 5.1 容器环境
- mock / Isaac / SocketCAN 控制链路
- D405 Isaac 运行时 extension
- 非抓取版 open-vocab RGB-D bundle 闭环

并且在当前环境中，当前验证状态应分开看：

- `scripts/verify_open_vocab_data_loop_in_container.sh`
  - 截至 2026-06-09 仍稳定通过
- `scripts/verify_open_vocab_data_loop_from_isaac_in_container.sh`
  - 截至 2026-06-09 已通过专项验证
  - 当前可稳定写出 `observation.json`、`bundle.json`，并恢复出非空 `Object3DDescriptor`

但这仍然只代表：

- 观测层、感知中间对象、bundle 落盘和 Isaac 单帧 RGB-D 接入已经打通
- sample / Isaac 双输入现在都能走通同一条非抓取版 bundle 主干

不代表：

- 已经具备真实 grounding / SAM2
- 已经具备 grasp proposal / executability / grasp FSM
- 已经可以直接做稳定抓取

## 阅读顺序

1. [`OPEN_VOCAB_CURRENT_STATE_AUDIT.md`](./OPEN_VOCAB_CURRENT_STATE_AUDIT.md)
   - 先看当前仓库真实实现到了哪一步，哪些已经验过，哪些只是接口占位。
2. [`OPEN_VOCAB_DATA_LOOP.md`](./OPEN_VOCAB_DATA_LOOP.md)
   - 看当前已经跑通的非抓取版 RGB-D 数据闭环，以及它产出的 bundle 长什么样。
3. [`OPEN_VOCAB_PIPELINE_STAGE_SPEC.md`](./OPEN_VOCAB_PIPELINE_STAGE_SPEC.md)
   - 看你当前 1-5 步 pipeline 如何拆成工程阶段、每阶段输入输出是什么、当前做到哪里、还缺什么。
4. [`OPEN_VOCAB_PIPELINE_WORKPACKAGES.md`](./OPEN_VOCAB_PIPELINE_WORKPACKAGES.md)
   - 看从“现在的 sample / Isaac 闭环”到“可迁移的真机抓取系统”该如何拆工作包、依赖关系和退出条件。
5. [`OPEN_VOCAB_OBSERVATION_LAYER_SPEC.md`](./OPEN_VOCAB_OBSERVATION_LAYER_SPEC.md)
   - 看 Isaac / 真机共享 RGB-D 观测层已经如何落地，以及后续扩展要求。
6. [`OPEN_VOCAB_SIM2REAL_BOUNDARIES.md`](./OPEN_VOCAB_SIM2REAL_BOUNDARIES.md)
   - 看 Isaac 到真机时哪些层必须共用、哪些层只能接口共用、哪些 Isaac 捷径必须禁止进入主路径。
7. [`OPEN_VOCAB_MODULE_OWNERSHIP.md`](./OPEN_VOCAB_MODULE_OWNERSHIP.md)
   - 看功能归属，避免本地语义重新混回 `vendor`。
8. [`OPEN_VOCAB_PHASE1_EXECUTION_PLAN.md`](./OPEN_VOCAB_PHASE1_EXECUTION_PLAN.md)
   - 看“先不用抓取”这一阶段已经完成了什么、剩下什么、退出条件是什么。
9. [`ISAAC_TO_REAL_OPEN_VOCAB_GRASPING_ANALYSIS.md`](./ISAAC_TO_REAL_OPEN_VOCAB_GRASPING_ANALYSIS.md)
   - 看“先在 Isaac 完成 pipeline，再迁移真机”这条路线到底可不可行，以及卡点在哪里。
10. [`OPEN_VOCAB_MODEL_STACK_SPEC.md`](./OPEN_VOCAB_MODEL_STACK_SPEC.md)
   - 看 grounding / segmentation / 3D 恢复 / 后续 grasping 的推荐技术栈。
11. [`OPEN_VOCAB_GRASPING_ARCHITECTURE.md`](./OPEN_VOCAB_GRASPING_ARCHITECTURE.md)
   - 看完整分层、主数据流和模块职责。
12. [`OPEN_VOCAB_GRASPING_DATA_CONTRACTS.md`](./OPEN_VOCAB_GRASPING_DATA_CONTRACTS.md)
    - 看每层传什么对象、字段、坐标系和约束。
13. [`OPEN_VOCAB_GRASPING_GAP_LIST.md`](./OPEN_VOCAB_GRASPING_GAP_LIST.md)
    - 看从“当前已打通的非抓取闭环”到“可执行抓取系统”之间还缺哪些模块、每个模块的责任是什么。
14. [`OPEN_VOCAB_GRASPING_ROADMAP.md`](./OPEN_VOCAB_GRASPING_ROADMAP.md)
    - 看从当前阶段到完整抓取系统的分阶段路线。
15. [`OPEN_VOCAB_GRASPING_EVAL_SPEC.md`](./OPEN_VOCAB_GRASPING_EVAL_SPEC.md)
    - 看怎么验收，不让系统停留在“能跑 demo”。
16. [`OPEN_VOCAB_GRASPING_REFERENCES.md`](./OPEN_VOCAB_GRASPING_REFERENCES.md)
    - 看开源项目和论文参考，以及每类参考在当前项目里该借鉴什么。

## 与现有控制文档的关系

- [`A1Z_SDK_TASK_CONTROL_SPEC.md`](./A1Z_SDK_TASK_CONTROL_SPEC.md) 聚焦“基于 A1Z SDK 做任务执行系统”
- 本文档集聚焦“open-vocab perception 到 grasping pipeline”

两者的分工是：

- `A1Z_SDK_TASK_CONTROL_SPEC.md` 负责下半段：运动执行、IK、约束、状态机和安全边界
- 本文档集负责上半段到中段：语言、grounding、segmentation、3D 恢复、grasp candidate 与 sim2real 边界

## 当前建议

当前不要把重点放在“端到端 VLA 直接抓”。  
先把这条模块化主链做稳，并保持共享语义继续收敛在 `a1z_ext`：

- `FrameSource -> RGBDFrameCapture -> RGBDObservation`
- `TaskSpec -> GroundingCandidate[] -> MaskCandidate[] -> Object3DDescriptor[]`
- `Object3DDescriptor[] -> GraspCandidate[] -> ExecutablePlan -> ExecutionResult`

并且继续遵守三个约束：

- `vendor/GALAXEA-A1Z` 只保留上游镜像角色
- Isaac 专有 D405 运行时留在 `exts/a1z.d405.runtime`
- 共享感知、抓取和任务语义只进入 `a1z_ext`
