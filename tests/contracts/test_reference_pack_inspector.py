import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "inspect_defect_reference_pack.py"


class ReferencePackInspectorContract(unittest.TestCase):
    def test_inspector_summarizes_reference_pack_structure(self):
        spec = importlib.util.spec_from_file_location("reference_pack_inspector", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Scratches").mkdir()
            (root / "validation_images" / "GroundTruth").mkdir(parents=True)
            (root / "labels").mkdir()
            Image.new("RGBA", (16, 16), (255, 0, 0, 128)).save(root / "Scratches" / "scratch_0.png")
            Image.new("RGB", (32, 24), (20, 30, 40)).save(
                root / "validation_images" / "GroundTruth" / "groundtruth_01.jpeg"
            )
            (root / "CarPanelDefects.usd").write_text("#usda 1.0\n", encoding="utf-8")
            (root / "labels" / "frame_000000.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")

            summary = module.inspect_reference_pack(root)

        self.assertEqual(4, summary["total_files"])
        self.assertEqual({"jpeg": 1, "png": 1, "txt": 1, "usd": 1}, summary["extensions"])
        self.assertEqual({"Scratches": 1, "validation_images": 1, "labels": 1, ".": 1}, summary["top_level"])
        self.assertEqual({"Scratch": 1}, summary["candidate_defect_sources"])
        self.assertEqual({"yolo_txt": 1}, summary["annotation_candidates"])
        self.assertEqual(
            {
                "count": 2,
                "modes": {"RGB": 1, "RGBA": 1},
                "sizes": {"16x16": 1, "32x24": 1},
            },
            summary["images"],
        )
        self.assertEqual(["CarPanelDefects.usd"], summary["asset_samples"])
        self.assertEqual(["Scratches/scratch_0.png"], summary["image_samples"][:1])

    def test_cli_prints_json_summary(self):
        spec = importlib.util.spec_from_file_location("reference_pack_inspector", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new("RGB", (8, 8), (1, 2, 3)).save(root / "sample.jpg")

            output = module.format_summary(module.inspect_reference_pack(root))

        parsed = json.loads(output)
        self.assertEqual(1, parsed["total_files"])
        self.assertEqual({"jpg": 1}, parsed["extensions"])


if __name__ == "__main__":
    unittest.main()
