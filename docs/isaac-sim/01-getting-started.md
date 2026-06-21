# 01 — Getting Started with Isaac Sim 5.1

> **Goal**: Verify your installation, launch Isaac Sim, understand the UI, and run your first Python script.

---

## 1. Installation Verification

Before launching, confirm everything is in place:

```bash
# Check Isaac Sim installation
ls /workspace/isaacsim/isaac-sim.sh
# Expected: /workspace/isaacsim/isaac-sim.sh

# Check NVIDIA driver
nvidia-smi | head -5
# Expected: Driver Version 550+ with your GPU listed

# Check VNC server is running on :1
ps aux | grep vnc | grep ':1'
# If not running: vncserver :1 -geometry 1920x1080 -depth 24

# Check ROS2 Humble
source /opt/ros/humble/setup.bash
ros2 --version
# Expected: humble or similar
```

## 2. First Launch — Interactive Mode (VNC)

The simplest way to get started is launching Isaac Sim interactively, viewing via VNC.

### Step-by-step:

```bash
# 1. Set required environment variables
export DISPLAY=:1
export OMNI_KIT_ALLOW_ROOT=1

# 2. Launch Isaac Sim with Pegasus extension
/workspace/isaacsim/isaac-sim.sh --allow-root \
  --ext-path /workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator \
  --enable pegasus.simulator
```

Connect to VNC at `localhost:5900` (or `localhost:5901` if you used `:1`). You should see the Isaac Sim UI appear.

### What you'll see:
- A loading screen with NVIDIA and Omniverse logos
- The main Isaac Sim window with menus, toolbars, and an empty viewport
- The **Console** at the bottom (blue/gray text area)

> **First-launch tip**: The first launch can take 1–3 minutes. Watch the console for messages. If it hangs at "Loading shaders", just wait — it's compiling.

## 3. UI Walkthrough

```
┌────────────────────────────────────────────────────────────┐
│ Menu Bar    File  Edit  Create  Window  Help                │
├────────────────────────────────────────────────────────────┤
│ Toolbar     [Play] [Stop] [Snap] [Transform tools]         │
├───────────────────────┬────────────────────────────────────┤
│                       │                                    │
│    Viewport           │   Properties Panel                 │
│   (3D scene)          │   (selected object details)        │
│                       │                                    │
│                       │                                    │
├───────────────────────┴────────────────────────────────────┤
│    Stage (left panel) — USD hierarchy tree                 │
├────────────────────────────────────────────────────────────┤
│    Console — log output, Python errors, print statements   │
└────────────────────────────────────────────────────────────┘
```

### Key panels:

| Panel | Shortcut | Purpose |
|---|---|---|
| **Viewport** | Click anywhere in 3D area | View and interact with the scene |
| **Stage** | `Window > Stage` | USD prim hierarchy (scene graph) |
| **Properties** | `Window > Property` | Edit selected object's attributes |
| **Console** | `Window > Console` | See logs, errors, `print()` output |
| **Script Editor** | `Window > Script Editor` | Run Python inside Isaac Sim |
| **Content** | `Window > Content` | Browse assets, materials, environments |

## 4. Viewport Controls

| Action | Input |
|---|---|
| **Orbit** (rotate view) | **Middle-mouse drag** or `Alt + Left-mouse drag` |
| **Pan** | **Middle-mouse + Shift drag** or `Alt + Middle-mouse drag` |
| **Zoom** | **Scroll wheel** or `Alt + Right-mouse drag` |
| **Focus on object** | Select object in Stage, press **`F`** |
| **Frame all** | Press **`F`** with nothing selected |
| **Toggle wireframe** | Press **`W`** (shaded → wireframe → shaded+wire) |

> **Critical tip**: If you lose sight of your drone/scene, select it in the Stage panel and press **`F`** — the camera instantly focuses on it.

## 5. Launch Methods

Isaac Sim supports several launch modes. Know when to use each:

### 5a. Interactive (GUI with VNC)

```bash
# Full GUI — for visual debugging and scene setup
export DISPLAY=:1
/workspace/isaacsim/isaac-sim.sh --allow-root
```

**Use for**: Scene setup, visual debugging, learning the tool.

### 5b. Interactive + Execute Script (`--exec`)

```bash
# GUI is open, then run a script inside it
# Launch the GUI first, then in another terminal:
/workspace/isaacsim/isaac-sim.sh --allow-root \
  --exec /workspace/aerial_ws/scripts/spawn_drone_px4_exec.py
```

The `--exec` flag runs a Python script **inside the already-running** Isaac Sim process. This is the standard pattern for our project.

> **CRITICAL**: Scripts for `--exec` must NOT create a `SimulationApp()` object. The app is already running. See the pattern below.

### 5c. Headless (`-p` flag, standalone SimulationApp)

```bash
# No GUI — script creates its own SimulationApp
/workspace/isaacsim/isaac-sim.sh --allow-root -p my_script.py
```

**Use for**: Batch processing, dataset generation, CI/CD pipelines.

### 5d. tmux (background Isaac Sim)

```bash
# Use tmux to keep Isaac Sim running in background
tmux new-session -d -s isaac-sim \
  '/workspace/isaacsim/isaac-sim.sh --allow-root --ext-path ...'

# Attach to view logs
tmux attach -t isaac-sim

# Detach with Ctrl+B, D
```

> **Why tmux and not `&`**: Isaac Sim needs a terminal for its console output. Backgrounding with `&` loses the PTY and causes Kit to freeze. Always use `tmux` for background launches.

## 6. First Python Script — The `--exec` Pattern

Here's the canonical pattern for scripts that run via `--exec`:

```python
#!/usr/bin/env python3
"""
Minimal --exec script pattern for Isaac Sim 5.1.
Runs inside an already-running Isaac Sim. No SimulationApp() call.
"""

import asyncio
import carb
import omni.kit.app
from isaacsim.core.utils.extensions import enable_extension

# 1. Enable needed extensions
enable_extension("isaacsim.ros2.bridge")
omni.kit.app.get_app().update()  # Let Kit process extension load

# 2. Do work inside an async function
async def my_setup():
    # Initialize world
    from omni.isaac.core import World
    world = World()
    await world.initialize_simulation_context_async()
    await world.reset_async()

    # Create a cube
    from omni.isaac.core.objects import DynamicCuboid
    cube = DynamicCuboid(
        prim_path="/World/my_cube",
        position=[0, 0, 2],
        size=0.5,
        color=[1, 0, 0],
    )

    carb.log_info("Scene ready! Red cube at 2m height.")

# 3. Schedule the async function
asyncio.ensure_future(my_setup())
```

Save this as `first_script.py` and run:

```bash
# First launch Isaac Sim GUI in one terminal:
export DISPLAY=:1
/workspace/isaacsim/isaac-sim.sh --allow-root

# Then in another terminal, execute the script:
/workspace/isaacsim/isaac-sim.sh --allow-root \
  --exec /workspace/aerial_ws/scripts/first_script.py
```

Check the Console in the Isaac Sim GUI — you should see `"Scene ready! Red cube at 2m height."`

## 7. Common First-Launch Problems

| Symptom | Likely Cause | Fix |
|---|---|---|
| `DISPLAY not set` error | No VNC running | `vncserver :1 -geometry 1920x1080 -depth 24` |
| Black window / crash | GPU driver issue | `nvidia-smi` to verify driver; reinstall if needed |
| `GLXBadFBConfig` error | VNC doesn't support GPU rendering | Use VirtualGL or switch to `Xvfb` for headless |
| Stuck at "Loading shaders" | First run compiling shader cache | Wait 3–5 minutes; subsequent launches are fast |
| `Permission denied` on `isaac-sim.sh` | File not executable | `chmod +x /workspace/isaacsim/isaac-sim.sh` |
| `Cannot connect to Omniverse` | Licensing | Isaac Sim 5.1 works offline; no login needed |
| No Pegasus extension | Extension path wrong | Verify: `ls /workspace/pegasus/PegasusSimulator/extensions/pegasus.simulator/` |
| Script doesn't run with `--exec` | Isaac Sim GUI not running first | You need the GUI open before `--exec` works |
| ImportError: SimulationApp | Using standalone pattern in --exec | Remove `SimulationApp()` call; use async pattern |
| Kit hangs after script exits | Script didn't use async | Always use `asyncio.ensure_future()` for --exec scripts |

### Diagnostic Commands

```bash
# Check VNC
ps aux | grep Xvnc

# Check GPU
nvidia-smi

# Check display
echo $DISPLAY

# Test X11
xdpyinfo -display :1 | head -5

# Kill stuck Isaac Sim
pkill -f isaac-sim
```

---

**Next**: [02-ros2-bridge.md](02-ros2-bridge.md) — Connect Isaac Sim to ROS2.

## References

- Isaac Sim 5.1 Quick Start: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/
- Omniverse Launcher Guide: https://docs.omniverse.nvidia.com/launcher/latest/
