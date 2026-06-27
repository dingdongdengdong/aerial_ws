#!/usr/bin/env python3
"""Isaac Sim 6.0 Replicator SDG scaffold for Issue #9 defect segmentation.

Run inside the Isaac Sim 6.0 container:

    ROS_DOMAIN_ID=22 /isaac-sim/python.sh \
      /workspace/aerial_ws/scripts/isaac_sim_replicator_defects.py \
      --config /workspace/aerial_ws/configs/sdg/replicator_defects.json \
      --num-frames 50 \
      --output-dir /workspace/aerial_ws/dataset/synthetic

The module keeps imports host-safe so contract tests can validate config and
output layout without Isaac Sim installed. Isaac/Omniverse imports happen only
inside run_replicator().
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_CONFIG = REPO_ROOT / "configs" / "sdg" / "replicator_defects.json"


def load_config(path: Path | str = DEFAULT_CONFIG) -> Dict[str, Any]:
    """Load the SDG JSON config and validate the fields this script requires."""
    config_path = Path(path)
    config = json.loads(config_path.read_text())

    required_top_level = {"classes", "runtime", "generation", "domain_randomization", "outputs"}
    missing = required_top_level.difference(config)
    if missing:
        raise ValueError(f"{config_path} is missing required keys: {sorted(missing)}")

    if config["classes"] != ["crack", "corrosion", "spalling"]:
        raise ValueError("Issue #9 class order must be: crack, corrosion, spalling")

    return config


def output_paths(config: Mapping[str, Any], repo_root: Path = REPO_ROOT) -> Dict[str, Path]:
    """Return concrete output paths for the configured dataset layout."""
    root = repo_root / config["outputs"]["root"]
    return {
        "images": root / config["outputs"]["images"],
        "masks": root / config["outputs"]["masks"],
        "labels_yolo_seg": root / config["outputs"]["labels_yolo_seg"],
        "metadata": root / config["outputs"]["metadata"],
    }


def ensure_output_layout(config: Mapping[str, Any], repo_root: Path = REPO_ROOT) -> Dict[str, Path]:
    """Create the dataset directories that are safe to create outside Isaac."""
    paths = output_paths(config, repo_root)
    for key, path in paths.items():
        if key == "metadata":
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
    return paths


def class_mapping(classes: Iterable[str]) -> Dict[str, int]:
    """Return the stable class-name to class-id map used by YOLO labels."""
    return {name: idx for idx, name in enumerate(classes)}


def bbox_polygon_from_mask_pixels(
    pixels: Iterable[Tuple[int, int]],
    image_width: int,
    image_height: int,
) -> List[float]:
    """Convert mask pixels to a normalized rectangular YOLO-seg polygon.

    This is a conservative fallback for converting Replicator mask artifacts to
    YOLO-seg labels. A later training step can replace it with contour tracing
    if the writer emits richer instance masks.
    """
    coords = list(pixels)
    if not coords:
        return []

    xs = [x for x, _ in coords]
    ys = [y for _, y in coords]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    return [
        min_x / image_width,
        min_y / image_height,
        max_x / image_width,
        min_y / image_height,
        max_x / image_width,
        max_y / image_height,
        min_x / image_width,
        max_y / image_height,
    ]


def write_metadata_record(metadata_path: Path, record: Mapping[str, Any]) -> None:
    """Append one JSONL metadata record."""
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with metadata_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")


def _start_simulation_app(headless: bool) -> Any:
    from isaacsim import SimulationApp

    return SimulationApp({"headless": headless})


def _surface_material(rep: Any, material_name: str) -> Any:
    colors = {
        "painted_steel": (0.35, 0.42, 0.48),
        "rusted_steel": (0.55, 0.24, 0.08),
        "bare_concrete": (0.45, 0.45, 0.42),
    }
    return rep.create.material_omnipbr(
        diffuse=colors.get(material_name, (0.4, 0.4, 0.4)),
        roughness=0.75,
        metallic=0.4 if "steel" in material_name else 0.0,
    )


def _defect_material(rep: Any, class_name: str) -> Any:
    colors = {
        "crack": (0.02, 0.02, 0.018),
        "corrosion": (0.75, 0.26, 0.04),
        "spalling": (0.62, 0.58, 0.50),
    }
    return rep.create.material_omnipbr(
        diffuse=colors[class_name],
        roughness=0.92,
        metallic=0.0,
    )


def _build_scene(rep: Any, config: Mapping[str, Any], output_dir: Path) -> Tuple[Any, Any]:
    """Build a no-crane-required inspection scene with semantic defect proxies."""
    width, height = config["generation"]["resolution"]
    materials = config["domain_randomization"]["surface_materials"]
    altitude_min, altitude_max = config["domain_randomization"]["camera_altitude_m"]
    pitch_min, pitch_max = config["domain_randomization"]["camera_pitch_deg"]
    scale_min, scale_max = config["domain_randomization"]["defect_scale_m"]

    with rep.new_layer():
        surface_nodes = []
        for idx, material_name in enumerate(materials):
            x = (idx - 1) * 2.8
            panel = rep.create.cube(position=(x, 0.0, 1.2), scale=(2.4, 0.08, 1.4))
            with panel:
                rep.modify.semantics([("class", "inspection_surface")])
                rep.modify.material(_surface_material(rep, material_name))
            surface_nodes.append(panel)

        for idx, class_name in enumerate(config["classes"]):
            defect = rep.create.cube(
                position=rep.distribution.uniform((-2.6, -0.12, 0.4), (2.6, -0.08, 1.9)),
                rotation=rep.distribution.uniform((0, 0, 0), (0, 0, 360)),
                scale=rep.distribution.uniform((scale_min, 0.012, 0.015), (scale_max, 0.02, 0.08)),
            )
            with defect:
                rep.modify.semantics([("class", class_name)])
                rep.modify.material(_defect_material(rep, class_name))

        camera = rep.create.camera(
            position=rep.distribution.uniform((-3.0, -5.5, altitude_min), (3.0, -4.0, altitude_max)),
            rotation=rep.distribution.uniform((pitch_min, 0, -20), (pitch_max, 0, 20)),
            focal_length=24,
        )
        render_product = rep.create.render_product(camera, (width, height))

        rgb = rep.AnnotatorRegistry.get_annotator("rgb")
        semantic_segmentation = rep.AnnotatorRegistry.get_annotator("semantic_segmentation")
        instance_segmentation = rep.AnnotatorRegistry.get_annotator("instance_segmentation")
        render_product.annotators = [rgb, semantic_segmentation, instance_segmentation]

        basic_writer = rep.writers.get("BasicWriter")
        basic_writer.initialize(
            output_dir=str(output_dir),
            rgb=True,
            semantic_segmentation=True,
            instance_segmentation=True,
        )
        basic_writer.attach([render_product])

        # Keep a YoloWriter in the graph for bbox labels while masks remain the
        # source of truth for labels_yolo_seg conversion.
        try:
            yolo_writer = rep.writers.get("YoloWriter")
            yolo_writer.initialize(
                output_dir=str(output_dir / "labels_yolo_bbox"),
                class_mapping=class_mapping(config["classes"]),
            )
            yolo_writer.attach([render_product])
        except Exception as exc:  # pragma: no cover - Isaac runtime dependent
            print(f"YoloWriter unavailable, continuing with masks only: {exc}")

    return camera, render_product


def run_replicator(config: Mapping[str, Any], num_frames: int, output_dir: Path, headless: bool) -> None:
    """Run Isaac Sim Replicator. Requires /isaac-sim/python.sh."""
    os.environ.setdefault("ROS_DOMAIN_ID", str(config["runtime"]["ros_domain_id"]))

    simulation_app = _start_simulation_app(headless)
    try:
        import omni.replicator.core as rep

        output_dir.mkdir(parents=True, exist_ok=True)
        _build_scene(rep, config, output_dir)

        for frame in range(num_frames):
            rep.orchestrator.step()
            if frame % 25 == 0:
                print(f"Replicator generated {frame}/{num_frames} frames")

        rep.orchestrator.wait_until_complete()
    finally:
        simulation_app.close()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--num-frames", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Validate config and create output directories without launching Isaac Sim.",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    config = load_config(args.config)
    num_frames = args.num_frames or int(config["generation"]["smoke_test_frames"])
    output_dir = args.output_dir or args.repo_root / config["outputs"]["root"]

    paths = ensure_output_layout(config, args.repo_root)
    write_metadata_record(
        paths["metadata"],
        {
            "event": "prepared",
            "classes": config["classes"],
            "num_frames": num_frames,
            "runtime": config["runtime"]["isaac_sim_image"],
            "output_dir": str(output_dir),
        },
    )

    if args.prepare_only:
        print(f"Prepared Replicator output layout at {output_dir}")
        return 0

    run_replicator(config, num_frames, output_dir, args.headless)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
