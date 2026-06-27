# 开放词汇 Pipeline 阶段规范

本文档把你当前定义的主链拆成一套能直接指导研发的阶段规范。

当前主链是：

1. 自然语言指令
2. RGB 画面上的 box / point grounding
3. SAM2 或等价模型输出 mask
4. mask 与深度融合，恢复目标 3D 描述
5. 抓取

但工程上不能只写成 5 步。  
在当前 A1Z 项目里，它至少应拆成 8 个阶段：

1. 观测采集
2. 指令解释
3. grounding / pointing
4. segmentation
5. 3D 几何恢复
6. grasp candidate 生成
7. 可执行性筛选
8. 执行与抓后验证

## 1. 当前适用范围

本文档面向当前仓库现实，而不是理想系统。

当前已具备：

- `a1z_ext/interfaces/observation.py`
- `a1z_ext/runtime/frame_sources/*`
- `a1z_ext/perception/*`
- sample 闭环稳定通过
- Isaac D405 observation / bundle 路径已经接入

当前未具备：

- 真实 GroundingDINO
- 真实 SAM2
- `GraspCandidate`
- `ExecutablePlan`
- `ExecutionResult`
- grasp FSM

因此当前阶段最准确的判断是：

- **阶段 1 到阶段 5 已经有骨架**
- **阶段 6 到阶段 8 还没有落到代码**

## 2. 阶段总览

| 阶段 | 目标 | 当前对象 | 当前状态 | 建议归属 |
| --- | --- | --- | --- | --- |
| 1. 观测采集 | 统一 RGB-D 输入 | `RGBDObservation` / `RGBDFrameCapture` | 已落地 | `a1z_ext/runtime/frame_sources` |
| 2. 指令解释 | 自然语言收敛成结构化任务 | `TaskSpec` | 已落地但很轻量 | `a1z_ext/perception/task_interpreter.py` |
| 3. grounding | 找到目标候选框/点 | `GroundingCandidate[]` | stub | `a1z_ext/perception/grounding.py` |
| 4. segmentation | 从候选框/点得到 mask | `MaskCandidate[]` | stub | `a1z_ext/perception/segmentation.py` |
| 5. 3D 恢复 | 从 mask + depth 恢复 3D 描述 | `Object3DDescriptor[]` | MVP 已落地 | `a1z_ext/perception/object_3d.py` |
| 6. grasp candidate | 从 3D 描述生成抓取候选 | `GraspCandidate[]` | 缺失 | `a1z_ext/grasping` |
| 7. 可执行性筛选 | 判断候选能否安全执行 | `ExecutablePlan` | 缺失 | `a1z_ext/grasping` |
| 8. 执行与验证 | 执行动作并判断成功失败 | `ExecutionResult` | 缺失 | `a1z_ext/task` |

## 3. 阶段 1：观测采集

### 3.1 目标

把 sample、Isaac、真机 RGB-D 输入整理成统一观测对象。

### 3.2 输入

- 后端专有相机接口
- RGB
- depth
- intrinsics
- `camera -> target` 外参

### 3.3 输出

- `RGBDObservation`
- `RGBDFrameCapture`

### 3.4 当前仓库状态

当前已存在：

- `SampleRGBDFrameSource`
- `IsaacD405FrameSource`
- `run_pipeline_from_frame_capture(...)`

当前真实状态：

- sample 路径截至 2026-06-09 稳定通过
- Isaac 路径截至 2026-06-09 已通过专项 verify
- Isaac 当前已能作为“非抓取版 bundle 闭环”的专项输入源
- Isaac 仍未证明适合长时间高频数据生产

### 3.5 这一层必须负责的事

- depth 单位统一成米
- 明确 `camera_frame_id`
- 明确 `target_frame_id`
- 明确 `extrinsic_camera_to_target`
- 输出稳定的 `observation.json`

### 3.6 这一层不能负责的事

- grounding
- segmentation
- 3D 恢复
- grasp proposal

### 3.7 sim2real 注意事项

- Isaac 与真机只允许接口共用
- Isaac world frame 不能混成真机 base frame
- adapter 内必须完成坐标整理，不能把模糊语义泄漏到上层

## 4. 阶段 2：指令解释

### 4.1 目标

把自然语言收敛成稳定任务对象。

### 4.2 输入

- 文本指令
- 可选视觉上下文摘要

### 4.3 输出

- `TaskSpec`

### 4.4 当前仓库状态

当前 `TaskSpec` 已落地，`interpret_text_instruction(...)` 已存在。  
但当前仍是轻量结构化解析，不是完整 LLM / VLM 任务解释层。

### 4.5 这一层最低要求

- 只输出 schema 约束对象
- 保留 `action_type`
- 保留 `target_object.text`
- 保留 `preferred_grasp_mode`
- 保留超时与 safety profile

### 4.6 当前建议

当前不要让 LLM 直接输出动作或关节值。  
在这套系统里，LLM 只能负责：

- 语义归一化
- 对象指代消解
- 目标约束补充

## 5. 阶段 3：grounding / pointing

### 5.1 目标

根据 `TaskSpec.target_object` 在 RGB 图像上找出 top-k 目标候选。

### 5.2 输入

- `TaskSpec`
- RGB 图像

### 5.3 输出

- `GroundingCandidate[]`

### 5.4 当前仓库状态

当前 `a1z_ext/perception/grounding.py` 是 deterministic stub：

- 有红色区域时，用启发式框出红色区域
- 否则回退到中心框
- 固定输出 top-k 候选

这层当前的价值只有两个：

- 先把 bundle 契约跑通
- 给后续 GroundingDINO 接入保留壳层

### 5.5 主推荐实现

- GroundingDINO

### 5.6 工程要求

- 必须保留 top-k，而不是只留 top-1
- `rank` 只表示排序，不表示最终执行决策
- grounding 失败要结构化返回，不能 silent fail
- 输出层不泄漏模型私有类型

### 5.7 验收重点

- `top-k recall`
- grounding latency
- 歧义目标保留率

### 5.8 sim2real 注意事项

- 不允许 Isaac 真值 bbox 进入共享主链
- Isaac 真值只能作为调试对照

## 6. 阶段 4：segmentation

### 6.1 目标

把 grounding 候选变成可用于几何恢复的 mask 候选。

### 6.2 输入

- RGB 图像
- `GroundingCandidate[]`

### 6.3 输出

- `MaskCandidate[]`

### 6.4 当前仓库状态

当前 `a1z_ext/perception/segmentation.py` 是 box-to-mask stub：

- 直接把 bbox 填充成矩形 mask
- 保存 `.npy`
- 回写基础质量字段

它不是 SAM2 的近似实现，只是数据契约占位。

### 6.5 主推荐实现

- SAM2 image predictor

### 6.6 工程要求

- 同时支持 box prompt 与 point prompt
- mask 结果要有质量分数字段
- 低质量 mask 不能直接推进到 grasp 主链
- 落盘结果必须可回放

### 6.7 验收重点

- mask usability rate
- depth valid ratio
- boundary touch ratio
- segmentation latency

## 7. 阶段 5：3D 几何恢复

### 7.1 目标

从 `mask + depth + intrinsics + extrinsic` 恢复抓取相关 3D 描述。

### 7.2 输入

- `MaskCandidate[]`
- depth
- intrinsics
- `extrinsic_camera_to_target`

### 7.3 输出

- `Object3DDescriptor[]`

### 7.4 当前仓库状态

当前 `a1z_ext/perception/object_3d.py` 已在做真实几何恢复：

- mask 投影
- 点云恢复
- 质心
- 顶部点
- 主轴
- 包围盒

但它仍是 MVP：

- 没有稳健支撑面拟合
- 没有 keepout / workspace 过滤
- 没有 Open3D 增强

### 7.5 当前最关键的现实约束

这一层现在不是主要卡在 schema，而是卡在 Isaac 观测质量。

当前已知事实：

- sample 输入下 `Object3DDescriptor` 非空
- Isaac 输入下 observation / bundle 路径已接入
- 但 D405 optical frame 与 streaming-hosted 采帧基线仍未完全收口

所以这层下一步的首要任务不是继续加字段，而是先把：

- 相机视角
- 深度有效区域
- 有效 mask 与有效 depth 的重合

收敛到稳定状态。

### 7.6 推荐增强

- Open3D
- 桌面平面拟合
- 法向估计
- 点云去噪
- 点云质量评分

### 7.7 验收重点

- centroid error
- top surface height error
- usable point cloud ratio
- `object_descriptors` 非空率

## 8. 阶段 6：grasp candidate 生成

### 8.1 目标

从 3D 描述生成可排序的抓取候选，而不是直接把物体中心当抓取点。

### 8.2 输入

- `Object3DDescriptor[]`
- 夹爪几何约束
- 任务语义约束

### 8.3 输出

- `GraspCandidate[]`

### 8.4 当前仓库状态

这一层当前不存在。

### 8.5 MVP 路线

当前最务实的是：

- 规则式 top-down parallel jaw grasp

而不是一开始就接复杂 6-DoF grasp 网络。

### 8.6 第一版至少应包含

- `pregrasp_pose`
- `grasp_pose`
- `lift_pose`
- `approach_vector`
- `gripper_opening_m`
- `overall_score`

### 8.7 何时再考虑学习式 grasp

只有在下面三件事都稳定后才值得引：

- 观测层稳定
- `Object3DDescriptor` 稳定
- executability filter 存在

## 9. 阶段 7：可执行性筛选

### 9.1 目标

把“几何上像能抓”筛成“机器人真的能执行且风险受控”。

### 9.2 输入

- `GraspCandidate[]`
- 当前关节状态
- 机器人约束
- safety profile

### 9.3 输出

- `ExecutablePlan`

### 9.4 当前仓库状态

这一层当前不存在。

但当前项目已经具备它的依赖基础：

- 上游 SDK 有 IK
- 本地有 mock / Isaac / SocketCAN backend
- `a1z_ext/robots/isaacsim_robot.py` 已有 joint limit 缓存与控制能力

### 9.5 这一层必须显式承担的检查

- pregrasp IK
- grasp IK
- lift IK
- retreat IK
- joint margin
- 姿态连续性
- 桌面 keepout
- 相机/支架 keepout

### 9.6 一个关键原则

不能把：

- “IK 有解”

等价成：

- “计划可执行”

## 10. 阶段 8：执行与抓后验证

### 10.1 目标

把可执行计划真正跑完，并给出结构化成功/失败结论。

### 10.2 输入

- `ExecutablePlan`
- robot service

### 10.3 输出

- `ExecutionResult`

### 10.4 当前仓库状态

这一层当前不存在。

### 10.5 最低状态机

- `OpenGripper`
- `MoveToPregrasp`
- `Approach`
- `CloseGripper`
- `Lift`
- `Retreat`
- `Verify`
- `Failed`
- `Done`

### 10.6 最低抓后验证

- 夹爪闭合后开口变化
- 抬升后目标是否离开支撑面
- 原位目标是否仍明显存在

## 11. 跨阶段共性约束

### 11.1 共享逻辑归属

共享语义只允许进入：

- `a1z_ext/interfaces`
- `a1z_ext/perception`
- 后续 `a1z_ext/grasping`
- 后续 `a1z_ext/task`

### 11.2 后端专有逻辑归属

Isaac 专有逻辑只允许进入：

- `exts/a1z.d405.runtime`
- `a1z_ext/runtime/frame_sources/isaac_rgbd.py`
- `a1z_ext/robots/isaacsim_robot.py`

### 11.3 当前阶段边界

截至当前仓库状态，真正应优先收口的是：

1. 阶段 1 的 Isaac 观测稳定性
2. 阶段 3 和 4 的真实模型替换
3. 阶段 5 的几何稳健性

不是直接跳到阶段 8。

## 12. 推荐参考

按阶段最相关的主参考如下：

- 指令解释：OpenVLA、VIMA
- grounding：GroundingDINO
- segmentation：SAM2、Grounded-SAM-2
- 3D 几何：Open3D
- grasp proposal：Contact-GraspNet、GPD、GraspNet
- 系统集成：OK-Robot、OWG、OVAL-Grasp

更完整列表见：

- [`OPEN_VOCAB_GRASPING_REFERENCES.md`](./OPEN_VOCAB_GRASPING_REFERENCES.md)

## 13. 结论

你当前这条主链不是不能做，而是必须承认它实际上分成了两段：

- 已经有骨架的 perception / observation 段
- 还没写出来的 grasp / execution 段

当前最合理的推进方式不是继续把这两段混写成“5 步”，而是按照本文 8 个阶段逐层收口。
