# 开放词汇 RGB-D 观测层规范

本文档定义当前 A1Z 项目里 Isaac / 真机共享 RGB-D 观测层的职责、对象和边界。

它关注的是：

- 上层 perception 应该看见什么
- Isaac / sample / 真机采帧层应负责什么
- 当前仓库里哪些部分已经落地
- 后续还应补哪些内容

结论先行：

- **共享 perception pipeline 现在已经可以只吃统一 `RGBDFrameCapture`**
- **Isaac / sample 差异已经被收敛在 `frame_sources` adapter 内**
- **下一步不是再讨论要不要 observation 层，而是继续补真机 frame source 和稳定性边界**

## 1. 当前已落地的对象

当前仓库已经实现：

- [`a1z_ext/interfaces/observation.py`](../a1z_ext/interfaces/observation.py)
- [`a1z_ext/runtime/frame_sources/base.py`](../a1z_ext/runtime/frame_sources/base.py)
- [`a1z_ext/runtime/frame_sources/sample_rgbd.py`](../a1z_ext/runtime/frame_sources/sample_rgbd.py)
- [`a1z_ext/runtime/frame_sources/isaac_rgbd.py`](../a1z_ext/runtime/frame_sources/isaac_rgbd.py)

已经存在的核心对象包括：

- `CameraIntrinsics`
- `RGBDObservation`
- `RGBDFrameCapture`
- `FrameSource`
- `SampleRGBDFrameSource`
- `IsaacD405FrameSource`

因此从当前仓库实况出发，观测层不是“建议新增”，而是“已经建立，仍需继续扩展”。

## 2. 当前对象模型

## 2.1 `CameraIntrinsics`

当前字段包括：

- `fx`
- `fy`
- `cx`
- `cy`
- `distortion_model`
- `distortion_coeffs`
- `schema_name`
- `schema_version`

当前阶段即使不做畸变建模，也保留：

- `distortion_model = "none"`
- `distortion_coeffs = []`

这样后面接真机不会推翻 schema。

## 2.2 `RGBDObservation`

职责：

- 描述一帧可送入 perception 主干的标准观测

当前字段包括：

- `observation_id`
- `timestamp_ns`
- `source_backend`
- `width`
- `height`
- `camera_frame_id`
- `target_frame_id`
- `intrinsics`
- `extrinsic_camera_to_target`
- `rgb_encoding`
- `depth_encoding`
- `rgb_path`
- `depth_path`
- `calibration_version`
- `sensor_model`
- `scene_context`
- `schema_name`
- `schema_version`

当前 `RGBDObservation.create(...)` 已负责：

- 构造 observation id
- 规范化 intrinsics
- 校验 `extrinsic_camera_to_target` 为 `4x4`

## 2.3 `RGBDFrameCapture`

职责：

- 把 observation 和一帧原始 `rgb/depth` 数据打包

当前字段包括：

- `observation`
- `rgb`
- `depth_m`
- `source_info`

并提供 `validate()`，当前会检查：

- `rgb` 维度是否合法
- `depth_m` 维度是否合法
- RGB / depth 分辨率一致
- observation 的宽高与图像一致
- 外参矩阵可解析

## 2.4 `FrameSource`

当前是共享 RGB-D 采帧接口，定义在：

- [`a1z_ext/runtime/frame_sources/base.py`](../a1z_ext/runtime/frame_sources/base.py)

当前语义包括：

- `open()`
- `capture() -> RGBDFrameCapture`
- `close()`
- `health() -> dict`

当前项目里最关键的约束是：

- `capture()` 返回的必须是已经整理好坐标语义的 `RGBDFrameCapture`
- 上层 perception 不再去问底层 prim path、ROS topic 或驱动句柄

## 3. 当前共享 perception 的入口

当前共享 perception 主入口已经是：

- [`run_pipeline_from_frame_capture(...)`](../a1z_ext/perception/pipeline.py)

也就是说，主逻辑现在已经不再以散装参数为主入口，而是以：

- `RGBDFrameCapture`

为主入口。

为了兼容旧路径，当前仍保留：

- `run_pipeline_from_observation(...)`

但它已经退化为向后兼容包装器，而不是主入口。

## 4. Isaac adapter 的职责

当前 Isaac adapter 为：

- [`IsaacD405FrameSource`](../a1z_ext/runtime/frame_sources/isaac_rgbd.py)

它当前负责：

1. 启用本地 `a1z.d405.runtime` extension
2. 获取当前 stage 或打开 stage
3. 通过运行时服务挂接 D405 资产
4. 获取 color / depth camera prim
5. 采集一帧 RGB / depth
6. 提取 intrinsics
7. 提取 `camera -> target` 外参
8. 组装 `RGBDObservation`
9. 组装 `RGBDFrameCapture`

它当前不负责：

- grounding
- segmentation
- 3D 恢复
- grasp proposal

这条边界必须继续保持。

## 5. sample adapter 的职责

当前 sample adapter 为：

- [`SampleRGBDFrameSource`](../a1z_ext/runtime/frame_sources/sample_rgbd.py)

它的作用是：

- 用一套稳定样例输入验证共享 perception 主干
- 让 observation / bundle 逻辑能在不依赖 Isaac 的情况下持续回归测试

它的价值不是替代真实输入，而是作为最小、稳定、低噪声的回归基线。

## 6. 真机 adapter 的目标形态

当前真机 frame source 还没有实现，但目标应当与 Isaac adapter 同构。

推荐新增：

- `a1z_ext/runtime/frame_sources/realsense_rgbd.py`

它应负责：

1. 初始化真机 RGB-D 设备
2. 同步一帧 RGB + depth
3. 读取当前 intrinsics
4. 读取标定得到的 `camera -> target` 外参
5. 组装 `RGBDObservation`
6. 组装 `RGBDFrameCapture`

它同样不应负责：

- 任务解释
- visual grounding
- segmentation
- grasp planning

## 7. 坐标语义要求

观测层最容易出问题的不是模型，而是坐标语义。

当前及后续都应固定下面这些规则：

- depth 单位统一为米
- `extrinsic_camera_to_target` 一律表示 `camera frame -> target frame`
- `target_frame_id` 当前推荐统一为 `robot_base_frame`
- `camera_frame_id` 必须进入 `observation.json`
- perception 主干只处理已经整理好的统一坐标语义

如果某个 adapter 当前只能取到世界坐标下的相机 pose，也必须在 adapter 内部整理成主链需要的语义，而不是把模糊坐标泄漏到上层。

## 8. 当前落盘规范

当前 bundle runner 已经固定输出：

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
  masks/
```

约束如下：

- `bundle.json` 只保存共享 perception 结果
- `observation.json` 保存统一观测 schema
- `observation_metadata.json` 保存 adapter 侧调试信息

这样做的价值是：

- Isaac / sample / 真机输出天然可比
- 离线回放与问题定位更直接

## 9. 当前验收状态

在当前环境内，观测层已经满足：

1. `sample` 能稳定产出 `RGBDFrameCapture`
2. `isaacsim_d405` 能稳定产出 `RGBDFrameCapture`
3. 同一 perception 主干同时接受两种 capture，不改主逻辑
4. `observation.json` 与 bundle 落盘结构一致

当前还没有满足的是：

1. 真机 RGB-D frame source 已接入
2. Isaac 长时稳定性已经完全收敛

## 10. 当前剩余风险

## 10.1 Isaac Kit async 边界

当前 Isaac 路径在日志中仍会出现 `asyncio` re-entry 类错误。  
这说明：

- `runheadless.sh --exec` 路径已经能完成 bundle 产出
- 但 `Kit async script + sync capture stepping` 的边界还需要进一步收敛

## 10.2 真机标定链尚未接入

当前 observation schema 已支持：

- `calibration_version`
- `camera_frame_id`
- `target_frame_id`
- `extrinsic_camera_to_target`

但真机侧还没有对应 adapter 和标定管理逻辑。

## 11. 后续扩展要求

后续继续建设时，观测层应坚持以下约束：

1. 共享 perception 不 import Isaac API
2. 共享 perception 不 import 真机驱动 API
3. 所有 backend 差异都留在 `frame_sources` adapter
4. 所有落盘继续围绕 `RGBDObservation + PipelineBundle`

## 12. 结论

当前仓库里的 observation 层已经从“建议”变成“现实”：

- 对象层已建立
- sample / Isaac 已接入
- perception 主干已切到统一 capture 入口

因此下一步应关注：

- 真机 frame source
- 长时稳定性
- 标定与健康检查

而不是重新讨论要不要这层。
