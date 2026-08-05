# A1Z 惯性参数审计

## 当前结论

当前生成链只对 `arm_link6` 使用 CAD 导出惯性参数；其他原有 link 默认保留
GALAXEA SDK vendored URDF 的参数。

这样处理的原因不是简单的“官方值和 CAD 值不同”，而是官方 `arm_link6`
惯量张量不满足刚体主惯量三角不等式，属于物理上不可实现的张量。当前
control URDF 和 Isaac URDF 均使用 CAD 值。

`arm_link5` 不需要覆盖：官方 URDF、CAD CSV 和当前生成物的质量、质心、
惯量一致，而且张量物理有效。

## 参数来源和优先级

1. 默认来源：
   `vendor/GALAXEA-A1Z/a1z/robot_models/a1z/A1Z_G1Z.urdf`
2. `arm_link6` 唯一例外：
   `build/robot_packages/A1Z_G1Z/urdf/A1Z_nogripper.csv`
3. 生成物：
   - `build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_control.urdf`
   - `build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_isaac.urdf`
4. Isaac 生产物理层：
   `build/scenes/A1Z_G1Z_isaac/payloads/Physics/physics.usda`

生成脚本从 CAD CSV 按 link 名读取 `arm_link6`，不会在脚本中维护第二份手写
数值。缺少 CSV、缺少 link、质量非正或对角惯量非正时，生成过程会直接失败。

## arm_link5

当前值：

- mass: `0.36875049 kg`
- COM: `[-0.00366248, -0.00002724, -0.03904971] m`
- inertia:
  - `ixx = 0.00010146`
  - `ixy = -0.00000007`
  - `ixz = 0.00000555`
  - `iyy = 0.00011993`
  - `iyz = 0`
  - `izz = 0.00008271`

主惯量：

```text
[0.00008119035, 0.00010297937, 0.00011993028] kg·m²
```

最小三角余量为 `+0.00006423944 kg·m²`，物理有效。

## arm_link6 官方源问题

官方 vendored URDF 中：

```text
mass = 0.55665538 kg
ixx  = 0.00030053
ixy  = 0.00030053
ixz  = -0.00000170
iyy  = 0.00037247
iyz  = -0.00000005
izz  = 0.00041454
```

其主惯量为：

```text
[0.00003382103, 0.00041453798, 0.00063918099] kg·m²
```

刚体必须满足 `I1 + I2 >= I3`，但该张量为：

```text
0.00003382103 + 0.00041453798 - 0.00063918099
= -0.00019082199 kg·m²
```

因此它虽然正定，但不是物理上可实现的刚体惯量。

## arm_link6 当前修复值

CAD CSV 和当前两个生成 URDF 使用：

```text
mass = 0.42335647 kg
COM  = [0.05514353, -0.00002867, -0.00013152] m
ixx  = 0.00028807
ixy  = -0.00000065
ixz  = -0.00000280
iyy  = 0.00050989
iyz  = 0.00001432
izz  = 0.00062848
```

对应主惯量：

```text
[0.00028804569, 0.00050818578, 0.00063020853] kg·m²
```

最小三角余量为 `+0.00016602294 kg·m²`，物理有效。

生产 Physics USD 需要通过统一入口重建后，才会同步该值。

## 其他有差异的 link

`arm_link3` 和 `arm_link4` 的官方值与 `A1Z_nogripper.csv` 不同，但当前张量均
物理有效，且没有独立证据证明 CAD 裸件值比 SDK 的装配模型更符合真机，因此
当前继续保留官方参数，不因“数值不同”自动覆盖。

手指 link 同样保留官方参数；`config/sim.env` 不再用环境变量缩放手指质量。

## 静态重力补偿边界

静态逆动力学 `g(q)` 在 `qdot = 0`、`qddot = 0` 时由质量、质心、关节几何和
重力决定，不受旋转惯量张量影响。因此：

- 修复 `arm_link6` 张量是必要的，主要消除动态响应和仿真稳定性缺陷；
- `arm_link6` 的质量和质心修复会改变静态重力前馈；
- 单独的 J4 真机下坠仍不能只归因于旋转惯量。

在当前 D405/支架配置与姿态 `[0, 60, -60, 0, 0, 0] deg` 下，CAD
`arm_link6` 的 J4 静态重力前馈约为 `-1.84303 N·m`。

## 回归验证

重新生成并执行合同测试：

```bash
python3 scripts/prepare_a1z_urdfs.py --env-file config/real.env

A1Z_PROFILE=real ./scripts/a1z_sdk_python_in_container.sh -m pytest -q \
  tests/test_d405_mount_contract.py \
  tests/test_camera_bracket_contract.py
```

测试会检查：

- `arm_link6` 在 control/Isaac URDF 中与 CAD CSV 数值一致；
- 该惯量通过物理可实现性检查；
- 其他受保护 link 仍与官方模型一致；
- 相机、支架和夹爪参数没有被覆盖回旧值。

生产 USD 需要通过统一入口重建：

```bash
./scripts/rebuild_a1z_world.sh
```

重建后必须再次核对 Physics USD，不能只检查源 URDF。
