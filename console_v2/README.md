# A1Z Console V2

面向真实 A1Z 的本地控制台，当前提供：

- 顶部菜单栏和左侧功能导航；
- 机械臂模式和关节目标控制；
- SDK 关节状态回读；
- 基于本地 PTY 的真实交互式终端；
- 可旋转、缩放和平移的 A1Z G1Z 模型。

## 启动

桌面窗口不依赖系统浏览器，从仓库根目录运行：

```bash
./scripts/run_a1z_console_v2_desktop.sh
```

默认按真机模式启动：连接真实 SDK 遥测，操作会提交到真实控制服务，且启动步骤不可跳过。
首次进入依次完成：

1. 检测宿主机 Python/硬件依赖与 Docker daemon，并选择控制服务运行位置；
2. 检查选定环境中的 SocketCAN 连接（Docker 可在下一步完成接口配置）；
3. 按所选控制模式和重力补偿启动控制服务，验证后端、控制循环与实际模式后才进入控制页。

宿主机方式要求硬件依赖已经安装且 `can0` 已按目标 bitrate 启用；Docker
方式会复用或创建 `a1z-ros2-humble-real`，并通过项目控制服务管理脚本完成启动。
真机容器使用动态设备视图，不会固化 `/dev/videoN` 或 `/dev/mediaN`。
`config/real.env` 默认的 `A1Z_CAMERA_MODE=auto` 会在 D405 未连接时跳过
RealSense 与相机桥接节点，但不影响容器、SocketCAN 或控制服务。需要强制
启用/禁用相机时，可显式设置 `A1Z_CAMERA_MODE=on` 或 `off`。

真机控制的 CAN 反馈检查分为启动和运行两个阶段。SDK 夹爪回零结束后，
控制循环使用零位置增益、零前馈力矩的非运动探测帧，等待六轴都产生新鲜
反馈后才进入严格的 200 ms 运行期保护。启动采集窗口默认为 2 s，可通过
`A1Z_ARM_FEEDBACK_STARTUP_TIMEOUT_S` 调整；该窗口从夹爪初始化完成后单独计时，
不会消耗运行期 200 ms 的安全预算。

官方 SDK 提示部分 Linux `socketcan` / `gs_usb` 与 CAN 盒存在兼容性
问题。本项目的真机配置默认在相邻 MIT 命令之间加入 100 µs
间隔，不改变官方帧编码、目标值或反馈解析，避免六帧突发时最后
一轴丢失回帧。可通过 `A1Z_CAN_INTER_COMMAND_DELAY_S` 调整；只有在已
验证官方内核/`gs_usb` 补丁或替换适配器后才应设为 `0`。该兼容层
不会放宽六轴 200 ms 运行期安全限制。

仅在明确进行无硬件界面测试时启用开发模式：

```bash
./scripts/run_a1z_console_v2_desktop.sh --development-mode
```

开发模式不会连接遥测或发送机械臂命令，并允许跳过启动步骤。Vite 的普通
`DEV` 状态不会再自动启用该模式。

桌面模式使用 Electron 内置渲染内核，本地终端直接通过受限 IPC 连接 PTY，
不需要启动 Python 终端后端。
当前 Ubuntu 主机禁用非特权 user namespace，源码启动器仅在 Linux 开发模式为
Electron 增加 `--no-sandbox`；窗口仍保持 context isolation、禁止 Node integration，
并拒绝非本地导航。正式分发前应改用正确安装权限的 sandbox helper。

可生成不依赖 Vite 开发服务器的 Linux 桌面目录：

```bash
cd console_v2/frontend
npm run desktop:package
./release/linux-unpacked/a1z-console-v2 --no-sandbox
```

浏览器开发模式仍可运行：

```bash
./scripts/run_a1z_console_v2.sh
```

默认在 `127.0.0.1:5173` 启动并打开浏览器。自动化验证时可禁止打开浏览器：

```bash
./scripts/run_a1z_console_v2.sh --no-open
```

浏览器界面的显式开发模式同样使用 `--development-mode`，可与 `--no-open`
组合。

终端后端只绑定 `127.0.0.1:8765`，新终端会话的初始工作目录是仓库根目录。

## 验证

```bash
cd console_v2/frontend
npm run typecheck
npm run build
```
