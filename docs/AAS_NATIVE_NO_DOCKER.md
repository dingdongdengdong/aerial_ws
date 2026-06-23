# Aerial Autonomy Stack Native Runbook (No Docker)

This note explains how to adapt the upstream `aerial-autonomy-stack` README flow to this
workspace when the AAS Docker architecture cannot run.

Upstream AAS uses three Docker container roles:

| Upstream role | Container image | Purpose |
| --- | --- | --- |
| Simulation | `simulation-image` | Gazebo Harmonic, PX4/ArduPilot SITL, simulated sensors, bridges |
| Aircraft | `aircraft-image` | ROS2 autonomy nodes, perception, offboard control, XRCE-DDS/MAVROS |
| Ground | `ground-image` | QGroundControl, ground system, MAVLink router, Zenoh bridge |

Our current environment is already a container. It can run ROS2/PX4/Isaac Sim tools, but
it cannot create the Docker bridge networks required by upstream `sim_run.sh` because it
lacks `CAP_NET_ADMIN`. Therefore the exact upstream README command is not runnable here:

```bash
cd /workspace/aerial_ws/external/aerial-autonomy-stack/tools_and_docs
AUTOPILOT=px4 NUM_QUADS=1 NUM_VTOLS=1 WORLD=swiss_town HEADLESS=false RTF=3.0 ./sim_run.sh
```

The native path below keeps the useful AAS pieces but runs them directly in this dev
container as normal processes.

## Goal

Run a single-drone AAS-derived stack locally:

```text
Isaac Sim + Pegasus or PX4 SITL
    -> MAVLink
    -> MAVROS
    -> AAS ROS2 nodes: autopilot_interface, offboard_control, mission
    -> project ROS2 node: pegasus_ai inference_node
    -> Foxglove bridge for inspection/debug
```

This is intentionally not a full upstream multi-container, multi-drone Gazebo system. It
matches this repo's architecture: single drone, localhost networking, Isaac Sim/Pegasus,
ROS_DOMAIN_ID=44, Foxglove on port 8765.

## Current environment status

Checked in this dev container:

| Check | Status |
| --- | --- |
| Ubuntu 22.04 | OK |
| NVIDIA driver 580.65.06 | OK |
| Docker Engine | OK after manual daemon start |
| NVIDIA Container Toolkit | OK |
| Docker custom bridge networks | Blocked: `operation not permitted` |
| ROS2 Humble | OK |
| MAVROS | OK |
| Foxglove bridge | OK |
| MicroXRCEAgent | OK |
| `gz` / Gazebo Harmonic CLI | Not present in current PATH |
| `mavlink-routerd` | Not present in current PATH |
| `zenoh-bridge-ros2dds` | Not present in current PATH |

Because Gazebo Harmonic and the upstream bridge utilities are not currently available,
the recommended native path is Isaac Sim + Pegasus, not upstream Gazebo.

## Native architecture mapping

| Upstream container action | Native replacement in this repo |
| --- | --- |
| `simulation-image`: Gazebo + PX4 SITL | Isaac Sim + Pegasus, or standalone `/workspace/PX4-Autopilot` |
| `aircraft-image`: AAS ROS2 nodes | `/workspace/aerial_ws/ros2_ws/install` nodes |
| `ground-image`: QGC/ground/Zenoh | Foxglove bridge + local ROS2 CLI |
| Docker SIM/AIR networks | localhost UDP + single `ROS_DOMAIN_ID=44` |
| GStreamer camera stream | ROS2 camera topic from Isaac Sim/Pegasus |
| `yolo_py` GStreamer inference | `pegasus_ai/inference_node` ROS2 image subscriber |
| `kiss_icp`, `state_sharing`, Zenoh | Not launched for single-drone crane inspection |

## One-time setup

From repo root:

```bash
cd /workspace/aerial_ws

git submodule update --init --recursive

source /opt/ros/humble/setup.bash
cd ros2_ws
colcon build
source install/setup.bash
```

Do not use `--symlink-install` in this container unless setuptools/colcon are pinned to
a compatible version. The current environment has setuptools 82.0.1, and colcon's
`setup.py develop --editable` path fails for some upstream Python packages with
`error: option --editable not recognized`. A normal `colcon build` works.

Useful environment variables for every terminal:

```bash
source /opt/ros/humble/setup.bash
source /workspace/aerial_ws/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=44
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

For Isaac Sim terminals also set:

```bash
export DISPLAY=:1
export OMNI_KIT_ALLOW_ROOT=1
export LD_LIBRARY_PATH=/workspace/isaacsim/exts/isaacsim.ros2.bridge/humble/lib:${LD_LIBRARY_PATH}
```

## Recommended native run: Isaac Sim + Pegasus + local AAS nodes

### Terminal 1: start Foxglove bridge

Always start Foxglove with ROS2 so there is a live debug surface.

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=44
ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765 use_sim_time:=true
```

Connect Foxglove Studio to:

```text
ws://localhost:8765
```

### Terminal 2: start Isaac Sim with Pegasus

Use the `--exec` script that is compatible with an already-running Isaac Sim app.

```bash
export DISPLAY=:1
export OMNI_KIT_ALLOW_ROOT=1
export ROS_DOMAIN_ID=44
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export LD_LIBRARY_PATH=/workspace/isaacsim/exts/isaacsim.ros2.bridge/humble/lib:${LD_LIBRARY_PATH}

/workspace/isaacsim/isaac-sim.sh --allow-root \
  --ext-path /workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator \
  --enable pegasus.simulator \
  --/isaac/startup/ros_bridge_extension=isaacsim.ros2.bridge \
  --exec /workspace/aerial_ws/scripts/spawn_drone_px4_exec.py
```

Expected result:

- Isaac Sim opens on display `:1`.
- Pegasus spawns the drone.
- Pegasus/PX4 owns its internal PX4 lifecycle.
- Do not repeatedly try to arm SITL from this runbook; verify bridge and topics first.

### Terminal 3: launch the local AAS-derived drone stack

```bash
source /opt/ros/humble/setup.bash
source /workspace/aerial_ws/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=44

ros2 launch pegasus_bringup drone_stack.launch.py \
  drone_id:=1 \
  fcu_url:=udp://:4560@localhost:14550 \
  gcs_url:=udp://@localhost:14550 \
  camera_topic:=/drone/inspection_camera/color/image_raw \
  mission_file:=/workspace/aerial_ws/missions/crane_inspection_demo.yaml \
  model_type:=mock
```

This launches:

- `mavros/mavros_node`
- `autopilot_interface/px4_interface`
- `offboard_control/px4_offboard`
- `mission/mission`
- `pegasus_ai/inference_node`

It intentionally does not launch upstream-only multi-drone pieces:

- `state_sharing`
- `drone_traffic_client`
- `ground_system`
- `zenoh-bridge-ros2dds`
- `kiss_icp`
- upstream `yolo_py` GStreamer pipeline

## Alternative native run: standalone PX4 SITL + local AAS nodes

Use this if Isaac Sim is not needed and you only want to check ROS2/MAVROS/AAS node
startup.

### Terminal 1: PX4 SITL

```bash
cd /workspace/PX4-Autopilot
make px4_sitl none
```

### Terminal 2: Foxglove bridge

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=44
ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765 use_sim_time:=true
```

### Terminal 3: MAVROS + AAS nodes

For standalone PX4, use the standard external MAVROS port instead of Pegasus `:4560`:

```bash
source /opt/ros/humble/setup.bash
source /workspace/aerial_ws/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=44

ros2 launch pegasus_bringup drone_stack.launch.py \
  drone_id:=1 \
  fcu_url:=udp://:14540@localhost:18570 \
  gcs_url:=udp://@localhost:14550 \
  camera_topic:=/camera/image_raw \
  mission_file:=/workspace/aerial_ws/missions/crane_inspection_demo.yaml \
  model_type:=mock
```

Expected result:

- MAVROS topics appear.
- AAS action servers appear under `/Drone1/...`.
- Camera inference may run in mock mode if no camera topic exists.
- This is a control-stack smoke test, not a visual simulation.

## Verification commands

Run these from a sourced ROS2 terminal:

```bash
source /opt/ros/humble/setup.bash
source /workspace/aerial_ws/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=44

ros2 topic list | sort
ros2 node list | sort
ros2 action list | sort
ros2 topic echo --once /mavros/state
```

Expected important entries:

```text
/mavros/state
/mavros/local_position/pose
/Drone1/takeoff_action
/Drone1/land_action
/Drone1/offboard_action
/detections
```

For Foxglove:

```bash
ros2 topic list | wc -l
```

The exact count depends on which simulator path is running. A nonzero topic count with
MAVROS topics is the first pass condition.

For Isaac Sim screenshot proof:

```bash
DISPLAY=:1 python3 - <<'PY'
from mss import MSS
with MSS(display=':1') as sct:
    sct.shot(output='/workspace/aerial_ws/monitor-1.png')
print('/workspace/aerial_ws/monitor-1.png')
PY
```

## Why not run upstream Gazebo natively first?

It is possible in principle, but it is a larger port than the project currently needs.
The upstream Docker build installs and wires together several components that are not
present here by default:

- Gazebo Harmonic / `gz sim`
- `ros_gz_bridge`
- PX4 v1.17 with AAS custom airframes `5140_gz_aas_x500` and `5141_gz_aas_standard_vtol`
- `gz_gst_bridge` built from AAS resources
- `mavlink-routerd`
- `zenoh-bridge-ros2dds`
- QGroundControl AppImage runtime setup
- optional LiDAR/odometry stacks

If we later need exact upstream Gazebo parity without Docker, create a separate native
setup script that mirrors `tools_and_docs/docker/simulation.dockerfile` and then renders
`simulation/simulation.yml.erb` into local tmux commands. For the crane-inspection repo,
the Isaac Sim native path is the better first target.

## Troubleshooting

### Docker requirement check passes, but `sim_run.sh` fails

That can happen in nested containers. AAS `check_requirements.sh` checks Docker Engine and
NVIDIA runtime, but it does not verify custom Docker network creation. Test it directly:

```bash
docker network create --subnet=10.42.0.0/16 aas-preflight-net
```

If it returns `operation not permitted`, upstream `sim_run.sh` cannot work in the current
container.

### MAVROS connects to nothing

Use the correct port for the selected simulator path:

| Path | `fcu_url` |
| --- | --- |
| Pegasus/Isaac Sim PX4 backend | `udp://:4560@localhost:14550` |
| Standalone PX4 SITL | `udp://:14540@localhost:18570` |

### No camera detections

Confirm the camera topic exists and QoS matches:

```bash
ros2 topic list | grep image
ros2 topic info /drone/inspection_camera/color/image_raw --verbose
```

Pegasus camera publishers are reliable QoS. Subscribers should use reliable QoS.

### Foxglove is empty

Foxglove only displays existing ROS2 topics. Start the data sources first:

1. PX4/Isaac Sim
2. MAVROS + AAS nodes
3. Foxglove bridge

Then re-check:

```bash
ros2 topic list | wc -l
```
