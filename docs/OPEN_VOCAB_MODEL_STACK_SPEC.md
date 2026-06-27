# 开放词汇 Pipeline 模型与技术栈规范

本文档定义当前这条 pipeline 各阶段推荐采用什么技术栈，以及这些技术栈在当前项目里分别扮演什么角色。

目标不是“把最新模型名堆进去”，而是：

- 给当前阶段一个稳的选型顺序
- 明确哪些东西是主路径
- 明确哪些东西只是后续增强项

## 1. 当前 pipeline 分段

你现在的目标链路是：

1. 自然语言指令
2. RGB 图像上的 box / point grounding
3. mask segmentation
4. mask + depth -> 3D object descriptor
5. 后续再接抓取

当前文档只聚焦前四段和它们的依赖栈。

## 2. 选型原则

当前项目的选型必须满足四条原则：

1. 能在 Isaac 和真机之间复用同一上位机主干
2. 不把模型 demo 脚本直接当系统主干
3. 先稳住数据契约，再替换算法实现
4. 先做单帧可靠，再谈视频跟踪和闭环增强

## 3. 各阶段推荐技术栈

## 3.1 指令解释层

当前角色：

- 把自然语言收敛成 `TaskSpec`

当前阶段推荐：

- 先保留本地轻量规则或结构化 LLM 输出

要求：

- 输出必须落到统一 `TaskSpec`
- 不允许直接把一大段提示词结果散落到后续模块

短期建议：

- 先用轻量结构化文本解析
- 后续再接真正的 LLM / VLM structured output

不建议当前就做：

- 端到端语言直接出动作

## 3.2 Grounding 层

主推荐：

- GroundingDINO

角色：

- 从文本生成开放词汇检测框
- 产生 top-k `GroundingCandidate`

为什么它是当前主推荐：

- 工程上成熟
- 跟你当前 box-first 流程一致
- 输出形态天然适合进入后续 segmentation

当前仓库里的要求：

- `grounding.py` 继续作为统一包装层
- 模型实现放在包装层后面，而不是把 demo 逻辑塞进主流程

## 3.3 Segmentation 层

主推荐：

- SAM2

角色：

- 接收 box / point prompt
- 生成 `MaskCandidate`

为什么是当前主推荐：

- 跟 GroundingDINO 串联自然
- 单帧可用，未来也方便扩到视频追踪

当前仓库里的要求：

- `segmentation.py` 继续只输出统一 mask 候选对象
- 不把 SAM2 的私有数据结构泄漏到主干 schema

## 3.4 3D 恢复层

当前阶段主推荐：

- `numpy` 实现基础恢复
- 逐步引入 Open3D

角色：

- 从 `mask + depth + intrinsics + extrinsic` 恢复 3D 目标描述

当前必须先做的内容：

- 有效深度筛选
- 点云恢复
- 质心、顶部点、包围盒、主轴
- 质量指标

Open3D 在这里的正确角色是：

- 法向估计
- 平面分割
- 更稳的局部几何分析

而不是：

- 直接替代 perception 全流程

## 4. 后续抓取阶段的预留选型

虽然当前先不用抓取，但现在就应该明确后续路线，避免前面的数据契约做错。

### 4.1 抓取 MVP

主推荐：

- 规则式 top-down grasp

原因：

- 对当前桌面单物体抓取最实用
- 依赖少
- 方便与 A1Z SDK 的执行约束层结合

### 4.2 学习式 grasp proposal

推荐作为增强项，而不是当前主路径：

- Contact-GraspNet
- GPD
- GraspNet 系方法

这些方法适合后续解决：

- 复杂姿态
- 更强泛化
- 多候选排序

但当前不适合作为救火主方案。

## 5. 当前仓库中的技术栈边界

为了后续维护清晰，建议保持下面这组边界。

### 5.1 `a1z_ext/perception`

只放：

- 共享 perception 逻辑
- 统一 schema 包装
- 与具体模型实现解耦的接口

不放：

- Isaac API
- RealSense 驱动 API
- ROS2 topic 依赖

### 5.2 `a1z_ext/runtime/frame_sources`

只放：

- 相机输入适配器
- observation 构造逻辑

不放：

- grounding
- segmentation
- grasp logic

### 5.3 `exts/a1z.d405.runtime`

只放：

- Isaac 内 D405 资产语义
- Isaac 相机 prim / runtime service

不放：

- 共享 perception 主逻辑
- 任务语义

## 6. 依赖引入顺序

当前建议按下面顺序引依赖。

### 第一层：现在就该稳定

- Python
- `numpy`
- `dataclasses`
- JSON / `.npy`

### 第二层：观测闭环稳定后引入

- PyTorch
- OpenCV
- Open3D

### 第三层：抓取增强阶段再引入

- grasp proposal 相关模型依赖
- 更复杂的点云/姿态推理栈

## 7. 当前不建议的路线

当前阶段不建议直接走下面这些路线作为主系统。

### 7.1 端到端 VLA 直接控机械臂

原因：

- 你现在首先缺的是观测层和任务中间层
- 不是一个“大模型输出动作”就能补齐

### 7.2 Isaac 真值直接代替 perception

原因：

- 会破坏 sim2real 主干
- 后面迁移真机时会重新返工

### 7.3 先上复杂 grasp 网络再补基础几何

原因：

- 当前 observation 主干已经建立，但抓取中间层还不存在
- 几何层仍是 MVP，顺序不该倒过来

## 8. 推荐实现顺序

当前最务实的落地顺序是：

1. 收口 Isaac RGB-D 输入稳定性
2. 新增真机 RGB-D frame source
3. 稳定 `mask + depth -> 3D descriptor`
4. 接 GroundingDINO
5. 接 SAM2
6. 引入 Open3D 几何增强
7. 再进入 grasp 阶段

## 9. 与现有文档的关系

这份文档负责回答：

- “当前该用什么栈”
- “这些栈在系统里处于什么层”

相关文档分工如下：

- [`OPEN_VOCAB_OBSERVATION_LAYER_SPEC.md`](./OPEN_VOCAB_OBSERVATION_LAYER_SPEC.md)
  - 定义观测层边界
- [`OPEN_VOCAB_PHASE1_EXECUTION_PLAN.md`](./OPEN_VOCAB_PHASE1_EXECUTION_PLAN.md)
  - 定义当前阶段的执行计划
- [`OPEN_VOCAB_GRASPING_REFERENCES.md`](./OPEN_VOCAB_GRASPING_REFERENCES.md)
  - 记录外部项目和论文参考

## 10. 结论

当前这条 pipeline 的主路径应当非常克制：

- GroundingDINO 解决 box grounding
- SAM2 解决 mask
- `numpy/Open3D` 解决 3D 恢复
- A1Z SDK 以后解决执行

先把这条路做直，再去考虑更大的统一模型。
