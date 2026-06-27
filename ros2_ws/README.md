# A1Z ROS 2 Workspace

This workspace is the independent ROS 2 integration layer for A1Z. It is meant
to run entirely in Docker, separate from the Isaac Sim process.

Recommended deployment:

1. Isaac container:
   - runs Isaac Sim
   - runs the in-process `a1z_ext` robot server
   - exposes the A1Z protocol over TCP
2. ROS container:
   - builds this `ros2_ws`
   - runs `a1z_motion`
   - optionally runs `a1z_d405` and `a1z_open_vocab`
   - connects to Isaac via `A1Z_TCP_HOST` / `A1Z_TCP_PORT`

Minimal build inside a ROS 2 Humble container:

```bash
cd /workspace/A1Z/ros2_ws
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
ros2 launch a1z_motion a1z_motion.launch.py
```

Optional VLM request bridge:

```bash
cd /workspace/A1Z/ros2_ws
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash

# GPT-compatible default
set -a
source /workspace/A1Z/config/a1z_vlm.env
set +a
ros2 launch a1z_open_vocab a1z_open_vocab.launch.py

# Or Kimi/Moonshot-compatible
set -a
source /workspace/A1Z/config/a1z_vlm.env
set +a
ros2 launch a1z_open_vocab a1z_open_vocab.launch.py llm_provider:=kimi
```

Once the VLM bridge has received a color image, trigger one request with:

```bash
ros2 service call /a1z/open_vocab/request_vlm std_srvs/srv/Trigger {}
```

Environment variables:

- `A1Z_CONTROL_URDF`
- `A1Z_SDK_DIR`
- `A1Z_TCP_HOST`
- `A1Z_TCP_PORT`
- `A1Z_WORLD_FRAME`
- `A1Z_ROBOT_BASE_FRAME`
- `A1Z_TOOL_FRAME`
- `OPENAI_API_KEY`
- `MOONSHOT_API_KEY`
