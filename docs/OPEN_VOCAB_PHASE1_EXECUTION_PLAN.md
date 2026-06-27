# 开放词汇非抓取闭环 Phase 1 执行计划

本文档只覆盖当前阶段：

- 在 Isaac 中完成统一观测闭环
- 使这条链可迁移到真机
- 暂时不做抓取执行

也就是说，当前目标不是：

- 自然语言到抓取成功

当前目标是：

- 自然语言
- RGB-D 观测
- grounding / segmentation 占位或替换实现
- 3D 描述恢复
- 统一 bundle 落盘

并要求这条链后续能直接接到真机相机输入。

## 1. 当前阶段完成定义

Phase 1 的完成标准不是“效果很智能”，而是“工程主干稳定”。

这一阶段的核心交付应包括：

1. 统一 observation 层
2. sample / Isaac 双输入路径
3. 非抓取 perception 主干
4. 可回放 bundle
5. 稳定专项验证脚本

## 2. 当前真实状态

基于当前仓库与当前环境复验，下面这些项已经完成。

## 2.1 已完成项

### P1-A：统一观测对象

已经落地：

- `CameraIntrinsics`
- `RGBDObservation`
- `RGBDFrameCapture`
- `FrameSource`

代码位置：

- [`a1z_ext/interfaces/observation.py`](../a1z_ext/interfaces/observation.py)
- [`a1z_ext/runtime/frame_sources/base.py`](../a1z_ext/runtime/frame_sources/base.py)

### P1-B：sample / Isaac 双输入路径

已经落地：

- `SampleRGBDFrameSource`
- `IsaacD405FrameSource`

代码位置：

- [`a1z_ext/runtime/frame_sources/sample_rgbd.py`](../a1z_ext/runtime/frame_sources/sample_rgbd.py)
- [`a1z_ext/runtime/frame_sources/isaac_rgbd.py`](../a1z_ext/runtime/frame_sources/isaac_rgbd.py)

### P1-C：perception 主干已切到 capture 入口

已经落地：

- `run_pipeline_from_frame_capture(...)`

兼容保留：

- `run_pipeline_from_observation(...)`

代码位置：

- [`a1z_ext/perception/pipeline.py`](../a1z_ext/perception/pipeline.py)

### P1-D：验证脚本已建立

当前环境内已明确：

- [`scripts/verify_open_vocab_data_loop_in_container.sh`](../scripts/verify_open_vocab_data_loop_in_container.sh) 稳定通过
- [`scripts/verify_open_vocab_data_loop_from_isaac_in_container.sh`](../scripts/verify_open_vocab_data_loop_from_isaac_in_container.sh) 已通过专项验证，并恢复出非空 `object_descriptors`

## 2.2 当前验收结果

当前可确认：

- `sample` 输入路径已稳定可运行
- Isaac D405 输入路径已打通到 observation / bundle 层，并已专项验通
- `TaskSpec -> GroundingCandidate[] -> MaskCandidate[] -> Object3DDescriptor[] -> PipelineBundle` 骨架已存在
- `observation.json` / `bundle.json` / 原始观测落盘结构已固定

因此当前状态应定义为：

- **样例闭环已完成**
- **Isaac observation / bundle 闭环已验通**
- **Isaac 几何恢复闭环已在专项 verify 下验通**
- **Phase 1 主干已经基本落地**

## 3. 当前阶段未完成项

Phase 1 虽然主干已基本落地，但仍有收尾项没有完成。

## 3.1 P1-E：Isaac 运行时稳定性收口

当前问题：

- 当前专项 verify 已通过
- verify 脚本还必须保持单实例清理，避免旧专项 Kit 进程叠加占满 GPU
- 仍需确认这条路径是否适合作为高频、长时、稳定数据生产入口

需要补：

- 在通过专项 verify 的基础上，继续验证长时间运行稳定性
- 保持专项验证脚本的单实例运行约束

退出条件：

- Isaac 验证不仅能写出 bundle，而且 `object_descriptors` 连续多次非空

## 3.2 P1-F：真机 RGB-D adapter 预留

当前 observation 层已存在，但真机 adapter 还未接入。

需要补：

- `realsense_d405` 或等价 frame source
- 真机标定版本管理
- 真机采帧健康检查

退出条件：

- 真机输入也能生成同结构 `RGBDFrameCapture`

## 3.3 P1-G：stub 替换边界稳定化

当前 `grounding.py` / `segmentation.py` 仍是 stub。  
Phase 1 不要求立刻替换成真模型，但要求：

- stub 的输入输出契约稳定
- 替换 GroundingDINO / SAM2 时不需要推翻目录和 schema

退出条件：

- 真实模型接入只需要替换模块实现，不需要重构主干

## 4. 当前阶段的代码资产

当前阶段的核心资产已经包括：

### 共享对象

- [`a1z_ext/interfaces/observation.py`](../a1z_ext/interfaces/observation.py)
- [`a1z_ext/interfaces/schemas.py`](../a1z_ext/interfaces/schemas.py)

### 运行时输入层

- [`a1z_ext/runtime/frame_sources/base.py`](../a1z_ext/runtime/frame_sources/base.py)
- [`a1z_ext/runtime/frame_sources/sample_rgbd.py`](../a1z_ext/runtime/frame_sources/sample_rgbd.py)
- [`a1z_ext/runtime/frame_sources/isaac_rgbd.py`](../a1z_ext/runtime/frame_sources/isaac_rgbd.py)

### 共享 perception

- [`a1z_ext/perception/pipeline.py`](../a1z_ext/perception/pipeline.py)
- [`a1z_ext/perception/task_interpreter.py`](../a1z_ext/perception/task_interpreter.py)
- [`a1z_ext/perception/grounding.py`](../a1z_ext/perception/grounding.py)
- [`a1z_ext/perception/segmentation.py`](../a1z_ext/perception/segmentation.py)
- [`a1z_ext/perception/object_3d.py`](../a1z_ext/perception/object_3d.py)

### runner / verify

- [`scripts/run_open_vocab_data_loop.py`](../scripts/run_open_vocab_data_loop.py)
- [`scripts/run_open_vocab_data_loop_from_isaac.py`](../scripts/run_open_vocab_data_loop_from_isaac.py)
- [`scripts/verify_open_vocab_data_loop_in_container.sh`](../scripts/verify_open_vocab_data_loop_in_container.sh)
- [`scripts/verify_open_vocab_data_loop_from_isaac_in_container.sh`](../scripts/verify_open_vocab_data_loop_from_isaac_in_container.sh)

## 5. 非目标

Phase 1 明确不做：

- grasp candidate 生成
- IK 可执行性筛选
- grasp FSM
- post-grasp verification
- 学习式 grasp proposal
- 任务导向抓取

这些事情应该进入下一阶段，而不是继续掺进当前 observation / bundle 主干。

## 6. 当前阶段技术栈要求

当前阶段继续保持：

- Python 3.11
- `numpy`
- `dataclasses`
- `.json + .npy` 落盘

在 observation / bundle 主干稳定后，再逐步引入：

- PyTorch
- OpenCV
- Open3D

但这些依赖不应倒过来主导当前阶段。

## 7. 当前质量门槛

Phase 1 当前至少应维持下面这些门槛。

## 7.1 结构门槛

- 共享 perception 不 import Isaac API
- 共享 perception 不 import 真机驱动 API
- `vendor` 不新增本地 pipeline 语义

## 7.2 运行门槛

- sample 验证稳定通过
- Isaac 验证至少稳定写出 observation 与 bundle
- 输出目录内容完整且可回放

## 7.3 数据门槛

- `bundle.json` 字段稳定
- `observation.json` 字段稳定
- `object_descriptors` 在 sample 输入下为非空
- Isaac 输入下恢复出非空 `object_descriptors` 已完成

## 8. 剩余风险与应对

当前阶段最现实的风险仍有三类。

## 8.1 Isaac 异步边界噪声

表现：

- 早先日志里出现过 `Cannot enter into task ... while another task ...`
- 当前更主要的表现是 streaming-hosted 采帧拿到空背景 / 错视角帧

应对：

- 收敛 `run_open_vocab_data_loop_from_isaac.py` 的执行模型
- 保持 `capture_async()` 路径
- 继续修采帧时序和相机 readiness

## 8.2 几何恢复仍是 MVP

表现：

- `Object3DDescriptor` 已可产出，但仍缺稳健几何处理

应对：

- 引入 Open3D 做法向、平面和质量增强
- 明确空 depth / 低质量点云的失败分类

## 8.3 真机输入仍未接入

表现：

- 当前 sim2real 仍停在 observation 契约层，不是完整真机闭环

应对：

- 新增真机 RGB-D frame source
- 补标定版本和健康检查

## 9. Phase 1 完成后的下一步

只有在当前阶段收口后，才应该进入下一阶段：

1. 接真实 GroundingDINO
2. 接真实 SAM2
3. 引入 Open3D 几何增强
4. 定义 `GraspCandidate`
5. 建 executability filter 与 grasp FSM

顺序不要倒。

## 10. 结论

当前 Phase 1 不再是纯计划态。  
更准确地说，它已经处在：

- **主干已完成**
- **稳定性与真机 adapter 仍待收口**

这就是当前最合理的工程判断。
