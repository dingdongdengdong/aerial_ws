#!/usr/bin/env bash
set -euo pipefail

ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-22}"
FOXGLOVE_PORT="${FOXGLOVE_PORT:-8865}"

source /opt/ros/humble/setup.bash

if ! ros2 pkg prefix foxglove_bridge >/dev/null 2>&1; then
  apt-get update
  apt-get install -y --no-install-recommends ros-humble-foxglove-bridge
fi

echo "[aerial_ws] Foxglove WebSocket bridge: ws://localhost:${FOXGLOVE_PORT} (ROS_DOMAIN_ID=${ROS_DOMAIN_ID})"
exec ros2 launch foxglove_bridge foxglove_bridge_launch.xml \
  port:=${FOXGLOVE_PORT} \
  address:=0.0.0.0
