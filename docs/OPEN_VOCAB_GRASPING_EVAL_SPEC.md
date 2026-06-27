# 开放词汇抓取评测规范

本文档定义开放词汇抓取系统的评测任务、指标、失败分类和验收门槛。

目标是防止系统停留在：

- 单次 demo 成功
- 人工挑图
- 只展示感知成功、不展示抓取失败

## 1. 评测原则

### 1.1 分层评测

必须分别评估：

- grounding
- segmentation
- 3D 恢复
- grasp proposal
- executability
- 执行状态机
- end-to-end success

### 1.2 分场景评测

至少区分：

- uncluttered tabletop
- mildly cluttered tabletop
- heavily cluttered tabletop
- ambiguous language query

### 1.3 分后端评测

至少区分：

- mock
- Isaac
- 真机

其中：

- mock 用于接口和状态机稳定性
- Isaac 用于几何和执行逻辑验证
- 真机用于最终现实验收

## 2. 任务集合

## 2.1 MVP 任务集合

第一阶段仅评测：

- 单物体桌面抓取
- top-down grasp
- 单轮语言指令

指令样例类型：

- 类别 + 颜色
- 类别 + 相对位置
- 类别 + 否定约束

例如：

- 红色杯子
- 左边的白盒子
- 不是瓶子的那个蓝色物体

## 2.2 增强任务集合

后续逐步增加：

- 遮挡场景
- 外形相近物体
- 多个同类物体
- 局部抓取需求
- 放置目标

## 3. 分层指标

## 3.1 Grounding 指标

推荐记录：

- top-1 hit rate
- top-k recall
- grounding latency
- ambiguity retention rate

### 解释

对于抓取系统，top-k recall 通常比 top-1 accuracy 更重要。  
因为后面还有 segmentation、3D 几何和 grasp reranking。

## 3.2 Segmentation 指标

推荐记录：

- IoU 或近似人工标注 IoU
- mask stability score
- depth valid ratio
- mask usability rate

### mask usability

定义为：

- 能进入 3D 恢复并产生有效 `Object3DDescriptor` 的 mask 占比

这比纯视觉指标更贴合机器人任务。

## 3.3 3D 恢复指标

推荐记录：

- centroid error
- top surface height error
- support plane normal error
- usable point cloud ratio

### 当前阶段重点

不必一开始就追完整 6D pose 误差。  
对抓取来说，优先看：

- 顶面高度是否对
- 法向是否对
- 可抓区域是否稳定

## 3.4 Grasp Proposal 指标

推荐记录：

- valid candidate rate
- executable candidate rate
- top-1 executable success rate
- candidate generation latency

### 定义

- `valid candidate`: 几何上合理
- `executable candidate`: 经过 IK 和安全筛选后仍可执行

## 3.5 Executability 指标

推荐记录：

- IK solve rate
- joint margin rejection rate
- table clearance rejection rate
- camera keepout rejection rate

### 目的

这组指标能直接说明失败到底来自：

- 候选姿态差
- 机器人工作空间差
- 约束设置过严

## 3.6 执行状态机指标

推荐记录：

- state transition success rate
- average execution time
- timeout rate
- backend disconnect rate

### 每阶段指标

- `MoveToPregrasp` success
- `Approach` success
- `CloseGripper` success
- `Lift` success
- `Retreat` success

## 3.7 End-to-End 指标

最终必须记录：

- task success rate
- grasp-only success rate
- post-lift hold rate
- retry success uplift
- end-to-end latency

### 区分两个成功率

- `grasp-only success`: 夹住了
- `task success`: 夹住并完成任务退出条件

## 4. 失败分类

## 4.1 一级失败分类

- `perception_failure`
- `geometry_failure`
- `planning_failure`
- `execution_failure`
- `verification_failure`
- `hardware_failure`

## 4.2 二级失败分类

### perception

- wrong_object_grounded
- no_candidate_found
- mask_low_quality

### geometry

- depth_invalid
- plane_estimation_failed
- object_descriptor_unstable

### planning

- no_grasp_candidate
- ik_unsolved
- safety_filter_rejected

### execution

- move_timeout
- backend_disconnect
- gripper_command_failed

### verification

- object_not_lifted
- object_slipped
- false_positive_grasp

### hardware

- camera_drop_frame
- calibration_drift
- joint_feedback_invalid

## 5. 后端评测要求

## 5.1 mock

要求：

- 100% 跑通任务状态机
- 所有失败都能稳定复现为结构化错误

不要求：

- 真实几何一致性

## 5.2 Isaac

要求：

- 3D 几何恢复、抓取位姿生成、IK 过滤、状态机时序都要过
- 抓取任务可批量回放

重点：

- 先把仿真语义对齐真机，而不是追求漂亮画面

## 5.3 真机

要求：

- 在受控桌面场景下验证最终抓取率
- 必须记录全部失败样本

不允许：

- 只展示成功案例

## 6. 验收门槛建议

下面给的是建议门槛，不是行业标准。

## 6.1 MVP 门槛

在单物体、桌面、top-down 场景中：

- grounding top-k recall >= 0.95
- mask usable rate >= 0.90
- executable candidate rate >= 0.80
- Isaac end-to-end success >= 0.75
- 真机 end-to-end success >= 0.60

## 6.2 可内部联调门槛

- mock 状态机通过率 = 1.00
- Isaac end-to-end success >= 0.85
- 真机 uncluttered success >= 0.75

## 6.3 进入复杂场景前门槛

在 uncluttered 场景未达到稳定前，不要进入：

- 遮挡重场景
- 多相似物体
- task-oriented part grasp

## 7. 数据记录要求

每次评测任务至少保存：

- 原始指令
- RGB 帧
- 深度帧
- grounding 候选
- 分割 mask
- 3D descriptor
- grasp candidates
- selected plan
- 执行日志
- 最终结果

推荐统一存成一个 `trial bundle`。

## 8. 人工复核要求

系统评测不能只看自动指标。  
每轮评测建议抽样复核：

- 语言是否理解对
- grounding 是否抓到正确对象
- mask 是否 usable
- 3D 中心和法向是否可信
- 失败分类是否正确

## 9. 参考启发

这套评测思路受以下工作启发：

- OK-Robot 强调模块组合细节与真实失败模式分析
- GraspNet-1Billion 强调 grasp benchmark 与统一评测
- OWG / OVAL-Grasp 说明开放词汇抓取不能只看 detection success

## 10. 结论

开放词汇抓取的真正评测对象不是“模型准不准”，而是：

- 目标找没找对
- 找到后能不能恢复出稳定 3D 描述
- 描述能不能转成可执行抓取
- 执行后到底抓没抓到

只有这四层都评，系统才算真的被验证过。

