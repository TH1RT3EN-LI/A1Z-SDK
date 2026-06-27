# 当前开放词汇 Pipeline 能力审计

本文档只回答三件事：

- 基于当前仓库实际代码，A1Z 项目已经走到哪一步
- 哪些能力是真有的，并且已经在当前环境里验证过
- 哪些能力只是接口占位、局部实现，或者仍然缺失

结论先行：

- **当前已经具备控制底座、统一 RGB-D 观测层和非抓取版 bundle 闭环**
- **当前已经能从 Isaac D405 资产采一帧 RGB-D，并送进共享 perception 主干**
- **当前还不具备“给定自然语言和 RGB-D，稳定完成抓取”的完整系统**

更准确地说，当前系统已经从“只有 SDK 和规划文档”推进到：

- 有共享 schema
- 有共享 frame source / observation 语义
- 有 sample / Isaac 双输入闭环
- 有 bundle 落盘和验证脚本

但仍然停在：

- grounding / segmentation 为 stub
- 只有 `Object3DDescriptor`
- 没有 `GraspCandidate`、`ExecutablePlan`、`ExecutionResult`
- 没有抓取执行状态机

## 1. 已验证能力

这里的“已验证”指的是：当前环境内可以实际跑通，并且仓库里有对应代码与验证脚本。

## 1.1 控制后端分层已存在

当前仓库已经把本地扩展和上游 SDK 拆开：

- 上游镜像：`vendor/GALAXEA-A1Z`
- 本地扩展：`a1z_ext`

其中 [`a1z_ext/robots/get_robot.py`](../a1z_ext/robots/get_robot.py) 已提供三类 backend：

- `socketcan`
- `mock`
- `isaacsim`

这意味着上位机后续不必直接绑定某一种底层驱动，可以围绕统一机器人接口继续建设任务系统。

## 1.2 Isaac 机器人 backend 具备实际控制语义

[`a1z_ext/robots/isaacsim_robot.py`](../a1z_ext/robots/isaacsim_robot.py) 当前已经具备：

- 关节状态读取
- 夹爪状态读取
- 关节目标命令
- 夹爪目标命令
- 轨迹播放
- Isaac 主线程调度
- 关节限位缓存
- 控制模式、增益和 DOF 信息回传

这说明 Isaac 侧不是单纯“能看到模型”，而是已经能承担统一控制后端的角色。

## 1.3 mock backend 足以承担上层逻辑联调

[`a1z_ext/robots/mock_robot.py`](../a1z_ext/robots/mock_robot.py) 已提供：

- 关节状态维护
- 限位裁剪
- gripper 语义
- 插值式 `move_joints`
- 录制 / 回放接口

这意味着后续即使真机和 Isaac 暂时不稳定，上层任务状态机、超时、失败分类和服务契约仍然可以先在 `mock` 上推进。

## 1.4 控制服务边界已经形成

[`a1z_ext/robots/server.py`](../a1z_ext/robots/server.py) 已把统一机器人接口包装成 socket 服务，并暴露：

- `status`
- `move`
- `command`
- `gripper`
- `dance`
- `stop`
- `info`

这说明当前仓库已经具备运行时服务边界，而不是只有脚本直连对象。

## 1.5 D405 Isaac 运行时资产已接入

当前本地 extension：

- [`exts/a1z.d405.runtime`](../exts/a1z.d405.runtime)

已经承担两件关键工作：

1. 在场景里挂接 D405 腕部相机资产
2. 维护 color / depth 相机 prim 路径，并提供运行时服务

这一步很关键，因为后续共享采帧入口已经不是散落的 prim path 字符串，而是统一的运行时资产边界。

## 1.6 统一 observation / frame source 已经落地

当前仓库已经新增并接入：

- [`a1z_ext/interfaces/observation.py`](../a1z_ext/interfaces/observation.py)
- [`a1z_ext/runtime/frame_sources/base.py`](../a1z_ext/runtime/frame_sources/base.py)
- [`a1z_ext/runtime/frame_sources/sample_rgbd.py`](../a1z_ext/runtime/frame_sources/sample_rgbd.py)
- [`a1z_ext/runtime/frame_sources/isaac_rgbd.py`](../a1z_ext/runtime/frame_sources/isaac_rgbd.py)

其中已经存在：

- `CameraIntrinsics`
- `RGBDObservation`
- `RGBDFrameCapture`
- `FrameSource`
- `SampleRGBDFrameSource`
- `IsaacD405FrameSource`

所以“统一 observation schema 还没有”这句话已经不成立。  
当前更准确的说法是：

- **统一 observation 层已经建立**
- **后续仍需扩到真机 RGB-D adapter，并补强长期稳定性**

## 1.7 非抓取版 open-vocab bundle 闭环已验证

当前共享 perception 骨架包括：

- [`a1z_ext/interfaces/schemas.py`](../a1z_ext/interfaces/schemas.py)
- [`a1z_ext/perception/task_interpreter.py`](../a1z_ext/perception/task_interpreter.py)
- [`a1z_ext/perception/grounding.py`](../a1z_ext/perception/grounding.py)
- [`a1z_ext/perception/segmentation.py`](../a1z_ext/perception/segmentation.py)
- [`a1z_ext/perception/object_3d.py`](../a1z_ext/perception/object_3d.py)
- [`a1z_ext/perception/pipeline.py`](../a1z_ext/perception/pipeline.py)

当前闭环对象为：

- `TaskSpec`
- `GroundingCandidate[]`
- `MaskCandidate[]`
- `Object3DDescriptor[]`
- `PipelineBundle`

并且当前环境里，下面这条验证已经通过：

- [`scripts/verify_open_vocab_data_loop_in_container.sh`](../scripts/verify_open_vocab_data_loop_in_container.sh)

验证结果确认：

- `task.action_type == "pick"`
- `grounding_candidates == 3`
- `mask_candidates == 3`
- `object_descriptors >= 1`
- `observation.source_backend == "sample"`

## 1.8 Isaac D405 -> 共享 perception observation / bundle 链路已在当前环境复验

当前仓库已经新增：

- [`scripts/run_open_vocab_data_loop_from_isaac.py`](../scripts/run_open_vocab_data_loop_from_isaac.py)
- [`scripts/verify_open_vocab_data_loop_from_isaac_in_container.sh`](../scripts/verify_open_vocab_data_loop_from_isaac_in_container.sh)

并且它当前已经明确具备下面这些“功能存在”能力，产物包括：

- `bundle.json`
- `observation.json`
- `observation_metadata.json`
- `rgb.npy`
- `depth_m.npy`
- `intrinsics.json`
- `extrinsic_camera_to_target.npy`
- `extrinsic_camera_to_base.npy`
- `masks/*.npy`

当前它稳定能证明的是：

- `observation.source_backend == "isaacsim_d405"`
- `observation.camera_frame_id == "d405_color_optical_frame"`
- `observation.target_frame_id == "robot_base_frame"`
- `bundle.json` / `observation.json` / 原始 `rgb/depth` 文件会被产出

但当前最新单实例验证结果也表明：

- `progress.step == "bundle_written"`
- `grounding_candidates == 3`
- `mask_candidates == 3`
- `object_descriptors == 3`

因此当前更准确的认定应是：

- **Isaac 真实 RGB-D 接入已经打通**
- **并且当前 Docker 内专项 verify 已恢复出非空 `Object3DDescriptor`**

## 2. 已实现但仍有残余风险的部分

这些能力当前不是“没有”，而是“已经能工作，但还不能当成长期稳定能力来依赖”。

## 2.1 Isaac 专项采帧路径仍有运行时噪声

当前新的主要问题已经不是早先的 `asyncio` re-entry，而是：

- verify 脚本如果不做单实例清理，会叠多份 Kit 进程，占满 GPU
- 当前专项 verify 已通过，但仍依赖专项 runner 和单实例运行约束
- D405 optical frame 和专项启动路径已经收敛到当前可用状态

当前 [`scripts/verify_open_vocab_data_loop_from_isaac_in_container.sh`](../scripts/verify_open_vocab_data_loop_from_isaac_in_container.sh) 已补上“启动前清理旧专项 Kit 进程”的逻辑，避免多实例污染结果。

但这条路径目前仍意味着：

- 这条路径已经适合作为“专项验证和骨架验证”
- 是否适合作为高频、长时、稳定的数据生产路径仍需额外验证

## 2.2 3D 恢复是可用雏形，不是最终几何层

[`a1z_ext/perception/object_3d.py`](../a1z_ext/perception/object_3d.py) 当前已经在做真实的：

- `mask + depth + intrinsics + extrinsic -> 点云恢复`
- 质心、顶部点、包围盒、主轴估计

但它仍然是 MVP 几何层，当前还没有：

- 稳定支撑面拟合
- 法向稳健估计
- 工作空间 / keepout 检查
- 几何异常分类
- Open3D 增强

因此更准确的判断是：

- **当前已经有真实几何恢复雏形**
- **但还没有达到抓取规划可直接依赖的稳态**

## 2.3 grounding / segmentation 虽然可跑，但本质仍然是 stub

当前：

- [`a1z_ext/perception/grounding.py`](../a1z_ext/perception/grounding.py) 只是 deterministic stub，并对红色区域做简单启发式 box 推断
- [`a1z_ext/perception/segmentation.py`](../a1z_ext/perception/segmentation.py) 仍然是 box 派生矩形 mask

它们的价值在于：

- 固定数据契约
- 验证 perception 主干拼装
- 让 Isaac RGB-D 闭环先跑起来

它们不证明：

- 真实 open-vocabulary grounding 能力
- 真实 SAM2 分割能力

## 3. 当前明确缺失的模块

下面这些能力，当前仓库还没有真正落到代码。

## 3.1 没有 grasp candidate 层

当前只有 `Object3DDescriptor`，没有：

- `GraspCandidate`
- top-down / learned grasp proposal
- 多候选重排序

也就是说，现在只有“目标 3D 描述”，还没有“怎么抓”的显式对象。

## 3.2 没有 executability filter

当前控制后端和 IK 基础不等于任务级可执行性层。  
当前仓库里还没有独立的：

- pregrasp 可达性检查
- grasp 可达性检查
- lift / retreat 可达性检查
- joint margin 检查
- keepout / 桌面 / 相机支架安全约束
- 当前姿态连续性排序

因此不能把“IK 有解”直接等价成“可以执行抓取”。

## 3.3 没有抓取执行状态机

当前还没有独立的抓取任务执行器，例如：

- `OpenGripper`
- `MoveToPregrasp`
- `Approach`
- `CloseGripper`
- `Lift`
- `Retreat`
- `Verify`

这层不补上，就仍然只是 perception + control pieces，不是抓取系统。

## 3.4 没有抓后验证与失败分类

当前没有：

- 抓取成功 / 失败判定
- 失败阶段分类
- 重试策略
- 结构化 `ExecutionResult`

因此即使后面能走完一次动作，也还不能说已经形成任务级系统。

## 3.5 没有真机 RGB-D adapter

当前共享 observation 层已经建立，Isaac adapter 也已实现。  
但真机侧仍然缺：

- `realsense_d405` 或等价 frame source
- 真机标定版本管理
- 真机 RGB / depth 同步与健康检查

所以现在是：

- **Isaac / sample 双输入已打通**
- **真机 RGB-D 适配仍未接入**

## 4. 当前最合理的工程判断

基于当前仓库真实状态，应当这样判断。

## 4.1 “先在 Isaac 完成前半段 pipeline，再迁移真机”是可行路线

因为当前已经具备：

- 统一 observation / bundle 契约
- 共享 perception 主干
- Isaac 真实 RGB-D 接入
- 统一机器人 backend 分层

这条路线在架构上是正确的。

## 4.2 “现在已经能直接用 SDK 完成抓取任务”这个结论不成立

当前 SDK 和本地扩展已经足够承接抓取系统，但还没有把中间缺口补齐。  
至少还差：

- 真 grounding / SAM2
- grasp proposal
- executability filter
- grasp FSM
- post-grasp verification

## 4.3 当前最该补的不是更多脚本，而是中间层

当前下一阶段的优先级应是：

1. 稳住 Isaac observation 路径
2. 引入真机 RGB-D adapter
3. 用真实模型替换 grounding / segmentation stub
4. 定义 `GraspCandidate` / `ExecutablePlan` / `ExecutionResult`
5. 补 executability filter 和 grasp FSM

## 5. 结论

当前 A1Z 项目已经证明了三件事：

1. 本地语义和上游 SDK 的分层方向是对的
2. 非抓取版 open-vocab RGB-D 数据闭环已经落地并可复验
3. Isaac D405 已经能够作为共享 perception 主干的真实观测输入

但当前项目还没有证明：

1. 真实 open-vocabulary grounding / segmentation 已经可用
2. 抓取候选生成和可执行性筛选已经存在
3. 整条抓取任务链已经可稳定执行

因此最准确的状态描述应是：

- **控制底座已具备**
- **Isaac 内非抓取 perception 闭环已打通**
- **真抓取系统仍缺中间规划与执行层**
