# 开放词汇感知数据闭环

本文档说明当前仓库已经具备的“非抓取版”开放词汇 RGB-D 数据闭环，以及它在当前环境中的真实验证状态。

当前目标仍然是：

- 在现有 docker / Isaac 容器内
- 先不做抓取执行
- 先把统一数据契约、统一观测入口和 perception bundle 闭环做稳

当前闭环覆盖：

1. 自然语言指令
2. `TaskSpec`
3. `GroundingCandidate[]`
4. `MaskCandidate[]`
5. `Object3DDescriptor[]`
6. `PipelineBundle`
7. `RGBDObservation` 与原始观测落盘

当前明确不覆盖：

- 真实 GroundingDINO
- 真实 SAM2
- grasp proposal
- executability filter
- grasp FSM
- post-grasp verification

## 1. 当前实现位置

### schema

- [`a1z_ext/interfaces/schemas.py`](../a1z_ext/interfaces/schemas.py)
- [`a1z_ext/interfaces/observation.py`](../a1z_ext/interfaces/observation.py)

### frame source / runtime

- [`a1z_ext/runtime/frame_sources/base.py`](../a1z_ext/runtime/frame_sources/base.py)
- [`a1z_ext/runtime/frame_sources/sample_rgbd.py`](../a1z_ext/runtime/frame_sources/sample_rgbd.py)
- [`a1z_ext/runtime/frame_sources/isaac_rgbd.py`](../a1z_ext/runtime/frame_sources/isaac_rgbd.py)

### perception

- [`a1z_ext/perception/task_interpreter.py`](../a1z_ext/perception/task_interpreter.py)
- [`a1z_ext/perception/grounding.py`](../a1z_ext/perception/grounding.py)
- [`a1z_ext/perception/segmentation.py`](../a1z_ext/perception/segmentation.py)
- [`a1z_ext/perception/object_3d.py`](../a1z_ext/perception/object_3d.py)
- [`a1z_ext/perception/pipeline.py`](../a1z_ext/perception/pipeline.py)

### scripts

- [`scripts/run_open_vocab_data_loop.py`](../scripts/run_open_vocab_data_loop.py)
- [`scripts/verify_open_vocab_data_loop_in_container.sh`](../scripts/verify_open_vocab_data_loop_in_container.sh)
- [`scripts/run_open_vocab_data_loop_from_isaac.py`](../scripts/run_open_vocab_data_loop_from_isaac.py)
- [`scripts/verify_open_vocab_data_loop_from_isaac_in_container.sh`](../scripts/verify_open_vocab_data_loop_from_isaac_in_container.sh)

## 2. 当前主数据流

当前共享主干已经从“散装 `rgb/depth/intrinsics/extrinsic` 参数”收敛成：

```text
FrameSource
  -> RGBDFrameCapture
  -> RGBDObservation
  -> run_pipeline_from_frame_capture(...)
  -> PipelineBundle
```

其中：

- `FrameSource` 负责从不同后端采一帧
- `RGBDFrameCapture` 负责把 observation 与原始 `rgb/depth` 打包
- `run_pipeline_from_frame_capture(...)` 负责拼装共享 perception bundle

这意味着 perception 主干已经不需要直接依赖 Isaac API、ROS2 消息结构或真机驱动对象。

## 3. 当前两条输入路径

## 3.1 sample 路径

sample 路径使用：

- [`SampleRGBDFrameSource`](../a1z_ext/runtime/frame_sources/sample_rgbd.py)

并通过：

- [`scripts/run_open_vocab_data_loop.py`](../scripts/run_open_vocab_data_loop.py)

构造统一 `RGBDFrameCapture`，再进入共享 pipeline。

这条路径当前在环境内已稳定通过验证：

- [`scripts/verify_open_vocab_data_loop_in_container.sh`](../scripts/verify_open_vocab_data_loop_in_container.sh)

## 3.2 Isaac 路径

Isaac 路径使用：

- [`IsaacD405FrameSource`](../a1z_ext/runtime/frame_sources/isaac_rgbd.py)

并通过：

- [`scripts/run_open_vocab_data_loop_from_isaac.py`](../scripts/run_open_vocab_data_loop_from_isaac.py)

直接从 Isaac D405 资产采集：

- RGB
- depth
- intrinsics
- `camera -> target` 外参

然后送进同一条共享 perception 主干。

这条路径当前已经能稳定产出下列文件：

- `observation.json`
- `bundle.json`
- `rgb.npy`
- `depth_m.npy`

并且截至 2026-06-09，专项验证里已经恢复出非空 `Object3DDescriptor`。

## 4. 当前落盘产物

当前 bundle runner 会固定落盘下面这些文件：

```text
runtime/<run_name>/
  bundle.json
  observation.json
  observation_metadata.json
  rgb.npy
  depth_m.npy
  intrinsics.json
  extrinsic_camera_to_target.npy
  extrinsic_camera_to_base.npy
  masks/*.npy
```

它们的职责分别是：

- `bundle.json`
  - 共享 perception 主结果
- `observation.json`
  - 统一 RGB-D 观测 schema
- `observation_metadata.json`
  - adapter 侧调试信息
- `rgb.npy` / `depth_m.npy`
  - 原始观测回放数据
- `intrinsics.json` / `extrinsic_*.npy`
  - 几何恢复输入

## 5. 当前专项 Isaac 验证产物状态

在当前环境中，截至 2026-06-09 的专项 Isaac 验证结果满足：

- `progress.step == "bundle_written"`
- `grounding_candidates == 3`
- `mask_candidates == 3`
- `object_descriptors == 3`

`observation.json` 中的关键字段为：

- `source_backend == "isaacsim_d405"`
- `camera_frame_id == "d405_color_optical_frame"`
- `target_frame_id == "robot_base_frame"`
- `sensor_model == "simulated_realsense_d405"`
- `calibration_version == "isaac_d405_runtime_v1"`

`observation_metadata.json` 中还包含：

- `stage_path`
- `color_camera_path`
- `depth_camera_path`
- `render_product_path`

这说明当前 Isaac 路径已经不只是“能出几张图”，而是已经在当前 Docker/Isaac 容器里专项验通了统一 bundle。

## 6. 当前实现的性质

当前实现是：

- **真实观测层 + 真实几何恢复雏形 + stub 感知前端**

更具体地说：

- `observation`、`frame source`、落盘结构是真的
- `mask + depth -> Object3DDescriptor` 是真的
- `grounding.py` 和 `segmentation.py` 当前还是占位实现

这样做的工程价值是：

- 先把输入输出对象和运行边界稳定下来
- 让 Isaac / sample 路径共享同一 perception 主干
- 为后续替换 GroundingDINO / SAM2 留出稳定接口

## 7. 当前闭环已经证明了什么

当前这条闭环已经证明：

1. perception 主干可以只依赖统一 `RGBDFrameCapture`
2. sample 与 Isaac 可以共享同一 bundle 逻辑
3. Isaac D405 运行时资产能够作为共享 perception 的真实观测输入
4. `TaskSpec -> GroundingCandidate[] -> MaskCandidate[] -> Object3DDescriptor[] -> PipelineBundle` 这条数据链已经在工程上落地

## 8. 当前闭环没有证明什么

当前闭环没有证明：

1. 真实 open-vocabulary grounding 已可用
2. 真实 SAM2 segmentation 已可用
3. 真实 GroundingDINO / SAM2 已接入
4. 抓取候选、可执行性筛选和任务状态机已经存在

## 9. 当前限制

当前版本有三类明确限制。

## 9.1 模型能力限制

- grounding 仍是 stub
- segmentation 仍是 stub
- 没有多模态推理质量评估

## 9.2 几何能力限制

- 几何恢复仍是 MVP
- 没有 Open3D 增强
- 没有稳定支撑面 / 法向估计
- 没有工作空间与 keepout 约束

## 9.3 运行时限制

- Isaac 路径当前依赖专项 runner / verify 入口，尚未证明适合长时间高频数据生产
- verify 脚本必须保持单实例清理，否则旧 Kit 进程会叠加占满 GPU
- 真机 RGB-D frame source 还未接入

## 10. 下一步替换顺序

推荐按下面顺序替换和扩展当前闭环：

1. 稳住 Isaac frame source 的 async / sync 边界
2. 新增真机 RGB-D frame source
3. 用真实结构化 LLM / VLM 替换任务解释占位逻辑
4. 用 GroundingDINO 替换 `grounding.py` stub
5. 用 SAM2 替换 `segmentation.py` stub
6. 用 Open3D 增强 `object_3d.py`
7. 在此基础上新增 `GraspCandidate` 与 executability 层

## 11. 结论

当前仓库已经具备：

- 在现有 docker / Isaac 容器内运行
- 统一 observation / frame source 层
- sample / Isaac 双输入
- 非抓取版 open-vocab RGB-D bundle 闭环

这一步的意义是：

- 把项目从“只有规划文档”推进到“已有可运行的数据主干”
- 并为后续真实模型接入和抓取执行层补齐打下稳定边界
