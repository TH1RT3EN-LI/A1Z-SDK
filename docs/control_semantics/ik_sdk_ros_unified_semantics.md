# A1Z IK / SDK / ROS / AnyGrasp 统一语义

## 结论

当前链路需要显式区分两个概念：

- `arm_link6`：机械臂最后一节的法兰/安装参考 frame
- `grasp_tcp`：夹爪抓取中心对应的工具 TCP frame

本次已将主链默认语义统一为：

- IK 末端 frame：`grasp_tcp`
- ROS 工具 frame：`grasp_tcp`
- adapter 默认 `ee_grasp_origin_xyz_m`：`[0, 0, 0]`
- adapter 默认 `ee_approach_axis_xyz`：`[1, 0, 0]`
- adapter 默认 `ee_opening_axis_xyz`：`[0, 1, 0]`

其中 `grasp_tcp` 相对 `arm_link6` 的固定偏移为：

- `translation = [0.08, 0.0, 0.0]` meters

## 之前的问题

之前主链里存在一类语义混用：

1. FK/IK 默认把 `arm_link6` 当末端 frame
2. ROS 也默认把 `arm_link6` 当 `tool_link_frame`
3. AnyGrasp adapter 又通过 `ee_grasp_origin_xyz_m=[0.08,0,0]` 人工补一个 TCP 偏移

这会导致同一条链路里同时存在：

- “法兰 pose”
- “工具 TCP pose”
- “抓取中心 pose”

但代码里没有始终明确区分它们。

结果就是：

- IK 求解目标和视觉/抓取目标不一定是同一个几何点
- ROS 发布的 tool frame 也不一定等于真实抓取中心
- adapter 的轴定义调参会和 TCP 平移补偿纠缠在一起
- 表面上像是 sign、binding、camera correction 都可能有问题，实际先天就存在 frame 语义不一致

## 本次修正

### 1. URDF

在 `arm_link6` 下新增固定 frame：

- link: `grasp_tcp`
- joint: `grasp_tcp_joint`

固定变换：

- parent: `arm_link6`
- child: `grasp_tcp`
- origin xyz: `[0.08, 0, 0]`

### 2. IK / Adapter

以下主链默认 `end_effector_frame` 已切到 `grasp_tcp`：

- `run_anygrasp_adapter.py`
- `run_anygrasp_best_plan.py`
- `run_contact_graspnet_adapter.py`
- `run_grconvnet_adapter.py`
- `summarize_anygrasp_ik_target_gap.py`
- `scan_anygrasp_mapping_hypotheses.py`

同时将主链默认 TCP 轴定义切到：

- opening = `+Y`
- approach = `+X`

配合官方 AnyGrasp `binding=opening=c1,height=c2,approach=c0` 后，当前默认目标 TCP 语义为：

- `tcp_x = approach`
- `tcp_y = opening`
- `tcp_z = height`

因此主链默认 `ee_grasp_origin_xyz_m` 为 `[0,0,0]`，不再额外补抓取中心平移。

### 3. ROS

当前容器环境默认值为：

- `A1Z_TOOL_LINK_FRAME=grasp_tcp`
- `A1Z_TOOL_FRAME=grasp_tcp`

因此在本次提交覆盖到的主链脚本和运行环境里，ROS 侧工具语义也按 `grasp_tcp` 解释。

## 现在这套语义怎么理解

统一后，推荐按下面理解：

- SDK / 控制状态里的关节角：就是控制 URDF 的 6 轴关节角
- IK 输入目标 pose：是 `robot_base_frame -> grasp_tcp`
- ROS `/a1z/move_ee` 的目标 pose：也是 `robot_base_frame -> grasp_tcp`
- AnyGrasp adapter 输出的 tool/grasp pose：先落到 `grasp_tcp` 语义，再转成关节空间

也就是说，后续如果再有偏差，优先排查：

1. AnyGrasp raw rotation 列绑定
2. 相机坐标系修正
3. `camera -> base` 外参
4. 真实夹爪轴方向与我们定义的 `grasp_tcp` 轴是否一致

而不是再把 `arm_link6` 和 TCP 混在一起看。

## 当前仍需继续验证的部分

- 一些 verify 脚本和历史分析脚本还保留旧默认值，后续需要逐步更新
- `grasp_tcp` 的位置目前设置为 `x=0.08m`
- 如果真实抓取中心不在该点，还需要做一次更精确的 TCP 标定
- AnyGrasp 官方 `rotation_matrix` 语义按 `column_0=approach`、`column_1=opening`、`column_2=height` 解释；A1Z 当前默认 binding 已切到 `opening=c1,height=c2,approach=c0`
- AnyGrasp `binding_label / camera_correction / extrinsic_correction` 仍然需要独立验证；本次修复的是语义底座，不是最终抓取对齐结论
