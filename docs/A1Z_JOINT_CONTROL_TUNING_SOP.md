# A1Z 真机关节精度测试与控制调试 SOP

本文档用于排查以下问题：

- GUI 同时改变 J1-J6 时，最终角度误差比单关节运动大；
- 重力补偿是否使用了正确的 G1Z、相机支架和 D405 质量；
- 问题应归因于 URDF/重力补偿、关节零点、运动速度，还是 KP/KD；
- 在不增加外层 PID 或重复补发命令的前提下，如何得到可复现的真机数据。

本文档日期为 2026-08-01。命令基于仓库当前固定的 GALAXEA A1Z SDK
`gripper` 分支提交 `e931ecd0e25ad35df251097ba42921b3d2fa7224`。

## 1. 官方流程与项目流程的边界

GALAXEA 官方公开资料给出了控制原理、API、示例和首轮重力补偿建议，但没有给出一套完整的
“六轴角度精度自动整定”流程。官方明确说明：

- 电机固件执行 MIT 混合控制：
  `torque = kp * position_error + kd * velocity_error + feedforward_torque`；
- SDK 默认以 250 Hz 读取反馈、用 Pinocchio/RNEA 计算动力学前馈，再向电机发送命令；
- 位置保持模式是默认 KP/KD 加动力学前馈；
- `move_joints()` 是阻塞式插值运动；
- 首次验证重力补偿时应从 `gravity_comp_factor=0.3` 开始，确认方向正确后逐步增加；
- SDK 允许通过 `urdf_path`、`default_kp`、`default_kd`、`start(initial_kp,
  initial_kd)` 和 `move_joints(..., kp, kd)` 修改控制参数。

本项目在官方 SDK 外增加了以下工程步骤：

- 使用当前 G1Z + 相机支架 + D405 的生成控制 URDF；
- 保证同一时刻只有一个进程占用 CAN 控制权；
- 每次 `move` 后读取 SDK 反馈并检查目标误差；
- 保存 `target/measured/error` JSON，比较单轴运动和六轴同时运动；
- 只有在质量、重心、重力方向和零点排除后才调整 KP/KD。

这里的 `move` 仍然只向 SDK 提交一次轨迹。项目服务随后验证反馈，但不会根据残余误差自动再次
补发目标。因此它不是新增的一层 PID，也不是迭代式闭环补偿。

## 2. 必须先满足的安全条件

以下条件缺一不可：

1. 机械臂固定牢固，工作空间内无人、无易碰撞物，实体急停在操作者手边。
2. 重力模式、服务启停、电机诊断期间有人托住机械臂；失能后机械臂最终仍可能下坠。
3. 首轮测试不夹持物体，不使用大臂展姿态，速度从 `0.10 rad/s` 开始。
4. 所有测试姿态必须先由现场人员确认路径安全，不能只依赖 URDF 关节限位。
5. 同一时刻只允许一个控制进程向 `can0` 发送命令。
6. 出现反向补偿、快速下坠、持续振荡、撞限位、异常噪声、温升、CAN 故障或反馈丢失时，立即
   使用实体急停。`a1zctl estop` 只是服务在线时的软件急停，不能代替实体急停或断电。

特别注意官方示例的退出行为：

- `vendor/GALAXEA-A1Z/examples/gravity_comp.py`
- `vendor/GALAXEA-A1Z/examples/position_hold.py`

这两个脚本在正常退出或 `Ctrl+C` 后都会执行 `move_joints(zeros)`，即先返回六关节全零位，再失能。
所以 `Ctrl+C` 不是原地急停。只有确认“当前位置到全零位”的整条路径安全时，才能直接运行这两个
官方示例。

官方 `motor_diag.py` 的命令也不是全部只读：

| 命令 | 是否发 CAN 命令 | 影响 |
|---|---:|---|
| `--check-can` | 否 | 读取 SocketCAN 接口和错误计数 |
| `--listen` | 否 | 被动监听报文，可在控制服务运行时使用 |
| `--scan` | 是 | 逐电机使能、探测、失能；机械臂可能失去保持 |
| `--probe` | 是 | 指定电机使能、读反馈、失能 |
| `--monitor` | 是 | 使能全部电机并持续发送零增益/零扭矩类命令，退出后失能 |
| `--clear-error` | 是 | 修改 MotorB 错误状态 |

`--scan`、`--probe`、`--monitor` 只能在控制服务已停止且机械臂被可靠支撑时使用，不属于日常在线
监控流程。

## 3. 命令环境

以下命令默认从仓库根目录、同一个 Bash 终端执行：

```bash
cd /home/th1rt3en/dev/forge/A1Z
export A1Z_PROFILE=real
export A1Z_CONTROL_URDF="$PWD/build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_control.urdf"
```

当前真机配置的关键预期值：

- CAN：`can0`，1,000,000 bit/s；
- 控制频率：250 Hz，最低健康阈值 80 Hz；
- 默认 KP：`[30, 30, 30, 20, 5, 5]`；
- 默认 KD：`[1, 1, 1, 0.5, 0.5, 0.5]`；
- 控制 URDF 自由度：`nq=6, nv=6`；
- 当前生成模型总质量：`5.41111337 kg`；
- 其中 A1Z+G1Z 主体：`5.30911337 kg`，相机支架：`0.030 kg`，D405：`0.072 kg`；
- `arm_link6` 使用物理有效的 CAD 惯性参数，质量为 `0.42335647 kg`，不采用官方 URDF 中违反主惯量三角不等式的张量。

总质量只用于检查模型是否意外漂移；真正影响姿态相关前馈的还有各 link 的质心和惯量。

## 4. 阶段 A：离线校验控制模型

本阶段不使能机械臂，可先执行。

### A1. 重新生成控制 URDF

```bash
python3 scripts/prepare_a1z_urdfs.py --env-file config/real.env
```

### A2. 验证 SDK、控制模型、Isaac 模型和 D405 frame

```bash
A1Z_PROFILE=real ./scripts/verify_a1z_sdk_in_container.sh
```

预期至少看到：

```text
a1z ok
Control URDF DoF: nq=6, nv=6
Isaac URDF DoF:   nq=8, nv=8
SDK container verification passed.
```

### A3. 打印质量清单

```bash
python3 - "$A1Z_CONTROL_URDF" <<'PY'
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
rows = []
for link in root.findall("link"):
    mass = link.find("inertial/mass")
    if mass is not None:
        rows.append((link.get("name"), float(mass.get("value"))))
for name, value in rows:
    print(f"{name:32s} {value:.9f} kg")
print(f"{'TOTAL':32s} {sum(value for _, value in rows):.9f} kg")
PY
```

预期 `TOTAL` 为 `5.411113370 kg`。如果不一致，先停止真机调试，检查
`config/d405.json`、`config/camera_bracket.json`、官方源 URDF、
`A1Z_nogripper.csv` 中的 `arm_link6` 行和生成脚本。

### A4. 执行模型合同测试

```bash
A1Z_PROFILE=real ./scripts/a1z_sdk_python_in_container.sh -m pytest -q \
  tests/test_d405_payload_performance.py \
  tests/test_d405_mount_contract.py \
  tests/test_camera_bracket_contract.py
```

必须全部通过后才能进入真机阶段。

## 5. 阶段 B：CAN 和控制服务只读检查

### B1. 查看服务状态

```bash
A1Z_PROFILE=real ./scripts/manage_a1z_control_server.sh status
```

如果服务在线，再读取能力和关节反馈：

```bash
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json info
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json status
```

`info` 应显示：

- `backend: socketcan`；
- `running: true`、`faulted: false`；
- `control_freq_hz: 250`；
- 正确的 `default_kp/default_kd`；
- 当前 `control_mode` 和 `gravity_comp_factor`。

`status` 用于检查六轴的 `pos_deg`、`vel_rad_s`、`torque_nm`、温度、错误码、急停和运行状态。

### B2. 官方 CAN 接口检查

此命令不打开 CAN 总线，不发控制帧：

```bash
A1Z_PROFILE=real ./scripts/a1z_sdk_python_in_container.sh \
  vendor/GALAXEA-A1Z/tools/motor_diag.py --check-can --channel can0
```

预期接口为 `UP`，且没有 `bus-off` 或 `error-passive`。

### B3. 官方被动监听

此命令只接收，不发送，可以在控制服务在线时执行：

```bash
A1Z_PROFILE=real ./scripts/a1z_sdk_python_in_container.sh \
  vendor/GALAXEA-A1Z/tools/motor_diag.py --listen --duration 10 --channel can0
```

服务在线时应持续看到对应 CAN ID 的报文。服务已停止时没有持续报文不一定代表硬件故障。

### B4. 查看服务日志

```bash
tail -n 100 runtime/logs/a1z-control-real.log
```

若有控制频率过低、反馈陈旧、动力学力矩越限、温度或 CAN 异常，先解决日志中的根因，不进入运动
测试。

## 6. 阶段 C：按官方建议验证重力补偿

本阶段必须托住机械臂。`0.3` 只用于先验证补偿方向，不足以完整承托机械臂是正常现象。

项目推荐通过唯一控制服务执行，因为它使用当前控制 URDF，且不会在退出时自动跑到全零位：

```bash
A1Z_PROFILE=real ./scripts/manage_a1z_control_server.sh restart \
  --gravity-mode --gravity-factor 0.3
```

确认实际运行参数：

```bash
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json info
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json status
```

现场检查：

1. 补偿力方向是否在抵消重力，而不是加速下坠或主动抬升；
2. 各姿态下手动拖动是否连续，无周期振荡和明显关节冲击；
3. `status` 中无 fault、estop、反馈丢失或异常温度；
4. 尤其比较伸展和收拢姿态。如果只有某些姿态明显过补偿或欠补偿，优先怀疑质量、质心、安装方向
   或关节符号，而不是先加 KP。

只有当前档位确认安全后，才逐档执行下一条命令；不要把它们写进自动循环：

```bash
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json gravity-factor 0.5
```

```bash
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json gravity-factor 0.7
```

```bash
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json gravity-factor 1.0
```

每档都重复读取 `status` 和现场检查。若某档出现反向、抬升或振荡，立即停止增加，并记录该姿态、
关节角、力矩和 factor。

结束重力模式时继续托住机械臂：

```bash
A1Z_PROFILE=real ./scripts/manage_a1z_control_server.sh stop
```

## 7. 阶段 D：位置保持基线

在现场人员托住机械臂的情况下，以正确 URDF、全重力补偿和位置保持模式重新启动：

```bash
A1Z_PROFILE=real ./scripts/manage_a1z_control_server.sh start --gravity-factor 1.0
```

确认不是零力漂浮模式：

```bash
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json info
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json status
```

必须满足 `control_mode: position_hold`、`running: true`、`faulted: false`。

静止 3-5 秒，连续读取三次状态：

```bash
for A1Z_STATUS_SAMPLE in 1 2 3; do
  date --iso-8601=ns
  A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json status
  sleep 1
done
```

如果机械臂在不发送新目标时仍持续漂移、振荡或反馈角跳变，不做后续目标角测试。先查重力补偿、
零点、CAN 反馈和机械结构。

## 8. 阶段 E：单轴与六轴小步 A/B 测试

项目 `move` 的行为是：调用一次 SDK `move_joints()`，轨迹完成后每 50 ms 读取反馈，要求最大绝对
关节误差不超过 `0.75 deg` 且连续两次满足；等待上限为 2 秒。返回中的关键字段是：

- `ok`；
- `data.completion`；
- `data.verification.target_deg`；
- `data.verification.measured_deg`；
- `data.verification.error_deg`；
- `data.verification.max_error_deg`。

`0.75 deg` 是当前项目的命令验收阈值，不是 GALAXEA 官方精度承诺。官方 `±0.1 mm` 是重复定位
规格，也不能直接换算成每个关节的一次绝对角度误差。

### E1. 建立本次记录目录

```bash
A1Z_TUNE_RUN="runtime/control_tuning/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$A1Z_TUNE_RUN"
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json info \
  | tee "$A1Z_TUNE_RUN/info.json"
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json status \
  | tee "$A1Z_TUNE_RUN/status-before.json"
```

### E2. 现场确认三个测试姿态

以下姿态围绕项目 `home=[0,60,-60,0,0,0] deg` 做 2 度小步，只是建议的低幅度测试集合。执行前
仍必须确认当前实机、线束、相机和周围环境允许这些路径：

```bash
A1Z_HOME_DEG='0,60,-60,0,0,0'
A1Z_SINGLE_DEG='0,62,-60,0,0,0'
A1Z_MULTI_DEG='2,62,-62,2,2,2'
```

若现场不允许，修改为已审批的三个姿态，但要保持：

- HOME 是每次试验相同的起点；
- SINGLE 只改变一个关节；
- MULTI 同时改变六个关节；
- SINGLE 和 MULTI 中被比较关节的变化量一致。

### E3. 先回 HOME，检查反馈后再继续

```bash
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json move \
  "$A1Z_HOME_DEG" --speed 0.10 \
  | tee -a "$A1Z_TUNE_RUN/home.jsonl"
```

必须看到 `ok: true` 和 `completion: feedback_verified` 或 `already_at_target`。若为
`submitted_unverified`、`reached: false`、fault 或 estop，停止试验并保存输出。

### E4. 单轴运动

```bash
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json move \
  "$A1Z_SINGLE_DEG" --speed 0.10 \
  | tee -a "$A1Z_TUNE_RUN/single.jsonl"
```

人工检查结果为 `ok: true` 后，再回 HOME：

```bash
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json move \
  "$A1Z_HOME_DEG" --speed 0.10 \
  | tee -a "$A1Z_TUNE_RUN/home.jsonl"
```

### E5. 六轴同时运动

```bash
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json move \
  "$A1Z_MULTI_DEG" --speed 0.10 \
  | tee -a "$A1Z_TUNE_RUN/multi.jsonl"
```

每条命令都人工确认成功后，再按 `HOME -> SINGLE -> HOME -> MULTI` 的顺序重复 3 次。不要用无人
值守循环发送运动命令。

### E6. 比较速度影响

只有 `0.10 rad/s` 的三轮结果稳定且安全时，才把相同测试重复到 `0.20 rad/s`。姿态、负载和测试
顺序必须保持不变：

```bash
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json move \
  "$A1Z_MULTI_DEG" --speed 0.20 \
  | tee -a "$A1Z_TUNE_RUN/multi-speed-020.jsonl"
```

不要同时改变速度、质量参数和增益，否则无法判断原因。

### E7. 汇总已保存的目标和反馈

以下命令只读取本轮 JSONL，并额外计算有符号误差
`signed_error = target_deg - measured_deg`：

```bash
python3 - "$A1Z_TUNE_RUN" <<'PY'
import json
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
for path in sorted(run_dir.glob("*.jsonl")):
    print(f"\n[{path.name}]")
    for trial, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        response = json.loads(line)
        verification = response.get("data", {}).get("verification", {})
        target = verification.get("target_deg", [])
        measured = verification.get("measured_deg", [])
        signed = (
            [round(t - m, 3) for t, m in zip(target, measured)]
            if len(target) == len(measured) == 6
            else []
        )
        print(
            f"trial={trial} ok={response.get('ok')} "
            f"max_abs_error={verification.get('max_error_deg')} "
            f"signed_error_deg={signed}"
        )
PY
```

对比 `single.jsonl` 和 `multi.jsonl` 中同一关节的误差，并检查三轮误差方向是否一致。随机变化更像
重复性、通信或机械问题；方向稳定且随姿态变化的误差更像动力学模型或静态控制偏差。

## 9. 如何根据结果定位原因

| 观察结果 | 优先检查 | 不应先做的事 |
|---|---|---|
| 同一关节在所有姿态都有接近固定的有符号偏差 | 电机零点、反馈零位、关节符号 | 盲目提高全部 KP |
| 伸展姿态误差大，收拢姿态误差小 | link/工具质量、质心、安装方向、gravity factor | 做外层重复补发掩盖模型错误 |
| 低速准确，高速或六轴同时运动误差大，但稍后会继续收敛 | 轨迹速度/加速度、动态前馈、验收等待时间 | 立刻做零点标定 |
| 最终稳定偏差随负载方向变化 | 重力前馈、质量/质心、静摩擦和 KP | 只增加 KD |
| 过冲或周期振荡 | KP 偏高、KD 偏低、机械间隙 | 继续提高 KP |
| 运动结束后角度稳定，但末端位置重复性差 | URDF 几何、安装刚度、TCP/手眼标定 | 用关节 PID 解决几何标定 |
| 反馈丢失、温度或错误码异常 | CAN、电源、电机/驱动器、控制频率 | 继续精度试验 |

判断“六轴同时运动更差”时，要区分两类误差：

1. **只在运动过程中增大，静止后消失**：更像速度、惯性、前馈或采样时刻问题；
2. **静止后仍保留，并随姿态/负载变化**：更像质量/质心、重力补偿、静摩擦或位置刚度问题。

## 10. KP/KD 调试流程

只有 A-D 阶段通过、零点没有固定偏差、重力补偿方向正确且质量模型可信后，才进入本阶段。

官方 SDK 支持主动传入 KP/KD，但没有公开自动整定或推荐扫参流程。当前项目真机默认值来自：

```text
a1z_ext/config/control_defaults.json
```

查看当前值：

```bash
python3 - <<'PY'
import json
from pathlib import Path

cfg = json.loads(Path("a1z_ext/config/control_defaults.json").read_text())
print("default_kp =", cfg["default_kp"])
print("default_kd =", cfg["default_kd"])
PY
```

工程调试规则（不是官方自动整定流程）：

1. 一次只改一个关节的一类参数；
2. 保留基线 `[30,30,30,20,5,5]` 和 `[1,1,1,0.5,0.5,0.5]`；
3. 每次变化不超过当前值的 5%-10%；
4. 先用 2-5 度低速单轴小步验证，再做六轴小步；
5. 静态误差大且不振荡时才小幅增加 KP；
6. 有过冲/振荡时先降低 KP 或小幅增加 KD；
7. 每组参数重复同一 E 阶段，禁止同时修改 URDF、factor 和速度。

修改 JSON 后先验证格式和差异：

```bash
python3 -m json.tool a1z_ext/config/control_defaults.json >/dev/null
git diff -- a1z_ext/config/control_defaults.json
```

然后重启服务并确认生效：

```bash
A1Z_PROFILE=real ./scripts/manage_a1z_control_server.sh restart \
  --gravity-factor 1.0
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json info
```

`info.default_kp/default_kd` 必须与本轮记录一致。出现振荡、异常噪声、过流或温升时立即恢复上一组
已验证参数，不继续增益扫描。

## 11. 官方电机诊断：仅停机维修时执行

先停服务并可靠支撑机械臂：

```bash
A1Z_PROFILE=real ./scripts/manage_a1z_control_server.sh stop
```

确认没有项目控制服务占用 CAN 后，扫描 J1-J6：

```bash
A1Z_PROFILE=real ./scripts/a1z_sdk_python_in_container.sh \
  --require-control-server-stopped \
  vendor/GALAXEA-A1Z/tools/motor_diag.py \
  --scan --joints 0 1 2 3 4 5 --channel can0
```

只探测一个关节：

```bash
A1Z_PROFILE=real ./scripts/a1z_sdk_python_in_container.sh \
  --require-control-server-stopped \
  vendor/GALAXEA-A1Z/tools/motor_diag.py --probe 3 --channel can0
```

`--scan` 和 `--probe` 最终会发送失能命令。`--monitor` 会持续改变全部电机控制状态，本 SOP 不将它
作为精度调试手段。

只有 MotorB 已报告明确错误、根因已处理后，才清除对应错误：

```bash
A1Z_PROFILE=real ./scripts/a1z_sdk_python_in_container.sh \
  --require-control-server-stopped \
  vendor/GALAXEA-A1Z/tools/motor_diag.py \
  --clear-error --joints 3 --channel can0
```

不要把清错当成修复；清错后必须重新执行 B 阶段。

## 12. 官方零点标定：只有固定零位偏差时执行

零点标定会把电机的**当前位置永久设为零点**，不是普通精度测试，也不能靠软件命令自动恢复原
零点。只有满足以下条件才允许执行：

- 已排除质量、重力补偿和反馈采样问题；
- 已按官方零位图把机械臂机械对准；
- 机械臂固定并被支撑；
- 有现场复核和标定前照片/角度记录；
- 控制服务已停止。

项目容器封装没有交互式 stdin，所以最后的 `--yes` 会跳过脚本确认。仅在上述检查完成后，对确实
需要标定的单关节执行，不应直接 `--all`：

```bash
A1Z_PROFILE=real ./scripts/a1z_sdk_python_in_container.sh \
  --require-control-server-stopped \
  vendor/GALAXEA-A1Z/tools/set_zero.py --joints 0 --channel can0 --yes
```

标定后重新上电，依次执行 B、C、D、E 阶段。官方原生环境中的等价命令是：

```bash
sudo python3 tools/set_zero.py --joints 0
```

## 13. 官方原始示例命令及当前项目限制

### 13.1 官方重力补偿示例

必须先停止项目服务、托住机械臂，并确认退出回全零路径安全：

```bash
A1Z_PROFILE=real ./scripts/manage_a1z_control_server.sh stop
A1Z_PROFILE=real ./scripts/a1z_sdk_python_in_container.sh \
  --require-control-server-stopped \
  vendor/GALAXEA-A1Z/examples/gravity_comp.py \
  --mode gravity \
  --gravity_factor 0.3 \
  --freq 250 \
  --can can0 \
  --urdf /workspace/A1Z/build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_control.urdf
```

位置保持当前姿态可把 `--mode gravity` 改为 `--mode hold`。此示例支持临时覆盖 KD：

```bash
--kd 1.0,1.0,1.0,0.5,0.5,0.5
```

不要在没有明确试验记录时随意改变该数组。

### 13.2 官方位置保持示例

官方原始命令形式为：

```bash
python3 examples/position_hold.py \
  --gravity_factor 1.0 \
  --freq 250 \
  --can can0 \
  --q_target_deg 0,60,-60,0,0,0 \
  --speed 0.10
```

当前固定版本的 `position_hold.py` 没有 `--urdf` 参数，会使用 SDK 包内默认 URDF；它也只在
`move_joints()` 返回后打印 `Target reached.`，没有比较目标和实测角。因此当前 G1Z+D405 真机不把
这条原始命令作为验收命令。实际使用第 7-8 节的项目服务，它会加载正确控制 URDF并返回反馈验证
结果。

## 14. 结束与恢复正常服务

直接 SDK 示例或维修诊断结束后，确认没有残留直接 CAN 进程，再恢复项目服务：

```bash
A1Z_PROFILE=real ./scripts/manage_a1z_control_server.sh start \
  --gravity-factor 1.0
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json info
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh --json status
```

最后保存：

- 本次 Git 提交和控制 URDF 质量清单；
- factor、KP/KD、速度、负载和测试姿态；
- 每轮 `target_deg/measured_deg/error_deg/max_error_deg`；
- 服务日志和任何电机错误码；
- 是否单轴正常、六轴异常，以及误差在静止后是否继续收敛。

只有相同配置下至少三次重复结果一致，才能据此决定下一步。不要用单次成功或单次失败直接修改全部
关节增益。

## 15. 官方资料与仓库依据

- [GALAXEA A1Z Software API](https://docs.galaxea-dynamics.com/A1Z/en/docs/software_api/a1z_api)
- [GALAXEA A1Z 文档与安全/规格](https://docs.galaxea-dynamics.com/A1Z/docs/)
- [GALAXEA A1Z 电机零点标定](https://docs.galaxea-dynamics.com/Tools/en/docs/a1z/a1z_calibration)
- [GALAXEA A1Z 官方 GitHub](https://github.com/userguide-galaxea/GALAXEA-A1Z)
- 仓库固定版本说明：`vendor/GALAXEA-A1Z_UPSTREAM`
- 官方示例：`vendor/GALAXEA-A1Z/examples/gravity_comp.py`
- 官方示例：`vendor/GALAXEA-A1Z/examples/position_hold.py`
- 官方诊断：`vendor/GALAXEA-A1Z/tools/motor_diag.py`
- 项目控制服务：`a1z_ext/robots/server.py`
- 项目控制参数：`a1z_ext/config/control_defaults.json`
- 当前生成控制模型：`build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_control.urdf`
