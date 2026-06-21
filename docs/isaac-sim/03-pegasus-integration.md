# 03 — Pegasus Simulator Integration

> **Goal**: Understand Pegasus Simulator backends, connect PX4 SITL, configure MAVROS, and control drones via OFFBOARD mode.

---

## 1. Pegasus Simulator Architecture

Pegasus Simulator is an Isaac Sim extension that provides multirotor dynamics, sensors, and flight controller backends. It lives at:

```
/workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator/
```

### Three Backends

| Backend | Purpose | Protocol | When to Use |
|---|---|---|---|
| **PX4MavlinkBackend** | Flight control via PX4 SITL | MAVLink | Full autonomous flight with PX4 flight stack |
| **ArduPilotMavlinkBackend** | Flight control via ArduPilot SITL | MAVLink | ArduPilot-based vehicles |
| **ROS2Backend** | Sensor data to ROS2 topics | DDS (ROS2) | Publishing camera, IMU, pose data |

### The Dual Backend Pattern

Common pattern: use **PX4MavlinkBackend** for flight control AND **ROS2Backend** for sensor data:

```python
from pegasus.simulator.logic.backends.px4_mavlink_backend import (
    PX4MavlinkBackend, PX4MavlinkBackendConfig
)
from pegasus.simulator.logic.backends.ros2_backend import ROS2Backend

# Backend 1: PX4 for flight control
px4_backend = PX4MavlinkBackend(PX4MavlinkBackendConfig({
    "vehicle_id": 0,
    "px4_autolaunch": True,
    "px4_dir": "/workspace/PX4-Autopilot",
    "px4_vehicle_model": "gazebo-classic_iris",
}))

# Backend 2: ROS2 for sensor data
ros2_backend = ROS2Backend(
    vehicle_id=1,
    config={
        "namespace": "drone",
        "pub_sensors": False,
        "pub_graphical_sensors": True,
        "pub_state": False,
        "pub_tf": True,
        "sub_control": False,
    },
)

# Use both
config_mr.backends = [px4_backend, ros2_backend]
```

> **Why two backends**: PX4MavlinkBackend handles the MAVLink protocol (position control, arming, flight modes) while ROS2Backend exposes camera/IMU data as standard ROS2 topics. They serve different purposes and don't conflict.

## 2. PX4 MAVLink Port Table

PX4 SITL uses these UDP/TCP ports. Knowing them prevents hours of debugging.

| Port | Protocol | Name | Purpose |
|---|---|---|---|
| `4560` | TCP | HIL (Hardware-in-the-Loop) | Pegasus ↔ PX4 internal communication |
| `14540` | UDP | Standard MAVLink | Default MAVLink streaming (used by Pegasus backend) |
| `18570` | UDP | GCS (Ground Control Station) | **Connect MAVROS here** (QGC also connects here) |
| `14580` | UDP | Onboard companion link | For onboard computer (Raspberry Pi, Jetson) |
| `14280` | UDP | Low-rate telemetry | Low-bandwidth telemetry link |
| `13030` | UDP | Gimbal control | Camera gimbal commands |

> **CRITICAL**: MAVROS connects to `udp://:14540@localhost:18570` — the **GCS port (18570)**, NOT the onboard port (14580). Connecting to 14580 will give you "no heartbeat" errors.

## 3. MAVROS Connection

MAVROS bridges MAVLink to ROS2, exposing PX4 telemetry as ROS2 topics.

### Installation

```bash
sudo apt install ros-humble-mavros ros-humble-mavros-extras
```

### Connection Command (Correct)

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=44

ros2 run mavros mavros_node --ros-args \
  -p fcu_url:=udp://:14540@localhost:18570 \
  -p gcs_url:=udp://@localhost:14550
```

> **Explanation**: `udp://:14540@localhost:18570` means "bind to port 14540, connect to localhost:18570." Port 18570 is the PX4 GCS port.

### Verify MAVROS is working

```bash
# Check heartbeat / connection state
ros2 topic echo /mavros/state --once
# Expected: connected: True, armed: False, mode: "MANUAL"

# Check position data
ros2 topic echo /mavros/local_position/pose --once
# Expected: valid position data if drone is spawned
```

### Key MAVROS Topics

| Topic | Type | Content |
|---|---|---|
| `/mavros/state` | `mavros_msgs/State` | Connection state, armed, flight mode |
| `/mavros/local_position/pose` | `PoseStamped` | Local NED position |
| `/mavros/local_position/velocity_local` | `TwistStamped` | Velocity in NED |
| `/mavros/imu/data` | `Imu` | IMU readings |
| `/mavros/setpoint_position/local` | `PoseStamped` | **Send position setpoints** (OFFBOARD) |
| `/mavros/setpoint_raw/local` | `PositionTarget` | Raw setpoints (velocity, thrust, etc.) |
| `/mavros/cmd/arming` | `CommandBool` | Arm/disarm service |
| `/mavros/set_mode` | `SetMode` | Change flight mode service |

## 4. OFFBOARD Control via pymavlink

For direct python control without MAVROS:

### pymavlink 2.4+ API (CRITICAL)

The pymavlink API changed in version 2.4. In the old API, you called `mav.pack(msg)`. In 2.4+, you call **`msg.pack(mav)`** — the arguments are reversed!

```python
from pymavlink import mavutil

# Connect
mav = mavutil.mavlink_connection("udp:localhost:14540")

# Wait for heartbeat
mav.wait_heartbeat()
print("Heartbeat received!")

# Create a SET_POSITION_TARGET_LOCAL_NED message
msg = mav.mav.set_position_target_local_ned_encode(
    0,                          # time_boot_ms
    0, 0,                       # target system, target component
    mavutil.mavlink.MAV_FRAME_LOCAL_NED,  # frame
    0b0000111111111000,         # type_mask (position only)
    5.0, 2.0, -8.0,            # x, y, z (NED: north, east, down)
    0, 0, 0,                   # vx, vy, vz
    0, 0, 0,                   # afx, afy, afz
    0, 0                       # yaw, yaw_rate
)

# CORRECT for pymavlink 2.4+: msg.pack(mav)
msg.pack(mav)
mav.send(msg)

# WRONG (old API): mav.pack(msg)  ← will throw AttributeError!
```

### OFFBOARD Mode via pymavlink

```python
# Set OFFBOARD mode — custom_mode=6 for PX4!
# NOT 14 (that's for ArduPilot)
mav.mav.set_mode_send(
    mav.target_system,
    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
    6  # PX4 OFFBOARD main_mode
)

# Arm
mav.mav.command_long_send(
    mav.target_system,
    mav.target_component,
    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
    0,
    1, 0, 0, 0, 0, 0, 0  # 1 = arm
)
```

> **CRITICAL**: PX4 OFFBOARD custom_mode is **6**, not 14. Mode 14 is ArduPilot's GUIDED mode. Using 14 will fail silently on PX4.

### OFFBOARD via ROS2 Service (MAVROS)

```bash
# Set OFFBOARD mode
ros2 service call /mavros/set_mode mavros_msgs/srv/SetMode \
  "{custom_mode: 'OFFBOARD'}"

# Arm
ros2 service call /mavros/cmd/arming mavros_msgs/srv/CommandBool \
  "{value: true}"
```

## 5. Script Pattern: `--exec` Mode (No SimulationApp)

Scripts that run via `--exec` (inside an already-running Isaac Sim) must follow a specific async pattern:

```python
#!/usr/bin/env python3
"""
--exec script pattern for Pegasus + PX4.
NO SimulationApp() call — app is already running.
"""

import asyncio
import numpy as np
import carb
import omni.kit.app
from isaacsim.core.utils.extensions import enable_extension

# 1. Enable extensions
enable_extension("pegasus.simulator")
enable_extension("isaacsim.ros2.bridge")
omni.kit.app.get_app().update()

# 2. Import Pegasus modules AFTER extension is enabled
from pegasus.simulator.logic.interface.pegasus_interface import PegasusInterface
from pegasus.simulator.logic.vehicles.multirotor import Multirotor, MultirotorConfig
from pegasus.simulator.logic.backends.px4_mavlink_backend import (
    PX4MavlinkBackend, PX4MavlinkBackendConfig
)
from pegasus.simulator.logic.graphical_sensors.monocular_camera import MonocularCamera
from scipy.spatial.transform import Rotation

async def spawn_drone():
    """Async world initialization + drone spawn."""

    # 3. Initialize Pegasus world (async)
    pegasus_iface = PegasusInterface()
    pegasus_iface.initialize_world()
    world = pegasus_iface.world
    await world.initialize_simulation_context_async()
    await world.reset_async()

    # 4. Configure backends
    px4_config = PX4MavlinkBackendConfig({
        "vehicle_id": 0,
        "px4_autolaunch": True,
        "px4_dir": "/workspace/PX4-Autopilot",
        "px4_vehicle_model": "gazebo-classic_iris",
    })
    px4_backend = PX4MavlinkBackend(px4_config)

    # 5. Configure sensors
    config_mr = MultirotorConfig()
    config_mr.backends = [px4_backend]
    config_mr.graphical_sensors = [
        MonocularCamera(
            "inspection_camera",
            config={
                "depth": True,
                "position": np.array([0.10, 0.0, -0.15]),
                "orientation": np.array([0.0, 90.0, 0.0]),  # 90° pitch = down
                "resolution": (640, 640),
                "frequency": 20,
            },
        )
    ]

    # 6. Spawn the drone
    USD_FILE = (
        "/workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator"
        "/pegasus/simulator/assets/Robots/Iris/iris.usd"
    )
    Multirotor(
        "/World/quadrotor",
        USD_FILE,
        vehicle_id=0,
        init_pos=[0.0, 0.0, 0.07],
        init_orientation=Rotation.from_euler("XYZ", [0, 0, 0], degrees=True).as_quat(),
        config=config_mr,
    )

    await omni.kit.app.get_app().next_update_async()
    await world.reset_async()
    carb.log_info("Drone spawned! PX4 SITL running on UDP 14540")

# 7. Schedule the async function
asyncio.ensure_future(spawn_drone())
```

### Run it:

```bash
# After Isaac Sim GUI is open:
/workspace/isaacsim/isaac-sim.sh --allow-root \
  --exec /workspace/aerial_ws/scripts/spawn_drone_px4_exec.py
```

## 6. Standalone Script Pattern (`-p` flag, with SimulationApp)

For headless or standalone scripts that create their own simulation:

```python
#!/usr/bin/env python3
"""Standalone pattern with SimulationApp."""

from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})  # or False for GUI

from isaacsim.core.utils.extensions import enable_extension
enable_extension("pegasus.simulator")
# ... rest of imports and setup ...

# Main simulation loop
from omni.isaac.core import World
world = World()
world.reset()

# ... spawn drone, run simulation ...

while simulation_app.is_running():
    world.step(render=True)

simulation_app.close()
```

Run with:
```bash
/workspace/isaacsim/isaac-sim.sh --allow-root -p my_standalone_script.py
```

## 7. CRITICAL: ROS2Backend rclpy Conflict in `--exec` Mode

**Do NOT use ROS2Backend in `--exec` mode.** The ROS2Backend initializes `rclpy`, and `rclpy.init()` can only be called once per process. When Isaac Sim launches with the ROS2 Bridge extension, `rclpy` is already initialized. The ROS2Backend's attempt to `rclpy.init()` again causes a crash.

### Workaround: Use PX4MavlinkBackend + MAVROS

For `--exec` scripts, use only `PX4MavlinkBackend` and let MAVROS (running externally) handle the ROS2 integration:

```
Isaac Sim → PX4MavlinkBackend → MAVLink → PX4 SITL
                                            ↓
                                       MAVROS (external) → ROS2 topics
```

### When to use ROS2Backend

Only use ROS2Backend in **standalone scripts** (`-p` flag) where you control the entire `rclpy` lifecycle.

## 8. Setpoint-Before-Arm Requirement

PX4 requires that it receives OFFBOARD setpoints **before** you switch to OFFBOARD mode. If you switch to OFFBOARD and there are no setpoints, PX4 will immediately fall back to a failsafe mode (HOLD or LAND).

### Correct Order:

```python
# 1. Start streaming setpoints (at least 2Hz)
for i in range(50):  # Send for a few seconds
    send_setpoint(x=0, y=0, z=-5)
    time.sleep(0.05)

# 2. Request OFFBOARD mode
set_mode("OFFBOARD")

# 3. Arm
arm()

# 4. Continue streaming setpoints
while flying:
    send_setpoint(x, y, z)
    time.sleep(0.05)
```

### CLI version:

```bash
# 1. Stream setpoints in background
while true; do
  ros2 topic pub --once /mavros/setpoint_position/local geometry_msgs/msg/PoseStamped \
    "{header: {frame_id: 'map'}, pose: {position: {x: 0, y: 0, z: 5}}}"
  sleep 0.05
done &

# 2. Now switch to OFFBOARD
ros2 service call /mavros/set_mode mavros_msgs/srv/SetMode "{custom_mode: 'OFFBOARD'}"

# 3. Arm
ros2 service call /mavros/cmd/arming mavros_msgs/srv/CommandBool "{value: true}"
```

## 9. Complete Verification Sequence

```bash
# Terminal 1: Isaac Sim with drone
export DISPLAY=:1
export ROS_DOMAIN_ID=44
/workspace/isaacsim/isaac-sim.sh --allow-root \
  --ext-path .../pegasus.simulator --enable pegasus.simulator
# Wait for GUI, then:
/workspace/isaacsim/isaac-sim.sh --allow-root \
  --exec .../spawn_drone_px4_exec.py

# Terminal 2: MAVROS
export ROS_DOMAIN_ID=44
source /opt/ros/humble/setup.bash
ros2 run mavros mavros_node --ros-args \
  -p fcu_url:=udp://:14540@localhost:18570

# Terminal 3: Verify
export ROS_DOMAIN_ID=44
source /opt/ros/humble/setup.bash
ros2 topic echo /mavros/state --once
# Expected: connected: True
```

## 10. Common Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| MAVROS on port 14580 instead of 18570 | No heartbeat, connection failed | Use `udp://:14540@localhost:18570` |
| OFFBOARD custom_mode=14 | Mode switch fails or wrong behavior | Use `custom_mode=6` for PX4 OFFBOARD |
| `mav.pack(msg)` with pymavlink 2.4+ | `AttributeError: 'MAVLink' object has no attribute 'pack'` | Use `msg.pack(mav)` |
| ROS2Backend in `--exec` mode | `rclpy.init()` already called, crash | Use PX4MavlinkBackend only in `--exec` |
| Forgot setpoint-before-arm | Drone falls back to HOLD/LAND mode | Stream setpoints BEFORE arming |
| Missing `px4_autolaunch: True` | PX4 SITL not running, no heartbeat | Set `px4_autolaunch: True` in config |
| Wrong PX4 directory path | `FileNotFoundError` for PX4 binary | Set `px4_dir: "/workspace/PX4-Autopilot"` |

---

**Next**: [04-synthetic-data.md](04-synthetic-data.md) — Generate training data with Isaac Sim Replicator.

## References

- Pegasus Simulator Docs: https://pegasus-simulator.github.io/
- PX4 OFFBOARD Mode: https://docs.px4.io/main/en/flight_modes/offboard.html
- MAVROS: https://github.com/mavlink/mavros
- pymavlink: https://github.com/ArduPilot/pymavlink
