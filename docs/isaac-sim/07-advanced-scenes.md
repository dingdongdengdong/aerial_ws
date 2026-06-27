# 07 — Advanced USD Scene Setup

> **Goal**: Build complex 3D scenes for drone inspection: load SimReady assets, compose from primitives, and manage external USD references — all from Python scripts.

---

## 1. USD Scene Basics

Isaac Sim uses **Universal Scene Description (USD)** as its native scene format. Everything in the viewport is a **prim** (primitive) in a USD stage. Prims are organized in a hierarchy at paths like `/World/quadrotor`, `/World/background`, `/World/container_prop_001`.

### Key USD Concepts

| Concept | Description | Example |
|---|---|---|
| **Stage** | The entire scene | `omni.usd.get_context().get_stage()` |
| **Prim** | A single object in the stage | `/World/quadrotor` |
| **Xform** | A transformable prim (position, rotation, scale) | `UsdGeom.Xformable(prim)` |
| **Reference** | A link to an external USD file | `prim.GetReferences().AddReference(path)` |
| **Default Prim** | The root prim a USD file exposes by default | Set in USD metadata |

---

## 2. SimReady Assets

NVIDIA provides **SimReady** assets — physically accurate 3D models with materials, collision meshes, and semantic labeling. They're available through the Omniverse asset store or bundled with Isaac Sim.

### Container Harbor Example

Our project uses SimReady shipping containers, pallets, drums, and other port props. The asset structure:

```
/workspace/aerial_ws/assets/container_harbor/
└── Assets/simready_content/common_assets/props/
    ├── container_a01/
    │   └── container_a01.usd
    ├── container_a02/
    │   └── container_a02.usd
    ├── blockpallet_a01/
    │   └── blockpallet_a01.usd
    ├── steeldrum_a01/
    │   └── steeldrum_a01.usd
    └── ... (many more)
```

### Loading SimReady Props via AddReference

The standard pattern for loading SimReady props from Python:

```python
import omni.usd
from pxr import UsdGeom, Gf

stage = omni.usd.get_context().get_stage()
usd_path = "/workspace/aerial_ws/assets/container_harbor/Assets/simready_content/common_assets/props/container_a01/container_a01.usd"

# 1. Define a new Xform prim at the desired path
prim = stage.DefinePrim("/World/container_001", "Xform")

# 2. Add a reference to the USD file
prim.GetReferences().AddReference(usd_path)

# 3. Set position using the Xformable API
xform = UsdGeom.Xformable(prim)
xform.AddTranslateOp().Set(Gf.Vec3d(5.0, -2.0, 0.0))
```

> **CRITICAL**: Some USD files lack a `defaultPrim` metadata field. Without it, `AddReference(path)` silently produces an empty prim (the Xform exists but has no children). **Always pass the root prim path as the second argument** when loading assets:
> ```python
> prim.GetReferences().AddReference(usd_path, "/ContainerCrane")
> ```
> This tells USD which prim in the referenced file to compose. Check the USD file in the Content browser or with `usdcat` to find the correct root prim path.

### Container Prop Naming Convention

```
/World/container_prop_000  ← Grid of shipping containers
/World/container_prop_001
/World/container_prop_002
...
/World/container_crane_cc  ← Ship-to-shore container crane
/World/transfer_crane_tc   ← RTG transfer crane
```

Use descriptive, zero-padded names to make the Stage panel readable and to enable iteration in scripts.

---

## 3. Building from Primitives

Isaac Sim wraps USD primitives through the `omni.isaac.core.objects` module:

```python
import numpy as np
from omni.isaac.core.objects import (
    DynamicCuboid, DynamicCylinder, DynamicSphere,
    FixedCuboid, VisualCuboid
)

# Dynamic (physics-enabled) objects respond to gravity and collisions
cube = DynamicCuboid(
    prim_path="/World/dynamic_box",
    name="dynamic_box",
    position=np.array([0, 0, 5]),    # spawn 5m above ground
    orientation=np.array([1, 0, 0, 0]),  # w, x, y, z quaternion
    scale=np.array([1, 1, 1]),       # size in meters
    color=np.array([1, 0, 0]),       # red (RGB, 0-1)
)

# Fixed (static) objects don't move — good for buildings, ground
floor = FixedCuboid(
    prim_path="/World/floor",
    name="floor",
    position=np.array([0, 0, 0]),
    scale=np.array([20, 20, 0.1]),
    color=np.array([0.5, 0.5, 0.5]),
)

# Visual-only (no physics) objects — good for decorations
marker = VisualCuboid(
    prim_path="/World/waypoint",
    name="waypoint",
    position=np.array([5, 0, 2]),
    scale=np.array([0.2, 0.2, 0.2]),
    color=np.array([0, 1, 0]),
)
```

### Cylinder Example

```python
from omni.isaac.core.objects import DynamicCylinder

# A horizontal cylinder (like a pipe)
pipe = DynamicCylinder(
    prim_path="/World/pipe_001",
    name="pipe_001",
    position=np.array([3, 0, 2]),
    orientation=np.array([0.707, 0, 0, 0.707]),  # 90° rotation around X
    radius=0.1,
    height=5.0,
    color=np.array([0.6, 0.6, 0.6]),
)
```

### Using pxr.UsdGeom Directly

For more control, use Pixar's USD Python API (`pxr`):

```python
from pxr import UsdGeom, Gf, Sdf, Usd

stage = omni.usd.get_context().get_stage()

# Create a cube primitive
cube_path = Sdf.Path("/World/manual_cube")
cube_prim = UsdGeom.Cube.Define(stage, cube_path)

# Set size
cube_prim.GetSizeAttr().Set(2.0)

# Add a transform (position, rotation, scale)
xform = UsdGeom.Xformable(cube_prim)
xform_op = xform.AddTranslateOp()
xform_op.Set(Gf.Vec3d(10.0, 0.0, 5.0))

# Add a rotate operation
rotate_op = xform.AddRotateXYZOp()
rotate_op.Set(Gf.Vec3f(0, 45, 0))  # 45° around Y
```

---

## 4. Loading External USD via AddReference

### Pattern: Load a Cached Scene

```python
import omni.usd
from pxr import UsdGeom, Gf

def load_crane_asset(asset_path: str, prim_path: str, position: tuple, root_prim: str):
    """
    Load a crane USD asset into the stage.

    Args:
        asset_path: Absolute path to .usd file
        prim_path:  Target prim path in the stage (e.g., "/World/crane_01")
        position:   (x, y, z) world position
        root_prim:  Prim path inside the USD file to compose
                    (e.g., "/ContainerCrane")
    """
    stage = omni.usd.get_context().get_stage()

    # Create the container prim
    prim = stage.DefinePrim(prim_path, "Xform")

    # Add reference with explicit root prim
    prim.GetReferences().AddReference(asset_path, root_prim)

    # Set position
    xform = UsdGeom.Xformable(prim)
    xform.AddTranslateOp().Set(Gf.Vec3d(*position))

    return prim

# Usage
load_crane_asset(
    asset_path="/workspace/aerial_ws/assets/cranes/container_crane.usd",
    prim_path="/World/container_crane_cc",
    position=(-25.0, -20.0, 0.0),
    root_prim="/ContainerCrane",
)

load_crane_asset(
    asset_path="/workspace/aerial_ws/assets/cranes/transfer_crane.usd",
    prim_path="/World/transfer_crane_tc",
    position=(15.0, -15.0, 0.0),
    root_prim="/TransferCrane",
)
```

### Pattern: Grid Scatter of Props

```python
import random

def scatter_props(props_list, base_x, base_y, spacing, rows, cols):
    """
    Scatter SimReady props in a grid with jitter.

    Args:
        props_list: List of (usd_path, prim_name) tuples
        base_x, base_y: Bottom-left corner of grid
        spacing: Distance between grid cells
        rows, cols: Grid dimensions
    """
    stage = omni.usd.get_context().get_stage()
    loaded = 0

    for i, (usd_path, _) in enumerate(props_list):
        row = i // cols
        col = i % cols

        x = base_x + col * spacing + random.uniform(-0.5, 0.5)
        y = base_y + row * spacing + random.uniform(-0.5, 0.5)
        z = 0.0  # ground level

        prim_path = f"/World/prop_{i:03d}"

        try:
            prim = stage.DefinePrim(prim_path, "Xform")
            prim.GetReferences().AddReference(usd_path)

            xform = UsdGeom.Xformable(prim)
            xform.AddTranslateOp().Set(Gf.Vec3d(x, y, z))
            loaded += 1
        except Exception as exc:
            print(f"  Failed to load {prim_path}: {exc}")

    print(f"Loaded {loaded} props")
```

---

## 5. The `--exec` Pattern for Scene Setup Scripts

Scene setup scripts that run via `--exec` follow this structure:

```python
#!/usr/bin/env python3
"""
Container Harbor scene setup for --exec mode.
Loads warehouse environment, scatters container props, places cranes.
"""

import asyncio
import os
import random
import carb
import omni.kit.app
import omni.usd
import numpy as np
from pxr import UsdGeom, Gf
from isaacsim.core.utils.extensions import enable_extension

# Enable needed extensions
enable_extension("pegasus.simulator")
enable_extension("isaacsim.ros2.bridge")
omni.kit.app.get_app().update()

from pegasus.simulator.logic.interface.pegasus_interface import PegasusInterface

# ── Asset paths ──────────────────────────────────────────
PROPS_ROOT = "/workspace/aerial_ws/assets/container_harbor/Assets/simready_content/common_assets/props"

CONTAINERS = [
    f"{PROPS_ROOT}/container_a01/container_a01.usd",
    f"{PROPS_ROOT}/container_a02/container_a02.usd",
    f"{PROPS_ROOT}/container_b02/container_b02.usd",
    f"{PROPS_ROOT}/container_c01/container_c01.usd",
    # ... add all container paths
]

CRANE_DIR = "/workspace/aerial_ws/assets/cranes"

async def setup_scene():
    carb.log_info("Starting container harbor scene setup...")

    # 1. Initialize Pegasus world
    pg = PegasusInterface()
    pg.initialize_world()
    world = pg.world
    await world.initialize_simulation_context_async()
    await world.reset_async()

    # 2. Load warehouse background
    try:
        from isaacsim.storage.native import get_assets_root_path
        assets_root = get_assets_root_path()
        if assets_root:
            pg.load_asset(
                assets_root + "/Isaac/Environments/Simple_Warehouse/warehouse_with_forklifts.usd",
                "/World/background",
            )
            carb.log_info("Warehouse loaded")
    except Exception as exc:
        carb.log_warn(f"Warehouse skipped: {exc}")

    await omni.kit.app.get_app().next_update_async()

    # 3. Scatter containers
    stage = omni.usd.get_context().get_stage()
    random.seed(42)
    loaded = 0

    spacing = 4.0
    cols = 5
    base_x, base_y = -6.0, -8.0

    for i, usd_path in enumerate(CONTAINERS):
        if not os.path.exists(usd_path):
            carb.log_warn(f"Prop not found: {usd_path}")
            continue

        row = i // cols
        col = i % cols
        x = base_x + col * spacing + random.uniform(-0.5, 0.5)
        y = base_y + row * spacing + random.uniform(-0.5, 0.5)

        prim_path = f"/World/container_prop_{i:03d}"
        prim = stage.DefinePrim(prim_path, "Xform")
        prim.GetReferences().AddReference(usd_path)

        xform = UsdGeom.Xformable(prim)
        xform.AddTranslateOp().Set(Gf.Vec3d(x, y, 0))
        loaded += 1

    carb.log_info(f"Scattered {loaded} container props")

    # 4. Load cranes
    cranes = [
        ("container_crane.usd", "/World/crane_cc", (-25, -20, 0), "/ContainerCrane"),
        ("transfer_crane.usd", "/World/crane_tc", (15, -15, 0), "/TransferCrane"),
    ]

    for filename, prim_path, pos, root_prim in cranes:
        full_path = os.path.join(CRANE_DIR, filename)
        if os.path.exists(full_path):
            prim = stage.DefinePrim(prim_path, "Xform")
            prim.GetReferences().AddReference(full_path, root_prim)
            UsdGeom.Xformable(prim).AddTranslateOp().Set(Gf.Vec3d(*pos))
            carb.log_info(f"Loaded crane: {filename}")

    await omni.kit.app.get_app().next_update_async()
    await world.reset_async()

    carb.log_info("Container harbor scene ready!")
    carb.log_info(f"  Props: {loaded} containers")
    carb.log_info(f"  Cranes: placed at outdoor positions")

# Schedule
asyncio.ensure_future(setup_scene())
```

Run it:
```bash
/isaac-sim/isaac-sim.sh --allow-root \
  --exec /workspace/aerial_ws/scripts/setup_container_harbor.py
```

---

## 6. Useful USD Commands (Command Line)

```bash
# Inspect a USD file's structure
usdcat /workspace/aerial_ws/assets/cranes/container_crane.usd | head -50

# Find the root prim name
usdcat file.usd | grep -E 'def (Xform|Scope|Mesh)' | head -5

# Check if a USD file has a defaultPrim
usdcat file.usd | grep defaultPrim

# List all prims in a stage
usdcat file.usd | grep 'def '
```

---

## 7. Scene Setup Checklist

- [ ] Extensions enabled: `pegasus.simulator`, `isaacsim.ros2.bridge`
- [ ] Physics context initialized (`initialize_simulation_context_async`)
- [ ] World reset after all loading (`world.reset_async`)
- [ ] All USD paths are absolute (not relative)
- [ ] Explicit `root_prim` passed to `AddReference` for files without `defaultPrim`
- [ ] `await next_update_async()` between major loading operations
- [ ] Props scattered with unique, descriptive prim paths
- [ ] Scene loads without console errors

## 8. Common Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Missing `root_prim` in AddReference | Prim created but empty (no children) | Pass explicit root prim path: `AddReference(path, "/RootPrimName")` |
| Relative USD paths | `FileNotFoundError` | Use absolute paths |
| No `next_update_async` after loading | Props invisible or physics not registered | Add `await app.next_update_async()` after loading |
| Loading assets before physics init | Crash or empty scene | Initialize physics context first |
| Overlapping prim paths | Props disappear or one overwrites another | Use unique prim paths like `/World/prop_{i:03d}` |
| Forgetting `world.reset_async()` | Physics state stale after loading | Call `await world.reset_async()` as final step |

---

## References

- USD Documentation: https://openusd.org/release/index.html
- Isaac Sim Core API: https://docs.isaacsim.omniverse.nvidia.com/6.0.0/
- SimReady Assets: https://developer.nvidia.com/omniverse/simready-assets
- pxr (Pixar USD Python): https://openusd.org/release/api/python_api.html
