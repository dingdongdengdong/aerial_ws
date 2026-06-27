import importlib.util
import json
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

    def test_docs_explain_no_crane_asset_replicator_run_and_nvidia_skill_choice(self):
        doc = DOC.read_text()

        self.assertIn("Issue #9", doc)
        self.assertIn("crack, corrosion, and spalling", doc)
        self.assertIn("physical-ai-defect-image-generation", doc)
        self.assertIn("No crane CAD is required for the first milestone batch", doc)
        self.assertIn("/isaac-sim/python.sh /workspace/aerial_ws/scripts/isaac_sim_replicator_defects.py", doc)
        self.assertIn("labels_yolo_seg", doc)


if __name__ == "__main__":
    unittest.main()
