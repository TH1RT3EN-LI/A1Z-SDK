# A1Z WebRTC Streaming

This workspace uses one shared Isaac Sim 5.1 headless WebRTC session for both local and remote viewing. The old local desktop GUI path was removed because Isaac Sim local windows are unreliable under Wayland/Xwayland in this setup.

## Current Server Address

- Isaac Sim host IP on the target subnet: `10.66.0.11`
- Isaac Sim container: `isaac-sim-5-1-dev`
- World USD: `/workspace/A1Z/build/scenes/A1Z_G1Z_world.usd`

## Prepared Assets

- Extracted robot package: `/workspace/A1Z/build/robot_packages/A1Z_G1Z`
- Isaac URDF: `/workspace/A1Z/build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_isaac.urdf`
- Control URDF: `/workspace/A1Z/build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_control.urdf`
- SDK source tree: `/workspace/A1Z/vendor/GALAXEA-A1Z`
- Generated robot USD: `/workspace/A1Z/build/scenes/A1Z_G1Z_robot.usd`
- Generated world USD: `/workspace/A1Z/build/scenes/A1Z_G1Z_world.usd`

## One-Time Setup

Run on the host:

```bash
./scripts/setup_a1z_isaac.sh
```

## Import Or Rebuild The World

Run inside the container:

```bash
/workspace/A1Z/scripts/rebuild_a1z_world.sh
```

This rebuild path now regenerates the prepared A1Z URDF variants first, including the fixed `arm_link6 -> d405_link` wrist-camera chain.

The Isaac import path now uses the simulation URDF with movable gripper fingers:

```bash
/isaac-sim/python.sh /workspace/A1Z/scripts/import_a1z_g1z_to_usd.py \
  --urdf /workspace/A1Z/build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_isaac.urdf
```

## Start Or Reuse The Shared WebRTC Session

Run on the host:

```bash
./scripts/open_a1z_webrtc_host.sh 10.66.0.11
```

This is the main UI entrypoint. It starts the headless Isaac stream if needed,
or reuses the existing stream so local and remote clients stay on the same
Isaac session.

Use the lower-level starter when you only want to ensure the stream exists:

```bash
./scripts/start_a1z_webrtc_streaming_host.sh 10.66.0.11
```

Both wrappers wait until the in-container A1Z SDK socket is actively listening
before returning.

Only force a restart when you intentionally want to disconnect existing viewers
and launch a fresh Isaac process:

```bash
./scripts/open_a1z_webrtc_host.sh --restart 10.66.0.11
```

Log file:

```bash
tail -f /workspace/A1Z/runtime/logs/isaac-sim-streaming.log
```

Stop:

```bash
./scripts/stop_a1z_webrtc_streaming_host.sh
```

The stop wrapper also removes a stale `/tmp/a1z.sock` if the Isaac process is already gone.

## Known Good Minimal Streaming

When debugging a black screen, the current known-good baseline is the official minimal streaming launch inside the container:

```bash
cd /isaac-sim

./runheadless.sh \
  --/app/livestream/publicEndpointAddress=10.66.0.11
```

This baseline was verified to reach `Isaac Sim Full Streaming App is loaded.` and expose:

- `49100/tcp` for signaling
- `47998/udp` for media

Important: this official minimal launch does not load the A1Z world or robot by itself. It only verifies that Isaac Sim headless streaming works on `10.66.0.11`.

## Known Good A1Z World Streaming

The current verified way to stream the A1Z world is to stay on the official `runheadless.sh` path and add the project stage-open plus SDK bridge script:

```bash
cd /isaac-sim

A1Z_WORLD_USD=/workspace/A1Z/build/scenes/A1Z_G1Z_world.usd \
./runheadless.sh \
  --/app/livestream/publicEndpointAddress=10.66.0.11 \
  --exec /workspace/A1Z/scripts/open_a1z_world_with_a1z_sdk.py
```

This path was verified to:

- reach `Isaac Sim Full Streaming App is loaded.`
- load the A1Z world under `/World/A1Z_G1Z/...`
- start the A1Z SDK socket server inside the same Kit process

The default control socket inside the container is:

```bash
/tmp/a1z.sock
```

The current Docker-first ROS 2 integration path also uses the optional TCP
listener exposed by the same in-process A1Z server:

```bash
0.0.0.0:18080
```

Once the stream is up, the current Isaac instance can be controlled from the host with:

```bash
./scripts/a1zctl_in_container.sh status
./scripts/a1zctl_in_container.sh move --preset ready
./scripts/a1zctl_in_container.sh gripper 0.25
./scripts/a1zctl_in_container.sh stop
```

An independent ROS 2 container can connect to the same Isaac-backed robot server
over `A1Z_TCP_HOST` / `A1Z_TCP_PORT` without sharing `/tmp/a1z.sock`.

Runtime inspection from the host:

```bash
./scripts/a1z_runtime_status.sh
```

Current end-to-end health check from the host:

```bash
./scripts/verify_a1z_control_stack.sh
```

If a live Isaac stream is already running, this script reuses it for a
read-only backend smoke check instead of launching a second Kit process.

The gripper open/close control in Isaac is backed by the movable finger joints in `A1Z_G1Z_isaac.urdf`.

## Model Split

The workspace now keeps two explicit A1Z_G1Z URDF variants:

- `A1Z_G1Z_control.urdf`: 6-axis control/dynamics model. The gripper is handled as a separate hardware device in the SDK, so the finger joints are fixed in this URDF.
- `A1Z_G1Z_isaac.urdf`: Isaac simulation model. The finger joints remain movable so the gripper can be opened and closed in simulation.

Use `A1Z_G1Z_control.urdf` for SDK / Pinocchio / real-arm control logic, and `A1Z_G1Z_isaac.urdf` for Isaac import and simulation.

## Workspace Layout

- Upstream SDK mirror: `/workspace/A1Z/vendor/GALAXEA-A1Z`
- Rebuildable assets: `/workspace/A1Z/build`
- Runtime state: `/workspace/A1Z/runtime`
- Source archive stash: `/workspace/A1Z/artifacts`

## WebRTC Clients

Use the same client and target from the local machine or a remote Linux machine:

```bash
./isaacsim-webrtc-streaming-client-1.1.5-linux-x64.AppImage --no-sandbox
```

In the client:

- Server IP: `10.66.0.11`
- Expected fixed ports on the server:
  - `49100/tcp` for WebRTC signaling
  - `47998/udp` for WebRTC media

To auto-open a local client after the shared stream is ready, set:

```bash
export A1Z_WEBRTC_CLIENT_APP=/path/to/isaacsim-webrtc-streaming-client-1.1.5-linux-x64.AppImage
./scripts/open_a1z_webrtc_host.sh --client
```

To start or reuse the stream without opening a local client:

```bash
./scripts/open_a1z_webrtc_host.sh --no-client
```

## Notes

- The container must stay on `--network=host`.
- This setup is for one Isaac Sim instance and one client at a time.
- Local and remote viewing use the same WebRTC path; there is no separate local Isaac GUI launcher.
- The stage open script frames the default perspective camera toward the robot after the world loads.
- The current project launcher also starts the SDK socket server in the same Isaac process, so `a1zctl` commands drive the same robot shown in the remote stream.
- If the official minimal `runheadless.sh` path works but the project streaming script shows a black screen, treat the issue as stage-loading or viewport setup related rather than a base WebRTC connectivity problem.
