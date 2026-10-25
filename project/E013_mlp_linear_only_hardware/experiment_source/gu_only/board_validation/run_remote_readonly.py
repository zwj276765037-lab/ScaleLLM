#!/usr/bin/env python3
"""Run an audited read-only PowerShell probe over the existing SSH alias.

No remote files are written. Scripts are passed using UTF-16LE EncodedCommand,
and subprocess argv keeps PowerShell quoting away from the local shell.
"""

import argparse
import base64
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zlib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe", choices=["device", "tools", "interfaces", "project"])
    parser.add_argument("--host", default="hap-dell")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--show-data", action="store_true")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    experiment = source.parents[2]
    output_root = args.output_root or experiment / "experiment_results/board_validation/host_preflight"
    script_path = source / ("probe_" + args.probe + ".ps1")
    script = script_path.read_text(encoding="utf-8")
    compressor = zlib.compressobj(level=9, wbits=-15)
    compressed = compressor.compress(script.encode("utf-8")) + compressor.flush()
    payload = base64.b64encode(compressed).decode("ascii")
    bootstrap = ("$b=[Convert]::FromBase64String('" + payload + "');"
                 "$m=New-Object IO.MemoryStream(,$b);"
                 "$d=New-Object IO.Compression.DeflateStream($m,[IO.Compression.CompressionMode]::Decompress);"
                 "$r=New-Object IO.StreamReader($d,[Text.Encoding]::UTF8);"
                 "& ([ScriptBlock]::Create($r.ReadToEnd()))")
    encoded = base64.b64encode(bootstrap.encode("utf-16le")).decode("ascii")
    argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", args.host,
            "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
            "-EncodedCommand", encoded]
    started = dt.datetime.now(dt.timezone.utc)
    run_dir = output_root / (started.strftime("%Y%m%dT%H%M%S.%fZ") + "_" + args.probe)
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / script_path.name).write_text(script, encoding="utf-8")
    (run_dir / "encoded_bootstrap.ps1").write_text(bootstrap, encoding="utf-8")
    timed_out = False
    try:
        process = subprocess.run(argv, capture_output=True, timeout=args.timeout, check=False)
        stdout, stderr, returncode = process.stdout, process.stderr, process.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, returncode = exc.stdout or b"", exc.stderr or b"", None
        timed_out = True
    ended = dt.datetime.now(dt.timezone.utc)
    for name, data in [("stdout", stdout), ("stderr", stderr)]:
        (run_dir / (name + ".bin")).write_bytes(data)
        try:
            decoded = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            decoded = data.decode("cp936", errors="replace")
        (run_dir / (name + ".txt")).write_text(decoded, encoding="utf-8")
    parsed = None
    parse_error = None
    try:
        parsed = json.loads(stdout.decode("utf-8-sig"))
        (run_dir / "data.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        parse_error = str(exc)
    manifest = {
        "schema": 1, "scope": "read-only Windows host preflight; no hardware operations",
        "runtime_id": "/root/board_host_prepare", "probe": args.probe,
        "started_utc": started.isoformat(), "ended_utc": ended.isoformat(),
        "host_alias": args.host, "transport": "ssh argv + PowerShell UTF-16LE EncodedCommand; in-memory Deflate UTF-8 probe",
        "script": script_path.name, "script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
        "argv_without_encoded_script": argv[:-1] + ["<UTF16LE_BASE64_OF_SAVED_SCRIPT>"],
        "exit_code": returncode, "timeout": timed_out, "timeout_seconds": args.timeout,
        "json_parse_error": parse_error,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": str(run_dir), "exit_code": returncode, "timeout": timed_out,
                      "json_parse_error": parse_error, "data": parsed if args.show_data else "saved in data.json"}, ensure_ascii=False, indent=2))
    return 1 if timed_out or returncode != 0 or parse_error else 0


if __name__ == "__main__":
    sys.exit(main())
