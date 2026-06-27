# 开放词汇抓取参考项目与论文

本文档收集当前与本项目最相关的开源项目和论文，并明确每个参考该借鉴什么，不该照搬什么。

## 1. 使用原则

参考文献和开源项目分三类使用：

- 直接工程参考
- 算法能力参考
- 长期路线参考

当前 A1Z 项目最需要的是前两类，不是马上把第三类变成主系统。

## 2. 直接工程参考

## 2.1 Grounding DINO

- 项目：<https://github.com/IDEA-Research/GroundingDINO>
- 论文：<https://arxiv.org/abs/2303.05499>

适合借鉴：

- 开放词汇 box grounding
- top-k 检测候选
- 语言驱动目标定位

不适合直接承担：

- 分割
- 抓取姿态生成
- 执行决策

为什么重要：

这是你当前 pipeline 第 2 步最稳的开源主参考之一。

## 2.2 SAM 2

- 官方页面：<https://ai.meta.com/research/sam2/>
- 论文：<https://arxiv.org/abs/2408.00714>

适合借鉴：

- point / box / mask prompt segmentation
- 图像与视频统一分割
- 后续跟踪扩展

不适合直接承担：

- 目标识别
- 3D 恢复
- 抓取评分

为什么重要：

它对应你当前 pipeline 第 3 步，并且比只保留单帧 SAM 更利于以后接闭环跟踪。

## 2.3 Grounded-SAM-2

- 项目：<https://github.com/IDEA-Research/Grounded-SAM-2>

适合借鉴：

- grounding + segmentation 串联方式
- JSON 结果落盘格式
- 多 prompt 类型在 tracking 中的使用

不适合直接照搬：

- 全部依赖其 demo 脚本结构

为什么重要：

你当前 pipeline 的前半段几乎就是它的简化版。

## 2.4 Open3D

- 文档：<https://www.open3d.org/docs/latest/jupyter/geometry/pointcloud.html>
- 论文：<https://open3d.org/paper.pdf>

适合借鉴：

- 点云恢复
- 法向估计
- 平面分割
- 局部几何分析

为什么重要：

你现在第 4 步“mask + depth -> 位置”过于粗。  
Open3D 是把它升级成“可抓取几何描述”的最稳工程工具。

## 3. 抓取生成参考

## 3.1 Contact-GraspNet

- 项目：<https://github.com/NVlabs/contact_graspnet>
- 论文：<https://arxiv.org/abs/2103.14127>

适合借鉴：

- 从场景点云生成 6-DoF grasp distribution
- object-wise grasp 需要先做 segmentation

局限：

- 对视角和点云条件有依赖
- 不适合你当前直接作为唯一主路径

为什么重要：

它说明“先分割，再局部 grasp synthesis”是成熟路径。

## 3.2 GPD

- 项目：<https://github.com/atenpas/gpd>

适合借鉴：

- 点云上的抓取候选采样与工作空间定义
- grasp pose 表示方式

局限：

- 偏传统 pipeline
- 对参数敏感

为什么重要：

它适合作为规则式 / 几何式 baseline，对比学习式方法。

## 3.3 GraspNet-1Billion

- 论文：<https://openaccess.thecvf.com/content_CVPR_2020/papers/Fang_GraspNet-1Billion_A_Large-Scale_Benchmark_for_General_Object_Grasping_CVPR_2020_paper.pdf>
- 组织页：<https://github.com/graspnet>

适合借鉴：

- grasp benchmark
- 大规模 RGB-D grasp 数据与评测思路

为什么重要：

如果以后你要替换 grasp proposal 模块，GraspNet 系生态几乎是绕不过去的基线。

## 4. 系统级参考

## 4.1 OK-Robot

- 项目：<https://github.com/ok-robot/ok-robot>
- 论文：<https://arxiv.org/abs/2401.12202>
- 项目页：<https://ok-robot.github.io/>

适合借鉴：

- 模块化 open-vocabulary manipulation 系统思路
- “感知、抓取、执行组合细节很重要”的系统结论
- 失败模式分析方式

特别值得吸收的结论：

- 开放词汇系统失败往往来自多个小误差叠加
- 查询词、候选选择、抓取姿态、硬件细节都会显著影响成功率
- 规则式 top-down baseline 在一些条件下仍然很有价值

为什么重要：

它和你现在要做的事情最像，但它是整套 pick-and-drop 系统，不是单独一个模型。

## 4.2 OWG

- 项目：<https://github.com/gtziafas/OWG>

适合借鉴：

- open-world grasping 的模块划分
- referring segmentation -> grasp planning -> contact reasoning 的分段思路

为什么重要：

这和你当前链路非常接近，尤其适合当“中长期增强路线”的系统参考。

## 4.3 OVAL-Grasp

- 项目页：<https://ekjt.github.io/OVAL-Grasp/>

适合借鉴：

- task-oriented / part-aware grasp
- 用语言把抓取从“抓住物体”提升到“抓对部位”

为什么重要：

当你从“抓起来”升级到“按任务抓”，它会变得很 relevant。

## 5. 6D 姿态与对象几何参考

## 5.1 FoundationPose

- 项目：<https://github.com/NVlabs/FoundationPose>
- 论文：<https://arxiv.org/abs/2312.08344>

适合借鉴：

- novel object 6D pose estimation / tracking
- model-based 与 model-free 双模式

局限：

- 更适合“已知对象、追踪稳定姿态”的任务
- 当前 MVP 若只做 top-down 桌面抓取，不必马上引入

为什么重要：

如果后面你不满足于“中心点 + 法向”，而要拿稳定 6D pose，它是当前最值得认真评估的候选之一。

## 5.2 OnePose

- 项目：<https://github.com/zju3dv/OnePose>
- 论文：<https://arxiv.org/abs/2205.12257>

适合借鉴：

- 无 CAD 的 one-shot pose estimation

局限：

- 引入成本较高
- 当前桌面抓取 MVP 不是必须件

为什么重要：

如果你的目标对象是新物体，且没有 CAD，这条路线值得保留。

## 6. 高层多模态控制参考

## 6.1 OpenVLA

- 项目：<https://github.com/openvla/openvla>
- 论文：<https://arxiv.org/abs/2406.09246>

适合借鉴：

- 语言、视觉、动作统一建模
- 多任务 manipulation policy

当前建议角色：

- 高层策略参考
- 任务解释与重排序思路参考

当前不建议角色：

- 直接取代 A1Z SDK 执行层

## 6.2 VIMA

- 项目：<https://github.com/vimalabs/VIMA>
- 论文：<https://arxiv.org/abs/2210.03094>

适合借鉴：

- multimodal prompt 的任务表达方式
- object-centric token 设计思想

为什么重要：

它可以帮助你把语言任务输入设计得更工程化，而不是只传一句原始文本。

## 7. 这些参考如何映射到你的 pipeline

## 当前主线

- 第 1 步，自然语言任务解释：
  - 参考 OpenVLA / VIMA
- 第 2 步，RGB grounding：
  - 参考 Grounding DINO
- 第 3 步，SAM2 分割：
  - 参考 SAM 2 / Grounded-SAM-2
- 第 4 步，depth + mask 恢复 3D：
  - 参考 Open3D
- 第 5 步，抓取：
  - MVP：规则式 top-down
  - 增强：Contact-GraspNet / GPD / GraspNet 系
- 系统组合与失败分析：
  - 参考 OK-Robot / OWG

## 8. 当前推荐与不推荐

## 当前推荐

- Grounding DINO + SAM 2 做前半段
- Open3D 做几何恢复
- 规则式 top-down 抓取做第一版
- A1Z SDK + 本地约束层做执行
- OK-Robot 风格的失败分析做系统改进闭环

## 当前不推荐

- 直接上端到端 VLA 控制真机
- 还没做好 3D 恢复就接入复杂 6-DoF grasp 网络
- 把 Grounded-SAM-2 的 demo 当生产架构
- 用单次 center point 代替抓取候选集

## 9. 结论

对你当前项目来说，最有价值的不是“找一个最强模型替换全部模块”，而是：

- 用成熟开源项目补每一段短板
- 用论文给出边界判断和路线选择
- 保持任务对象、几何对象、抓取对象、执行对象彼此解耦

这也是为什么这套文档最终推荐的是：

- 模块化开放词汇抓取系统

而不是：

- 单模型黑盒抓取系统

