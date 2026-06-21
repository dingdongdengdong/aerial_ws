# 05 — Common Pitfalls & Error Reference

> **Goal**: A quick-reference table of every common error you'll encounter, with symptoms and fixes.

---

## Error Quick-Reference Table

| # | Error / Symptom | Root Cause | Fix |
|---|---|---|---|
| 1 | `AttributeError: 'NoneType' object has no attribute '_physx_interface'` | Physics context not initialized; trying to use physics before world is ready | Call `await world.initialize_simulation_context_async()` before any physics operations |
| 2 | `ImportError: cannot import name 'SimulationApp'` | Trying to use SimulationApp in a `--exec` script | Remove `from isaacsim import SimulationApp`; the app is already running. Use the async pattern instead |
| 3 | Topics visible but no data arrives | QoS mismatch — Pegasus publishes RELIABLE, subscriber uses BEST_EFFORT | Use `QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)` in subscriber |
| 4 | `AttributeError: 'MAVLink' object has no attribute 'pack'` | Using old pymavlink API `mav.pack(msg)` | Use `msg.pack(mav)` (pymavlink 2.4+ inverted the API) |
| 5 | MAVROS: no heartbeat / connection timeout | Wrong port — using 14580 instead of 18570 | Use `udp://:14540@localhost:18570` (GCS port, not onboard port) |
| 6 | PX4 OFFBOARD: fails to arm or falls back to HOLD | Wrong custom_mode value (14 instead of 6) | Use `custom_mode=6` for PX4 OFFBOARD. Mode 14 is ArduPilot GUIDED |
| 7 | `rclpy.init() called multiple times` crash | ROS2Backend used in `--exec` mode when ROS2 Bridge is already running | Do NOT use ROS2Backend in `--exec` scripts. Use PX4MavlinkBackend + external MAVROS |
| 8 | Isaac Sim freezes / hangs | Launched in background with `&` instead of tmux | Use `tmux new-session -d -s isaac-sim '...'` for background launches |
| 9 | `Symbol not found` / segfault at launch | LD_LIBRARY_PATH not pointing to Isaac Sim's internal ROS2 libs | Export `LD_LIBRARY_PATH=/workspace/isaacsim/exts/isaacsim.ros2.bridge/humble/lib:$LD_LIBRARY_PATH` |
| 10 | `ros2 topic list` shows different topics in different terminals | ROS_DOMAIN_ID mismatch between terminals | Set `export ROS_DOMAIN_ID=44` in EVERY terminal |
| 11 | PX4 setpoints ignored; drone won't move | Sending setpoint AFTER switching to OFFBOARD | Stream setpoints for 2+ seconds BEFORE switching to OFFBOARD mode |
| 12 | `FileNotFoundError: px4` | `px4_dir` path wrong or PX4 not compiled | Set `px4_dir: "/workspace/PX4-Autopilot"` and verify `make px4_sitl` completed |
| 13 | Isaac Sim hangs at "Loading shaders" | First launch — shader compilation (normal) | Wait 3–5 minutes. Subsequent launches are fast |
| 14 | `DISPLAY not set` or `cannot open display :1` | VNC not running on display :1 | `vncserver :1 -geometry 1920x1080 -depth 24` or `export DISPLAY=:0` |
| 15 | `GLXBadFBConfig` | VNC without GPU acceleration | Use VirtualGL or `Xvfb` for headless; or install TurboVNC + VirtualGL |
| 16 | Script runs but nothing happens in viewport | Simulation not playing; timeline stopped | Start the timeline: `.pg.timeline.play()` or click Play in the toolbar |
| 17 | `import pegasus.simulator` fails | Pegasus extension not enabled | `enable_extension("pegasus.simulator")` before importing pegasus modules |
| 18 | `Requested extension not found: pegasus.simulator` | Extension path not in search path | Add `--ext-path /workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator` to launch command |
| 19 | `carb.log_info` output not visible | Looking in wrong console; or log level too high | Check the Isaac Sim Console panel (Window > Console). Set log level to INFO |
| 20 | No camera topics after drone spawn | ROS2Backend not configured with `pub_graphical_sensors: True` | Set `"pub_graphical_sensors": True` in ROS2Backend config |
| 21 | Camera image is all black | Camera pointing wrong direction; scene too dark | Check camera orientation: `[0.0, 90.0, 0.0]` = pitch 90° down. Add lights to scene |
| 22 | `OmniGraph` errors in console | Extension dependencies not loaded | Enable `isaacsim.ros2.bridge` BEFORE `pegasus.simulator` |
| 23 | `PermissionError` running `.sh` file | File permissions | `chmod +x /workspace/isaacsim/isaac-sim.sh` |
| 24 | DDS discovery blocked by firewall | `ros2 topic list` empty even with correct setup | Check firewall: `sudo ufw status`. Ensure UDP multicast is allowed on loopback |
| 25 | Foxglove shows no data | Foxglove bridge launched WITHOUT ROS_DOMAIN_ID set | Launch Foxglove bridge with `export ROS_DOMAIN_ID=44` in the same terminal |

---

## Detailed Fixes for Top Pitfalls

### Pitfall 1: `AttributeError: '_physx_interface'`

**Full error**:
```
AttributeError: 'NoneType' object has no attribute '_physx_interface'
```

**When it happens**: Inside an `--exec` script, after creating a World but before initializing physics.

**Why**: The World object exists in the USD stage, but the physics simulation context hasn't been started.

**Fix — always use this pattern in `--exec` scripts**:
```python
async def setup():
    world = World()
    await world.initialize_simulation_context_async()  # ← REQUIRED
    await world.reset_async()                          # ← REQUIRED
    # Now safe to do physics
```

### Pitfall 2: `ImportError: SimulationApp`

**Full error**:
```
ImportError: cannot import name 'SimulationApp' from 'isaacsim'
```

**When it happens**: Running a standalone script (with `SimulationApp()`) via `--exec`.

**Why**: In `--exec` mode, Isaac Sim is **already running**. You cannot create another SimulationApp inside it.

**Fix**: Remove `from isaacsim import SimulationApp` and `simulation_app = SimulationApp(...)`. Use the async pattern with `asyncio.ensure_future()`.

### Pitfall 3: QoS Mismatch

**Symptom**: `ros2 topic list` shows the topic, `ros2 topic hz` shows 0 Hz, `ros2 topic echo` shows nothing.

**Why**: Pegasus publishes with **RELIABLE** QoS. Your subscriber defaults to **BEST_EFFORT**. The DDS layer silently rejects the incompatible subscription.

**Fix — in every ROS2 subscriber that reads Pegasus data**:
```python
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy

pegasus_qos = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,      # MUST match
    durability=DurabilityPolicy.VOLATILE,
    history=HistoryPolicy.KEEP_LAST,
)

self.subscription = self.create_subscription(
    Image,
    "/drone/inspection_camera/color/image_raw",
    self.callback,
    pegasus_qos,  # <-- explicit QoS
)
```

**Verification**:
```bash
ros2 topic info /drone/inspection_camera/color/image_raw --verbose | grep -i reliable
# Publisher: Reliability: RELIABLE ← must match
# Subscriber: Reliability: RELIABLE ← must match
```

### Pitfall 4: pymavlink pack() API

**Symptom**:
```
AttributeError: 'MAVLink' object has no attribute 'pack'
```

**Why**: pymavlink 2.4+ changed the API. `pack()` is now a method on the **message object**, not on the **mavlink connection**.

**Fix**:
```python
# ✗ WRONG (pymavlink < 2.4):
msg = mav.mav.set_mode_encode(...)
mav.pack(msg)       # AttributeError in 2.4+

# ✓ CORRECT (pymavlink 2.4+):
msg = mav.mav.set_mode_encode(...)
msg.pack(mav)       # pack() is on the message
mav.send(msg)
```

### Pitfall 5: MAVROS Port

**Symptom**: MAVROS logs "HEARTBEAT timeout" or never connects.

**Why**: Connecting to the wrong UDP port.

**Correct connection**:
```bash
ros2 run mavros mavros_node --ros-args \
  -p fcu_url:=udp://:14540@localhost:18570
  #                    ^^^^^               ← local bind port
  #                              ^^^^^     ← PX4 GCS port (NOT 14580!)
```

### Pitfall 6: OFFBOARD custom_mode

**Symptom**: Mode switch appears to succeed but drone behaves erratically or doesn't respond.

**Why**: Using `custom_mode=14` (ArduPilot GUIDED) instead of `custom_mode=6` (PX4 OFFBOARD).

**Fix**:
```python
# ✗ WRONG:
mav.mav.set_mode_send(
    target_system,
    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
    14  # ArduPilot GUIDED — won't work on PX4
)

# ✓ CORRECT:
mav.mav.set_mode_send(
    target_system,
    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
    6   # PX4 OFFBOARD
)
```

### Pitfall 7: ROS2Backend + `--exec` Conflict

**Symptom**:
```
RuntimeError: rclpy.init() has already been called
```

**Why**: Isaac Sim's ROS2 Bridge already calls `rclpy.init()`. The ROS2Backend also tries to call it. `rclpy.init()` can only be called once per process.

**Fix**: In `--exec` scripts, use **only PX4MavlinkBackend** (or ArduPilotMavlinkBackend). Let MAVROS handle the ROS2 publishing externally.

### Pitfall 11: Setpoint-Before-Arm

**Symptom**: Drone arms in OFFBOARD mode but immediately falls or switches to HOLD mode.

**Why**: PX4 must receive valid OFFBOARD setpoints at >2Hz **before** you switch to OFFBOARD mode. Otherwise it triggers a failsafe.

**Correct sequence**:
```
1. Start streaming setpoints (>2Hz, ≥2 seconds)
2. Request OFFBOARD mode
3. Arm
4. Continue streaming setpoints
```

```bash
# Correct CLI flow:
# Step 1: Stream setpoints
ros2 topic pub --rate 20 /mavros/setpoint_position/local geometry_msgs/msg/PoseStamped \
  "{header: {frame_id: 'map'}, pose: {position: {x: 0, y: 0, z: 5}, orientation: {w: 1}}}"

# Wait 2-3 seconds in ANOTHER terminal, then:
# Step 2: OFFBOARD
ros2 service call /mavros/set_mode mavros_msgs/srv/SetMode "{custom_mode: 'OFFBOARD'}"

# Step 3: Arm
ros2 service call /mavros/cmd/arming mavros_msgs/srv/CommandBool "{value: true}"
```

### Pitfall 8: tmux vs Background Terminal

**Symptom**: Isaac Sim launched with `&` freezes or stdout/stderr is lost.

**Why**: Isaac Sim requires a PTY (pseudo-terminal) for its console output. Shell backgrounding (`&`) detaches the PTY and Kit freezes.

**Fix — always use tmux for background Isaac Sim**:
```bash
# Start Isaac Sim in a detached tmux session
tmux new-session -d -s isaac-sim \
  '/workspace/isaacsim/isaac-sim.sh --allow-root --ext-path ...'

# Check it's running
tmux capture-pane -t isaac-sim -p | tail -20

# Attach to see console
tmux attach -t isaac-sim

# Detach: Ctrl+B, then D

# Kill
tmux kill-session -t isaac-sim
```

---

## Quick Diagnostic Commands

```bash
# Is Isaac Sim running?
ps aux | grep isaac-sim | grep -v grep

# What ROS2 topics exist?
export ROS_DOMAIN_ID=44
ros2 topic list

# Is MAVROS connected?
ros2 topic echo /mavros/state --once 2>/dev/null | grep connected

# Are we getting camera data?
ros2 topic hz /drone/inspection_camera/color/image_raw

# What's on the console?
tail -100 /tmp/isaac_sim_output.log  # if you log to file

# Check DDS discovery
ros2 doctor --report
```

---

**Next**: [06-full-stack.md](06-full-stack.md) — Launch the complete simulation in the correct order.
