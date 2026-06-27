#!/usr/bin/env bash
set -euo pipefail

ISAAC_SIM_VERSION="${ISAAC_SIM_VERSION:-6.0.0}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-22}"
FOXGLOVE_PORT="${FOXGLOVE_PORT:-8865}"
HEADLESS="${HEADLESS:-1}"
AERIAL_WS="${AERIAL_WS:-/workspace/aerial_ws}"

cd "${AERIAL_WS}"

echo "[aerial_ws] Isaac Sim image: nvcr.io/nvidia/isaac-sim:${ISAAC_SIM_VERSION}"
echo "[aerial_ws] ROS_DOMAIN_ID=${ROS_DOMAIN_ID} FOXGLOVE_PORT=${FOXGLOVE_PORT} HEADLESS=${HEADLESS}"

args=(--allow-root --/isaac/startup/ros_bridge_extension=isaacsim.ros2.bridge)

if [[ "${HEADLESS}" == "1" ]]; then
  args+=(--headless)
fi

if [[ -n "${PEGASUS_EXT_PATH:-}" ]]; then
  if [[ -d "${PEGASUS_EXT_PATH}" ]]; then
    args+=(--ext-path "${PEGASUS_EXT_PATH}" --enable pegasus.simulator)
  else
    echo "[aerial_ws] WARNING: PEGASUS_EXT_PATH is set but not mounted: ${PEGASUS_EXT_PATH}" >&2
  fi
fi

if [[ -n "${ISAAC_SIM_EXEC:-}" ]]; then
  if [[ ! -f "${ISAAC_SIM_EXEC}" ]]; then
    echo "[aerial_ws] ERROR: ISAAC_SIM_EXEC does not exist: ${ISAAC_SIM_EXEC}" >&2
    exit 66
  fi
  args+=(--exec "${ISAAC_SIM_EXEC}")
fi

exec /isaac-sim/isaac-sim.sh "${args[@]}"
