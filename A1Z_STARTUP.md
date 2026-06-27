cd /home/th1rt3en/dev/forge/A1Z
./scripts/open_a1z_webrtc_host.sh --restart --no-client

---


cd /home/th1rt3en/dev/forge/A1Z
A1Z_TCP_HOST=127.0.0.1 ./scripts/run_a1z_ros2_motion_in_container.sh


---


cd /home/th1rt3en/dev/forge/A1Z

./scripts/stop_a1z_webrtc_streaming_host.sh || true

docker exec a1z-ros2-humble bash -lc '
set +e
for pattern in \
  "/opt/ros/humble/bin/ros2 launch a1z_motion a1z_motion.launch.py" \
  "/workspace/A1Z/ros2_ws/install/a1z_d405/lib/a1z_d405/d405_bridge" \
  "/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/robot_state" \
  "/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/motion_executor" \
  "/workspace/A1Z/ros2_ws/install/a1z_open_vocab/lib/a1z_open_vocab/vision_request"
do
  ps -eo pid=,args= | grep -F "$pattern" | grep -v grep | awk "{print \$1}" | xargs -r kill
done

sleep 2

for pattern in \
  "/opt/ros/humble/bin/ros2 launch a1z_motion a1z_motion.launch.py" \
  "/workspace/A1Z/ros2_ws/install/a1z_d405/lib/a1z_d405/d405_bridge" \
  "/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/robot_state" \
  "/workspace/A1Z/ros2_ws/install/a1z_motion/lib/a1z_motion/motion_executor" \
  "/workspace/A1Z/ros2_ws/install/a1z_open_vocab/lib/a1z_open_vocab/vision_request"
do
  ps -eo pid=,args= | grep -F "$pattern" | grep -v grep | awk "{print \$1}" | xargs -r kill -9
done

pkill -f "ros2 daemon" 2>/dev/null || true
' || true

docker stop a1z-ros2-humble gracious_fermi isaac-sim-5-1-dev || true