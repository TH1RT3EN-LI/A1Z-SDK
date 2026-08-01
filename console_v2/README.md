# A1Z Console V2

从空白开始构建的 A1Z Web Console。当前迭代只提供界面框架：

- 顶部菜单栏和左侧功能导航；
- 中央主工作区；
- 基于本地 PTY 的真实交互式终端；
- 可旋转、缩放和平移的完整 A1Z G1Z + D405 模型；
- 模型、RGB 和深度视图切换框架。

本迭代不连接 ROS、控制服务、CAN 或真实相机。

## 启动

桌面窗口不依赖系统浏览器，从仓库根目录运行：

```bash
./scripts/run_a1z_console_v2_desktop.sh
```

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

终端后端只绑定 `127.0.0.1:8765`，新终端会话的初始工作目录是仓库根目录。

## 验证

```bash
cd console_v2/frontend
npm run typecheck
npm run build
```
