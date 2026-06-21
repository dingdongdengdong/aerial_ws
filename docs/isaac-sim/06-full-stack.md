# 06 — Full Stack Launch

> **Goal**: Launch the complete simulation stack in the correct order: PX4 SITL → MAVROS → autopilot nodes → Foxglove bridge → Isaac Sim (with drone spawn).

---

## Launch Order (Strict)

The stack has dependencies. Launch in this exact sequence:

```
1. PX4 SITL            ← Flight controller (auto-launched by Pegasus)
2. MAVROS              ← MAVLink ↔ ROS2 bridge
3. Autopilot Interface ← Takeoff/Land/Orbit action servers
4. Foxglove Bridge     ← Web visualization
5. Isaac Sim + Drone   ← 3D simulation and rendering
```

> **Why this order**: MAVROS can't connect until PX4 is running. Autopilot nodes need MAVROS topics. Foxglove needs data sources. Isaac Sim with Pegasus is the final piece that ties it all together.

---

## Step-by-Step Launch

### Terminal Setup

Open **5 terminal windows** (or use tmux panes). Every terminal needs:

```bash
export ROS_DOMAIN_ID=44
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
source /opt/ros/humble/setup.bash
source /workspace/aerial_ws/ros2_ws/install/setup.bash
```

### Terminal 1: Isaac Sim GUI (Always First)

The Isaac Sim GUI must be running before any `--exec` scripts are launched.

```bash
export DISPLAY=:1
export OMNI_KIT_ALLOW_ROOT=1

/workspace/isaacsim/isaac-sim.sh --allow-root \
  --ext-path /workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator \
  --enable pegasus.simulator \
  --/isaac/startup/ros_bridge_extension=isaacsim.ros2.bridge

# Wait for the GUI to fully load (view the VNC at :1 to confirm).
# You'll see the Isaac Sim main window with menus and viewport.
```

> **Verification**: VNC shows the Isaac Sim UI with File/Edit/Create menus and an empty 3D viewport.

### Terminal 2: Spawn Drone with PX4 Backend (--exec)

Once the GUI is ready, spawn the drone. This auto-launches PX4 SITL.

```bash
/workspace/isaacsim/isaac-sim.sh --allow-root \
  --exec /workspace/aerial_ws/scripts/spawn_drone_px4_exec.py
```

**What this does**:
- Enables `pegasus.simulator` and `isaacsim.ros2.bridge` extensions
- Initializes physics world
- Configures PX4MavlinkBackend with `px4_autolaunch: True, px4_dir: /workspace/PX4-Autopilot`
- Spawns Iris quadrotor with 640×640 20Hz downward camera
- PX4 SITL starts automatically, listening on UDP 14540

> **Verification**: Check the Isaac Sim Console (in the GUI) for:
> ```
> Pegasus AI — PX4 drone spawned!
>   PX4 SITL: auto-launched, MAVLink on UDP 14540
>   Camera:   /drone/inspection_camera/color/image_raw
> ```

### Terminal 3: MAVROS

```bash
export ROS_DOMAIN_ID=44
source /opt/ros/humble/setup.bash

ros2 run mavros mavros_node --ros-args \
  -p fcu_url:=udp://:14540@localhost:18570 \
  -p gcs_url:=udp://@localhost:14550
```

> **Verification**: After a few seconds, check:
> ```bash
> # In another terminal:
> ros2 topic echo /mavros/state --once
> # Expected output: connected: True, armed: False, mode: "MANUAL"
> ```

### Terminal 4: Autopilot Interface (Action Server)

```bash
export ROS_DOMAIN_ID=44
source /opt/ros/humble/setup.bash
source /workspace/aerial_ws/ros2_ws/install/setup.bash

ros2 run autopilot_interface px4_interface_node
```

This starts the action server that handles Takeoff, Land, Orbit, and Offboard actions.

> **Verification**:
> ```bash
> ros2 action list
> # Should show: /drone/takeoff, /drone/land, /drone/orbit, /drone/offboard
> ```

### Terminal 5: Foxglove Bridge (Optional)

```bash
export ROS_DOMAIN_ID=44
source /opt/ros/humble/setup.bash

ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765
```

Open browser at `http://localhost:8765` to view live telemetry.

> **Verification**: Foxglove UI shows topics like `/mavros/local_position/pose`, `/drone/inspection_camera/color/image_raw`, etc.

---

## All-in-One tmux Launch Script

For convenience, here's a script that launches everything in tmux windows:

```bash
#!/bin/bash
# File: /workspace/aerial_ws/scripts/launch_full_stack.sh
# Usage: bash launch_full_stack.sh

SESSION="pegasus-stack"
export ROS_DOMAIN_ID=44
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export LD_LIBRARY_PATH="/workspace/isaacsim/exts/isaacsim.ros2.bridge/humble/lib:$LD_LIBRARY_PATH"

# Create tmux session with 5 windows
tmux new-session -d -s "$SESSION" -n "isaac-gui"
tmux new-window -t "$SESSION" -n "drone"
tmux new-window -t "$SESSION" -n "mavros"
tmux new-window -t "$SESSION" -n "autopilot"
tmux new-window -t "$SESSION" -n "foxglove"

# Window 0: Isaac Sim GUI
tmux send-keys -t "$SESSION:0" \
  'export DISPLAY=:1 OMNI_KIT_ALLOW_ROOT=1' Enter
tmux send-keys -t "$SESSION:0" \
  '/workspace/isaacsim/isaac-sim.sh --allow-root --ext-path /workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator --enable pegasus.simulator --/isaac/startup/ros_bridge_extension=isaacsim.ros2.bridge' Enter

echo "Waiting for Isaac Sim GUI to start..."
sleep 30

# Window 1: Spawn drone
tmux send-keys -t "$SESSION:1" \
  '/workspace/isaacsim/isaac-sim.sh --allow-root --exec /workspace/aerial_ws/scripts/spawn_drone_px4_exec.py' Enter

sleep 10

# Window 2: MAVROS
tmux send-keys -t "$SESSION:2" \
  'source /opt/ros/humble/setup.bash' Enter
tmux send-keys -t "$SESSION:2" \
  'ros2 run mavros mavros_node --ros-args -p fcu_url:=udp://:14540@localhost:18570' Enter

sleep 5

# Window 3: Autopilot interface
tmux send-keys -t "$SESSION:3" \
  'source /opt/ros/humble/setup.bash && source /workspace/aerial_ws/ros2_ws/install/setup.bash' Enter
tmux send-keys -t "$SESSION:3" \
  'ros2 run autopilot_interface px4_interface_node' Enter

sleep 3

# Window 4: Foxglove bridge
tmux send-keys -t "$SESSION:4" \
  'source /opt/ros/humble/setup.bash' Enter
tmux send-keys -t "$SESSION:4" \
  'ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765' Enter

echo ""
echo "Full stack launched in tmux session '$SESSION'"
echo ""
echo "Windows:"
echo "  0: isaac-gui   — Isaac Sim GUI (VNC :1)"
echo "  1: drone       — Drone spawn (exec mode)"
echo "  2: mavros      — MAVROS bridge"
echo "  3: autopilot   — px4_interface action server"
echo "  4: foxglove    — Foxglove WebSocket bridge"
echo ""
echo "Attach: tmux attach -t $SESSION"
echo "Detach: Ctrl+B, D"
echo "Kill:   tmux kill-session -t $SESSION"
```

## Verification Checklist

After launching, run these checks in a new terminal:

```bash
export ROS_DOMAIN_ID=44
source /opt/ros/humble/setup.bash

# 1. Check MAVROS connection
ros2 topic echo /mavros/state --once 2>/dev/null | grep -E "connected|armed|mode"
# Expected: connected: True, armed: False, mode: "MANUAL"

# 2. Check ROS2 nodes
ros2 node list
# Should include: mavros, px4_interface_node, foxglove_bridge

# 3. Check topics
ros2 topic list | head -20
# Should include mavros/*, drone/* topics

# 4. Check camera data rate
ros2 topic hz /drone/inspection_camera/color/image_raw
# Expected: ~20 Hz

# 5. Check MAVROS position
ros2 topic echo /mavros/local_position/pose --once
# Should show position data (may be near 0,0,0.07 if just spawned)
```

---

## Test: Full Autonomous Flight Sequence

Once everything is running, test with an OFFBOARD takeoff:

```bash
export ROS_DOMAIN_ID=44
source /opt/ros/humble/setup.bash

# 1. Stream setpoints at 2m altitude
ros2 topic pub --rate 20 /mavros/setpoint_position/local geometry_msgs/msg/PoseStamped \
  "{header: {frame_id: 'map'}, pose: {position: {x: 0, y: 0, z: 2}, orientation: {w: 1.0}}}" &
PUB_PID=$!

sleep 3

# 2. OFFBOARD mode
ros2 service call /mavros/set_mode mavros_msgs/srv/SetMode "{custom_mode: 'OFFBOARD'}"

# 3. Arm
ros2 service call /mavros/cmd/arming mavros_msgs/srv/CommandBool "{value: true}"

# Drone should now takeoff to 2m altitude
# Watch in Isaac Sim viewport (VNC)

# 4. Land after 10 seconds
sleep 10
ros2 service call /mavros/cmd/land mavros_msgs/srv/CommandTOL \
  "{min_pitch: 0.0, yaw: 0.0, latitude: 0.0, longitude: 0.0, altitude: 0.0}"

# 5. Cleanup
kill $PUB_PID
```

## Common Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Starting Foxglove before MAVROS | Foxglove shows empty topic list | Launch in correct order; Foxglove discovers topics dynamically |
| MAVROS launched before PX4 SITL | HEARTBEAT timeout, no connection | Ensure PX4 is running (Pegasus backend auto-launches it) |
| `source /workspace/aerial_ws/ros2_ws/install/setup.bash` fails | `autopilot_interface` package not found | Run `colcon build` first in the ros2_ws |
| Forgetting ROS_DOMAIN_ID in one terminal | Topics invisible from that terminal | Set `export ROS_DOMAIN_ID=44` in ALL terminals |
| Isaac Sim not spawning drone | Extension path issues | Double-check `--ext-path` points to correct Pegasus location |
| Foxglove can't connect | Port already in use | Check `lsof -i :8765`, kill existing process |
| Drone appears but doesn't respond to commands | MAVROS not connected | Verify with `ros2 topic echo /mavros/state --once` |
| `ros2 topic pub` outputs nothing | Topic doesn't exist yet | Wait for MAVROS to connect and topics to appear (~5 seconds) |

## Quick Shutdown

```bash
# Kill all tmux sessions
tmux kill-session -t pegasus-stack

# Kill any remaining processes
pkill -f isaac-sim
pkill -f mavros_node
pkill -f px4_interface
pkill -f foxglove_bridge
pkill -f px4

# Kill VNC (if needed)
vncserver -kill :1
```

---

**Next**: [07-advanced-scenes.md](07-advanced-scenes.md) — Build complex USD scenes with SimReady assets.

## References

- PX4 SITL: https://docs.px4.io/main/en/simulation/
- MAVROS: https://github.com/mavlink/mavros
- Foxglove Bridge: https://github.com/foxglove/ros-foxglove-bridge
