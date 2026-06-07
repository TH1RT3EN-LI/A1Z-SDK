# Isaac Sim 5.1 Development Container

This repository should be developed inside the `isaac-sim-5-1-dev` container.

## Baseline

- Image: `nvcr.io/nvidia/isaac-sim:5.1.0`
- Container name: `isaac-sim-5-1-dev`
- Workspace mount: `/home/th1rt3en/dev/forge/A1Z` -> `/workspace/A1Z`
- Persistent container home: `/home/th1rt3en/.local/share/isaac-sim-5.1-dev/home` -> `/home/ubuntu`
- Working directory in container: `/workspace/A1Z`
- Runtime mode: headless development container with WebRTC viewing
- Interactive dev user inside container: `ubuntu` (`uid=1000`, `gid=1000`, added to `isaac-sim`)

The Isaac Sim image is shared. The `isaac-sim-5-1-dev` container instance in this repository is project-scoped because it mounts this workspace as `/workspace/A1Z`.

Host-side defaults for the helper scripts live in:

```bash
./config/a1z_container.env
```

The current container helpers propagate these SDK runtime defaults into the container:

- `A1Z_BACKEND`
- `A1Z_CAN_CHANNEL`
- `A1Z_SOCKET_PATH`

## Rule For Future Work

All Isaac Sim related development, package installation, Python execution, and validation should be performed inside `isaac-sim-5-1-dev`.

Do not treat the host machine as the primary runtime environment for Isaac Sim work.

## Create The Container

```bash
./scripts/create_isaac_sim_dev_container.sh
```

## Daily Usage

Enter the container:

```bash
docker exec -it -u ubuntu isaac-sim-5-1-dev /bin/bash
```

Run Isaac Sim Python:

```bash
docker exec -it -u ubuntu isaac-sim-5-1-dev /isaac-sim/python.sh -c "import isaacsim; print('isaacsim ok')"
```

Run a script from this repository:

```bash
docker exec -it -u ubuntu isaac-sim-5-1-dev /isaac-sim/python.sh /workspace/A1Z/path/to/script.py
```

Run Isaac Python through the host helper with the project defaults:

```bash
./scripts/a1z_isaac_python_in_container.sh -c "import isaacsim; print('isaac ok')"
```

Prepare the robot package and rebuild the USD assets:

```bash
./scripts/setup_a1z_isaac.sh
```

That setup flow now also prepares the derived URDF variants used by the project runtime, including the D405 wrist-camera chain mounted on `arm_link6`.

Prepare the SDK runtime inside the current container:

```bash
./scripts/setup_a1z_sdk_in_container.sh
```

Run SDK Python inside the isolated container venv:

```bash
./scripts/a1z_sdk_python_in_container.sh -c "import a1z; print('a1z ok')"
```

Run the control CLI inside the container venv:

```bash
./scripts/a1zctl_in_container.sh status
```

Open an interactive SDK shell inside the container venv:

```bash
./scripts/a1z_sdk_shell_in_container.sh
```

Run the SDK/container health check:

```bash
./scripts/verify_a1z_sdk_in_container.sh
```

Run the current full control-stack health check:

```bash
./scripts/verify_a1z_control_stack.sh
```

This verifies the SDK runtime, mock backend, and Isaac backend. The SocketCAN
step is treated as an expected warning when no physical arm or `can0` is
attached yet.

Run the full offline control-path check without any physical arm or `can0`:

```bash
./scripts/verify_a1z_mock_control_in_container.sh
```

Run the real-arm SocketCAN preflight before hardware bring-up:

```bash
./scripts/verify_a1z_socketcan_preflight_in_container.sh
```

The Isaac import path uses:

```bash
/workspace/A1Z/build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_isaac.urdf
```

The SDK control path uses the generated control URDF via environment override:

```bash
/workspace/A1Z/build/robot_packages/A1Z_G1Z/urdf/A1Z_G1Z_control.urdf
```

For real-arm SDK use, the current container also needs:

- `python-can`
- `pin` / Pinocchio
- editable install of `/workspace/A1Z/vendor/GALAXEA-A1Z`
- host-side SocketCAN interface already up (for example `can0`)

The SDK runtime is intentionally isolated in `/home/ubuntu/.venvs/a1z-sdk` so the Isaac Python environment remains dedicated to Isaac Sim.

When no physical arm is attached, set `A1Z_BACKEND=mock` in `./config/a1z_container.env` or pass it inline for one-off runs:

```bash
A1Z_BACKEND=mock ./scripts/a1zctl_in_container.sh serve --backend mock --with-gripper
```

The `A1Z_BACKEND` value only controls the generic SDK wrappers such as
`a1zctl_in_container.sh`. The headless streaming launcher always starts the
Isaac-side backend inside the running Kit process.

Open the shared WebRTC UI from the host, published on `10.66.0.11` by default:

```bash
./scripts/open_a1z_webrtc_host.sh
```

This single path is used for both local and remote viewing. It starts the
stream if needed, otherwise it reuses the live stream so all viewers remain on
the same Isaac session.

The lower-level stream starter is also available:

```bash
./scripts/start_a1z_webrtc_streaming_host.sh
```

Both host wrappers wait until the Isaac-side A1Z SDK socket is listening before
returning. To intentionally replace a live stream, pass `--restart`.

If `A1Z_WEBRTC_CLIENT_APP` points to the Isaac Sim WebRTC client AppImage,
`./scripts/open_a1z_webrtc_host.sh --client` starts the shared stream and opens
the local viewer. Remote viewers connect to the same `10.66.0.11:49100` target.

Inspect the current container/stream/socket/backend state:

```bash
./scripts/a1z_runtime_status.sh
```

That launcher now uses the official `runheadless.sh` path and starts the A1Z SDK socket server inside the same Isaac Kit process. The default control socket remains:

```bash
/tmp/a1z.sock
```

So after streaming starts, the same Isaac instance can be driven with:

```bash
./scripts/a1zctl_in_container.sh status
./scripts/a1zctl_in_container.sh move --preset ready
./scripts/a1zctl_in_container.sh gripper 0.25
```

Run the Isaac-in-process control verification:

```bash
./scripts/verify_a1z_isaac_control_in_container.sh
```

Known-good official streaming smoke test inside the container:

```bash
cd /isaac-sim

./runheadless.sh \
  --/app/livestream/publicEndpointAddress=10.66.0.11
```

Launch headless Isaac Sim from inside the container:

```bash
docker exec -it -u ubuntu isaac-sim-5-1-dev /isaac-sim/runheadless.sh
```

## Container Lifecycle

Start:

```bash
docker start isaac-sim-5-1-dev
```

Stop:

```bash
docker stop isaac-sim-5-1-dev
```

Inspect:

```bash
docker ps -a --filter name=isaac-sim-5-1-dev
```

## Notes

- The current container is instantiated for headless development.
- Local and remote viewing both use WebRTC; GUI forwarding and the separate local Isaac GUI launcher are not part of this setup.
- The mounted `/home/ubuntu` path keeps Isaac Sim caches, logs, and user state across container restarts.
- The container starts as root only to add `ubuntu` to the `isaac-sim` group and keep the service alive.
- Daily work should be executed with `docker exec -u ubuntu ...`, which keeps files created in `/workspace/A1Z` owned by the host user.
- Use `/isaac-sim/python.sh` for Python execution instead of assuming `python3` is available on `PATH`.
- `./scripts/verify_a1z_isaac_control_in_container.sh` is an exclusive smoke test and assumes no other Isaac Sim process is currently running in the container.
- `./scripts/verify_a1z_mock_control_in_container.sh` now uses its own temporary socket path so it does not collide with a live Isaac session on `/tmp/a1z.sock`.
