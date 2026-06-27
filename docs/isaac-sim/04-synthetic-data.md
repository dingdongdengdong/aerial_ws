# 04 — Synthetic Data Generation

> **Goal**: Use Isaac Sim Replicator to generate synthetic training data for defect detection, with domain randomization and sim-to-real augmentation.

---

## Milestone Direction

This is the next project milestone after AAS unification. Keep AAS aircraft and
ground packages unchanged; SDG work belongs in this wrapper repo because it is
the Isaac Sim 6.0 replacement for the upstream AAS simulation role.

Use a new branch:

```bash
git switch -c feature/sdg-replicator-milestone
```

Initial success target:
- Generate a small synthetic inspection dataset from Isaac Sim/Omniverse Replicator.
- Include RGB images and labels for defects such as crack, corrosion, and spalling.
- Keep outputs under ignored `dataset/synthetic/`.
- Provide a command that runs inside `nvcr.io/nvidia/isaac-sim:6.0.0`.

Issue #9 is the active SDG target. No crane CAD is required for the first milestone batch.
Use Isaac/Omniverse metal or concrete inspection surfaces, then swap in crane
USD later when it is available. The selected class order is `crack`,
`corrosion`, `spalling`.

NVIDIA skills installed for this repo:

```bash
npx skills add nvidia/skills --full-depth \
  --skill data-designer \
  --skill physical-ai-defect-image-generation \
  -y
```

Use `physical-ai-defect-image-generation` as defect taxonomy and data handoff
guidance, not as the runtime. That NVIDIA skill is oriented around OSMO/Cosmos
AnomalyGen flows; this repository's runtime remains local Isaac Sim 6.0 with
Omniverse Replicator.

Reference data and credentials:

- User-provided defect demo pack:
  `https://d4i3qtqj3r0z5.cloudfront.net/DefectDet_DemoPack_NVDA%401.0.1.zip`
  (HTTP `Content-Length` observed as `341975385` bytes on 2026-06-28).
- Official Omniverse USD downloadable packs:
  `https://docs.omniverse.nvidia.com/usd/latest/usd_content_samples/downloadable_packs.html`.
- Store NVIDIA API credentials in ignored `.env` files as `NVIDIA_API_KEY`.
  Do not put raw NVIDIA API key values in tracked docs, code, tests, or commits.

Milestone config:

```bash
/workspace/aerial_ws/configs/sdg/replicator_defects.json
```

Smoke run inside the Isaac Sim 6.0 container:

```bash
cd /workspace/aerial_ws
export ROS_DOMAIN_ID=22

/isaac-sim/python.sh /workspace/aerial_ws/scripts/isaac_sim_replicator_defects.py \
  --config /workspace/aerial_ws/configs/sdg/replicator_defects.json \
  --num-frames 50 \
  --output-dir /workspace/aerial_ws/dataset/synthetic
```

Full Issue #9 target:

```bash
/isaac-sim/python.sh /workspace/aerial_ws/scripts/isaac_sim_replicator_defects.py \
  --config /workspace/aerial_ws/configs/sdg/replicator_defects.json \
  --num-frames 1000 \
  --output-dir /workspace/aerial_ws/dataset/synthetic
```

Expected output contract:

```text
dataset/synthetic/
├── images/
├── masks/
├── labels_yolo_seg/
└── metadata.jsonl
```

`labels_yolo_seg` is the training handoff target. Replicator segmentation masks
are the source of truth; YOLO-seg polygons should be regenerated from masks if
writer formats change.

The current scaffold uses Replicator `BasicWriter` outputs as raw artifacts,
then post-processes them into the stable handoff layout:

- `rgb_*.png` -> `images/frame_*.png`
- `semantic_segmentation_*.png` -> `masks/frame_*.png`
- `semantic_segmentation_labels_*.json` + mask pixels -> `labels_yolo_seg/frame_*.txt`

If a frame has no recognized defect-class pixels, the label file is intentionally
empty. This keeps image/label cardinality stable while making semantic tagging
issues visible during validation.

---

## 1. Isaac Sim Replicator Overview

Replicator is Isaac Sim's built-in framework for generating synthetic datasets. It provides:

- **Randomizers**: Vary scene parameters (lighting, materials, camera pose, defects)
- **Annotators**: Generate ground truth (bounding boxes, segmentation masks, depth, normals)
- **Writers**: Output data in standard formats (YOLO, COCO, KITTI)
- **Graph-based API**: Compose randomizers and annotators into pipelines

Official docs: https://docs.isaacsim.omniverse.nvidia.com/6.0.0/replicator_tutorials/index.html

### Replicator Pipeline Pattern

```
Scene Setup → Register Randomizers → Attach Annotators → Create Writer → Generate Frames
```

## 2. Basic Replicator Script

```python
#!/usr/bin/env python3
"""
Minimal Replicator script for synthetic data generation.
Run with: /isaac-sim/isaac-sim.sh --allow-root -p this_script.py
"""

from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})

import omni.replicator.core as rep

# ── 1. Scene setup ──────────────────────────────────────────
def setup_scene():
    """Create the inspection scene."""
    # Load a container yard scene
    scene = rep.create.from_usd("assets/container_harbor.usd")

    # Create a camera rig
    camera = rep.create.camera(
        position=(5, -2, 8),
        rotation=(0, -90, 0),  # Down-facing
        focal_length=24,
    )
    return scene, camera

# ── 2. Domain randomizers ───────────────────────────────────
def randomize_lighting():
    """Randomize lighting conditions."""
    with rep.randomizer.light():
        rep.randomizer.light(
            intensity=rep.distribution.uniform(100, 5000),
            color_temp=rep.distribution.uniform(2000, 8000),
        )

def randomize_sky():
    """Randomize background sky."""
    with rep.randomizer.sky():
        rep.randomizer.sky(
            type=rep.distribution.choice(["clear", "cloudy", "overcast", "sunset"]),
            sun_angle=rep.distribution.uniform(15, 75),
        )

def randomize_camera_pose():
    """Randomize camera position around the scene."""
    with rep.randomizer.camera_pose():
        rep.randomizer.camera_pose(
            position=rep.distribution.uniform(
                (-3, -2, 2), (3, 2, 10)
            ),
            look_at=rep.distribution.uniform(
                (-1, -1, 0), (1, 1, 3)
            ),
        )

# ── 3. Build the generation graph ───────────────────────────
def build_graph():
    scene, camera = setup_scene()

    # Register randomizers
    rep.randomizer.register(randomize_lighting)
    rep.randomizer.register(randomize_sky)
    rep.randomizer.register(randomize_camera_pose)

    # Create writers
    yolo_writer = rep.writers.get("YoloWriter")
    yolo_writer.initialize(
        output_dir="dataset/synthetic",
        class_mapping={
            "crack": 0,
            "corrosion": 1,
            "paint_damage": 2,
        },
    )

    coco_writer = rep.writers.get("CocoWriter")
    coco_writer.initialize(
        output_dir="dataset/synthetic_coco",
    )

    # Attach writers to the camera
    rep.orchestrator.step(yolo_writer, [camera])
    rep.orchestrator.step(coco_writer, [camera])

    return yolo_writer

# ── 4. Generate ─────────────────────────────────────────────
writer = build_graph()

for i in range(1000):
    rep.orchestrator.step()
    if i % 100 == 0:
        print(f"Generated {i}/1000 frames")

writer.close()
print("Dataset generation complete!")
simulation_app.close()
```

## 3. Domain Randomization Categories

### 3a. Defect Randomization (Crack, Corrosion, Paint Damage)

```python
def randomize_defects():
    """Create varied structural defects on container surfaces."""
    with rep.randomizer.defects():
        # Cracks
        rep.randomizer.crack(
            length=rep.distribution.uniform(0.02, 0.5),
            width=rep.distribution.uniform(0.001, 0.01),
            orientation=rep.distribution.uniform(0, 360),
            position=rep.distribution.uniform(
                (-2, -1, 0.5), (2, 1, 3)
            ),
            material="metal_crack",
        )

        # Corrosion patches
        rep.randomizer.corrosion(
            density=rep.distribution.uniform(0.1, 0.8),
            color_palette="rust",
            patch_size=rep.distribution.uniform(0.1, 0.5),
        )

        # Paint damage (scratches, chips)
        rep.randomizer.paint_damage(
            scratch_length=rep.distribution.uniform(0.05, 0.3),
            scratch_width=rep.distribution.uniform(0.002, 0.01),
            chip_density=rep.distribution.uniform(0.01, 0.1),
        )
```

### 3b. Environment Randomization (Lighting, Weather)

```python
def randomize_environment():
    """Vary lighting, weather, and atmospheric conditions."""
    with rep.randomizer.environment():
        # Sky and sun
        rep.randomizer.sky(
            type=rep.distribution.choice([
                "clear", "cloudy", "overcast", "sunset", "night"
            ]),
            sun_angle=rep.distribution.uniform(15, 75),
        )

        # Weather effects
        rep.randomizer.weather(
            rain=rep.distribution.choice([0, 0.3, 0.6]),
            fog=rep.distribution.uniform(0, 0.5),
            dust=rep.distribution.uniform(0, 0.2),
        )
```

### 3c. Camera Randomization (Noise, Lens Effects)

```python
def randomize_camera():
    """Simulate real camera imperfections."""
    with rep.randomizer.camera():
        # Camera pose variation
        rep.randomizer.camera_pose(
            position=rep.distribution.uniform(
                (-3, -2, 1), (3, 2, 5)
            ),
            look_at=rep.distribution.uniform(
                (-1, -1, 0), (1, 1, 2)
            ),
        )

        # Lens effects
        rep.randomizer.lens_effects(
            motion_blur=rep.distribution.uniform(0, 0.3),
            chromatic_aberration=rep.distribution.uniform(0, 0.02),
            vignette=rep.distribution.uniform(0, 0.3),
            distortion=rep.distribution.uniform(-0.1, 0.1),
        )

        # Sensor noise
        rep.randomizer.sensor_noise(
            gaussian=rep.distribution.uniform(0, 0.02),
            shot_noise=rep.distribution.uniform(0, 0.01),
            quantization=rep.distribution.choice([8, 10, 12]),
        )
```

## 4. Output Formats

### YOLO Format

```
dataset/synthetic/
├── images/
│   ├── frame_000000.png
│   ├── frame_000001.png
│   └── ...
└── labels/
    ├── frame_000000.txt   # class_id x_center y_center width height
    ├── frame_000001.txt
    └── ...
```

### COCO Format

```python
# COCO writer includes segmentation masks automatically
coco_writer = rep.writers.get("CocoWriter")
coco_writer.initialize(output_dir="dataset/synthetic_coco")

# Output:
# dataset/synthetic_coco/
# ├── images/
# ├── annotations/
# │   └── instances.json  # COCO-format annotations
# └── masks/              # Per-instance masks
```

### Segmentation Masks

```python
# Access semantic segmentation directly
semantic_annotator = rep.AnnotatorRegistry.get_annotator("semantic_segmentation")

# Instance segmentation (separate instances)
instance_annotator = rep.AnnotatorRegistry.get_annotator("instance_id_segmentation")

# 3D bounding boxes
bbox3d_annotator = rep.AnnotatorRegistry.get_annotator("bounding_box_3d")

# Depth maps
depth_annotator = rep.AnnotatorRegistry.get_annotator("distance_to_camera")
```

## 5. Replicator Graph Pattern (Complete)

```python
def build_complete_replicator_pipeline():
    """Production-ready Replicator graph with all randomizers."""

    # 1. Create scene
    with rep.new_layer():
        # Define the environment
        camera = rep.create.camera(position=(5, -2, 8), rotation=(0, -90, 0))

        # 2. Register all randomizers
        rep.randomizer.register(randomize_defects)
        rep.randomizer.register(randomize_environment)
        rep.randomizer.register(randomize_camera)

        # 3. Attach annotators to camera
        rp = rep.create.render_product(camera, (640, 640))

        # Attach multiple annotators
        rep.orchestrator.attach(rp, [
            rep.AnnotatorRegistry.get_annotator("rgb"),
            rep.AnnotatorRegistry.get_annotator("semantic_segmentation"),
            rep.AnnotatorRegistry.get_annotator("instance_id_segmentation"),
            rep.AnnotatorRegistry.get_annotator("bounding_box_2d_tight"),
            rep.AnnotatorRegistry.get_annotator("distance_to_camera"),
        ])

        # 4. Create writer
        writer = rep.writers.get("BasicWriter")
        writer.initialize(
            output_dir="dataset/full",
            rgb=True,
            semantic_segmentation=True,
            instance_segmentation=True,
            bounding_box_2d_tight=True,
            distance_to_camera=True,
        )

        # 5. Orchestrate
        rep.orchestrator.step(writer, [camera])

    return writer
```

## 6. Cosmos Transfer 2.5 Integration

NVIDIA Cosmos Transfer 2.5 can convert synthetic images to more photorealistic ones, reducing the sim-to-real gap. This is useful when your synthetic data doesn't quite match real drone footage.

Reference: https://github.com/nvidia-cosmos/cosmos-transfer2.5

### Conceptual Integration

```python
# Step 1: Generate synthetic dataset with Replicator
generate_synthetic_dataset(frames=10000)

# Step 2: Apply Cosmos Transfer style transfer
# (conceptual — exact API depends on Cosmos Transfer release)
from cosmos_transfer import CosmosTransferModel

model = CosmosTransferModel.from_pretrained("nvidia/cosmos-transfer-2.5")

for img_path in synthetic_images:
    synthetic = load_image(img_path)
    realistic = model.transfer(
        synthetic,
        target_domain="aerial_drone_inspection",
        strength=0.7,  # 0.0 = pure synthetic, 1.0 = max realism
    )
    save_image(realistic, img_path.replace("synthetic", "augmented"))

# Step 3: Train on the augmented dataset
# The augmented images look more like real drone footage
```

> **When to use**: If your model trained on pure synthetic data performs poorly on real images, Cosmos Transfer can help bridge the gap. It's an optional augmentation step, not needed if your domain randomization is sufficiently effective.

## 7. Running Replicator Scripts

### Headless (Production)

```bash
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 &

/isaac-sim/isaac-sim.sh --allow-root -p \
  /workspace/aerial_ws/scripts/generate_synthetic.py
```

### With GUI (Development)

```bash
export DISPLAY=:1

# Launch Isaac Sim first
/isaac-sim/isaac-sim.sh --allow-root

# Then run via --exec (for visual debugging)
/isaac-sim/isaac-sim.sh --allow-root \
  --exec /workspace/aerial_ws/scripts/generate_synthetic_exec.py
```

## 8. Annotator Reference

| Annotator | Output | Use Case |
|---|---|---|
| `rgb` | Color image RGBA | Training input |
| `semantic_segmentation` | Per-pixel class labels | Defect detection masks |
| `instance_id_segmentation` | Per-instance IDs | Separate individual defects |
| `bounding_box_2d_tight` | Tight 2D boxes | Object detection labels |
| `bounding_box_3d` | 3D boxes | 3D defect localization |
| `distance_to_camera` | Depth map (meters) | Depth estimation, VSLAM |
| `normals` | Surface normals | Material analysis |
| `pointcloud` | 3D point cloud | SfM, point cloud registration |

## 9. Common Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Running Replicator with `--exec` | `SimulationApp not found` | Use `-p` flag (standalone, not --exec) |
| Missing `headless: True` in SimulationApp | GUI opens even in batch mode | Pass `{"headless": True}` to SimulationApp |
| No X server in headless mode | Display errors | Use `Xvfb :99` for virtual display |
| Writer not closed | Corrupted output files | Always call `writer.close()` |
| Wrong class mapping | Labels don't match model classes | Double-check class IDs in YoloWriter config |
| GPU out of memory | Crash during generation | Reduce camera resolution or batch size |
| Randomizer not registered | No variation in output | `rep.randomizer.register(my_func)` BEFORE generating |

## 10. Dataset Generation Checklist

- [ ] Scene loaded correctly (check console output)
- [ ] Cameras positioned and oriented correctly
- [ ] Randomizers registered
- [ ] Annotators attached to render products
- [ ] Writer initialized with correct output directory
- [ ] Class mapping matches your model's class order
- [ ] Generated a small test batch (10 frames) first
- [ ] Verified output images look correct
- [ ] Checked labels match visible objects
- [ ] Scaled up to full dataset

---

**Next**: [05-pitfalls.md](05-pitfalls.md) — Avoid the most common Isaac Sim / Pegasus errors.

## References

- Replicator Tutorials: https://docs.isaacsim.omniverse.nvidia.com/6.0.0/replicator_tutorials/index.html
- Replicator API Reference: https://docs.omniverse.nvidia.com/kit/docs/replicator/latest/
- Cosmos Transfer 2.5: https://github.com/nvidia-cosmos/cosmos-transfer2.5
