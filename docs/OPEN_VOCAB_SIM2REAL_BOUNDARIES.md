# 开放词汇 Pipeline 的 Isaac / 真机 边界规范

本文档定义当前 A1Z 项目里，Isaac 与真机之间哪些层必须共享、哪些层只能接口共享、哪些 Isaac 捷径必须明确禁止进入主路径。

当前背景是：

- Isaac 需要先简单代替真机
- 真机本身是黑盒
- 你希望把上位机逻辑和底层驱动隔离开

在这个前提下，真正要追求的不是：

- “Isaac 抓成一次，真机就零改动成功”

而是：

- “同一套上位机模块、对象模型和评测方式可以在 Isaac / 真机间复用”

结论先行：

- **可迁移的核心不是仿真抓一次，而是共享上位机语义保持同构**
- **必须把共享逻辑和 backend / sensor adapter 拆开**
- **必须禁止 Isaac 真值捷径污染共享 perception / grasping 主路径**

## 1. 三层边界

系统应拆成三类层。

## 1.1 完全共享层

这些层应尽量做到 Isaac / 真机共用同一实现：

- 任务解释
- grounding 调用协议
- segmentation 调用协议
- 3D 恢复
- grasp candidate 表达
- executability filter 框架
- 抓取状态机
- 抓后验证规则
- 失败分类
- 评测与日志格式

当前它们应该主要落在：

- `a1z_ext/interfaces`
- `a1z_ext/perception`
- 后续新增的 `a1z_ext/grasping`
- 后续新增的 `a1z_ext/task`

## 1.2 接口共享但实现分离层

这些层应保持统一接口，但允许 Isaac 和真机各自有不同实现：

- RGB-D 取帧
- 相机内外参来源
- 标定版本管理
- 机器人状态查询
- 机器人命令发送
- 硬件健康检查
- 安全 profile 参数

当前这类层主要放在：

- `a1z_ext/runtime/frame_sources`
- 未来的 `a1z_ext/runtime/calibration`
- `a1z_ext/robots`

关键约束是：

- 上层只看到统一接口
- 不直接感知底下是 Isaac 还是真机

## 1.3 明确后端专有层

这些层本来就不应尝试共用实现：

- Isaac stage / prim 操作
- Isaac annotator / sensor API
- RealSense 驱动与流配置
- SocketCAN 总线和电机异常处理
- Isaac WebRTC / ROS2 publishing

这些层必须被封装在 adapter 里，不能泄漏到共享抓取逻辑。

## 2. 当前已经共享成功的对象

当前仓库里已经共享成功的对象有两类。

## 2.1 perception bundle 对象

当前已经存在：

- [`TaskSpec`](../a1z_ext/interfaces/schemas.py)
- `GroundingCandidate`
- `MaskCandidate`
- `Object3DDescriptor`
- `PipelineBundle`

要求继续保持：

- Isaac 与真机都产出同结构对象
- score 字段、frame_id、单位和坐标语义保持一致

## 2.2 统一 RGB-D 观测对象

当前已经存在：

- [`CameraIntrinsics`](../a1z_ext/interfaces/observation.py)
- [`RGBDObservation`](../a1z_ext/interfaces/observation.py)
- [`RGBDFrameCapture`](../a1z_ext/runtime/frame_sources/base.py)
- [`FrameSource`](../a1z_ext/runtime/frame_sources/base.py)

这说明“显式 Observation / Frame 契约还缺失”这一判断已经过时。  
当前更准确的判断是：

- **契约已建立**
- **Isaac / sample 已接入**
- **真机 adapter 仍需接入**

## 3. 当前必须继续保持一致的共享对象

当前要继续把一致性守住的，是下面三类对象。

## 3.1 任务对象

当前：

- Isaac 和 sample 都应接收同一种 `TaskSpec`

后续继续要求：

- 真机也必须接收同一种任务对象
- 不允许 Isaac 路径额外传真值 pose 进入共享主链
- 不允许真机路径另起一套任务描述

## 3.2 观测对象

当前：

- sample 与 Isaac 都已经能产出 `RGBDObservation + RGBDFrameCapture`

后续继续要求：

- 真机也必须产出同结构 observation
- `camera_frame_id`、`target_frame_id`、`calibration_version`、`extrinsic_camera_to_target` 不得省略

## 3.3 执行对象

当前还没有，但后续必须统一新增：

- `GraspCandidate`
- `ExecutablePlan`
- `ExecutionResult`

如果这层不统一，后面就会重新退化成“Isaac 一套特殊逻辑，真机一套特殊逻辑”。

## 4. Isaac 中禁止使用的捷径

为了保证可迁移性，下面这些 Isaac 捷径都不能进入共享主路径。

## 4.1 禁止直接用物体真值 pose 代替 3D 恢复

否则你验证到的只是：

- 控制后半段

而不是完整 pipeline。

## 4.2 禁止直接用真值 bbox / segmentation 代替 grounding 与 segmentation 主结果

这些真值可以作为：

- 调试对照
- 上限分析
- 单独评测基准

但不能作为共享 bundle 的默认主路径输入。

## 4.3 禁止共享 perception 直接 import Isaac 私有对象

共享模块例如：

- `grounding.py`
- `segmentation.py`
- `object_3d.py`
- `pipeline.py`

都不应直接依赖：

- stage
- prim
- Isaac annotator handle

这些依赖只能留在 adapter 层。

## 5. 当前代码归属要求

如果后续继续建设完整 pipeline，目录归属应继续遵守下面的边界：

```text
a1z_ext/
  interfaces/
    schemas.py
    observation.py
    execution.py
  perception/
    task_interpreter.py
    grounding.py
    segmentation.py
    object_3d.py
  grasping/
    proposal_topdown.py
    executability.py
  task/
    grasp_fsm.py
    verification.py
  runtime/
    frame_sources/
      isaac_rgbd.py
      realsense_rgbd.py
    calibration.py
    logging.py
```

其中：

- `perception/` 只吃统一 observation / capture
- `grasping/` 只吃共享几何对象和机器人约束
- `task/` 只吃共享 plan 和 robot service
- `runtime/frame_sources/` 专门负责“从 Isaac / 真机拿一帧”

## 6. 当前 sim2real 正确理解

当前项目语境下，“可迁移”不应理解为：

- 同一 demo 在 Isaac 成功一次，真机也应直接成功

而应理解为：

- 同一套上位机模块划分
- 同一套任务对象
- 同一套 observation / bundle 契约
- 同一套 grasp / execution 语义
- 同一套日志与评测方式

在不同 backend 上共享。

也就是说，真正应追求的是：

- **架构级可迁移**

而不是：

- **物理行为级完全等价**

## 7. 当前已经做到的可迁移基础

当前仓库已经具备三项关键基础：

1. 统一机器人 backend 分层
2. 统一 observation / frame source 层
3. 统一 bundle / schema 层

这三件事决定了 Isaac 已经能够承担“上位机开发替身”的角色。

## 8. 当前仍需补的 sim2real 缺口

即使当前基础已经成立，下面这些缺口仍必须补上：

## 8.1 真机 RGB-D adapter

当前 observation 层已经建立，但真机 RGB-D frame source 还没有接入。

## 8.2 标定版本与健康检查

当前 observation 已支持：

- `calibration_version`
- `sensor_model`
- `scene_context`

但真机侧还缺：

- 标定文件组织
- 外参版本管理
- 采帧健康检查

## 8.3 grasping 中间层

当前还没有：

- `GraspCandidate`
- `ExecutablePlan`
- `ExecutionResult`
- executability filter
- grasp FSM

这意味着现在只能谈 perception 可迁移，还不能谈完整抓取可迁移。

## 9. 技术栈要求

共享上位机主干继续保持：

- Python
- `dataclasses`
- `numpy`
- JSON / `.npy`

模型和几何增强层按阶段引入：

- PyTorch
- OpenCV
- Open3D

底层驱动与 Isaac API 继续隔离在 adapter 内。

## 10. 结论

当前仓库已经具备：

- 让 Isaac 承担共享上位机 perception 开发替身的结构基础
- 并且这一基础已经不是停留在设计图，而是有 sample / Isaac 双输入闭环

但要把这条路真正走到真机，必须继续守住边界：

- 真值捷径不进主链
- perception / grasping / task 只看共享对象
- backend 和 sensor 差异只留在 adapter 层
