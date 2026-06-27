# A1Z 中 SAM 与 AnyGrasp 的官方输入输出与调用方式

本文档只回答一件事：基于当前官方公开指导，SAM 和 AnyGrasp 分别吃什么输入、吐什么输出、以及应该怎么调用；同时给出它们在 A1Z 当前工程里的推荐接法。

当前 A1Z 主线默认采用：

- SAM: `SAM 2.1`
- AnyGrasp: `graspnet/anygrasp_sdk`

对应本仓库当前固定源码位置：

- `vendor/vision/sam2`
- `vendor/vision/anygrasp_sdk`

相关运行时目录：

- SAM checkpoint: `runtime/models/sam2/`
- AnyGrasp checkpoint: `runtime/models/anygrasp/`
- AnyGrasp license: `runtime/licenses/anygrasp/`

## 1. 结论先行

这两个模型在 A1Z 里的角色不要混：

- SAM 负责 `2D prompt -> mask`
- AnyGrasp 负责 `3D point cloud -> grasp candidates`

它们不是互相替代关系，而是串联关系：

```text
RGB image
  -> grounding / box / point prompt
  -> SAM mask
  -> mask 过滤 depth / point cloud
  -> AnyGrasp
  -> grasp candidates
  -> A1Z grasp adapter
  -> /a1z/move_ee 或后续 /a1z/pick_object
```

如果把 AnyGrasp 直接喂整幅场景点云，它也能跑，但在桌面抓取场景里，先用 SAM 做目标裁剪通常更稳，也更省后处理成本。

## 2. SAM 2.1

## 2.1 官方定位

按照 Meta 官方 `sam2` README，SAM 2.1 当前主接口分两类：

- 单帧图像分割：`SAM2ImagePredictor`
- 视频分割与跟踪：`SAM2VideoPredictor`

A1Z 当前主线优先用单帧图像分割；视频接口先作为后续增强项保留。

## 2.2 官方输入

### 图像模式

官方图像接口的最小调用流程是：

1. 构建模型
2. `set_image(...)`
3. `predict(...)`

`set_image(image)` 的输入：

- `image`
  - 类型：`numpy.ndarray` 或 `PIL.Image`
  - 语义：RGB 图像
  - 形状：
    - `numpy` 时为 `H x W x C`
    - `PIL.Image` 时为常规 RGB 图像对象
  - 像素范围：`[0, 255]`

`predict(...)` 的主要 prompt 输入：

- `point_coords`
  - 类型：`np.ndarray`
  - 形状：`N x 2`
  - 语义：点提示，像素坐标 `(x, y)`
- `point_labels`
  - 类型：`np.ndarray`
  - 形状：`N`
  - 语义：
    - `1` 前景点
    - `0` 背景点
- `box`
  - 类型：`np.ndarray`
  - 形状：`4`
  - 语义：`XYXY`
- `mask_input`
  - 类型：`np.ndarray`
  - 形状：典型为 `1 x H x W`
  - 语义：上一次低分辨率 mask logit，通常用于 refine
  - 官方源码注释里沿用 SAM 习惯，常见尺寸是 `1 x 256 x 256`
- `multimask_output`
  - `True` 时，单点等模糊 prompt 会返回多个候选 mask
- `return_logits`
  - `True` 时返回未阈值化 logits
- `normalize_coords`
  - 默认 `True`
  - 在官方源码语义里，这表示你传入的是原图像素坐标，内部会按原图宽高归一化再变到模型分辨率

### 视频模式

官方视频接口的最小调用流程是：

1. `predictor.init_state(video)`
2. `predictor.add_new_points_or_box(...)`
3. `predictor.propagate_in_video(...)`

视频模式关键输入：

- `video`
  - 传给 `init_state(...)`
  - 官方实现会加载整段视频帧并建立 inference state
- `frame_idx`
  - prompt 所在帧索引
- `obj_id`
  - 你自己分配的对象 ID
- `points` / `labels`
  - 与图像模式类似
- `box`
  - 同样是 `XYXY`

## 2.3 官方输出

### 图像模式

`predict(...)` 返回三项：

1. `masks`
   - 类型：`np.ndarray`
   - 形状：`C x H x W`
   - 语义：输出 mask，`H/W` 已恢复到原图尺寸
2. `iou_predictions`
   - 类型：`np.ndarray`
   - 形状：`C`
   - 语义：每个 mask 的质量分数
3. `low_res_masks`
   - 类型：`np.ndarray`
   - 形状：`C x 256 x 256` 一类的低分辨率 logits
   - 语义：可回灌给下一轮 `mask_input` 做 refinement

这里最重要的是：

- `masks` 给后续几何恢复使用
- `iou_predictions` 给 mask 排序和过滤使用
- `low_res_masks` 给交互式迭代 refine 使用

### 视频模式

`add_new_points_or_box(...)` 返回：

- `frame_idx`
- `obj_ids`
- `video_res_masks`

`propagate_in_video(...)` 逐帧 yield：

- `frame_idx`
- `obj_ids`
- `video_res_masks`

其中 `video_res_masks` 是按原视频分辨率还原后的 mask score tensor，按对象维度组织，不是单个对象的二值图。

## 2.4 官方调用方式

### 图像模式官方范式

```python
import torch
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

checkpoint = "runtime/models/sam2/sam2.1_hiera_small.pt"
model_cfg = "configs/sam2.1/sam2.1_hiera_s.yaml"

predictor = SAM2ImagePredictor(build_sam2(model_cfg, checkpoint))

with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
    predictor.set_image(rgb_image)
    masks, ious, low_res_masks = predictor.predict(
        box=box_xyxy,
        point_coords=point_coords,
        point_labels=point_labels,
        multimask_output=True,
    )
```

### 视频模式官方范式

```python
import torch
from sam2.build_sam import build_sam2_video_predictor

checkpoint = "runtime/models/sam2/sam2.1_hiera_small.pt"
model_cfg = "configs/sam2.1/sam2.1_hiera_s.yaml"

predictor = build_sam2_video_predictor(model_cfg, checkpoint)

with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
    state = predictor.init_state(video_path)

    frame_idx, obj_ids, masks = predictor.add_new_points_or_box(
        state,
        frame_idx=0,
        obj_id=1,
        box=box_xyxy,
    )

    for frame_idx, obj_ids, masks in predictor.propagate_in_video(state):
        pass
```

## 2.5 A1Z 中的推荐接法

对于你当前这套 RGB-D 抓取链路，SAM 不应该直接承担“识别是什么”和“生成 grasp pose”的职责。A1Z 里推荐把它限制成下面这个边界：

```text
输入:
  RGB
  +
  GroundingCandidate.bbox_xyxy / point_xy

输出:
  MaskCandidate
```

建议落地规则：

- 输入只喂 RGB，不喂 depth
- prompt 优先级：
  - `box`
  - `box + point`
  - `mask_input` 只用于 refine
- 输出不直接泄漏 SAM 私有结构
- 统一转成你现有文档里的 `MaskCandidate`

推荐映射：

- `masks[rank]` -> `mask_rle` 或二值 mask
- `ious[rank]` -> `mask_score`
- `box_xyxy` -> `bbox_xyxy`
- prompt 类型 -> `prompt_type`

对于 A1Z 第一版桌面抓取，建议默认使用：

- `sam2.1_hiera_small`
- `multimask_output=True`
- 取 `iou_predictions` 最优的 1 个 mask 进入 3D 恢复

## 3. AnyGrasp

## 3.1 官方定位

AnyGrasp 官方 SDK 的职责是从点云中输出并排序抓取候选。它不是 2D 分割模型，也不负责开放词汇文本理解。

官方公开仓库当前包括两类能力：

- grasp detection
- grasp tracking

对 A1Z 当前阶段，真正主用的是 detection。

## 3.2 官方输入

### detection 模式

官方 demo 的核心输入不是 RGB 图像本身，而是从 RGB-D 恢复出的 3D 点云和颜色：

- `points`
  - 类型：`np.ndarray`
  - 形状：`N x 3`
  - 语义：点云坐标，单位米
- `colors`
  - 类型：`np.ndarray`
  - 形状：`N x 3`
  - 语义：每个点的 RGB
  - 范围：官方 demo 使用 `float32` 的 `[0, 1]`
- `lims`
  - 类型：长度为 6 的列表
  - 语义：工作空间裁剪范围
  - 格式：`[xmin, xmax, ymin, ymax, zmin, zmax]`
- 若从深度图恢复点云，还需要相机内参：
  - `fx, fy, cx, cy`
  - `scale`

官方 detection demo 的核心调用形态是：

```python
gg, cloud = detector.get_grasp(
    points,
    colors,
    lims=lims,
    apply_object_mask=True,
    dense_grasp=False,
    collision_detection=True,
)
```

主要开关含义：

- `apply_object_mask=True`
  - 默认按 objectness 过滤背景 grasp
- `dense_grasp=False`
  - 关闭超密 grasp 预测
- `collision_detection=True`
  - 打开碰撞过滤

官方 README 明确建议普通场景保持默认设置。

### tracking 模式

tracking demo 的逐帧输入同样是：

- `points: N x 3`
- `colors: N x 3`

再加一项：

- `grasp_ids`
  - 当前要跟踪的 grasp ID 列表

官方 demo 的核心调用形态：

```python
target_gg, curr_gg, target_grasp_ids, corres_preds = tracker.update(
    points,
    colors,
    grasp_ids,
)
```

## 3.3 官方输出

### detection 模式

`get_grasp(...)` 官方 demo 返回：

1. `gg`
   - 类型：`GraspGroup`
   - 语义：一组抓取候选
2. `cloud`
   - 类型：Open3D 点云对象
   - 语义：主要用于调试和可视化

官方 demo 紧接着通常会做：

```python
gg = gg.nms().sort_by_score()
gg_pick = gg[0:20]
```

所以对工程接入来说，`gg` 才是主输出。

按照 `graspnetAPI` 的公开定义，单个 `Grasp` 主要字段包括：

- `score`
- `width`
- `height`
- `depth`
- `rotation_matrix`
- `translation`
- `object_id`

也就是说，AnyGrasp 的本质输出已经接近一个抓取姿态候选：

- 位置：`translation`
- 姿态：`rotation_matrix`
- 夹爪开口：`width`
- 抓取深度：`depth`
- 置信/质量：`score`

### tracking 模式

`tracker.update(...)` 返回：

- `target_gg`
  - 当前目标 grasp 集合
- `curr_gg`
  - 当前帧全量 grasp 集合
- `target_grasp_ids`
  - 更新后的 grasp ID
- `corres_preds`
  - grasp correspondence 结果

对 A1Z 第一版单帧抓取，这一支可以先不接。

## 3.4 官方调用方式

### 当前官方 main 分支示例

截至 2026-06-26，AnyGrasp 官方 `main` 分支的公开 detection demo 仍是：

```python
from gsnet import AnyGrasp

anygrasp = AnyGrasp(cfgs)
anygrasp.load_net()
gg, cloud = anygrasp.get_grasp(points, colors, lims=lims)
```

### A1Z 当前 pinned 版本示例

A1Z 当前实际钉住的是较新的 dev 线，接口形态已经变成：

```python
from gsnet import create_detector

detector = create_detector(cfgs)
gg, cloud = detector.get_grasp(points, colors, lims=lims)
```

这两种写法表达的能力一致，但初始化入口不同。后面在 A1Z 里统一包装时，不要把上游 demo API 直接暴露到主流程。

## 3.5 非公开依赖

AnyGrasp 和 SAM 最大的工程差异在这里：

- SAM checkpoint 公开可下载
- AnyGrasp SDK 二进制、license、checkpoint 不是完全公开免条件直装

AnyGrasp 当前实际还需要：

- license
- detection checkpoint
- tracking checkpoint

按当前仓库约定，建议放在：

- `runtime/licenses/anygrasp/`
- `runtime/models/anygrasp/checkpoint_detection.tar`
- `runtime/models/anygrasp/checkpoint_tracking.tar`

license 申请还依赖 machine feature id。官方说明里，feature id 可由 SDK 生成，然后提交表单申请 license。

## 3.6 A1Z 中的推荐接法

在 A1Z 里，不建议让 AnyGrasp直接处理“全图全桌面原始点云”。更稳的边界是：

```text
输入:
  mask 过滤后的 object point cloud
  +
  colors
  +
  workspace lims

输出:
  top-k grasp proposals
```

建议流程：

1. 用深度图 + 相机内参恢复整帧点云
2. 用 SAM mask 过滤出目标物体点
3. 可选再做一次工作空间裁剪
4. 把 `points/colors/lims` 喂给 AnyGrasp
5. 对 `GraspGroup` 做 `nms().sort_by_score()`
6. 取 top-k 候选交给 `A1Z grasp adapter`

这里的 adapter 才负责：

- 坐标系变换到 `robot_base_frame`
- 夹爪朝向约束
- top-down 模式筛选
- IK 过滤
- pregrasp / descend / lift waypoint 生成

AnyGrasp 不应直接越过 adapter 控制机械臂。

## 4. A1Z 当前推荐的数据契约映射

## 4.1 SAM -> MaskCandidate

推荐映射到你现有契约：

```text
SAM 输入:
  RGB
  + GroundingCandidate.bbox_xyxy
  + 可选 GroundingCandidate.point_xy

SAM 输出:
  MaskCandidate
    - source_model = "sam2"
    - prompt_type = "box" / "box+point"
    - bbox_xyxy
    - mask_area_px
    - mask_score
    - depth_valid_ratio
    - rank
```

## 4.2 AnyGrasp -> GraspCandidate

推荐不要把上游 `GraspGroup` 原样散到系统里，而是包装成统一候选：

```text
AnyGrasp 输入:
  object points
  + colors
  + lims

AnyGrasp 输出:
  top-k GraspCandidate
    - position <- grasp.translation
    - orientation <- grasp.rotation_matrix
    - gripper_opening_m <- grasp.width
    - contact/depth hint <- grasp.depth
    - overall_score <- grasp.score
```

对于 A1Z 第一版 top-down 模式，建议再加一层姿态筛选：

- approach 方向要接近桌面法向负方向
- yaw 允许保留
- 对明显侧抓、倒抓候选直接降权或拒绝

## 5. 建议的最小封装边界

为了让后续 ROS2 和容器边界稳定，建议只暴露两个本地包装接口：

### `segmentation.py`

```python
predict_masks(
    rgb_image,
    box_xyxy=None,
    point_xy=None,
    point_label=None,
) -> list[MaskCandidate]
```

### `grasping.py`

```python
predict_grasps(
    points_xyz,
    colors_rgb,
    workspace_lims,
) -> list[GraspCandidate]
```

这样上层永远只看到你自己的 schema，不直接依赖：

- `SAM2ImagePredictor`
- `SAM2VideoPredictor`
- `AnyGrasp`
- `create_detector`
- `GraspGroup`

## 6. A1Z 当前落地建议

如果你的目标是尽快做出可跑的桌面抓取主链，推荐配置是：

### SAM

- 模型：`sam2.1_hiera_small`
- 模式：图像单帧
- prompt：`box` 为主，必要时 `box + point`

### AnyGrasp

- 模式：detection
- 输入：SAM mask 过滤后的目标点云
- 开关：
  - `apply_object_mask=True`
  - `dense_grasp=False`
  - `collision_detection=True`

### A1Z 系统边界

- SAM 只负责 mask
- AnyGrasp 只负责 grasp proposal
- A1Z grasp adapter 负责执行约束与 motion bridge

## 7. 参考依据

本说明基于下面这些官方公开材料和当前仓库 pin 住的源码：

- SAM 2 官方 README:
  - <https://github.com/facebookresearch/sam2>
- SAM 2 图像接口源码:
  - `vendor/vision/sam2/sam2/sam2_image_predictor.py`
- SAM 2 视频接口源码:
  - `vendor/vision/sam2/sam2/sam2_video_predictor.py`
- AnyGrasp 官方 README:
  - <https://github.com/graspnet/anygrasp_sdk>
- AnyGrasp 官方 detection demo:
  - `vendor/vision/anygrasp_sdk/grasp_detection/demo.py`
- AnyGrasp 官方 tracking demo:
  - `vendor/vision/anygrasp_sdk/grasp_tracking/demo.py`
- `graspnetAPI` 抓取对象定义:
  - <https://github.com/graspnet/graspnetAPI>

需要注意的一点是：AnyGrasp 官方仓库在 2026 年 6 月仍处于 license 工具与 API 过渡期，`main` 与 `dev` 分支的初始化写法存在轻微差异；A1Z 当前应以本仓库 pin 住的版本为准做工程封装。
