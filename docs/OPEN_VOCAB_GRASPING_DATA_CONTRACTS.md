# 开放词汇抓取数据契约

本文档定义开放词汇抓取 pipeline 的核心数据对象、字段语义、坐标规范和状态契约。

目标是让模块之间通过稳定 schema 通信，而不是靠自由文本、隐式约定和散乱字典。

## 1. 通用规则

## 1.1 命名与单位

- 长度单位：米
- 角度单位：弧度
- 图像像素坐标：左上角原点
- 三维坐标：右手系
- 时间：Unix timestamp 秒，或显式 `duration_s`
- 置信度：`0.0 ~ 1.0`

## 1.2 ID 规范

每个中间对象都必须具备稳定 ID：

- `task_id`
- `candidate_id`
- `mask_id`
- `object_id`
- `plan_id`
- `execution_id`

## 1.3 坐标系规范

推荐至少显式声明下面这些 frame：

- `camera_color_frame`
- `camera_depth_frame`
- `robot_base_frame`
- `tool_frame`
- `world_frame`
- `table_frame`

任何 3D 位置、姿态、法向都必须带 `frame_id`。

## 2. TaskSpec

自然语言解释层输出对象。

```json
{
  "task_id": "uuid",
  "action_type": "pick",
  "target_object": {
    "text": "the red mug",
    "attributes": ["red", "mug"],
    "negative_constraints": ["not the bottle"]
  },
  "target_part": null,
  "preferred_grasp_mode": "top_down",
  "preferred_approach_axis": "table_normal_negative",
  "gripper_opening_hint_m": null,
  "position_tolerance_m": 0.02,
  "orientation_tolerance_rad": 0.26,
  "timeout_s": 20.0,
  "safety_profile": "tabletop_default",
  "confidence": 0.84
}
```

### 必填字段

- `task_id`
- `action_type`
- `target_object`
- `timeout_s`

### 当前阶段约束

第一版建议只支持：

- `action_type = pick`
- `preferred_grasp_mode = top_down`

不要一开始就把抽象做成“支持所有 manipulation task”。

## 3. GroundingCandidate

grounding 层输出对象。

```json
{
  "candidate_id": "uuid",
  "task_id": "uuid",
  "source_model": "grounding_dino",
  "text_prompt": "red mug",
  "bbox_xyxy": [120, 88, 260, 300],
  "point_xy": [186, 201],
  "score": 0.79,
  "rank": 0,
  "frame_id": "camera_color_frame"
}
```

### 约束

- `bbox_xyxy` 与 `point_xy` 至少有一个
- 应保留 top-k 候选
- `rank=0` 不代表一定执行，只代表 grounding 排名第一

## 4. MaskCandidate

分割层输出对象。

```json
{
  "mask_id": "uuid",
  "candidate_id": "uuid",
  "source_model": "sam2",
  "prompt_type": "box+point",
  "mask_rle": "...",
  "bbox_xyxy": [118, 86, 262, 303],
  "mask_area_px": 21543,
  "stability_score": 0.91,
  "mask_score": 0.87,
  "depth_valid_ratio": 0.94,
  "boundary_touch_ratio": 0.03,
  "rank": 0
}
```

### 质量过滤建议

至少剔除：

- `depth_valid_ratio` 过低
- `mask_area_px` 过小
- 与图像边界接触过多
- 多连通域碎裂严重

## 5. Object3DDescriptor

3D 恢复层输出对象。

```json
{
  "object_id": "uuid",
  "mask_id": "uuid",
  "frame_id": "robot_base_frame",
  "point_count": 4832,
  "centroid_xyz": [0.41, -0.08, 0.12],
  "top_point_xyz": [0.40, -0.07, 0.15],
  "support_plane_height_m": 0.00,
  "support_plane_normal_xyz": [0.0, 0.0, 1.0],
  "local_surface_normal_xyz": [0.02, -0.04, 0.99],
  "principal_axes": {
    "axis_1": [0.92, 0.37, 0.00],
    "axis_2": [-0.37, 0.92, 0.00],
    "axis_3": [0.00, 0.00, 1.00]
  },
  "bbox_extent_xyz_m": [0.07, 0.08, 0.10],
  "workspace_margin_ok": true,
  "point_cloud_quality": 0.82,
  "pose_confidence": 0.69
}
```

### 当前阶段最低要求

即使暂时不估计完整姿态，也至少要输出：

- `centroid_xyz`
- `top_point_xyz`
- `support_plane_normal_xyz`
- `local_surface_normal_xyz`

### 备注

如果没有可用 CAD 或 reference view，不要伪装成“6D pose 已知”。  
当前阶段应承认自己只有“抓取相关几何描述”。

## 6. GraspCandidate

抓取候选生成层输出对象。

```json
{
  "candidate_id": "uuid",
  "object_id": "uuid",
  "grasp_mode": "top_down_parallel_jaw",
  "frame_id": "robot_base_frame",
  "pregrasp_pose": {
    "position_xyz": [0.40, -0.07, 0.24],
    "quaternion_xyzw": [0.0, 1.0, 0.0, 0.0]
  },
  "grasp_pose": {
    "position_xyz": [0.40, -0.07, 0.16],
    "quaternion_xyzw": [0.0, 1.0, 0.0, 0.0]
  },
  "lift_pose": {
    "position_xyz": [0.40, -0.07, 0.28],
    "quaternion_xyzw": [0.0, 1.0, 0.0, 0.0]
  },
  "approach_vector_xyz": [0.0, 0.0, -1.0],
  "retreat_vector_xyz": [0.0, 0.0, 1.0],
  "gripper_opening_m": 0.06,
  "clearance_score": 0.71,
  "contact_score": 0.67,
  "overall_score": 0.69
}
```

### 约束

- 第一版建议固定成 top-down parallel jaw
- 抓取候选必须包含完整阶段位姿，不接受“只有一个 grasp pose”

## 7. ExecutablePlan

可执行性筛选层输出对象。

```json
{
  "plan_id": "uuid",
  "task_id": "uuid",
  "selected_grasp_candidate_id": "uuid",
  "backend": "isaacsim",
  "frame_id": "robot_base_frame",
  "joint_trajectory_segments": [
    {
      "segment_type": "move_to_pregrasp",
      "target_joint_rad": [0.1, 0.8, -1.2, 0.2, 0.3, 0.0],
      "timeout_s": 5.0
    },
    {
      "segment_type": "approach",
      "target_joint_rad": [0.15, 0.9, -1.35, 0.2, 0.3, 0.0],
      "timeout_s": 3.0
    },
    {
      "segment_type": "lift",
      "target_joint_rad": [0.15, 0.7, -1.1, 0.2, 0.3, 0.0],
      "timeout_s": 4.0
    }
  ],
  "gripper_commands": {
    "open_before_grasp": 1.0,
    "close_after_approach": 0.0
  },
  "ik_summary": {
    "pregrasp_solved": true,
    "grasp_solved": true,
    "lift_solved": true,
    "retreat_solved": true
  },
  "safety_summary": {
    "joint_margin_ok": true,
    "table_clearance_ok": true,
    "camera_keepout_ok": true
  }
}
```

### 约束

- 计划必须显式分段
- 每段必须有超时
- 必须记录每段的筛选结论

## 8. ExecutionResult

任务执行结果对象。

```json
{
  "execution_id": "uuid",
  "plan_id": "uuid",
  "status": "failed",
  "failure_stage": "verify",
  "failure_reason": "object_not_lifted",
  "retryable": true,
  "final_joint_rad": [0.14, 0.72, -1.08, 0.2, 0.3, 0.0],
  "final_gripper_opening": 0.01,
  "target_still_on_table": true,
  "timing_breakdown_s": {
    "grounding": 0.18,
    "segmentation": 0.11,
    "reconstruction": 0.04,
    "planning": 0.03,
    "execution": 6.70,
    "verification": 0.19
  }
}
```

### 状态集合

- `success`
- `failed`
- `timeout`
- `aborted`

### 失败原因建议枚举

- `grounding_not_found`
- `mask_low_quality`
- `depth_invalid`
- `workspace_out_of_range`
- `ik_unsolved`
- `joint_margin_violation`
- `approach_collision_risk`
- `gripper_close_failed`
- `object_not_lifted`
- `backend_disconnected`
- `execution_timeout`

## 9. 坐标变换契约

## 9.1 必须显式记录变换来源

每个 3D 结果都应附带：

- `frame_id`
- `transform_source`
- `timestamp`

例如：

```json
{
  "frame_id": "robot_base_frame",
  "transform_source": "camera_to_base_extrinsic_v3",
  "timestamp": 1731234567.52
}
```

## 9.2 不允许的隐式做法

- 不允许默认“相机就是世界坐标系”
- 不允许把 Isaac world frame 与真机 base frame 混写
- 不允许在不同模块里用不同单位

## 10. 版本化要求

所有核心对象建议带：

- `schema_name`
- `schema_version`

例如：

```json
{
  "schema_name": "GraspCandidate",
  "schema_version": "v1"
}
```

这样后面换模型、换字段、换策略时，不会悄悄破坏上下游。

## 11. 结论

这套契约的核心目的是：

- 让每一层都能独立调试
- 让 mock / Isaac / 真机后端共用同一任务对象
- 让你后面引入新的 grounding、segmentation、grasp 模型时，不必重写整条 pipeline

如果没有这层契约，后续任何模型替换都会退化成“改一堆脚本”。

