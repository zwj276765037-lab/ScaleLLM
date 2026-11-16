#!/usr/bin/env python3
"""Prepare the tested XDMA source from the pinned third-party mirror ZIP.

The caller obtains the source and applicable vendor licenses separately.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

from prepare_source import apply_unified_texts


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "public_source_manifest.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative_name(value):
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or ".." in path.parts
            or "\\" in value or ":" in value or path.as_posix() != value):
        raise ValueError("Invalid source path " + value)
    return value


def verify_sources(archive_path, manifest_path=MANIFEST):
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("schema") != "scalellm_xdma_public_source_v1":
        raise ValueError("Unsupported public source manifest")
    directory = manifest_path.parent
    archive_bytes = archive_path.read_bytes()
    archive = manifest["archive"]
    if len(archive_bytes) != archive["bytes"] or digest(archive_bytes) != archive["sha256"]:
        raise ValueError("Archive size/SHA256 differs from the fixed mirror")
    observed_path = directory / relative_name(manifest["observed_base_manifest"]["file"])
    observed_bytes = observed_path.read_bytes()
    if digest(observed_bytes) != manifest["observed_base_manifest"]["sha256"]:
        raise ValueError("Observed base identity manifest changed")
    observed = json.loads(observed_bytes)["files"]
    patches = []
    for item in manifest["patches"]:
        patch = (directory / relative_name(item["file"])).read_bytes()
        if digest(patch) != item["sha256"]:
            raise ValueError("Project patch identity changed " + item["file"])
        patches.append(patch.decode("utf-8"))
    if len(patches) != 2:
        raise ValueError("The bridge and IRQ policy patches are required")
    normalization = manifest["normalization"]
    bom_files = set(normalization["remove_utf8_bom_for"])
    final_lf_files = set(normalization["ensure_final_lf_for"])
    sources = {}
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Archive contains duplicate members")
        prefix = archive["prefix"]
        for member in names:
            relative_name(member.rstrip("/"))
            if not member.startswith(prefix):
                raise ValueError("Archive root differs")
        for name, expected in manifest["input_files"].items():
            relative_name(name)
            data = bundle.read(prefix + name)
            if len(data) != expected["bytes"] or digest(data) != expected["sha256"]:
                raise ValueError("Public source bytes differ " + name)
            if name in bom_files:
                if not data.startswith(b"\xef\xbb\xbf"):
                    raise ValueError("Expected UTF-8 BOM missing " + name)
                data = data[3:]
            text = data.decode("utf-8").replace("\r\n", "\n")
            if name in final_lf_files and not text.endswith("\n"):
                text += "\n"
            sources[name] = text
    if set(sources) != set(observed):
        raise ValueError("Public and observed source membership differs")
    bridged = apply_unified_texts(sources, patches[0])
    for name, expected in observed.items():
        if digest(bridged[name].encode("utf-8")) != expected["lf_sha256"]:
            raise ValueError("Bridge does not reproduce observed source " + name)
    final = apply_unified_texts(bridged, patches[1])
    outputs = {}
    for name, expected in manifest["final_files"].items():
        relative_name(name)
        data = final[name].encode("utf-8")
        if len(data) != expected["bytes"] or digest(data) != expected["sha256"]:
            raise ValueError("Final source differs from tested candidate " + name)
        outputs[name] = data
    receipt = dict(schema="scalellm_xdma_public_source_preparation_v1", status="PASS",
                   source_kind=manifest["source_kind"], repository=manifest["repository"],
                   commit=manifest["commit"], archive_sha256=archive["sha256"],
                   public_source_manifest_sha256=digest(manifest_bytes),
                   official_amd_archive_identity=manifest["official_amd_archive_identity"],
                   observed_base_files_matched=len(observed), final_files=manifest["final_files"],
                   normalization=normalization, patches=manifest["patches"],
                   driver_built=False, driver_installed=False, hardware_access=False)
    return outputs, receipt


def prepare(archive_path, output, manifest_path=MANIFEST):
    output = output.parent.resolve() / output.name
    if output.exists() or output.is_symlink():
        raise FileExistsError("Output must be a new directory")
    files, receipt = verify_sources(archive_path, manifest_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="." + output.name + "-", dir=output.parent) as temporary:
        staging = Path(temporary)
        for name, data in files.items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
        receipt.update(action="prepare", source_files_written=True)
        (staging / "source_preparation.json").write_text(json.dumps(receipt, indent=2) + "\n")
        if output.exists() or output.is_symlink():
            raise FileExistsError("Output appeared during source preparation")
        os.rename(staging, output)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect", "prepare"))
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        if args.output is None:
            parser.error("prepare requires --output")
        result = prepare(args.archive, args.output)
    else:
        if args.output is not None:
            parser.error("--output applies to prepare")
        _, result = verify_sources(args.archive)
        result.update(action="inspect", source_files_written=False)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
