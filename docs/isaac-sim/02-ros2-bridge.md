# 02 — ROS2 Bridge

> **Goal**: Understand and use Isaac Sim's built-in ROS2 Bridge to publish sensor data and exchange messages with the ROS2 ecosystem.

---

## 1. How the Bridge Works

Isaac Sim 5.1 ships with a **built-in ROS2 Humble distribution** located at:

```
/workspace/isaacsim/exts/isaacsim.ros2.bridge/humble/lib/
```

This is a **self-contained copy** of ROS2 Humble libraries. It is NOT the same as your system ROS2 at `/opt/ros/humble/`. The bridge extension (`isaacsim.ros2.bridge`) uses these internal libraries to create ROS2 publishers, subscribers, and services directly from within the Isaac Sim process.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                  Isaac Sim Process                       │
│  ┌─────────────────────────────────────────────────┐    │
│  │  isaacsim.ros2.bridge Extension                 │    │
│  │  ┌──────────────┐  ┌────────────────────────┐  │    │
│  │  │ ROS2 Node    │  │ Pegasus Simulator       │  │    │
│  │  │ (publishers) │←─│ (camera, IMU, odometry) │  │    │
│  │  └──────┬───────┘  └────────────────────────┘  │    │
│  └─────────┼──────────────────────────────────────┘    │
│            │ DDS (FastRTPS)                              │
│            │ Domain ID: 44                               │
└────────────┼───────────────────────────────────────────┘
             │
      ┌──────┴──────┐
      │  ROS2 Network│
      │  (other nodes)│
      │  MAVROS      │
      │  Foxglove    │
      │  Your nodes  │
      └─────────────┘
```

> **Key insight**: There is only ONE DDS participant. Isaac Sim's internal ROS2 libraries and your system ROS2 nodes must agree on `ROS_DOMAIN_ID` and `RMW_IMPLEMENTATION`. The bridge doesn't "translate" between two ROS2 instances — it runs ROS2 natively inside Isaac Sim.

## 2. Required Environment Variables

**These MUST be set before launching Isaac Sim** in every terminal that will interact with ROS2:

```bash
export ROS_DOMAIN_ID=44
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export LD_LIBRARY_PATH=/workspace/isaacsim/exts/isaacsim.ros2.bridge/humble/lib:$LD_LIBRARY_PATH
```

### Why Each Matters

| Variable | Value | Explanation |
|---|---|---|
| `ROS_DOMAIN_ID` | `44` | All DDS participants must use the same domain ID. We use 44 to isolate from default domain 0 and any other projects. Mismatched domain IDs = silent failure (topics invisible). |
| `RMW_IMPLEMENTATION` | `rmw_fastrtps_cpp` | The RMW (ROS Middleware) layer. Isaac Sim's internal libs are compiled for FastRTPS. CycloneDDS may work but is untested. |
| `LD_LIBRARY_PATH` | `...humble/lib` | **Critical**: Isaac Sim's internal ROS2 libraries MUST be found before system ones. Without this, you'll get ABI mismatches and segfaults. |

> **Pitfall**: If `LD_LIBRARY_PATH` is not set, Isaac Sim will load your system ROS2 libs instead of its own. This causes `Symbol not found` errors because the ABI doesn't match.

## 3. Enabling the ROS2 Bridge

### Method A: Launch Flag (Recommended)

```bash
/workspace/isaacsim/isaac-sim.sh --allow-root \
  --/isaac/startup/ros_bridge_extension=isaacsim.ros2.bridge \
  --ext-path /workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator \
  --enable pegasus.simulator
```

The `--/isaac/startup/ros_bridge_extension=isaacsim.ros2.bridge` tells the Kit startup system to enable the ROS2 bridge during initialization.

### Method B: Via Python (in --exec script)

```python
from isaacsim.core.utils.extensions import enable_extension
enable_extension("isaacsim.ros2.bridge")
```

Call this at the top of your `--exec` scripts after the GUI is already running.

### Method C: Via Script Editor

In the Isaac Sim GUI:
1. `Window > Script Editor`
2. Run:
```python
import omni.kit.app
from isaacsim.core.utils.extensions import enable_extension
enable_extension("isaacsim.ros2.bridge")
```

### Verify the Bridge is Active

After enabling, run in any terminal:
```bash
export ROS_DOMAIN_ID=44
ros2 topic list
# Should show topics if Pegasus is publishing
```

## 4. CRITICAL: QoS Mismatch

This is the **#1 cause of "topics exist but no data arrives."**

### The Problem
Pegasus Simulator publishes camera images with **RELIABLE** QoS. Most ROS2 subscribers default to **BEST_EFFORT** for sensor data. When publisher and subscriber QoS don't match, the subscription succeeds but **no data is delivered**.

### The Fix

Your subscriber node MUST declare RELIABLE QoS:

```python
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

# Correct: Match Pegasus RELIABLE QoS
reliable_qos = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.VOLATILE,
)

self.subscription = self.create_subscription(
    Image,
    "/drone/inspection_camera/color/image_raw",
    self.image_callback,
    reliable_qos,  # <-- MUST be RELIABLE
)
```

### ROS2 CLI verification

```bash
# Check what QoS a publisher is using
ros2 topic info /drone/inspection_camera/color/image_raw --verbose
# Look for "Reliability: RELIABLE" in the output

# If you see BEST_EFFORT on your subscriber, it won't receive data
```

### Common Mistake: Python rclpy Default

```python
# WRONG: Default QoS is BEST_EFFORT for sensor messages
self.subscription = self.create_subscription(
    Image, "/drone/inspection_camera/color/image_raw", self.callback, 10
)

# RIGHT: Explicit RELIABLE QoS
from rclpy.qos import QoSProfile, ReliabilityPolicy
qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
self.subscription = self.create_subscription(
    Image, "/drone/inspection_camera/color/image_raw", self.callback, qos
)
```

## 5. Verification Commands

### Complete Bridge Test

```bash
# Terminal 1: Set env and start Isaac Sim with ROS2 bridge
export ROS_DOMAIN_ID=44
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export LD_LIBRARY_PATH=/workspace/isaacsim/exts/isaacsim.ros2.bridge/humble/lib:$LD_LIBRARY_PATH
export DISPLAY=:1

/workspace/isaacsim/isaac-sim.sh --allow-root \
  --/isaac/startup/ros_bridge_extension=isaacsim.ros2.bridge \
  --ext-path /workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator \
  --enable pegasus.simulator

# Terminal 2: After Isaac Sim is up, spawn drone
/workspace/isaacsim/isaac-sim.sh --allow-root \
  --exec /workspace/aerial_ws/scripts/spawn_drone_px4_exec.py

# Terminal 3: Check topics (must set same env vars!)
export ROS_DOMAIN_ID=44
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
source /opt/ros/humble/setup.bash

ros2 topic list
# Expected: /drone/inspection_camera/color/image_raw, etc.

ros2 topic hz /drone/inspection_camera/color/image_raw
# Expected: ~20 Hz

ros2 topic echo /drone/inspection_camera/color/image_raw --once
# Should show image header data
```

## 6. Foxglove Bridge Setup

Foxglove provides a web-based visualization tool. We use `foxglove_bridge` to expose ROS2 topics via WebSocket.

```bash
# Install
sudo apt install ros-humble-foxglove-bridge

# Launch
export ROS_DOMAIN_ID=44
source /opt/ros/humble/setup.bash
ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765
```

Then open a browser to `http://localhost:8765` (or use Foxglove desktop app) and connect to `ws://localhost:8765`.

### Expected Topics in Foxglove

| Topic | Type | Rate |
|---|---|---|
| `/drone/inspection_camera/color/image_raw` | `sensor_msgs/Image` | ~20 Hz |
| `/drone/inspection_camera/depth` | `sensor_msgs/Image` | ~20 Hz |
| `/drone/inspection_camera/color/camera_info` | `sensor_msgs/CameraInfo` | ~20 Hz |
| `/drone/tf` | `tf2_msgs/TFMessage` | ~30 Hz |
| `/pegasus/state/pose` | `geometry_msgs/PoseStamped` | ~30 Hz |
| `/mavros/state` | `mavros_msgs/State` | ~10 Hz |
| `/mavros/local_position/pose` | `geometry_msgs/PoseStamped` | ~30 Hz |

## 7. Common Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| `ROS_DOMAIN_ID` not set or mismatched | `ros2 topic list` shows different topics | Set `ROS_DOMAIN_ID=44` in all terminals |
| Missing `LD_LIBRARY_PATH` | Segfault or "symbol not found" at launch | Add the `humble/lib` path |
| `RMW_IMPLEMENTATION` mismatch | Nodes can't communicate even on same domain | Use `rmw_fastrtps_cpp` everywhere |
| BEST_EFFORT subscriber with RELIABLE publisher | No data received | Set RELIABLE QoS explicitly |
| Forgot to source ROS2 | `ros2: command not found` | `source /opt/ros/humble/setup.bash` |
| Bridge not enabled | No topics appear | Use `--/isaac/startup/ros_bridge_extension=...` flag or enable in script |
| Multiple ROS2 installations conflict | DDS discovery loops | Use unique `ROS_DOMAIN_ID=44` |

## 8. Topic Namespace Reference

### Using Pegasus ROS2Backend

```
/drone/inspection_camera/color/image_raw      # RGB image
/drone/inspection_camera/depth                 # Depth map
/drone/inspection_camera/color/camera_info     # Intrinsics
/drone/tf                                      # Transforms
/drone/state/pose                              # Drone pose
/drone/state/twist                             # Velocity
/drone/sensors/imu                             # IMU data
```

### Custom Namespace Example

```python
ROS2Backend(
    vehicle_id=1,
    config={
        "namespace": "pegasus",
        "pub_sensors": True,
        "pub_graphical_sensors": True,
        "pub_state": True,
        "pub_tf": True,
        "sub_control": True,
    },
)
# Topics become: /pegasus/state/pose, /pegasus/tf, etc.
```

---

**Next**: [03-pegasus-integration.md](03-pegasus-integration.md) — Connect PX4 and Pegasus backends.

## References

- ROS2 Bridge Docs: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/ros2_bridge.html
- FastRTPS QoS Profiles: https://fast-dds.docs.eprosima.com/en/latest/
- Foxglove Bridge: https://github.com/foxglove/ros-foxglove-bridge
