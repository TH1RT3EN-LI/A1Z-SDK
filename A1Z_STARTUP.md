# A1Z startup

The repository has two explicit device profiles:

- `sim`: Isaac Sim arm and Isaac D405 adapter.
- `real`: SocketCAN arm and Intel RealSense D405.

Task logic is identical in both profiles. The physical profile is never
selected implicitly.

## Qt GUI Console

Start the console from the repository root:

```bash
./scripts/run_a1z_console.sh --profile sim
./scripts/run_a1z_console.sh --profile real
```

The first launch installs an isolated Qt/PySide runtime below
`runtime/a1z-console-python`. The GUI uses separate endpoints for simulation
(`37103`) and hardware (`37104`), verifies the reported backend before every
motion transaction, and never retries a motion request.

Run the read-only profile checks independently with:

```bash
python3 scripts/a1z_console_preflight.py --profile sim
python3 scripts/a1z_console_preflight.py --profile real
```

## Simulation

Start the existing Isaac application/control server, then:

```bash
cd /path/to/A1Z-SDK
A1Z_PROFILE=sim ./scripts/run_a1z_ros2_stack_in_container.sh start
python3 scripts/run_pick_pipeline.py --profile sim "抓取红色杯子"
```

Add `--execute --dry-run` to validate the execution stage without commands, or
`--execute` only after the plan has been reviewed.

## Physical robot

Run the read-only preflight first:

```bash
cd /path/to/A1Z-SDK
A1Z_PROFILE=real ./scripts/verify_a1z_socketcan_preflight_in_container.sh
```

Start the physical control server in a dedicated terminal:

```bash
A1Z_PROFILE=real ./scripts/a1zctl_in_container.sh serve
```

Then plan from live D405 data:

```bash
python3 scripts/run_pick_pipeline.py --profile real "抓取红色杯子"
```

To keep robot control on this laptop while offloading VLM/SAM/AnyGrasp to an
NVIDIA host, first follow [`docs/REMOTE_GPU.md`](docs/REMOTE_GPU.md); the
pipeline command remains the same.

The pipeline plans only by default. Use `--execute --dry-run` for a
non-actuating execution check. Use `--execute` only with the workspace clear,
an emergency stop available, and a human watching the arm.
