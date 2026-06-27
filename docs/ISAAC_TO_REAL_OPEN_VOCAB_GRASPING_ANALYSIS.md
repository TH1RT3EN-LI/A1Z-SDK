# Isaac 到真机的开放词汇抓取可迁移性分析

本文档分析当前 A1Z 项目是否适合先在 Isaac Sim 中完成整条开放词汇 pipeline，再迁移到真机执行。

结论先行：

- **作为开发路线：可行**
- **作为系统架构：应该这么做**
- **作为“仿真成功即可零改动上真机”的假设：不成立**

因此，正确目标不是：

- 在 Isaac 里做一个抓取 demo，然后直接照搬到真机

而是：

- 在 Isaac 里完成一套**可迁移的上位机 pipeline**
- 再通过真机 adapter、标定、约束层和任务执行层，把它迁移到真机

## 1. 当前问题定义

你当前要建设的主线是：

1. 自然语言指令
2. 深度相机 RGB 输入给 LLM / VLM，做 box / point grounding
3. pointing / boxing 结果输入 SAM2，得到 mask
4. mask 与深度融合，恢复目标 3D 位置或 3D 描述
5. 抓取

你希望先在 Isaac 中完成整条链，再尽可能直接迁移到真机。

这实际上涉及两个不同目标：

- **目标 A：在 Isaac 中把系统功能闭环做出来**
- **目标 B：让这套系统尽量少改地迁移到真机**

目标 A 可行。  
目标 B 也可行，但只在“模块边界设计正确”的前提下成立。

## 2. 当前仓库已经具备的基础

## 2.1 控制后端已经统一

当前仓库已经形成三类 backend：

- `mock`
- `isaacsim`
- `socketcan`

并统一收敛在：

- [`a1z_ext/robots`](../a1z_ext/robots)

这意味着：

- 上位机任务逻辑不必直接依赖真实 CAN 驱动
- 可以先在 Isaac / mock 上跑通执行逻辑
- 后续切换真机时，理论上只需切换 backend 与少量参数 / adapter

## 2.2 Isaac 端机器人控制不是空壳

当前已有独立 Isaac backend：

- [`a1z_ext/robots/isaacsim_robot.py`](../a1z_ext/robots/isaacsim_robot.py)

它已经支持：

- 关节状态获取
- 关节目标命令
- 夹爪目标命令
- 轨迹执行
- Isaac 主线程内执行控制
- 一定程度的 joint limit 缓存和控制参数配置

这说明 Isaac 端已经具备“作为控制替身”的基础。

## 2.3 统一 RGB-D 观测层已经建立

当前仓库已经有：

- [`a1z_ext/interfaces/observation.py`](../a1z_ext/interfaces/observation.py)
- [`a1z_ext/runtime/frame_sources/base.py`](../a1z_ext/runtime/frame_sources/base.py)
- [`a1z_ext/runtime/frame_sources/sample_rgbd.py`](../a1z_ext/runtime/frame_sources/sample_rgbd.py)
- [`a1z_ext/runtime/frame_sources/isaac_rgbd.py`](../a1z_ext/runtime/frame_sources/isaac_rgbd.py)

这意味着你现在已经不是“以后应该设计一个观测契约”，而是：

- **共享 observation / capture 契约已经落地**

这对 sim2real 至关重要。

## 2.4 Isaac D405 已经能进入共享 perception 主干

当前已经新增并验证：

- [`scripts/run_open_vocab_data_loop_from_isaac.py`](../scripts/run_open_vocab_data_loop_from_isaac.py)
- [`scripts/verify_open_vocab_data_loop_from_isaac_in_container.sh`](../scripts/verify_open_vocab_data_loop_from_isaac_in_container.sh)

这说明当前 Isaac 已经不只是“有个相机资产”，而是已经能：

- 采 RGB
- 采 depth
- 提 intrinsics
- 提 `camera -> target` 外参
- 组统一 observation
- 落统一 bundle

## 2.5 非抓取版感知 bundle 主干已经落地

当前仓库已存在：

- `TaskSpec`
- `GroundingCandidate`
- `MaskCandidate`
- `Object3DDescriptor`
- `PipelineBundle`

并且 sample / Isaac 双输入都能进入同一条 perception 主干。

这件事的意义很大，因为它说明你已经从“口头架构”进入“运行时对象已经存在”的阶段。

## 3. 当前仍然缺失的关键层

虽然控制底座和 observation 主干已经具备，但从“非抓取 perception bundle”到“可执行抓取系统”之间还缺若干层。

## 3.1 缺真正的 grounding / segmentation 实现

当前仓库虽然已有：

- [`a1z_ext/perception/grounding.py`](../a1z_ext/perception/grounding.py)
- [`a1z_ext/perception/segmentation.py`](../a1z_ext/perception/segmentation.py)

但它们当前仍是 stub：

- `grounding.py` 没有接 GroundingDINO
- `segmentation.py` 没有接 SAM2

也就是说：

- 结构和契约存在
- 真实模型能力仍未接入

## 3.2 缺 grasp proposal 层

你当前 pipeline 在第 4 步之后直接写“抓取”，但工程上这一段必须显式拆开：

- 从 `Object3DDescriptor` 生成抓取候选
- 对抓取候选排序
- 产出可执行计划

当前这层不存在。

## 3.3 缺 executability filter

当前控制层有 IK 基础，但没有完整任务级约束层。

也就是还缺：

- pregrasp 是否可达
- grasp 是否可达
- lift 是否可达
- retreat 是否可达
- joint margin 是否足够
- 桌面、相机支架等 keepout 是否安全

这一层如果不补，Isaac 里偶发可行的坏姿态在真机里会直接变成硬风险。

## 3.4 缺抓取状态机

当前你有机器人控制，不等于你有抓取任务执行器。

抓取至少要有：

- `OpenGripper`
- `MoveToPregrasp`
- `Approach`
- `CloseGripper`
- `Lift`
- `Retreat`
- `Verify`

当前这层还没有独立实现。

## 3.5 缺真机 RGB-D adapter

当前 observation 层已经建立，但真机侧还没有：

- `realsense_d405` 或等价 frame source
- 标定版本管理
- 采帧健康检查

所以现在可以说：

- Isaac observation 已接入
- 真机 observation 仍未接入

## 4. 可迁移性的正确理解

## 4.1 什么叫“可迁移”

在当前项目语境下，“可迁移”不应理解为：

- 同一个 demo 在 Isaac 成功一次，真机也应直接成功

而应理解为：

- 同一套上位机模块划分
- 同一套任务对象
- 同一套 observation / bundle 契约
- 同一套 grasp / execution 语义
- 同一套日志与评测方式

在不同 backend 上共享。

真正应追求的是：

- **架构级可迁移**

而不是：

- **物理行为级完全等价**

## 4.2 哪些层可以高度复用

下面这些层应尽量做到 Isaac / 真机共用同一实现：

- 任务解释层
- grounding 候选对象
- segmentation 候选对象
- 3D 描述对象
- grasp candidate 对象
- executability filter 框架
- 抓取状态机
- 失败分类
- 回放与评测系统

也就是说：

- 逻辑可以共用
- 数据结构可以共用
- 状态语义可以共用

## 4.3 哪些层只能接口复用，结果不能假设等价

下面这些层应尽量保持接口一致，但不能假设参数和效果等价：

- 深度图质量
- 目标点云质量
- 桌面法向估计
- 夹爪闭合反馈
- 成功判定阈值
- 重试阈值

最合理的策略是：

- 同接口
- 不同实现细节
- 不同参数集

## 4.4 哪些层不能直接从 Isaac 外推到真机

下面这些层必须明确承认“Isaac 不是等价真机”：

- 接触摩擦
- 物体刚度
- 滑移
- 夹爪接触模型
- 传感器噪声
- 深度空洞
- 外参漂移
- CAN 延迟 / 掉包 / 硬件反馈异常

所以 Isaac 的价值是：

- 替代黑盒真机完成上位机架构开发

而不是：

- 证明所有物理细节在真机上也会自然成立

## 5. 当前路线是否可行

## 5.1 作为“先做 perception / planning / task 主干”的路线：可行

因为当前已经具备：

- 统一 backend
- 统一 observation
- Isaac D405 真观测接入
- 统一 perception bundle

这足以支撑：

- 先在 Isaac 把 perception / planning / task 中间层做出来

## 5.2 作为“现在就能直接靠 SDK 完成目标任务”的结论：不可行

因为你当前还缺：

- 真实 grounding / segmentation
- grasp proposal
- executability filter
- grasp FSM
- post-grasp verification

所以现在还不能说：

- “已经能直接用 SDK 完成抓取目标任务”

更准确的表述是：

- **SDK 和本地扩展已经足够承接目标任务系统**
- **但中间层和执行层还需要补**

## 6. 当前最合理的下一步

当前最合理的建设顺序应是：

1. 收口 Isaac frame source 的 async / sync 边界
2. 新增真机 RGB-D frame source
3. 用真实模型替换 grounding / segmentation stub
4. 增强 `Object3DDescriptor`
5. 定义 `GraspCandidate`
6. 建 executability filter
7. 建 grasp FSM 和 `ExecutionResult`

## 7. 结论

当前项目完全适合：

- 先在 Isaac 中完成整条上位机 pipeline 的主干
- 再迁移到真机

但前提是你要明确：

- Isaac 负责替你隔离底层黑盒
- 共享上位机逻辑必须只依赖统一对象
- 真机迁移仍需要 adapter、标定和约束层收口

这条路线现在不是空想，已经有现实基础；  
但它也还没有走到“直接可抓”的阶段。
