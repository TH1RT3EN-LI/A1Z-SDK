# A1Z startup

The repository has two explicit device profiles:

- `sim`: Isaac Sim arm and Isaac D405 adapter.
- `real`: SocketCAN arm and Intel RealSense D405.

Task logic is identical in both profiles. The physical profile is never
selected implicitly.

## Simulation

Start the existing Isaac application/control server, then:

```bash
cd /home/th1rt3en/dev/forge/A1Z
A1Z_PROFILE=sim ./scripts/run_a1z_ros2_stack_in_container.sh start
python3 scripts/run_pick_pipeline.py --profile sim "抓取红色杯子"
```

Add `--execute --dry-run` to validate the execution stage without commands, or
`--execute` only after the plan has been reviewed.

## Physical robot

Run the read-only preflight first:

```bash
cd /home/th1rt3en/dev/forge/A1Z
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

The pipeline plans only by default. Use `--execute --dry-run` for a
non-actuating execution check. Use `--execute` only with the workspace clear,
an emergency stop available, and a human watching the arm.
