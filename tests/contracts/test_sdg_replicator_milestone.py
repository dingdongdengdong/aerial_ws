import ast
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "sdg" / "replicator_defects.json"
SCRIPT = REPO / "scripts" / "isaac_sim_replicator_defects.py"
DOC = REPO / "docs" / "isaac-sim" / "04-synthetic-data.md"


class SDGReplicatorMilestoneContract(unittest.TestCase):
    def test_replicator_config_declares_issue_9_dataset_contract(self):
        self.assertTrue(CONFIG.exists(), f"{CONFIG} must exist")

        config = json.loads(CONFIG.read_text())

        self.assertEqual(["crack", "corrosion", "spalling"], config["classes"])
        self.assertEqual("nvcr.io/nvidia/isaac-sim:6.0.0", config["runtime"]["isaac_sim_image"])
        self.assertEqual("/workspace/aerial_ws", config["runtime"]["container_repo"])
        self.assertEqual("/isaac-sim/python.sh", config["runtime"]["isaac_python"])
        self.assertEqual("22", str(config["runtime"]["ros_domain_id"]))
        self.assertEqual(1000, config["generation"]["target_frames"])
        self.assertGreaterEqual(len(config["domain_randomization"]["lighting_modes"]), 3)
        self.assertGreaterEqual(len(config["domain_randomization"]["surface_materials"]), 2)
        self.assertEqual([5.0, 15.0], config["domain_randomization"]["camera_altitude_m"])

        outputs = config["outputs"]
        self.assertEqual("dataset/synthetic", outputs["root"])
        self.assertEqual("images", outputs["images"])
        self.assertEqual("masks", outputs["masks"])
        self.assertEqual("labels_yolo_seg", outputs["labels_yolo_seg"])
        self.assertEqual("metadata.jsonl", outputs["metadata"])

    def test_replicator_script_has_host_safe_helpers_and_runtime_markers(self):
        self.assertTrue(SCRIPT.exists(), f"{SCRIPT} must exist")

        source = SCRIPT.read_text()
        self.assertIn("omni.replicator.core", source)
        self.assertIn("semantic_segmentation", source)
        self.assertIn("instance_segmentation", source)
        self.assertIn("YoloWriter", source)
        self.assertIn("Replicator", source)

        spec = importlib.util.spec_from_file_location("replicator_defects", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        config = module.load_config(CONFIG)
        self.assertEqual(["crack", "corrosion", "spalling"], config["classes"])
        self.assertEqual(
            {
                "images": REPO / "dataset" / "synthetic" / "images",
                "masks": REPO / "dataset" / "synthetic" / "masks",
                "labels_yolo_seg": REPO / "dataset" / "synthetic" / "labels_yolo_seg",
                "metadata": REPO / "dataset" / "synthetic" / "metadata.jsonl",
            },
            module.output_paths(config, REPO),
        )

    def test_replicator_uniform_distribution_bounds_are_ordered(self):
        source = SCRIPT.read_text()
        tree = ast.parse(source)

        checked = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr != "uniform":
                continue
            if len(node.args) < 2:
                continue
            try:
                lower = ast.literal_eval(node.args[0])
                upper = ast.literal_eval(node.args[1])
            except ValueError:
                continue
            if not isinstance(lower, tuple) or not isinstance(upper, tuple):
                continue

            checked += 1
            self.assertEqual(len(lower), len(upper))
            for axis, (lower_value, upper_value) in enumerate(zip(lower, upper)):
                self.assertLessEqual(
                    lower_value,
                    upper_value,
                    f"uniform lower bound must be <= upper bound on axis {axis}: "
                    f"{lower} -> {upper}",
                )

        self.assertGreater(checked, 0, "expected to validate at least one tuple uniform call")

    def test_replicator_scene_sets_visibility_primitives(self):
        source = SCRIPT.read_text()

        self.assertIn("rep.create.light", source)
        self.assertIn('light_type="Dome"', source)
        self.assertIn('light_type="Sphere"', source)
        self.assertIn("look_at=", source)
        self.assertIn("(0.0, 0.0, 1.2)", source)
        self.assertIn("def _panel_layout", source)
        self.assertIn("(5.4, 0.10, 3.2)", source)
        self.assertIn("position=(0.0, -4.2, 1.45)", source)

    def test_replicator_postprocess_runs_before_simulation_app_close(self):
        source = SCRIPT.read_text()
        run_start = source.index("def run_replicator")
        run_end = source.index("def build_arg_parser")
        run_replicator_source = source[run_start:run_end]

        self.assertLess(
            run_replicator_source.index("postprocess_replicator_outputs"),
            run_replicator_source.index("simulation_app.close()"),
        )

    def test_replicator_cleanup_removes_generated_frames_but_keeps_metadata_jsonl(self):
        spec = importlib.util.spec_from_file_location("replicator_defects", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            for relative_path in [
                "rgb_0001.png",
                "semantic_segmentation_0001.png",
                "semantic_segmentation_labels_0001.json",
                "instance_segmentation_0001.png",
                "images/frame_000001.png",
                "masks/frame_000001.png",
                "labels_yolo_seg/frame_000001.txt",
                "metadata.txt",
            ]:
                path = output_dir / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("generated", encoding="utf-8")
            metadata = output_dir / "metadata.jsonl"
            metadata.write_text('{"event": "prepared"}\n', encoding="utf-8")

            module.clear_generated_frame_outputs(output_dir)

            self.assertEqual('{"event": "prepared"}\n', metadata.read_text())
            self.assertEqual([metadata], sorted(path for path in output_dir.rglob("*") if path.is_file()))

    def test_replicator_postprocess_builds_training_handoff_from_basic_writer_outputs(self):
        spec = importlib.util.spec_from_file_location("replicator_defects", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        config = module.load_config(CONFIG)

        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "dataset" / "synthetic"
            output_dir.mkdir(parents=True)

            Image.new("RGB", (4, 4), (20, 30, 40)).save(output_dir / "rgb_0000.png")
            mask = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
            for x in range(1, 3):
                for y in range(1, 3):
                    mask.putpixel((x, y), (255, 0, 0, 255))
            mask.save(output_dir / "semantic_segmentation_0000.png")
            (output_dir / "semantic_segmentation_labels_0000.json").write_text(
                json.dumps({"(255, 0, 0, 255)": {"class": "crack"}}),
                encoding="utf-8",
            )

            records = module.postprocess_replicator_outputs(config, output_dir, root)

            image_path = output_dir / "images" / "frame_000000.png"
            mask_path = output_dir / "masks" / "frame_000000.png"
            label_path = output_dir / "labels_yolo_seg" / "frame_000000.txt"
            self.assertTrue(image_path.exists())
            self.assertTrue(mask_path.exists())
            self.assertEqual(
                "0 0.250000 0.250000 0.500000 0.250000 "
                "0.500000 0.500000 0.250000 0.500000",
                label_path.read_text().strip(),
            )
            self.assertEqual(
                [
                    {
                        "frame": 0,
                        "image": "images/frame_000000.png",
                        "mask": "masks/frame_000000.png",
                        "label": "labels_yolo_seg/frame_000000.txt",
                        "classes": ["crack"],
                    }
                ],
                records,
            )

    def test_replicator_postprocess_rejects_black_rgb_frames(self):
        spec = importlib.util.spec_from_file_location("replicator_defects", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        config = module.load_config(CONFIG)

        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "dataset" / "synthetic"
            output_dir.mkdir(parents=True)

            Image.new("RGB", (4, 4), (0, 0, 0)).save(output_dir / "rgb_0000.png")

            with self.assertRaisesRegex(ValueError, "black RGB frame"):
                module.postprocess_replicator_outputs(config, output_dir, root)

    def test_docs_explain_no_crane_asset_replicator_run_and_nvidia_skill_choice(self):
        doc = DOC.read_text()

        self.assertIn("Issue #9", doc)
        self.assertIn("crack, corrosion, and spalling", doc)
        self.assertIn("physical-ai-defect-image-generation", doc)
        self.assertIn("No crane CAD is required for the first milestone batch", doc)
        self.assertIn("/isaac-sim/python.sh /workspace/aerial_ws/scripts/isaac_sim_replicator_defects.py", doc)
        self.assertIn("labels_yolo_seg", doc)
        self.assertIn("DefectDet_DemoPack_NVDA%401.0.1.zip", doc)
        self.assertIn("downloadable_packs.html", doc)
        self.assertIn("NVIDIA_API_KEY", doc)
        self.assertIn("inspect_defect_reference_pack.py", doc)
        self.assertIn("100 scratch decal PNGs", doc)
        self.assertIn("not a YOLO-labeled dataset", doc)

    def test_tracked_reference_docs_do_not_contain_raw_nvidia_api_keys(self):
        tracked_reference_files = [
            REPO / "AGENTS.md",
            REPO / ".env.example",
            DOC,
        ]

        for path in tracked_reference_files:
            self.assertNotIn("nv" + "api-", path.read_text(), f"{path} must not store raw API keys")


if __name__ == "__main__":
    unittest.main()
