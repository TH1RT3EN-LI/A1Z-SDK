# A1Z Vision Stack

本文档固定 A1Z 当前用于开放词汇抓取的独立 GPU 视觉容器选型。

## 容器拆分

- `a1z-ros2-humble`
  - 继续负责 ROS2、动作接口、运动执行、状态机
- `a1z-vision-gpu`
  - 负责 GPU 感知与抓取候选
  - 当前承载：
    - SAM 2
    - AnyGrasp SDK
    - 后续 Grounding / 3D 恢复 / grasp proposal 前半段

这样拆分的目标不是“容器越多越高级”，而是把深度学习依赖和 ROS2 主环境隔离，同时保留同仓库开发。

## 当前主线选型

### SAM

- 主线：`SAM 2.1`
- 默认模型：`sam2.1_hiera_small`
- 上游仓库：`facebookresearch/sam2`
- 固定 commit：`2b90b9f5ceec907a1c18123530e92e794ad901a4`

选择理由：

- 官方支持 `python>=3.10`
- 跟当前 box/point prompt 分割链路最贴合
- 对单帧 RGB-D 抓取足够稳
- 不要求引入 SAM 3 的文本概念分割复杂度

`sam2.1_hiera_small` 是当前默认值，因为它比 `tiny` 更稳，又比 `base_plus` / `large` 更适合在 `RTX 5070 12GB` 上与 AnyGrasp 共享显存。

保留备选：

- `sam2.1_hiera_tiny`：低显存 / 低延迟 fallback
- `sam2.1_hiera_base_plus`：后续如果你确认显存预算充足再升

### SAM 3

- 状态：仅保留源码，不进当前主链
- 上游仓库：`facebookresearch/sam3`
- 固定 commit：`5dd401d1c5c1d5c3eedff06d41b77af824517619`

原因：

- 官方当前要求 `Python 3.12+`
- checkpoint 需要 Hugging Face 访问授权
- 你当前主问题是“box/point -> mask -> grasp”，不是“纯文本开放概念分割”

后续如果要做“直接文本找概念并分割”，再给它单开实验环境更干净。

### AnyGrasp

- 主线：`graspnet/anygrasp_sdk`
- 固定 commit：`554fc2410c57b3c02b99b970bd7239b0d2db26d5`
- 运行模式：官方 SDK 二进制 runtime

当前固定到上游 `dev` 线，是因为这条线已经开始切换到新的 license 工具，移除了旧版
`license_checker/lib_cxx.so` 机制，对现代 Python 和系统环境更友好。

当前仓库显示它支持：

- Python `3.10`
- Python `3.11/3.12/3.13`
- Python `3.14`
- CUDA `12.8`

同时仓库内已经带了多版本 `gsnet` / `tracker` 二进制，所以当前主线不再把
`MinkowskiEngine` 和 `pointnet2` 当成 first-day blocker。

另外，`graspnetAPI` 官方包把 `numpy` 强钉在 `1.20.3`，这与当前 Torch / Open3D
运行时不协调，所以基础容器不再把它作为 first-day 依赖。当前默认先保证
AnyGrasp runtime、Open3D 和 Torch 正常，后续如果你需要跑它那套旧 demo/eval
辅助工具，再单独补兼容环境更稳。

注意：

- AnyGrasp 仍然需要官方 license
- `checkpoint_detection.tar` / `checkpoint_tracking.tar` 不在公开仓库里
- 需要先拿 feature id 申请

## 当前运行时版本

`a1z-vision-gpu` 当前按下面版本固定：

- Base image: `a1z-ros2-humble:local`
- Python: `3.10`
- PyTorch: `2.7.0+cu128`
- TorchVision: `0.22.0+cu128`
- TorchAudio: `2.7.0+cu128`

这组版本是为了两件事同时成立：

- 与 ROS2 Humble 的 Python 大版本保持邻近，方便共享代码
- 给 AnyGrasp 和 SAM2 一个足够新的 CUDA / Torch 运行时

## 目录约定

- 源码：
  - `vendor/vision/sam2`
  - `vendor/vision/sam3`
  - `vendor/vision/anygrasp_sdk`
- SAM checkpoint：
  - `runtime/models/sam2/`
- AnyGrasp 权重：
  - `runtime/models/anygrasp/`
- AnyGrasp license：
  - `runtime/licenses/anygrasp/`

## 操作顺序

1. `./scripts/create_a1z_vision_gpu_container.sh`
2. `./scripts/setup_a1z_vision_in_container.sh`
3. `./scripts/verify_a1z_vision_stack_in_container.sh`
4. 拿到 AnyGrasp license 和 checkpoint 后，再次运行：
   - `./scripts/setup_anygrasp_sdk_in_container.sh`

## 跨容器工作区约定

ROS 容器和 GPU 视觉容器必须把同一个宿主机工程目录挂载到
`/workspace/A1Z`。目标分割和 AnyGrasp 入口会先运行
`scripts/ensure_a1z_vision_container.sh`：若工程移动后视觉容器仍指向旧目录，
脚本会保存当前视觉环境快照和旧容器备份，再用当前工程目录重建同名容器。
RGB-D 抓取结束后还会在视觉容器内显式检查 `color.png`，因此挂载错误会在
目标分割前给出明确错误，而不会再表现为后续 `FileNotFoundError`。
