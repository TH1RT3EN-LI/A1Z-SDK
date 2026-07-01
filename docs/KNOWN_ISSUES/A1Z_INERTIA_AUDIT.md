# A1Z Inertia Audit

## 目的

检查当前 A1Z 机械臂各 link 的惯量数据，确认除了已经修过的 `J5/J6` 腕部链之外，是否还有明显错误或漂移。

本次对比的三个来源：

1. `vendor/GALAXEA-A1Z/a1z/robot_models/a1z/A1Z_G1Z.urdf`
2. `build/robot_packages/A1Z_G1Z/urdf/A1Z_nogripper.csv`
3. `build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_isaac.urdf`

其中：

- `A1Z_nogripper.csv` 视为 CAD 导出参考值
- `A1Z_G1Z_isaac.urdf` 视为当前实际生成物

## 结论

当前检查结果不是“全身都有问题”。

明确结论如下：

- 一致：`base_link`
- 一致：`arm_link1`
- 一致：`arm_link2`
- **原来不一致，现已修正：`arm_link3`**
- **原来不一致，现已修正：`arm_link4`**
- 一致：`arm_link5`
- **原来不一致，现已修正：`arm_link6`**
- 当前未发现明确证据支持修改：`gripper_finger_left_link`
- 当前未发现明确证据支持修改：`gripper_finger_rIght_link`

也就是说，这一轮修复完成后，arm 主链当前没有新的明显惯量漂移项残留。

## 对比摘要

### `base_link`

- `vendor URDF == CAD CSV`
- `generated URDF == CAD CSV`

无问题。

### `arm_link1`

- `vendor URDF == CAD CSV`
- `generated URDF == CAD CSV`

无问题。

### `arm_link2`

- `vendor URDF == CAD CSV`
- `generated URDF == CAD CSV`

无问题。

### `arm_link3`

`vendor URDF` 与 `CAD CSV` 原本不一致，但当前生成物已覆盖为 `CAD CSV`。

差异量级：

- mass delta: `+0.05154789 kg`
- COM max abs delta: `0.00275268 m`
- inertia max abs delta: `0.00053619`

关键值对比：

- vendor mass: `0.99109270`
- csv mass: `0.93954481`

### `arm_link4`

`vendor URDF` 与 `CAD CSV` 原本不一致，但当前生成物已覆盖为 `CAD CSV`。

差异量级：

- mass delta: `+0.30600000 kg`
- COM max abs delta: `0.02215909 m`
- inertia max abs delta: `0.00031188`

这是当前除 `link6` 外最明显的问题项。

关键值对比：

- vendor mass: `0.48309874`
- csv mass: `0.17709874`

### `arm_link5`

- `vendor URDF == CAD CSV`
- 当前生成物也已与 CAD 对齐

无额外问题。

### `arm_link6`

`vendor URDF` 与 `CAD CSV` 原本明显不一致，但当前生成链已覆盖为 CAD 值。

当前状态：

- `generated URDF ~= CAD CSV`

已修正。

## 定量结果

按 `vendor_vs_csv / gen_vs_csv / gen_vs_vendor` 的对比结果：

```json
[
  {
    "link": "base_link",
    "vendor_vs_csv": {
      "mass_delta": 0.0,
      "com_max_abs_delta": 0.0,
      "inertia_max_abs_delta": 0.0
    },
    "gen_vs_csv": {
      "mass_delta": 0.0,
      "com_max_abs_delta": 0.0,
      "inertia_max_abs_delta": 0.0
    }
  },
  {
    "link": "arm_link1",
    "vendor_vs_csv": {
      "mass_delta": 0.0,
      "com_max_abs_delta": 0.0,
      "inertia_max_abs_delta": 0.0
    },
    "gen_vs_csv": {
      "mass_delta": 0.0,
      "com_max_abs_delta": 0.0,
      "inertia_max_abs_delta": 0.0
    }
  },
  {
    "link": "arm_link2",
    "vendor_vs_csv": {
      "mass_delta": 0.0,
      "com_max_abs_delta": 0.0,
      "inertia_max_abs_delta": 0.0
    },
    "gen_vs_csv": {
      "mass_delta": 0.0,
      "com_max_abs_delta": 0.0,
      "inertia_max_abs_delta": 0.0
    }
  },
  {
    "link": "arm_link3",
    "vendor_vs_csv": {
      "mass_delta": 0.05154789000000004,
      "com_max_abs_delta": 0.0027526799999999796,
      "inertia_max_abs_delta": 0.0005361899999999989
    },
    "gen_vs_csv": {
      "mass_delta": 0.05154789000000004,
      "com_max_abs_delta": 0.0027526799999999796,
      "inertia_max_abs_delta": 0.0005361899999999989
    }
  },
  {
    "link": "arm_link4",
    "vendor_vs_csv": {
      "mass_delta": 0.30600000000000005,
      "com_max_abs_delta": 0.02215909,
      "inertia_max_abs_delta": 0.00031188
    },
    "gen_vs_csv": {
      "mass_delta": 0.30600000000000005,
      "com_max_abs_delta": 0.02215909,
      "inertia_max_abs_delta": 0.00031188
    }
  },
  {
    "link": "arm_link5",
    "vendor_vs_csv": {
      "mass_delta": 0.0,
      "com_max_abs_delta": 0.0,
      "inertia_max_abs_delta": 0.0
    },
    "gen_vs_csv": {
      "mass_delta": -4.899999999641302e-07,
      "com_max_abs_delta": 4.800000000001851e-07,
      "inertia_max_abs_delta": 4.599999999999922e-07
    }
  },
  {
    "link": "arm_link6",
    "vendor_vs_csv": {
      "mass_delta": 0.13329891000000005,
      "com_max_abs_delta": 0.013578440000000004,
      "inertia_max_abs_delta": 0.00030118
    },
    "gen_vs_csv": {
      "mass_delta": -4.6999999997465736e-07,
      "com_max_abs_delta": 4.800000000000225e-07,
      "inertia_max_abs_delta": 4.799999999999683e-07
    }
  }
]
```

### `gripper_finger_left_link` / `gripper_finger_rIght_link`

本轮没有发现独立 CAD CSV 参考源。

当前判断：

- `vendor URDF` 与生成物一致
- 左右手指惯量表现为合理镜像关系
- 没有额外证据支持“夹爪惯量错误”这一结论

因此，这一轮没有对夹爪惯量做主动修改。

## 当前建议

1. 保持已经修好的 `arm_link3/link4/link5/link6`
2. 夹爪惯量暂不改，除非后续拿到独立 CAD 导出或观测到明确物理异常
3. 如果后续再做动力学精修，优先验证：
   - 基础关节运动
   - 腕部稳定性
   - 带夹爪与相机的整机重力补偿表现

## 相关文档

- 腕部物理问题修复：
  - [A1Z_J5_J6_PHYSICS_FIX](../A1Z_J5_J6_PHYSICS_FIX.md)
