#!/usr/bin/env python3
"""Inspect an extracted defect reference pack without importing Isaac Sim."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List


IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png"}
ASSET_EXTENSIONS = {".sldprt", ".usd", ".usdc"}
ANNOTATION_EXTENSIONS = {".json", ".txt", ".xml", ".yaml", ".yml"}


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _top_level(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    return relative.parts[0] if len(relative.parts) > 1 else "."


def _extension(path: Path) -> str:
    return path.suffix.lower().lstrip(".") or "<none>"


def _count_by_extension(paths: Iterable[Path]) -> Dict[str, int]:
    return dict(sorted(Counter(_extension(path) for path in paths).items()))


def _count_by_top_level(paths: Iterable[Path], root: Path) -> Dict[str, int]:
    return dict(sorted(Counter(_top_level(path, root) for path in paths).items()))


def _image_summary(paths: Iterable[Path]) -> Dict[str, Any]:
    from PIL import Image

    modes: Counter[str] = Counter()
    sizes: Counter[str] = Counter()
    count = 0
    for path in paths:
        try:
            with Image.open(path) as image:
                count += 1
                modes[image.mode] += 1
                sizes[f"{image.size[0]}x{image.size[1]}"] += 1
        except OSError:
            continue
    return {
        "count": count,
        "modes": dict(sorted(modes.items())),
        "sizes": dict(sorted(sizes.items())),
    }


def _candidate_defect_sources(paths: Iterable[Path], root: Path) -> Dict[str, int]:
    candidates: Counter[str] = Counter()
    for path in paths:
        parts = [part.lower() for part in path.relative_to(root).parts]
        if any("scratch" in part for part in parts):
            candidates["Scratch"] += 1
        if any("crack" in part for part in parts):
            candidates["Crack"] += 1
        if any("corrosion" in part or "rust" in part for part in parts):
            candidates["Corrosion"] += 1
        if any("spall" in part for part in parts):
            candidates["Spalling"] += 1
    return dict(sorted(candidates.items()))


def _annotation_candidates(paths: Iterable[Path]) -> Dict[str, int]:
    candidates: Counter[str] = Counter()
    for path in paths:
        suffix = path.suffix.lower()
        if suffix == ".txt":
            candidates["yolo_txt"] += 1
        elif suffix == ".json":
            candidates["json"] += 1
        elif suffix == ".xml":
            candidates["xml"] += 1
        elif suffix in {".yaml", ".yml"}:
            candidates["yaml"] += 1
    return dict(sorted(candidates.items()))


def _samples(paths: Iterable[Path], root: Path, limit: int = 12) -> List[str]:
    return [_relative(path, root) for path in sorted(paths)[:limit]]


def inspect_reference_pack(root: Path | str) -> Dict[str, Any]:
    """Return a deterministic summary for an extracted reference pack."""
    root_path = Path(root)
    files = sorted(path for path in root_path.rglob("*") if path.is_file())
    image_files = [path for path in files if path.suffix.lower() in IMAGE_EXTENSIONS]
    asset_files = [path for path in files if path.suffix.lower() in ASSET_EXTENSIONS]
    annotation_files = [path for path in files if path.suffix.lower() in ANNOTATION_EXTENSIONS]

    return {
        "root": str(root_path),
        "total_files": len(files),
        "extensions": _count_by_extension(files),
        "top_level": _count_by_top_level(files, root_path),
        "images": _image_summary(image_files),
        "candidate_defect_sources": _candidate_defect_sources(files, root_path),
        "annotation_candidates": _annotation_candidates(annotation_files),
        "asset_samples": _samples(asset_files, root_path),
        "image_samples": _samples(image_files, root_path),
        "annotation_samples": _samples(annotation_files, root_path),
    }


def format_summary(summary: Dict[str, Any]) -> str:
    """Render a stable JSON summary."""
    return json.dumps(summary, indent=2, sort_keys=True)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Extracted reference pack directory")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    print(format_summary(inspect_reference_pack(args.root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
