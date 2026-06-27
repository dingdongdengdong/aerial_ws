# AGENTS.md — aerial_ws Agent Memory

This repository is an isolated, distribution-oriented simulation workspace for AI agents working on aerial drone inspection with Isaac Sim, ROS 2, PX4/MAVROS, Pegasus, and Foxglove.

## Non-negotiable Defaults

- Treat this repo as isolated. Do not modify sibling repos unless the user explicitly asks.
- Use ROS 2 domain ID `22` everywhere: host shells, containers, tests, docs, and examples.
- Use Foxglove WebSocket port `8865` for this repo. Connect with `ws://<host-ip>:8865`.
- Target Isaac Sim container image `nvcr.io/nvidia/isaac-sim:6.0.0`.
- Prefer container paths:
  - repo: `/workspace/aerial_ws`
  - Isaac Sim launcher: `/isaac-sim/isaac-sim.sh`
  - Isaac Sim Python: `/isaac-sim/python.sh`
- Pegasus Simulator may be external. Keep its extension path configurable via `PEGASUS_EXT_PATH`.
- Aerial Autonomy Stack is the upstream architecture source of truth. Keep the
  `external/aerial-autonomy-stack` submodule initialized and use its aircraft
  and ground ROS packages from `ros2_ws/src`.
- Follow the upstream AAS `aircraft` and `ground` roles as-is. The only
  intentional architecture substitution is simulation: use this repo's Isaac Sim
  6.0/Pegasus stack instead of the upstream Gazebo simulation container.
- Treat `aerial_ws` as a thin wrapper/integration workspace around AAS. Prefer
  tiny, upstream-compatible changes. Do not fork/rewrite AAS behavior in this
  repo unless the user explicitly asks.

## Agent Workflow

- Before changing tracked files, create an appropriately named feature branch.
- Keep `.omx/`, `.env`, datasets, model weights, ROS build/install/log outputs, and generated caches out of commits.
- After implementing a requested feature, run the smallest useful validation commands and commit the intended tracked changes.
- Write docs for future AI agents: explicit commands, concrete paths, expected ports, expected ROS domain, and verification gates.
- First external-stack verification should build AAS aircraft and ground ROS
  packages only. Do not run the upstream AAS simulation container for this repo.

## Simulation Stack

- Primary stack file: `docker-compose.yml`.
- Simulation container must remain `nvcr.io/nvidia/isaac-sim:6.0.0`; do not
  replace it with the upstream AAS simulation image.
- Next active milestone after AAS unification is SDG: Isaac Sim/Omniverse
  Replicator synthetic-data generation for inspection defects.
- Default startup:
  - `cp .env.example .env`
  - `docker compose up foxglove`
  - `docker compose up isaac-sim-60`
- Foxglove URL: `ws://localhost:8865` on the host, or `ws://<host-ip>:8865` from another device.

## AAS Verification Gate

Use a ROS Humble build container if the host does not have ROS installed. AAS
`ground_system` expects MAVLink C headers at `/usr/local/include/mavlink`, so
mirror upstream's Dockerfile layout before running `colcon build`:

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

## Safety Boundary

AI perception nodes may detect, annotate, and report defects. They must not directly command motors. Flight-control commands must remain behind explicit mission/autopilot interfaces and the project safety procedures.
