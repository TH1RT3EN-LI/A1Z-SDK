# Remote GPU for the physical A1Z pipeline

This deployment keeps the real-time and safety boundary on the robot laptop:

```text
robot laptop                                      GPU host
────────────                                      ────────
SocketCAN control
D405 capture
task orchestration     SSH request.tar.gz ──────► VLM + SAM
local runtime store    ◄────── response.tar.gz    AnyGrasp/CUDA
planning + execution                              no job database
```

Only target perception and AnyGrasp are offloaded. The laptop stores the RGB-D
capture, masks, previews, grasp candidates, logs, selected plan, and execution
result beneath its own `--output-dir`. The GPU worker uses an ignored temporary
directory, streams the result back, and removes the temporary directory in a
`finally`/process-exit cleanup. Orphaned job directories older than 24 hours
are pruned when the next request starts. A lock serializes access to GPU 0.

Simulation never selects this backend. `--profile sim` continues to use its
local Isaac/vision environment.

## Why SSH is the first transport

- It reuses port 22 and public-key authentication; no unauthenticated model
  endpoint or Docker socket is exposed.
- A gzip tar on stdin/stdout is easy to inspect, test, and replace.
- The versioned request/response contract is independent of SSH. A future
  HTTP, queue, Ray, or cluster adapter can produce and consume the same
  artifacts without changing planning or robot control.
- The GPU host receives no robot-control credentials and cannot directly move
  the arm.

The worker accepts a fixed job type and fixed input filenames. It never accepts
an arbitrary image name, Docker image, shell command, or output path from the
client. Archives reject traversal paths, links, devices, excessive member
counts, and oversized files.

## 1. Prepare the GPU host

The GPU host needs:

1. NVIDIA driver, Docker Engine, and NVIDIA Container Toolkit.
2. A clone of this repository at an absolute path.
3. The vision container created by
   `scripts/create_a1z_vision_gpu_container.sh`.
4. Host-local, ignored deployment data:
   `config/a1z_vlm.env`, `vendor/vision/`, SAM/AnyGrasp checkpoints,
   AnyGrasp license, and `runtime/anygrasp/ifconfig.snapshot`.
5. OpenSSH listening on the private LAN or VPN address.

Optional worker timeouts, lock path, and stale-job retention can be set in the
ignored `config/remote_gpu_server.env`; the tracked
`config/remote_gpu_server.example.env` lists the settings.

The GPU host and laptop should run the same Git commit. Verify the worker
locally on the GPU host:

```bash
cd /absolute/path/to/A1Z
python3 scripts/a1z_remote_gpu_worker.py preflight
```

The preflight returns only readiness booleans, container name, CUDA device
count, and asset-presence flags. It does not return credentials, license
contents, or the machine fingerprint.

## 2. Authorize the laptop

Create a dedicated key on the laptop if necessary:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/a1z_gpu
ssh-copy-id -i ~/.ssh/a1z_gpu.pub GPU_USER@10.66.0.11
```

Keep the GPU host on a private LAN/VPN and disable password authentication
after public-key access has been verified. Do not publish SSH, Docker, Ray,
Jupyter, or model-service ports directly to the Internet.

For a dedicated worker key, the stronger `authorized_keys` form is:

```text
restrict,command="python3 /absolute/path/to/A1Z/scripts/a1z_remote_gpu_worker.py forced" ssh-ed25519 AAAA... laptop-a1z-gpu
```

`forced` mode parses `SSH_ORIGINAL_COMMAND` without evaluating a shell string
and permits only this repository's `preflight` and `run` modes. Use a separate,
unrestricted administrator key when an interactive GPU-host shell is needed.

## 3. Prepare the robot laptop

The laptop needs Linux, Docker Engine, Git, an SSH client, SocketCAN, the D405,
and USB/CAN access. It does **not** need an NVIDIA driver, CUDA, SAM, AnyGrasp,
model weights, or VLM credentials.

```bash
git clone git@github.com:TH1RT3EN-LI/A1Z-SDK.git
cd A1Z-SDK

# Builds the ROS 2/SDK image and creates the real container with USB/CAN access.
A1Z_PROFILE=real ./scripts/create_a1z_ros2_container.sh

# Read-only CAN, SDK, container, and D405 checks.
A1Z_PROFILE=real \
  ./scripts/verify_a1z_socketcan_preflight_in_container.sh
```

Configure `can0`, the D405 serial number, hand-eye calibration, safety limits,
and the physical control server as described in
[`REAL_HARDWARE.md`](REAL_HARDWARE.md). These are laptop/robot settings and are
not copied to the GPU host.

## 4. Configure the remote GPU endpoint

From the laptop clone:

```bash
./scripts/configure_remote_gpu_client.sh \
  --host 10.66.0.11 \
  --user GPU_USER \
  --remote-root /absolute/path/to/A1Z \
  --identity-file ~/.ssh/a1z_gpu

python3 scripts/run_remote_vision_job.py preflight
```

This writes `config/remote_gpu_client.env` with mode `0600`. The file is
ignored by Git because addresses, usernames, and key paths are deployment
settings. `config/remote_gpu_client.example.env` documents every setting.

`StrictHostKeyChecking=accept-new` is the bootstrap default: the first key is
stored, and later key changes fail. For a managed deployment, preload
`known_hosts` and set the value to `yes`.

## 5. Run the physical pipeline

Start the laptop-side control server and use the normal command:

```bash
python3 scripts/run_pick_pipeline.py \
  "pick up the red object" \
  --profile real \
  --output-dir runtime/pick_pipeline
```

The ignored client config selects `remote_ssh`. An explicit one-run override
is also available:

```bash
python3 scripts/run_pick_pipeline.py \
  "pick up the red object" \
  --profile real \
  --vision-backend remote_ssh
```

Inspect these laptop-local results before allowing motion:

```text
runtime/pick_pipeline/
├── capture/
├── target/
├── anygrasp/
├── remote_gpu/       transport, worker, VLM/SAM, and AnyGrasp logs
├── planning/
├── execution/
└── pipeline_manifest.json
```

For an already captured RGB-D frame, submit only the vision stages:

```bash
python3 scripts/run_remote_vision_job.py run \
  "pick up the red object" \
  --capture-dir runtime/pick_pipeline/capture \
  --output-dir runtime/remote_vision_test
```

## Migration and extension contract

The stable boundary is:

- request: instruction, provider, color image, RGB array, metric depth array,
  and camera intrinsics;
- response: target-selection artifacts, AnyGrasp artifacts, stage logs, status,
  and timing metadata;
- downstream: planning consumes only the laptop-local artifacts.

To migrate to a general GPU system, implement another transport beside
`a1z_ext.remote_gpu.ssh_client` and keep the request/response schema in
`a1z_ext.remote_gpu.protocol`. Robot acquisition, planning, execution, and
artifact storage do not need to move.

The licensed AnyGrasp SDK, model weights, VLM keys, and machine fingerprint
remain deployment data on the GPU server. They are intentionally absent from
GitHub and from every response archive.
