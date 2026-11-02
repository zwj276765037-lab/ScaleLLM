#!/usr/bin/env python3
"""Publish a readable subset of the sealed seven-rail evidence archive."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "0_Source/ScaleLLM_KV128_SevenRail_PMBus_20261102.zip"
DEST = ROOT / "docs/evidence/kv128_sevenrail_power"
TAG = "evidence-kv128-sevenrail-20261102"
PAGE = "https://github.com/zwj276765037-lab/ScaleLLM/releases/tag/" + TAG
BASE = "https://github.com/zwj276765037-lab/ScaleLLM/releases/download/" + TAG + "/"
EXPECTED = "d2ef53b5e14e940bc1277b9c079e517631920bc46f032212cd1495a9fcdfedb2"
with ARCHIVE.open("rb") as f:
    assert hashlib.file_digest(f, "sha256").hexdigest() == EXPECTED
selected = {
    "REPORT.md", "PACKAGE.md", "PACKAGE_MANIFEST.json",
    "results/summary.json", "results/window_summary.csv", "results/resolution.csv",
    "results/main_004_window_rail_v2.csv", "results/main_004_busy_by_opcode_layer_v2.csv",
    "results/main_004_busy_points_v2.csv", "results/main_004_commands_v2.csv",
    "results/main_004_sampler_independent.json",
    "native/main_004/receipt.json", "native/main_004/telemetry.json",
    "native/main_004/workload/workload.json", "native/main_004/workload/windows.jsonl",
    "native/identity_after_launcher.json", "native/identity_after/result.json",
    "provenance/main_004_transfer.json", "provenance/identity_transfer.json",
    "provenance/analysis_final_sha256.json",
    "source/design.md", "source/method_review.md", "source/workload_design.md", "source/results.md",
    "source/references/source_facts.md", "source/references/manifest.json",
    "source/references/main_004_independent_recompute.py", "source/references/main_004_independent_recompute.json",
}
with zipfile.ZipFile(ARCHIVE) as z:
    prefix = "kv128_repeat_sevenrail/"
    members = {n[len(prefix):] for n in z.namelist() if n.startswith(prefix)}
    selected |= {n for n in members if n.startswith("source/analysis_final/")}
    selected |= {n for n in members if n.startswith("results/main_004_v2_") and n.endswith(".png")}
    selected |= {"results/main_004_v2_" + n + ".svg" for n in ["summary", "busy_host", "common_coverage", "busy_conditional"]}
    assert selected <= members, selected - members
    records = []
    for name in sorted(selected):
        raw = z.read(prefix + name); published = raw
        if name.endswith(".md"):
            text = raw.decode("utf-8")
            def link(match):
                target = match.group(2)
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    return match.group(0)
                path = target.split("#", 1)[0]
                resolved = os.path.normpath(str(PurePosixPath(name).parent / path)).replace("\\", "/")
                if resolved in selected or resolved == "." or any(n.startswith(resolved.rstrip("/") + "/") for n in selected):
                    return match.group(0)
                to = os.path.relpath("DOWNLOADS.md", str(PurePosixPath(name).parent)).replace("\\", "/")
                return f"[{match.group(1)}]({to}#archive-files)"
            text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
            if name == "REPORT.md":
                lines = text.splitlines(keepends=True)
                lines.insert(1, "\n> 公开阅读版：数值与封存报告一致，仅调整链接。Git树包含精选表格、图和回执；完整16个正式原始文件及六类SVG在[Release证据包](DOWNLOADS.md)中。\n")
                text = "".join(lines)
            elif name == "PACKAGE.md":
                text = text.replace("# 下载包范围与复核\n", "# 下载包范围与复核\n\n> 以下说明针对完整Release ZIP；Git目录仅是阅读子集。请从[下载页](DOWNLOADS.md)取得完整包后运行下述解压复算命令。\n", 1)
            elif name == "source/analysis_final/README.md":
                text = text.replace("# Frozen offline analysis\n", "# Frozen offline analysis\n\n> These are archived instructions for the original local/ZIP layout. In a public Git checkout, use `python3 tools/release/verify_power_repeat_asset.py --download outputs/ScaleLLM_KV128_SevenRail_PMBus_20261102.zip --recompute` from the repository root. The raw JSONL inputs are in the Release archive, not this readable Git subset.\n", 1)
            published = text.encode("utf-8")
        p = DEST / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(published)
        records.append(dict(path=name, archive_member=prefix+name, source_bytes=len(raw),
                            source_sha256=hashlib.sha256(raw).hexdigest(), published_bytes=len(published),
                            published_sha256=hashlib.sha256(published).hexdigest(), markdown_links_adapted=raw != published))
asset = dict(schema="scalellm_kv128_sevenrail_release_asset_v1", asset_name=ARCHIVE.name,
             tag=TAG, release_page=PAGE, asset_url=BASE+ARCHIVE.name,
             sha256_sidecar_url=BASE+ARCHIVE.name+".sha256",
             validation_sidecar_url=BASE+ARCHIVE.stem+".validation.json",
             bytes=ARCHIVE.stat().st_size, sha256=EXPECTED, file_count=229,
             analysis_sha256="a00d62ac8031a1c3dd2b642f0804323c87429f5383106b5c48a2c57ff07f4bf7")
(DEST/"release_asset.json").write_text(json.dumps(asset, indent=2)+"\n")
(DEST/"PUBLICATION_MANIFEST.json").write_text(json.dumps({"schema":"scalellm_power_public_subset_v1", "archive_sha256":EXPECTED, "files":records}, indent=2)+"\n")
print(json.dumps({"files":len(records), "public_bytes":sum(r['published_bytes'] for r in records), "archive_bytes":asset['bytes']}))
