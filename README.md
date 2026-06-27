# Aerial AI — Crane Inspection Drone

> **Sim-to-Real AI Pipeline for Defect Detection**
> Aerial Autonomy Stack + Isaac Sim + PX4 SITL → Jetson Orin

## Architecture

This workspace follows upstream
[`aerial-autonomy-stack`](https://github.com/JacopoPan/aerial-autonomy-stack)
architecture for the `aircraft` and `ground` roles. The upstream AAS simulation
container is intentionally replaced by this repo's Isaac Sim 6.0/Pegasus stack.

Think of this repository as a thin wrapper around AAS. AAS is the main project;
this repo adds inspection-specific simulation, SDG, missions, inference glue,
and operational defaults. Future changes should stay small and
upstream-compatible unless there is an explicit reason to change AAS itself.

```
┌──────────────────────────────────────────────────────┐
│  Simulation role: Isaac Sim 6.0 + Pegasus             │
│  ├── Container Harbor + Cranes (USD scene)            │
│  ├── Iris Quadrotor (multirotor dynamics)             │
│  └── Inspection Camera (640×640, 20Hz, down-facing)   │
├──────────────────────────────────────────────────────┤
│  AAS ground role                                      │
│  ├── drone_traffic_controller                         │
│  ├── ground_system / ground_system_msgs               │
│  └── Zenoh/QGC-style supervision interfaces           │
├──────────────────────────────────────────────────────┤
│  AAS aircraft role                                    │
│  ├── autopilot_interface — Takeoff/Land/Orbit/Offboard│
│  ├── offboard_control — PX4 Offboard / ArduPilot Guided│
│  ├── mission — behavior-tree conops executor          │
│  ├── drone_traffic_client / state_sharing             │
│  └── yolo_py — AAS perception publisher               │
├──────────────────────────────────────────────────────┤
│  Autopilot links                                      │
│  └── PX4 / ArduPilot via XRCE-DDS or MAVROS           │
├──────────────────────────────────────────────────────┤
│  Repo-specific inspection nodes                       │
│  └── inference_node (TensorRT YOLO defect detection)  │
├──────────────────────────────────────────────────────┤
│  Jetson Orin Nano Super (deployment)                  │
│  TensorRT FP16, ≥30 FPS, ROS2 Humble                  │
└──────────────────────────────────────────────────────┘
```

## Quick Start for AI Agents

### Prerequisites
- Ubuntu 22.04 with Docker, Docker Compose, NVIDIA driver, and NVIDIA Container Toolkit
- NGC access to pull `nvcr.io/nvidia/isaac-sim:6.0.0`
- ROS 2 Humble for host-side ROS commands
- PX4-Autopilot v1.14.3 + MAVROS when running flight-controller integration

### 1. Clone and initialize dependencies

```bash
git clone --recurse-submodules https://github.com/dingdongdengdong/aerial_ws.git /workspace/aerial_ws
cd /workspace/aerial_ws
git submodule update --init --recursive
cp .env.example .env
```

Agent invariants:
- Keep this repo isolated and use `ROS_DOMAIN_ID=22` for every terminal and container.
- Keep `external/aerial-autonomy-stack` initialized; AAS aircraft and ground ROS
  packages in `ros2_ws/src` are links into that submodule.
- Do not use the upstream AAS simulation container here; use Isaac Sim 6.0.

### 2. Start the distribution simulation stack

```bash
cd /workspace/aerial_ws
export ROS_DOMAIN_ID=22
export FOXGLOVE_PORT=8865

# Terminal 1: Foxglove bridge. Connect with ws://localhost:8865
docker compose up foxglove

# Terminal 2: Isaac Sim 6.0 container
docker compose up isaac-sim-60
```

Optional Pegasus execution can be enabled in `.env` after mounting/providing the Pegasus extension path:

```bash
PEGASUS_EXT_PATH=/workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator
ISAAC_SIM_EXEC=/workspace/aerial_ws/scripts/spawn_pegasus_drone.py
```

### 3. Build ROS2 workspace for host-side nodes
```bash
cd /workspace/aerial_ws/ros2_ws
export ROS_DOMAIN_ID=22
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
```

### 4. Start PX4 SITL when testing flight integration
```bash
cd /workspace/PX4-Autopilot
export ROS_DOMAIN_ID=22
make px4_sitl none
```

### 5. Launch drone stack when PX4 is ready
```bash
export ROS_DOMAIN_ID=22
source /opt/ros/humble/setup.bash
source /workspace/aerial_ws/ros2_ws/install/setup.bash

ros2 run mavros mavros_node --ros-args \
  -p fcu_url:=udp://:14540@localhost:18570 \
  -p gcs_url:=udp://@localhost:14550

ros2 launch pegasus_bringup drone_stack.launch.py \
  drone_id:=1 \
  mission_file:=/workspace/aerial_ws/missions/crane_inspection.yaml
```

### 6. Run tests
```bash
cd /workspace/aerial_ws
python3 -m pytest tests/ -v
```

Non-simulation AAS validation without host ROS:

```bash
docker run --rm -e ROS_DOMAIN_ID=22 \
  -v "$PWD":/workspace/aerial_ws \
  -w /workspace/aerial_ws/ros2_ws \
  ros:humble-ros-base bash -lc '
apt-get update >/dev/null
apt-get install -y --no-install-recommends \
  python3-colcon-common-extensions python3-pip libgeographic-dev \
  nlohmann-json3-dev ros-humble-geographic-msgs ros-humble-mavlink \
  ros-humble-mavros-msgs ros-humble-vision-msgs ros-humble-py-trees \
  ros-humble-py-trees-ros >/dev/null
ln -s /opt/ros/humble/include/mavlink/v2.0 /usr/local/include/mavlink
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-up-to \
  autopilot_interface autopilot_interface_msgs drone_traffic_client \
  imu_publisher mission offboard_control state_sharing yolo_py \
  drone_traffic_controller ground_system ground_system_msgs \
  pegasus_ai pegasus_bringup pegasus_msgs
'
```

## TDD Milestones

| # | Milestone | Focus |
|---|-----------|-------|
| 0 | Foundation | CI, ROS2 ws, imports |
| 1 | SDG with Replicator | Isaac Sim/Omniverse Replicator defect datasets |
| 2 | Baseline Training | YOLO on synthetic, mAP@0.5 ≥ 0.70 |
| 3 | ROS2 Integration | Autopilot actions, topics, latency <200ms |
| 4 | Domain Hardening | Weather, noise, materials |
| 5 | Hybrid Training | 500+ real images, 70/30 split |
| 6 | Jetson Deploy | TensorRT FP16, ≥30 FPS |
| 7 | Drone Stack | Aerial Autonomy Stack + PX4 SITL + MAVROS |
| 8 | Final Demo | Sim autonomous + real flight |

## Project Structure

```
aerial_ws/
├── AGENTS.md                      # repo memory/instructions for AI agents
├── docker-compose.yml             # Isaac Sim 6.0 + Foxglove 8865 simulation stack
├── .env.example                   # distribution defaults (ROS_DOMAIN_ID=22)
├── external/aerial-autonomy-stack/ # upstream AAS source of truth
├── ros2_ws/src/
│   ├── autopilot_interface -> external AAS aircraft package
│   ├── offboard_control -> external AAS aircraft package
│   ├── mission -> external AAS aircraft package
│   ├── drone_traffic_client -> external AAS aircraft package
│   ├── ground_system -> external AAS ground package
│   ├── ground_system_msgs -> external AAS ground package
│   ├── pegasus_ai/               # repo-owned Isaac/Pegasus inspection nodes
│   ├── pegasus_bringup/          # repo-owned launch glue
│   └── pegasus_msgs/             # repo-owned inspection messages
├── scripts/                      # Isaac Sim integration scripts
├── tests/                        # Contract tests (TDD milestones)
├── missions/                     # Conops YAML files
├── docs/                         # TDD plan, safety, operations
├── dataset/
│   ├── synthetic/                # Isaac Sim generated
│   ├── real/                     # Collected real images
│   └── mixed_train/              # Hybrid training set
├── models/                       # Trained weights (ONNX, TensorRT)
└── pyproject.toml
```

## Next Milestone: SDG with Replicator

Create new work on `feature/sdg-replicator-milestone`. The milestone goal is to
generate inspection-defect synthetic data with Isaac Sim 6.0 Replicator while
keeping AAS aircraft/ground code unchanged. The first deliverable should be a
small, reproducible Replicator pipeline for container/crane inspection imagery,
labels, and validation commands.

## Safety

**AI NEVER CONTROLS MOTORS DIRECTLY** — only detects and reports.
Follow `docs/SAFETY_INJECTION_ORDER.md` for real drone deployment.

## License

Apache-2.0 — Aerial Autonomy Stack components retain their original BSD-3-Clause.
