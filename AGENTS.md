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

## Agent Workflow

- Before changing tracked files, create an appropriately named feature branch.
- Keep `.omx/`, `.env`, datasets, model weights, ROS build/install/log outputs, and generated caches out of commits.
- After implementing a requested feature, run the smallest useful validation commands and commit the intended tracked changes.
- Write docs for future AI agents: explicit commands, concrete paths, expected ports, expected ROS domain, and verification gates.

## Simulation Stack

- Primary stack file: `docker-compose.yml`.
- Default startup:
  - `cp .env.example .env`
  - `docker compose up foxglove`
  - `docker compose up isaac-sim-60`
- Foxglove URL: `ws://localhost:8865` on the host, or `ws://<host-ip>:8865` from another device.

## Safety Boundary

AI perception nodes may detect, annotate, and report defects. They must not directly command motors. Flight-control commands must remain behind explicit mission/autopilot interfaces and the project safety procedures.
