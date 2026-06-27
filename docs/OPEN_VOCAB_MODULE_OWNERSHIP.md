# 开放词汇抓取相关模块的归属规范

本文档专门解决一个工程管理问题：

- 什么东西属于上游 SDK
- 什么东西属于本地扩展
- 什么东西属于 Isaac 专有 extension
- 后续补功能时应该往哪里加

你前面已经明确希望把自己加的逻辑从上游 SDK 解耦出去，避免语义不清。

这份文档就是之后继续开发时的归属规则。

## 1. 总原则

## 1.1 `vendor/GALAXEA-A1Z` 只保留上游镜像语义

`vendor` 的角色应该是：

- 上游 SDK 镜像
- 上游能力参考
- 必要时用于同步和比对

它不应该继续承担：

- 本地任务系统
- 本地抓取 pipeline
- 本地 Isaac 替身逻辑
- 项目私有 CLI 语义
- 项目私有安全约束

一句话说：

- `vendor` 是镜像，不是你的业务层

## 1.2 `a1z_ext` 才是本地项目主实现层

凡是下面这些能力，都应当优先进入 `a1z_ext`：

- backend 适配
- 统一机器人服务语义
- perception pipeline
- grasping pipeline
- task/FSM
- 运行时数据契约
- 安全约束层
- 本地日志与评测

因为这些都是：

- 项目私有
- 会持续演化
- 不适合混回上游镜像

## 1.3 `exts/a1z.d405.runtime` 只放 Isaac 专有 D405 运行时语义

这个 extension 应当继续只负责：

- 在 Isaac 场景里挂 D405 资产
- 维护 color/depth 相机 prim
- Isaac 内 ROS2 发布或运行时服务

它不应该承担：

- open-vocab grounding
- SAM2
- 3D 几何恢复
- grasp proposal
- 抓取状态机

否则共享 pipeline 会被 Isaac 私有 API 污染。

## 1.4 `scripts/` 负责编排和验证，不负责沉淀业务语义

脚本的职责应该是：

- 启动
- 进入容器
- 验证
- 调用 runner

脚本不应成为下面这些逻辑的长期落点：

- 真正的 perception 核心算法
- 真正的 grasp planning 核心算法
- 任务状态机

脚本可以调用模块，但不应代替模块。

## 2. 当前各目录的正确职责

## 2.1 `vendor/GALAXEA-A1Z`

保留内容：

- 上游机器人模型与驱动
- 上游 SDK 的控制、动力学、IK 基础能力
- 上游工具与示例

不再新增：

- 本地抓取语义
- 本地 server contract
- 本地 mock/Isaac 行为修补
- 本地相机或 perception pipeline

## 2.2 `a1z_ext/robots`

这是本地“驱动适配和统一控制接口”层。

适合放：

- `mock_robot.py`
- `isaacsim_robot.py`
- `get_robot.py`
- `server.py`
- 统一错误语义
- 统一 health/status 接口

不适合放：

- grounding
- segmentation
- task interpretation
- grasp proposal

## 2.3 `a1z_ext/interfaces`

这是共享 schema 层。

适合放：

- `TaskSpec`
- `GroundingCandidate`
- `MaskCandidate`
- `Object3DDescriptor`
- `GraspCandidate`
- `ExecutablePlan`
- `ExecutionResult`
- `PerceptionFrame`

这层必须尽量稳定、弱依赖、可序列化。

## 2.4 `a1z_ext/perception`

这是共享感知主路径。

适合放：

- 指令解释
- grounding 调用封装
- segmentation 调用封装
- depth + mask -> 3D descriptor

不适合放：

- Isaac prim 读写
- RealSense 驱动调用
- 机器人控制命令

## 2.5 未来的 `a1z_ext/grasping`

这是当前最该新增的一层。

适合放：

- 规则式 top-down grasp proposal
- 学习式 grasp proposal 的统一包装
- executability filter
- safety profile 判定

这一层的输入应该是：

- `Object3DDescriptor`
- 机器人约束

输出应该是：

- `GraspCandidate`
- `ExecutablePlan`

## 2.6 未来的 `a1z_ext/task`

这是任务执行层。

适合放：

- 抓取状态机
- 后抓验证
- 重试策略
- failure taxonomy

这一层可以依赖：

- `a1z_ext/robots`
- `a1z_ext/grasping`
- `a1z_ext/interfaces`

但不应该反过来让底层依赖它。

## 2.7 未来的 `a1z_ext/runtime`

如果后续开始接真实 Isaac 帧和真机帧，建议新增这一层。

适合放：

- `frame_sources/isaac_rgbd.py`
- `frame_sources/realsense_rgbd.py`
- `calibration.py`
- `logging.py`

这层负责把“不同后端的原始观测”整理成统一对象。

## 3. 后续功能应该往哪里加

下面给出一个明确归属表，避免后面又混回去。

## 3.1 真实 Isaac RGB-D 取帧

应放：

- `a1z_ext/runtime/frame_sources/isaac_rgbd.py`
- 必要的 Isaac 绑定留在 `exts/a1z.d405.runtime` 的 service 边界

不应放：

- `vendor`
- `a1z_ext/perception`

原因：

- 取帧是后端适配层，不是 perception 主逻辑

## 3.2 RealSense 真机 RGB-D 取帧

应放：

- `a1z_ext/runtime/frame_sources/realsense_rgbd.py`

不应放：

- `vendor`
- Isaac extension

## 3.3 GroundingDINO / SAM2 集成

应放：

- `a1z_ext/perception`

不应放：

- `vendor`
- `exts/a1z.d405.runtime`
- `a1z_ext/robots`

原因：

- 这是共享 perception 层，不属于机器人 backend

## 3.4 3D 几何恢复增强

应放：

- `a1z_ext/perception/object_3d.py`
- 或其下属几何辅助模块

不应放：

- `vendor`
- Isaac extension

## 3.5 抓取候选与约束筛选

应放：

- `a1z_ext/grasping`

不应放：

- `vendor`
- `a1z_ext/robots`

原因：

- 这是任务中间层，不是底层驱动层

## 3.6 抓取状态机、验证与重试

应放：

- `a1z_ext/task`

不应放：

- `vendor`
- `scripts`

原因：

- 这是长期演化的业务逻辑，不应沉淀在临时脚本

## 4. 明确禁止的混层模式

后续开发时，下面这些模式应该明确禁止。

## 4.1 禁止在 `vendor` 里继续长本地任务语义

例如：

- 本地抓取 CLI
- 本地 server contract
- 本地 perception 逻辑
- 本地安全阈值

这些一旦继续进 `vendor`，后面再同步上游会再次变脏。

## 4.2 禁止让共享 perception 模块直接依赖 Isaac API

例如：

- 在 `grounding.py` 里直接读 stage
- 在 `object_3d.py` 里直接访问 prim

这会让真机路径根本复用不了。

## 4.3 禁止让 `scripts/` 里堆积长期业务逻辑

如果某个脚本里开始出现：

- 状态机
- 候选筛选
- 执行约束

那说明这段逻辑应该下沉进 `a1z_ext` 模块。

## 4.4 禁止把“调试专用真值捷径”写进共享主路径

例如：

- Isaac 真值 bbox
- Isaac 真值 pose
- Isaac 真值 mask

这些最多只能是 debug path，不能进入共享主路径默认流程。

## 5. 推荐的最终目录形态

后续如果把整条 pipeline 补完整，建议目录收敛成这样：

```text
vendor/GALAXEA-A1Z/
  # 上游镜像，仅保留上游语义

a1z_ext/
  config/
  robots/
  interfaces/
  runtime/
  perception/
  grasping/
  task/

exts/
  a1z.d405.runtime/
    # 仅 Isaac D405 runtime 资产和服务

scripts/
  # 启动、验证、编排入口

docs/
  # 规范、审计、roadmap、评测
```

## 6. 归属规范总结

这份归属规则可以浓缩成四句：

1. 上游能力留在 `vendor`
2. 本地共享逻辑进 `a1z_ext`
3. Isaac 专有相机运行时留在 `exts/a1z.d405.runtime`
4. 脚本只负责编排，文档负责约束，不再把长期语义写回镜像
