# A1Z J5/J6 Physics Fix

## 结论

这次 `J5` 在大约 `[-36°, 36°]` 区间卡住、`J6` 连带抖动和突变的问题，最终不是目标抓取链、不是 D405 挂载、也不是夹爪或相邻自碰撞本身导致的主问题。

落地结论是：

1. `arm_link5` / `arm_link6` 末端腕部链路的惯量参数不够可信，尤其原始 `URDF` 里的 `arm_link6` 惯量明显可疑。
2. Isaac Sim 里 `J5/J6` 这一段的 PhysX articulation / rigid body / joint drive 参数过于不稳定，导致腕部在某些姿态区间出现典型的数值不稳定现象：
   - 憋住不走
   - 局部抖动
   - 误差积累后突然跳过去
3. 在 `TGS` scene 下，articulation 的 `solverVelocityIterationCount > 4` 还会触发 PhysX 明确警告，这进一步说明腕部求解器参数不在稳定区间内。

最终通过同时修正：

- `link5/link6` 惯量
- articulation solver 参数
- `link5/link6` 刚体阻尼与求解参数
- `J5/J6` 运行时 drive 参数

后，控制恢复正常。

## 现象

现场症状有这些特征：

- `J5` 在大约 `[-36°, 36°]` 附近容易卡住。
- `J6` 会跟着失效或明显抖动。
- 肉眼观感像“有力在推，但局部卡住，过一会突然跳到另一个位置”。
- 其他关节大体正常，问题主要集中在 `link5` 之后的腕部链。

## 已排除项

下面这些都做过实验，结论是“不是主因”：

1. **D405**
   - 已将 D405 从实验链彻底摘掉。
   - 症状仍然存在。

2. **夹爪**
   - 已去掉 finger，只保留纯 arm。
   - 症状仍然存在。

3. **相邻碰撞**
   - 先关了 `4-5`、`5-6` 相邻碰撞。
   - 后来进一步关了整条 arm 的内部自碰撞。
   - `J5` 卡滞问题仍然存在。

4. **joint_sign 映射**
   - 尝试把真实机 `joint_sign=[1,1,-1,1,-1,1]` 接进 Isaac 控制。
   - 结果控制变差，说明这条不是正确修复方向。
   - 该试验已回退。

## 最终原因

这次问题本质上是**腕部链路物理建模与 PhysX 驱动稳定性叠加导致的数值问题**。

更具体地说：

1. **末端链惯量不稳**
   - `arm_link6` 原始惯量数据可疑。
   - 仅靠碰撞过滤无法解决由错误惯量带来的关节求解不稳定。
   - `arm_link5` 虽然原始值没有 `arm_link6` 那么明显异常，但它正好挂在 `J5` 后面，也必须一起纳入可信惯量源。

2. **腕部关节 drive 过“硬/飘”或参数不合适**
   - `J5/J6` 是轻载高速腕关节，比前四轴更敏感。
   - 如果 inertia、max force、damping、solver iteration 组合不合适，PhysX 很容易出现 stick-slip 式的不稳定。

3. **求解器配置与 TGS 约束不匹配**
   - 日志里出现了：
     - `Detected an articulation at /World/A1Z_G1Z/Geometry with more than 4 velocity iterations being added to a TGS scene`
   - 这说明 articulation solver 配置本身就踩到了当前 TGS 场景的稳定性边界。

## 实际修复

### 1. 覆盖 wrist 惯量

文件：

- `scripts/prepare_a1z_urdfs.py`

做法：

- 为 `arm_link5`
- 为 `arm_link6`

覆盖了来自 CAD 导出数据的惯量参数，再生成：

- `build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_isaac.urdf`
- `build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_control.urdf`

### 2. 运行时补 wrist 物理稳定参数

文件：

- `scripts/open_a1z_world_with_a1z_sdk.py`

启动世界后，运行时额外补了这些参数：

1. articulation 级别：
   - `enabledSelfCollisions = false`
   - `solverPositionIterationCount = 64`
   - `solverVelocityIterationCount = 4`
   - `sleepThreshold = 0`
   - `stabilizationThreshold = 0`

2. `link5/link6` rigid body 级别：
   - `linearDamping`
   - `angularDamping`
   - `solverPositionIterationCount`
   - `solverVelocityIterationCount`
   - `maxDepenetrationVelocity`
   - `sleepThreshold`
   - `stabilizationThreshold`

3. `J5/J6` joint drive 级别：
   - `stiffness`
   - `damping`
   - `maxForce`
   - `maxJointVelocity`
   - `jointFriction = 0`

### 3. 保持内部自碰撞关闭

当前实验链仍保留：

- arm 内部自碰撞关闭

这不是最终根因修复，但它减少了额外扰动，当前阶段继续保留。

## 验证结果

修复后，最小动作复测恢复正常：

```bash
bash scripts/a1zctl_in_container.sh move "0,60,-60,0,20,0" --speed 0.15
```

随后状态读数正常到位，`J5` 可到约 `20°`：

```text
J2  60.07
J3 -59.39
J5  19.90
```

用户现场反馈为“回复正常了”。

## 复现与生效步骤

每次改完相关参数后，需要重新生成并重启：

```bash
bash scripts/rebuild_a1z_world.sh
bash scripts/start_a1z_webrtc_streaming_host.sh --restart
```

验证：

```bash
bash scripts/a1zctl_in_container.sh status
bash scripts/a1zctl_in_container.sh move "0,60,-60,0,20,0" --speed 0.15
```

## 后续建议

1. 如果后面重新挂回 D405 或夹爪，优先保持当前 wrist 惯量和 PhysX 稳定参数不退化。
2. 如果再出现腕部局部抖动，先检查：
   - `link5/link6` 惯量是否被覆盖回旧值
   - `open_a1z_world_with_a1z_sdk.py` 的运行时 PhysX 补丁是否生效
   - `solverVelocityIterationCount` 是否又大于 `4`
3. 不建议再回到“只靠关碰撞”来解释这个问题。碰撞会放大症状，但这次主因不在那里。
