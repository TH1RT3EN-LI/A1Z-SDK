#!/usr/bin/env python3
"""Convert the camera-bracket STEP source to a normalized binary STL."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "assets" / "camera_bracket" / "camera_bracket.step"
DEFAULT_OUTPUT = ROOT / "assets" / "camera_bracket" / "camera_bracket.stl"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--linear-tolerance-mm", type=float, default=0.02)
    parser.add_argument("--angular-tolerance-rad", type=float, default=0.1)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source = args.source.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"STEP source does not exist: {source}")
    if args.linear_tolerance_mm <= 0.0 or args.angular_tolerance_rad <= 0.0:
        raise SystemExit("meshing tolerances must be positive")

    try:
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.BRepGProp import BRepGProp
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        from OCP.GProp import GProp_GProps
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.StlAPI import StlAPI_Writer
        from OCP.STEPControl import STEPControl_Reader
        from OCP.gp import gp_Trsf, gp_Vec
    except ImportError as exc:
        raise SystemExit(
            "OpenCascade Python bindings are required; install cadquery-ocp "
            "for the Python version used to run this converter"
        ) from exc

    reader = STEPControl_Reader()
    status = reader.ReadFile(str(source))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"OpenCascade could not read STEP file: status={status}")
    transferred = reader.TransferRoots()
    if transferred < 1:
        raise RuntimeError("STEP file did not contain a transferable root")
    shape = reader.OneShape()

    source_box = Bnd_Box()
    BRepBndLib.Add_s(shape, source_box)
    source_bounds = source_box.Get()
    center_x = (source_bounds[0] + source_bounds[3]) * 0.5
    center_y = (source_bounds[1] + source_bounds[4]) * 0.5
    translation_mm = (-center_x, -center_y, -source_bounds[2])

    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(*translation_mm))
    normalized = BRepBuilderAPI_Transform(shape, transform, True).Shape()

    normalized_box = Bnd_Box()
    BRepBndLib.Add_s(normalized, normalized_box)
    normalized_bounds = normalized_box.Get()
    volume_properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(normalized, volume_properties)
    centroid = volume_properties.CentreOfMass()
    inertia = volume_properties.MatrixOfInertia()
    mesher = BRepMesh_IncrementalMesh(
        normalized,
        args.linear_tolerance_mm,
        False,
        args.angular_tolerance_rad,
        True,
    )
    mesher.Perform()
    if not mesher.IsDone():
        raise RuntimeError("OpenCascade failed to mesh the normalized bracket")

    output.parent.mkdir(parents=True, exist_ok=True)
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    if not writer.Write(normalized, str(output)):
        raise RuntimeError(f"OpenCascade failed to write STL: {output}")

    report = {
        "source": _portable_path(source),
        "source_sha256": _sha256(source),
        "output": _portable_path(output),
        "output_sha256": _sha256(output),
        "normalization": "center X/Y and place the minimum Z surface at zero",
        "normalization_translation_mm": list(translation_mm),
        "source_bbox_mm": {
            "min": list(source_bounds[:3]),
            "max": list(source_bounds[3:]),
        },
        "normalized_bbox_mm": {
            "min": list(normalized_bounds[:3]),
            "max": list(normalized_bounds[3:]),
        },
        "cad_volume_mm3": volume_properties.Mass(),
        "normalized_volume_centroid_mm": [
            centroid.X(),
            centroid.Y(),
            centroid.Z(),
        ],
        "uniform_density_inertia_about_centroid_mm5": [
            [inertia.Value(row, column) for column in range(1, 4)]
            for row in range(1, 4)
        ],
        "linear_tolerance_mm": args.linear_tolerance_mm,
        "angular_tolerance_rad": args.angular_tolerance_rad,
    }
    report_path = output.with_suffix(".conversion.json")
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
