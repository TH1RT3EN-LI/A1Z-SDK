# A1Z Host Console

`A1Z Host Console` 是项目的宿主机桌面入口。它启动本机安装的完整
Isaac Sim App，不使用 WebRTC；机器人控制仍通过 A1Z TCP server，
AnyGrasp 仍通过已有的 ROS 2 与 GPU 视觉容器运行。

## 启动

```bash
./scripts/open_a1z_gui_console.sh
```

默认使用：

- Isaac Sim：`$ISAAC_SIM_ROOT`；未设置时使用 `$HOME/isaacsim`
- 世界：`build/scenes/A1Z_G1Z_world.usd`
- A1Z TCP：`127.0.0.1:37103`
- 原生 Isaac 6 API profile：`native_6_0`
- EE 视口拖拽控制：关闭

这些值可在“启动与状态”页面修改，保存在被 Git 忽略的
`runtime/gui-console/settings.json`。

需要 EE 拖拽目标时，在启动前勾选“启动时启用 EE 视口拖拽控制”。
该设置不会热切换当前运行实例，只对下一次启动生效。

## 操作顺序

1. 在“启动与状态”点击“启动完整项目”。
2. 等待右上角依次显示 A1Z 已连接、`ROS · 等待 D405/TF/RGB-D`，
   最终变为 `ROS · 已就绪`。完整启动会：
   - 启动宿主机 Isaac App；
   - 等待 `camera_status.ready` 和相机 warm-up；
   - 首次运行时自动创建项目 ROS 2 Humble 容器；
   - 启动 D405、TF、joint state 和 motion bridge；
   - 分别验证彩色与深度图像话题收到真实消息。
3. 如需查看相机、TF 和机器人状态，在“启动与状态”的 RViz 卡片中
   点击“启动 RViz”。Console 会使用项目的 `ROS_DOMAIN_ID=62` 和
   `ros2_ws/rviz/a1z_d405.rviz`。ROS 链路未通过上述验证时，Console
   不会提前启动 RViz。
4. 在“AnyGrasp”输入目标描述。首次建议保留“干运行”，先点
   “规划并执行”生成并检查结果；干运行不会发送实际执行动作。
5. 确认计划后取消“干运行”，再次执行并确认运动提示。

AnyGrasp 按钮会在启动流水线前同时检查 A1Z 协议和 D405
`camera_status.ready`；相机仍在 warm-up 或已经失败时不会发送任务。
RGB、Depth 和两路 CameraInfo 订阅使用 ROS 2 传感器 QoS
`BEST_EFFORT + VOLATILE`，与项目 D405 publisher 保持一致。

“仅感知与规划”会调用
`run_target_mask_to_anygrasp_from_ros.sh`；“规划并执行”会调用
`run_target_mask_to_anygrasp_pick_attempt.sh`。后者默认使用
`physical_v2 + best_direct`，要求抓图时刻关节角；闭合阶段由左右指共同接触
自动发现并锁定刚体，不再依赖目标 prim 解析。Console 不再提供目标路径辅助；
旧的 `sim_contact_attach` 如需显式路径，只能从兼容脚本或终端单独调用。
双侧接触稳定后夹爪不会立即停力：先施加 0.5 mm 初始预紧，再按 0.08 mm
步长低速收紧，直到弱侧有效夹持力达到 2 N 才锁定；保持阶段掉力会自动
有界补压，总预紧不超过 8 mm、单侧法向力上限为 12 N。两侧夹指 collider
使用独立高摩擦材料。闭合与释放速度都限制为 6 mm/s，增强夹持力不会改变
低速运动约束。两指采用虚拟中心耦合；单侧接触时固定接触指并让自由指追赶。
闭环优先使用 PhysX 接触法向力；只有双侧同物体接触、两指阻力和位置滞后均
越过阈值时，扣除空载基线的 projected joint force 才作为受限后备信号。

## 进程所有权

- 控制台只停止自己启动的 Isaac、RViz、AnyGrasp 和终端命令进程组。
- 如果完整启动创建了 ROS bridge，Console 会记录其所有权，并在
  “优雅停止”时先停止 bridge、再停止 Isaac。若 bridge 在启动前已经
  运行，Console 只验证它并标记为“外部”，不会在退出时停止它。
- RViz 使用项目专属容器名 `a1z-rviz-humble-isaac6`。Console 的
  “停止 RViz”只停止该自有实例，不会停止共享的 ROS bridge 容器。
- 如果 `37103` 已经是一个可识别的 A1Z 服务，控制台进入“外部附加”
  状态，不会取得或停止那个进程。
- 如果端口有响应但不是 A1Z 协议，启动会被拒绝并显示端口冲突。
- “优雅停止”按 `ROS bridge → A1Z stop → Isaac App` 的顺序退出。
  “强制停止”只对控制台记录的自有进程组生效。

## 页面说明

- “机器人命令”提供状态、预设/关节运动、夹爪和 physical grasp v2
  控制。运动命令要求先勾选安全确认。
- “项目终端”在宿主机通过 `/bin/bash -lc` 执行输入；它具备当前用户
  的全部权限，适合运行仓库脚本。停止按钮不会模糊匹配其他进程。
- 下方统一日志同时记录到
  `runtime/gui-console/logs/console_<timestamp>.log`。
