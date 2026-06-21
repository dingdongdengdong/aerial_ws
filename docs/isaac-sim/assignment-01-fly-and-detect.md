# Assignment: Isaac Sim + ROS2 + AI Pipeline

> **Target audience**: New Isaac Sim users who have read the learning guide.
> **Prerequisites**: Complete `docs/isaac-sim/01-getting-started.md` through `03-pegasus-integration.md`.
> **Estimated time**: 4–6 hours (if the stack is already running), 1–2 days (with setup).

---

## Overview

You will build an end-to-end pipeline: **fly a simulated drone from Foxglove, run YOLO inference on its camera feed, and see AI detections back in Isaac Sim**. Along the way you'll understand exactly how data flows between simulation, ROS2, and AI nodes.

```
┌──────────────┐     /cmd_vel      ┌──────────┐     MAVLink      ┌────────────┐
│  Foxglove    │ ──────────────────▶│  MAVROS  │ ────────────────▶│  PX4 SITL  │
│  (teleop)    │                   │          │                  │  (control) │
└──────────────┘                   └──────────┘                  └─────┬──────┘
                                                                      │
                                                               physics sim
                                                                      │
┌──────────────┐  /camera/image_raw  ┌────────────────────────────┐   │
│  Isaac Sim   │ ◀────────────────── │  /pegasus0/camera/color/   │ ◀─┘
│  (labels)    │                     │  image_raw (RELIABLE QoS)  │
└──────┬───────┘                     └───────────┬────────────────┘
       │                                         │
       │  /pegasus/ai/defect_json                │
       │                                         │
┌──────▼───────┐                     ┌───────────▼────────────────┐
│  Foxglove    │ ◀────────────────── │  pegasus_ai (YOLO+ONNX)   │
│  (detections)│                     │  inference_node           │
└──────────────┘                     └────────────────────────────┘
```

---

## Pre-Assignment Checklist

Before starting, verify:

```bash
# 1. ROS2 Humble sourced
source /opt/ros/humble/setup.bash
echo $ROS_DISTRO  # must say "humble"

# 2. ROS_DOMAIN_ID set (must match in every terminal)
export ROS_DOMAIN_ID=44
echo $ROS_DOMAIN_ID  # must say "44"

# 3. PX4 SITL builds
cd /workspace/PX4-Autopilot && ls build/px4_sitl_default/bin/px4
# File must exist

# 4. Isaac Sim present
ls /workspace/isaacsim/isaac-sim.sh
# File must exist

# 5. Pegasus Simulator present
ls /workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator/
# Directory must exist

# 6. ROS2 workspace built
cd /workspace/aerial_ws/ros2_ws && ls install/setup.bash
# File must exist

# 7. Foxglove bridge installed
ros2 pkg list | grep foxglove_bridge
# Must show foxglove_bridge

# 8. VNC running (for Isaac Sim GUI)
ps aux | grep Xtightvnc | grep -v grep
# Must show Xtightvnc on :1
```

If any check fails, fix it before continuing. The learning guide covers all of these.

---

## Task 1: Fly the Drone from Foxglove (2 hours)

**Goal**: Control a simulated drone by publishing velocity commands from Foxglove Studio.

### 1.1 Launch the Stack

Open **5 terminals** (or tmux panes). In each, first run:
```bash
source /opt/ros/humble/setup.bash
source /workspace/aerial_ws/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=44
```

**Terminal 1 — PX4 SITL:**
```bash
cd /workspace/PX4-Autopilot
make px4_sitl none
```
Wait until you see `PX4 SIM HITL initializing...` and `NuttShell (NSH)`.

**Terminal 2 — MAVROS:**
```bash
ros2 run mavros mavros_node --ros-args \
  -p fcu_url:=udp://:14540@localhost:18570 \
  -p gcs_url:=udp://@localhost:14550
```
Verify: `ros2 topic list | grep mavros/state` — must show topic.

**Terminal 3 — Foxglove Bridge:**
```bash
ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765 use_sim_time:=true
```

**Terminal 4 — Isaac Sim with Pegasus:**
```bash
export OMNI_KIT_ALLOW_ROOT=1 DISPLAY=:1
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export LD_LIBRARY_PATH=/workspace/isaacsim/exts/isaacsim.ros2.bridge/humble/lib
/workspace/isaacsim/isaac-sim.sh --allow-root \
  --ext-path /workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator \
  --enable pegasus.simulator \
  --/isaac/startup/ros_bridge_extension=isaacsim.ros2.bridge \
  --exec /workspace/aerial_ws/scripts/spawn_drone_px4_exec.py
```
Wait for `Isaac Sim Full App is loaded.` and the drone to appear in the viewport.

**Terminal 5 — Verify:**
```bash
ros2 topic list | wc -l
```
Should show **160+ topics**.

### 1.2 Open Foxglove Studio

1. Go to https://studio.foxglove.dev/
2. Click "Open Connection"
3. Enter `ws://localhost:8765`
4. In the Layout panel, add a **3D panel** and a **Raw Messages panel**

### 1.3 Arm and Take Off via MAVROS

In **Terminal 5**, arm the drone:
```bash
# Arm
ros2 service call /mavros/cmd/arming mavros_msgs/srv/CommandBool "{value: true}"

# Set OFFBOARD mode
ros2 service call /mavros/set_mode mavros_msgs/srv/SetMode "{base_mode: 0, custom_mode: 'OFFBOARD'}"

# Take off to 10m — stream position setpoints
ros2 topic pub -r 20 /mavros/setpoint_position/local geometry_msgs/msg/PoseStamped '{
  header: {frame_id: "map"},
  pose: {
    position: {x: 0.0, y: 0.0, z: 10.0},
    orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
  }
}'
```

> **Troubleshooting**: If the drone doesn't arm or falls back to HOLD mode, check `docs/isaac-sim/05-pitfalls.md` — entries 6, 11, and 29. OFFBOARD requires setpoints flowing BEFORE mode change.

### 1.4 Fly with Foxglove Velocity Commands

Now use Foxglove to publish velocity commands:

1. In Foxglove Studio, go to the **Publish** panel (top bar)
2. Topic: `/mavros/setpoint_velocity/cmd_vel_unstamped`
3. Message type: `geometry_msgs/msg/Twist`
4. Set values and click **Publish**:
   ```json
   {
     "linear":  {"x": 2.0, "y": 0.0, "z": 0.0},
     "angular": {"x": 0.0, "y": 0.0, "z": 0.0}
   }
   ```
   This moves the drone forward at 2 m/s. Try:
   - Positive Y → strafe right
   - Positive Z → climb (with negative Z for descend)
   - Angular Z → yaw rotation

5. Watch the 3D panel in Foxglove — the drone should move.
6. Switch to the Isaac Sim VNC view (port 5900) — the drone moves in 3D.

### ✅ Task 1 Deliverable

Screenshot showing:
- Foxglove Studio **Raw Messages** panel with `/mavros/local_position/pose` (showing non-zero position)
- Isaac Sim VNC viewport with the drone at a different position than spawn

Command to screenshot:
```bash
DISPLAY=:1 python3 -c "
from mss import MSS as mss
with mss(display=':1') as sct:
    sct.shot(output='/tmp/task1_isaac_sim.png')
print('Saved to /tmp/task1_isaac_sim.png')
"
```

---

## Task 2: YOLO Detection Pipeline — Camera → Inference → Labels (2 hours)

**Goal**: Run YOLO on the drone's camera feed and publish detection labels back to ROS2 (visible in Foxglove).

### 2.1 Understand the Data Flow

```
Isaac Sim (Pegasus camera) ──→ /pegasus0/inspection_camera/color/image_raw
                                   │ (RELIABLE QoS, 640x640, 20Hz)
                                   ▼
                           pegasus_ai inference_node (YOLO ONNX)
                                   │
                                   ▼
                           /pegasus/ai/defect_json (std_msgs/String)
                                   │
                                   ▼
                           Foxglove Studio (Raw Messages / Plot)
```

### 2.2 Verify the Camera Feed

In Terminal 5:
```bash
# Check camera topic exists
ros2 topic info /pegasus0/inspection_camera/color/image_raw --verbose

# Check frame rate
ros2 topic hz /pegasus0/inspection_camera/color/image_raw
# Should show ~20 Hz

# View a single frame (save to file)
ros2 run image_tools showimage --ros-args -r image:=/pegasus0/inspection_camera/color/image_raw
```

### 2.3 Launch the AI Inference Node

In a new terminal (Terminal 6):
```bash
source /opt/ros/humble/setup.bash
source /workspace/aerial_ws/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=44

# Check what inference nodes are available
ros2 pkg executables pegasus_ai

# Launch inference (adjust executable name based on what exists)
ros2 run pegasus_ai inference_node
```

> **If the node doesn't start**: Check `ros2_ws/src/pegasus_ai/pegasus_ai/` for the actual node name. The entry point is defined in `setup.py`.

### 2.4 Verify Detections

```bash
# Check detection topic
ros2 topic echo /pegasus/ai/defect_json
```

Expected output:
```json
{"frame": 42, "detections": [{"class": "crack", "confidence": 0.87, "bbox": [120, 80, 300, 200]}]}
```

### 2.5 Visualize in Foxglove

1. In Foxglove Studio, add a **Raw Messages** panel
2. Subscribe to `/pegasus/ai/defect_json`
3. Add a **3D panel** — enable `/pegasus0/state/pose` to track drone position
4. Add an **Image panel** — subscribe to `/pegasus0/inspection_camera/color/image_raw`

You should see:
- Live camera feed in the Image panel
- Detection JSON updates in Raw Messages (every frame where defects are found)

### ✅ Task 2 Deliverable

Screenshot showing:
- Foxglove with **Image panel** (camera feed) AND **Raw Messages** (detection JSON)
- At least one detection with confidence > 0.5

---

## Task 3: Trace the Full Connection — Sim ↔ ROS2 ↔ AI (1–2 hours)

**Goal**: Map every connection between Isaac Sim, ROS2, and the AI pipeline. Answer: how does a pixel in Isaac Sim become a detection label in Foxglove?

### 3.1 Topic Map

Draw (or list) every ROS2 topic in the system and which node publishes/subscribes to it. Use `ros2 topic info -v` on each:

```bash
# Run these and fill in the table
ros2 topic info /pegasus0/inspection_camera/color/image_raw -v
ros2 topic info /pegasus/ai/defect_json -v
ros2 topic info /mavros/setpoint_velocity/cmd_vel_unstamped -v
ros2 topic info /mavros/local_position/pose -v
ros2 topic info /mavros/state -v
```

### 3.2 Node Graph

Generate the ROS2 node graph:
```bash
ros2 run rqt_graph rqt_graph
# OR for text output:
rqt_graph  # if GUI available
```

Or programmatically:
```bash
# List all nodes
ros2 node list

# Show info for each node
for node in $(ros2 node list); do
  echo "=== $node ==="
  ros2 node info $node
  echo
done
```

### 3.3 Data Flow Questions

Answer these in your own words:

1. **Camera path**: How does an image get from Isaac Sim's 3D viewport to the YOLO inference node? What's the QoS, resolution, and topic name?

2. **Control path**: When you publish `/cmd_vel` from Foxglove, what transforms it into motor commands? List every node and topic in the chain.

3. **Detection path**: After YOLO finds a crack, what topic does it publish on? What format is the message? How would you add bounding box visualization?

4. **QoS trap**: Why does `ros2 topic echo` sometimes show the camera topic but receive no data? (Hint: read `docs/isaac-sim/02-ros2-bridge.md` and `05-pitfalls.md`)

5. **Namespace**: Why are Pegasus topics prefixed with `/pegasus0/` but MAVROS topics with `/mavros/`? What happens when you add a second drone (vehicle_id=1)?

### ✅ Task 3 Deliverable

A short markdown file (or comment on the GitHub issue) answering the 5 questions above, plus:
- The topic/node table from 3.1
- A text diagram showing data flow from Isaac Sim → ROS2 → Foxglove

---

## Grading Rubric

| Criterion | Points | Evidence |
|-----------|--------|----------|
| **Task 1**: Drone moves via Foxglove | 3 | Screenshot of non-zero position + Isaac Sim viewport |
| **Task 1**: Correct `/cmd_vel` topic used | 1 | Raw Messages shows Twist on correct topic |
| **Task 2**: Camera feed visible | 2 | Foxglove Image panel shows live feed |
| **Task 2**: YOLO detections published | 3 | Raw Messages shows detection JSON with confidence |
| **Task 2**: Detection labels in Foxglove | 1 | Both Image + Raw Messages panels in one screenshot |
| **Task 3**: Complete topic map | 2 | Table with publisher/subscriber for ≥5 topics |
| **Task 3**: 5 questions answered correctly | 3 | Clear, technically accurate answers |
| **Task 3**: Data flow diagram | 2 | Text or ascii diagram showing the full chain |
| **Bonus**: Bounding box overlay in Foxglove | +2 | Image panel showing detections drawn on camera feed |
| **Bonus**: Second drone spawned | +2 | Two drones (/pegasus0/, /pegasus1/) both publishing |
| **Total** | **17 + 4 bonus** | |

---

## Troubleshooting Quick Reference

| Problem | Check |
|---------|-------|
| 0 topics in `ros2 topic list` | `echo $ROS_DOMAIN_ID` — must be 44 everywhere |
| Camera topic exists but no images | QoS mismatch — subscriber must use RELIABLE |
| Drone won't arm | OFFBOARD mode needs setpoint stream before arming |
| `rclpy init` crash | Isaac Sim internal rclpy vs system rclpy conflict (normal in --exec) |
| Foxglove shows empty canvas | Launch data sources (PX4/MAVROS) BEFORE Foxglove bridge |
| Isaac Sim stuck at 0% CPU | Use tmux, not `&` background |
| `Isaac Sim Full App is loaded` never appears | Wait 3–5 min for first launch (shader compilation) |

Full error reference: `docs/isaac-sim/05-pitfalls.md`

---

## Submission

When done, comment on this assignment's GitHub issue with:
1. Your 3 screenshots (or paths to them)
2. Answers to the 5 Task 3 questions
3. Any errors you hit that aren't in `05-pitfalls.md` (so we can add them)
