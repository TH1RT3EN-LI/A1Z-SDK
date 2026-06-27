# 开放词汇抓取实施路线

本文档定义当前 A1Z 项目从“已有 SDK 控制能力”走到“可用开放词汇抓取系统”的分阶段路线。

路线强调：

- 先闭环
- 再增强
- 不一开始就上最重模型
- 每阶段都必须有清晰验收口径

## 1. 现状

当前已经有：

- A1Z SDK 控制后端
- `a1z_ext` 扩展层
- mock / Isaac / 真机后端切换
- RGB-D 设备与 D405 资产链
- 统一 observation / frame source 层
- 非抓取版 sample 闭环
- Isaac observation / bundle 接入路径
- 用户给出的基础抓取主线：
  - 文本
  - RGB grounding
  - SAM2 分割
  - mask + depth 定位
  - 抓取

当前需要明确承认：

- sample 非抓取闭环已稳定通过
- Isaac 端 observation / bundle 专项 verify 已通过
- Isaac 端当前已能恢复非空 `Object3DDescriptor`

当前还没有：

- `GraspCandidate`
- `ExecutablePlan`
- `ExecutionResult`
- 多候选重排序
- grasp proposal 层
- 执行前可达性筛选层
- 抓取状态机
- 抓后验证与失败恢复

## 2. 总体策略

先做一个稳的桌面单物体 top-down 抓取 MVP，再逐步扩展到更强的 grasping。

短期策略：

- 规则式抓取优先
- 几何恢复优先
- 约束与状态机优先

长期策略：

- 引入 6-DoF grasp 网络
- 引入 part-aware / task-aware grasp
- 评估 VLA 作为高层策略器

## 3. Phase 0：统一任务与运行时边界

### 目标

把现在“感知脚本 + 控制脚本”的临时串联，变成统一任务入口。

### 需要完成

- 定义 `TaskSpec`
- 定义统一 `ExecutionResult`
- 定义 perception / planning / execution 的模块边界
- 在 `a1z_ext` 下建立新目录：
  - `perception/`
  - `grasping/`
  - `task/`
  - `interfaces/`

### 不做的事

- 不在这一阶段引入新 grasp 网络
- 不直接做真机抓取

### 验收标准

- mock、Isaac、真机都能共享同一任务对象定义
- 任务层不直接 import CLI
- 感知层不直接操作机器人 backend

## 4. Phase 1：Grounding 与分割闭环

### 目标

把“语言 -> 目标 mask”这一段做成稳定模块。

### 推荐实现

- Grounding：Grounding DINO
- Segmentation：SAM 2
- 封装成：
  - `ground_object_candidates(task, image) -> GroundingCandidate[]`
  - `segment_candidates(image, candidates) -> MaskCandidate[]`

### 必须补的逻辑

- top-k grounding 保留
- mask 质量过滤
- grounding / mask score 归一化
- 歧义目标保留而不是直接丢弃

### 推荐参考

- Grounding DINO
- Grounded-SAM-2

### 验收标准

- 对单桌面多物体场景，能稳定产出 top-k box/mask
- grounding 和 segmentation 中间结果可视化可保存
- 歧义场景能输出多个候选而不是 silently fail

## 5. Phase 2：3D 恢复与 top-down grasp MVP

### 目标

把“mask -> 3D 几何 -> top-down grasp 候选”做通。

### 推荐实现

- 用 Open3D 做：
  - 点云恢复
  - 点云裁剪
  - 法向估计
  - 平面分割
- 输出 `Object3DDescriptor`
- 在此基础上生成规则式 top-down 抓取候选

### MVP 假设

- 单目标
- 静态桌面
- 物体在夹爪可容纳范围内
- 抓取接近方向固定为桌面法向

### 必须补的逻辑

- 深度有效率检查
- 点云质量评分
- 顶面点与支撑面估计
- 桌面高度约束

### 验收标准

- 能从 mask 恢复出稳定的目标 3D 中心与顶面点
- 能生成 `pregrasp / grasp / lift`
- 在 Isaac 中可视化抓取位姿

## 6. Phase 3：可执行性筛选与执行状态机

### 目标

让“能看到目标”变成“能执行抓取计划”。

### 推荐实现

- 新增 executability filter：
  - IK 可达性
  - 关节裕量
  - 末端禁入区
  - 当前姿态连续性
- 新增抓取状态机：
  - OpenGripper
  - MoveToPregrasp
  - Approach
  - CloseGripper
  - Lift
  - Retreat
  - Verify

### 依赖

- 上游 `a1z` IK
- 本地 `a1z_ext` backend
- 当前 [`A1Z_SDK_TASK_CONTROL_SPEC.md`](./A1Z_SDK_TASK_CONTROL_SPEC.md) 中定义的约束层

### 验收标准

- mock 中完整跑通状态机
- Isaac 中完整跑通状态机
- 每个失败都能输出明确 `failure_stage` 与 `failure_reason`

## 7. Phase 4：抓后验证与重试

### 目标

让系统对成功与失败有判断能力，而不是只执行一次动作。

### 最小验证

- 夹爪闭合后开口是否异常
- 目标是否从支撑面离开
- 原位置是否仍有高相似目标残留

### 重试策略

- 同物体的下一个 grasp candidate
- 同 grounding 的下一个 mask
- 同指令的下一个 grounding candidate

### 验收标准

- 失败任务能被分类成可重试 / 不可重试
- 系统最多重试 `N` 次后返回结构化失败

## 8. Phase 5：学习式 grasp proposal 增强

### 目标

在 MVP 稳定后，升级 grasp 生成质量。

### 推荐候选

- Contact-GraspNet
- GPD
- GraspNet baseline

### 选择原则

- 先离线评估
- 不直接替换主路径
- 必须经过同一 executability filter

### 注意

OK-Robot 的经验很重要：  
系统级成功率常常不是败在“有没有模型”，而是败在模块组合、视角条件、抓取姿态筛选和状态机细节上。

因此学习式 grasp proposal 应该作为增强件，而不是当前救命方案。

## 9. Phase 6：任务导向抓取与 part-aware grasp

### 目标

从“抓住物体”升级到“按任务抓物体正确部位”。

### 适用任务

- 抓杯柄
- 抓抽屉把手
- 抓锅盖边缘
- 抓可倾倒区域

### 推荐参考

- OVAL-Grasp
- OWG

### 前提

必须先把：

- 坐标系
- 3D 恢复
- grasp candidate
- 执行闭环

都做稳，否则 part-aware 只会放大错误。

## 10. Phase 7：VLA / Multimodal policy 探索

### 目标

让更大的模型参与高层任务规划，而不是取代全部控制逻辑。

### 推荐角色

- Task interpreter
- Candidate reranker
- Failure explanation
- Retry policy advisor

### 不建议的角色

当前阶段不建议让 VLA 直接：

- 输出连续控制
- 直接驱动真机动作

### 参考

- OpenVLA
- VIMA

## 11. 当前建议的优先级

按工程收益排序：

1. `TaskSpec` / `ExecutionResult` 契约
2. grounding + SAM2 模块化
3. `Object3DDescriptor`
4. 规则式 top-down grasp
5. executability filter
6. grasp state machine
7. post-grasp verification
8. 学习式 grasp proposal
9. part-aware grasp
10. VLA 探索

## 12. 每阶段交付物

## Phase 0-1

- 模块目录
- schema 定义
- grounding / segmentation API
- 可视化调试输出

## Phase 2

- 3D descriptor API
- top-down grasp generator
- Isaac 可视化验证

## Phase 3-4

- executability filter
- 抓取状态机
- 结果分类器
- mock / Isaac 回归用例

## Phase 5-7

- grasp 模型评测报告
- 替换策略报告
- 高层 VLA 适配实验

## 13. 关键结论

你这条链的真正瓶颈不在“有没有 LLM / SAM2”，而在中后段：

- 3D 恢复质量
- grasp proposal 质量
- executability 过滤
- 状态机执行
- 抓后验证

只要这五件补齐，当前系统就能从“感知到物体”升级成“具备任务抓取闭环”。
