# Isaac Sim 6.0 — Learning Guide for Pegasus AI

> **Comprehensive onboarding for new Isaac Sim users on the Pegasus AI drone inspection project.**
>
> Everything from first launch to full-stack PX4 + ROS2 + synthetic data generation.

---

## Prerequisites

| Component | Version / Spec | Notes |
|---|---|---|
| **OS** | Ubuntu 22.04 LTS | Required for Isaac Sim 6.0 |
| **GPU** | NVIDIA RTX 4060 Ti 16GB | Minimum VRAM for medium scenes |
| **NVIDIA Driver** | 550+ | `nvidia-smi` to check |
| **ROS 2** | Humble Hawksbill | `/opt/ros/humble/` |
| **Isaac Sim** | 6.0.0 container | `/isaac-sim/` |
| **Pegasus Simulator** | Latest | `/workspace/pegasus/PegasusSimulator/` |
| **PX4-Autopilot** | v1.14.3 | `/workspace/PX4-Autopilot/` |
| **MAVROS** | ROS2 Humble | `apt install ros-humble-mavros` |

## Quick-Start Commands for Agents

Use the repo-level Compose stack first. It fixes the distribution defaults: Isaac Sim 6.0, ROS domain `22`, and Foxglove port `8865`.

```bash
cd /workspace/aerial_ws
cp .env.example .env
export ROS_DOMAIN_ID=22
export FOXGLOVE_PORT=8865

# Terminal 1 — Foxglove bridge, connect with ws://localhost:8865
docker compose up foxglove

# Terminal 2 — Isaac Sim 6.0 container
docker compose up isaac-sim-60
```

If an agent runs commands inside the Isaac Sim container manually, use these paths and env vars:

```bash
export ROS_DOMAIN_ID=22
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export LD_LIBRARY_PATH=/isaac-sim/exts/isaacsim.ros2.core/humble/lib:$LD_LIBRARY_PATH
export PYTHONPATH=/isaac-sim/exts/isaacsim.ros2.core/humble/rclpy:$PYTHONPATH
/isaac-sim/isaac-sim.sh --allow-root --/isaac/startup/ros_bridge_extension=isaacsim.ros2.bridge
```

## Environment Variable Reference

| Variable | Value | Why |
|---|---|---|
| `ROS_DOMAIN_ID` | `22` | Isolates this project's DDS traffic from other ROS2 instances |
| `RMW_IMPLEMENTATION` | `rmw_fastrtps_cpp` | FastRTPS is the default; CycloneDDS also works but test first |
| `LD_LIBRARY_PATH` | `.../isaacsim.ros2.core/humble/lib` | Isaac Sim ships its own ROS2 Humble libraries — they MUST come first |
| `DISPLAY` | `:1` | Routes GUI to VNC display |
| `OMNI_KIT_ALLOW_ROOT` | `1` | Allows running as root (required in container/VM) |
| `FASTRTPS_DEFAULT_PROFILES_FILE` | (optional) | Custom QoS profiles if needed |

## File Path Reference

| Path | Contents |
|---|---|
| `/isaac-sim/isaac-sim.sh` | Isaac Sim launcher |
| `/isaac-sim/exts/isaacsim.ros2.bridge/` | ROS2 Bridge extension |
| `/isaac-sim/exts/isaacsim.ros2.core/humble/lib/` | Internal ROS2 Humble libraries |
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

- **Isaac Sim 6.0**: https://docs.isaacsim.omniverse.nvidia.com/6.0.0/
- **ROS2 Bridge**: https://docs.isaacsim.omniverse.nvidia.com/6.0.0/ros2_bridge.html
- **Replicator**: https://docs.isaacsim.omniverse.nvidia.com/6.0.0/replicator_tutorials/index.html
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
  ├── ROS2 Bridge → DDS (domain 22)
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
