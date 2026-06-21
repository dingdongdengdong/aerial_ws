# Isaac Sim 5.1 — Learning Guide for Pegasus AI

> **Comprehensive onboarding for new Isaac Sim users on the Pegasus AI drone inspection project.**
>
> Everything from first launch to full-stack PX4 + ROS2 + synthetic data generation.

---

## Prerequisites

| Component | Version / Spec | Notes |
|---|---|---|
| **OS** | Ubuntu 22.04 LTS | Required for Isaac Sim 5.1 |
| **GPU** | NVIDIA RTX 4060 Ti 16GB | Minimum VRAM for medium scenes |
| **NVIDIA Driver** | 550+ | `nvidia-smi` to check |
| **ROS 2** | Humble Hawksbill | `/opt/ros/humble/` |
| **Isaac Sim** | 5.1.0 | `/workspace/isaacsim/` |
| **Pegasus Simulator** | Latest | `/workspace/pegasus/PegasusSimulator/` |
| **PX4-Autopilot** | v1.14.3 | `/workspace/PX4-Autopilot/` |
| **MAVROS** | ROS2 Humble | `apt install ros-humble-mavros` |

## Quick-Start Commands

```bash
# 1. Source ROS2
source /opt/ros/humble/setup.bash

# 2. Set environment (CRITICAL — do this in every terminal)
export ROS_DOMAIN_ID=44
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export LD_LIBRARY_PATH=/workspace/isaacsim/exts/isaacsim.ros2.bridge/humble/lib:$LD_LIBRARY_PATH
export DISPLAY=:1

# 3. Launch Isaac Sim interactively (VNC)
/workspace/isaacsim/isaac-sim.sh --allow-root \
  --ext-path /workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator \
  --enable pegasus.simulator
```

## Environment Variable Reference

| Variable | Value | Why |
|---|---|---|
| `ROS_DOMAIN_ID` | `44` | Isolates this project's DDS traffic from other ROS2 instances |
| `RMW_IMPLEMENTATION` | `rmw_fastrtps_cpp` | FastRTPS is the default; CycloneDDS also works but test first |
| `LD_LIBRARY_PATH` | `.../isaacsim.ros2.bridge/humble/lib` | Isaac Sim ships its own ROS2 Humble libraries — they MUST come first |
| `DISPLAY` | `:1` | Routes GUI to VNC display |
| `OMNI_KIT_ALLOW_ROOT` | `1` | Allows running as root (required in container/VM) |
| `FASTRTPS_DEFAULT_PROFILES_FILE` | (optional) | Custom QoS profiles if needed |

## File Path Reference

| Path | Contents |
|---|---|
| `/workspace/isaacsim/isaac-sim.sh` | Isaac Sim launcher |
| `/workspace/isaacsim/exts/isaacsim.ros2.bridge/` | ROS2 Bridge extension |
| `/workspace/isaacsim/exts/isaacsim.ros2.bridge/humble/lib/` | Internal ROS2 Humble libraries |
| `/workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator/` | Pegasus simulator extension |
| `/workspace/PX4-Autopilot/` | PX4 SITL flight controller |
| `/opt/ros/humble/` | System ROS2 Humble installation |
| `/workspace/aerial_ws/scripts/` | Project scripts (spawn, test, etc.) |
| `/workspace/aerial_ws/docs/isaac-sim/` | This documentation set |

## Documentation Index

Read in order for the best learning experience:

| # | File | Topic |
|---|---|---|
| 1 | [`01-getting-started.md`](01-getting-started.md) | Installation, first launch, UI walkthrough, viewport controls |
| 2 | [`02-ros2-bridge.md`](02-ros2-bridge.md) | ROS2 Bridge architecture, env vars, QoS, Foxglove |
| 3 | [`03-pegasus-integration.md`](03-pegasus-integration.md) | Pegasus backends, PX4 MAVLink, MAVROS, OFFBOARD control |
| 4 | [`04-synthetic-data.md`](04-synthetic-data.md) | Replicator, domain randomization, Cosmos Transfer |
| 5 | [`05-pitfalls.md`](05-pitfalls.md) | Common errors and how to fix them |
| 6 | [`06-full-stack.md`](06-full-stack.md) | Complete launch order for the full simulation stack |
| 7 | [`07-advanced-scenes.md`](07-advanced-scenes.md) | USD scenes, SimReady assets, building from primitives |

## Key Official Documentation

- **Isaac Sim 5.1**: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/
- **ROS2 Bridge**: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/ros2_bridge.html
- **Replicator**: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/replicator_tutorials/index.html
- **Pegasus Simulator**: https://pegasus-simulator.github.io/
- **Isaac Lab**: https://isaac-sim.github.io/IsaacLab/
- **Cosmos Transfer 2.5**: https://github.com/nvidia-cosmos/cosmos-transfer2.5

## Project Architecture

```
Isaac Sim (rendering + physics)
  │
  ├── Pegasus Simulator (drone dynamics + sensors)
  │     ├── PX4MavlinkBackend ←→ PX4 SITL (flight control)
  │     ├── ROS2Backend → ROS2 topics (camera, IMU, pose)
  │     └── MonocularCamera (640×640, 20Hz, down-facing)
  │
  ├── ROS2 Bridge → DDS (domain 44)
  │     ├── /mavros/state, /mavros/local_position/pose
  │     ├── /drone/inspection_camera/color/image_raw
  │     └── /pegasus/state/pose, /pegasus/tf
  │
  ├── MAVROS ←→ MAVLink
  │     └── PX4 OFFBOARD control, telemetry
  │
  └── Aerial Autonomy Stack
        ├── autopilot_interface (C++) — action server
        ├── mission (Python) — conops executor
        └── inference_node (TensorRT YOLO)
```

---

**Next step**: Read [`01-getting-started.md`](01-getting-started.md) and launch Isaac Sim for the first time.
