#!/usr/bin/env python3
"""Reproducible, resource-bounded CPU evidence for the A023 Host module."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
BASE = Path(__file__).resolve().parent
STAMP = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
RUN = BASE / ("AT_" + STAMP)
RUN.mkdir()
CPUS = sorted(os.sched_getaffinity(0))[:8]
LIMIT_RSS = 96 * 1024**3
MIN_AVAILABLE = 64 * 1024**3

def memory_available():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("MemAvailable unavailable")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

env = dict(os.environ, PYTHONPATH=str(ROOT / "project/hardware"),
           PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1",
           OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
command = [sys.executable, "-B", "-m", "unittest", "discover", "-s",
           "project/hardware/tests", "-p", "test_scalellm_mlp_linear.py", "-v"]
sources = ["project/hardware/host/scalellm_mlp_linear.py",
           "project/hardware/tests/test_scalellm_mlp_linear.py",
           "project/hardware/model/fixbit_v2.py", "project/hardware/model/mlp_fixed.py",
           "project/hardware/host/scalellm_hostops.py", "project/hardware/host/scalellm_memory.py",
           "project/hardware/host/scalellm_runtime.py", "project/hardware/data/mlp_silu_q16.mem",
           "project/hardware/source/mlp_linear/design.md", "project/hardware/source/mlp_linear/abi.json",
           "PRO_plan/ScaleLLM_MLP_Linear_Only_Dual_DDR_Design.md"]
manifest = {"started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "root": str(ROOT), "command": command, "cwd": str(ROOT),
            "environment": {key: env[key] for key in ("PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
            "python": sys.version, "python_executable": sys.executable,
            "platform": platform.platform(), "cpus": CPUS,
            "resource_limits": {"cpu_count_max":8, "rss_bytes_max": LIMIT_RSS, "system_available_bytes_min": MIN_AVAILABLE},
            "mem_available_before": memory_available(),
            "sources_sha256": {path: sha(ROOT / path) for path in sources},
            "rng": {"generator": "numpy.random.default_rng/PCG64", "seeds": [6001,6002,6003,6010,6011,6020,6021,6030]},
            "reference": "Independent old fixbit_v2/mlp_fixed Python integer math and direct scalar byte indices; frozen 8192-entry SiLU ROM plus implicit top endpoint",
            "applicability": "CPU boundary/codec, synthetic cohort16; no real model 32-layer, RTL, EDA, GPU, or board result"}
for name in sources[:4]:
    shutil.copy2(ROOT / name, RUN / Path(name).name)
manifest["runner_sha256"] = sha(Path(__file__))
if manifest["mem_available_before"] < MIN_AVAILABLE:
    manifest.update(exit_code=None, stop_reason="system_available_before_below_64GiB")
    (RUN / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(RUN)
    raise SystemExit(2)
# Import numpy only after thread settings are established.
os.environ.update({key: env[key] for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")})
import numpy as np
manifest["numpy"] = np.__version__
sys.path.insert(0, str(ROOT / "project/hardware/tests"))
sys.path.insert(0, str(ROOT / "project/hardware"))
from test_scalellm_mlp_linear import REC576Tests, reference_rec576
q, meta = REC576Tests.fixture(1)
fixture = reference_rec576(q, meta)
(RUN / "tb_rec576.bin").write_bytes(fixture)
(RUN / "tb_rec576_beats.hex").write_text("".join(f"{int.from_bytes(fixture[i:i+32], 'little'):064x}\n" for i in range(0,576,32)))
(RUN / "tb_q_rows.hex").write_text("".join(f"{int.from_bytes(bytes(q[row]), 'little'):064x}\n" for row in range(16)))
(RUN / "tb_meta_rows.hex").write_text("".join(f"{int(meta[row,0]):06x}\n" for row in range(16)))
# Preserve every generated numeric random input under the same specified seeds.
arrays = {
 "h32_s24_seed6001": np.random.default_rng(6001).integers(-(1<<23),1<<23,(16,4096),dtype=np.int64),
 "h32_s32_seed6002": np.random.default_rng(6002).integers(-(1<<31),1<<31,(16,14336),dtype=np.int64),
 "fp32_seed6003": np.random.default_rng(6003).uniform(-130,130,(16,4096)).astype(np.float32),
 "quant_s27_seed6010": np.random.default_rng(6010).integers(-(1<<26),1<<26,(16,4096),dtype=np.int64),
 "quant_s35_seed6011": np.random.default_rng(6011).integers(-2_000_000_000,2_000_000_000,(16,14336),dtype=np.int64),
 "silu_gate_seed6020": np.random.default_rng(6020).integers(-1048576,1048577,(16,14336),dtype=np.int64),
 "silu_up_seed6021": np.random.default_rng(6021).integers(-8388608,8388608,(16,14336),dtype=np.int64),
 "prepare_gu_seed6030": np.random.default_rng(6030).integers(-2_000_000,2_000_001,(16,4096),dtype=np.int64)}
arrays["h32_s24_seed6001"][15,:32]=-(1<<23)
arrays["h32_s24_seed6001"][14,:32]=(1<<23)-1
arrays["h32_s32_seed6002"][15,:32]=-(1<<31)
arrays["h32_s32_seed6002"][14,:32]=(1<<31)-1
arrays["fp32_seed6003"][0,:8]=[-200,200,-1.5/65536,-.5/65536,.5/65536,1.5/65536,-128,128]
arrays["silu_gate_seed6020"][15,:4]=1048577
arrays["silu_up_seed6021"][15,:4]=[32768,-32768,98304,-98304]
np.savez_compressed(RUN / "random_inputs.npz", **arrays)
manifest["input_arrays_sha256"]={key: hashlib.sha256(value.tobytes()).hexdigest() for key,value in arrays.items()}
manifest["inputs_sha256"]={path.name:sha(path) for path in RUN.iterdir() if path.suffix in (".npz", ".hex", ".bin")}
manifest["deterministic_inputs"]="All nonrandom fixtures and exact extrema/ties are specified in the frozen test source."
manifest["exit_code"] = None
(RUN / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
def configure_child():
    os.sched_setaffinity(0, CPUS)
    resource.setrlimit(resource.RLIMIT_AS, (LIMIT_RSS, LIMIT_RSS))
started = time.monotonic()
peak_rss = 0
lowest_available = memory_available()
stop_reason = None
with (RUN / "unittest.log").open("w") as log:
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log,
                               stderr=subprocess.STDOUT, start_new_session=True,
                               preexec_fn=configure_child)
    manifest["pid"] = process.pid
    while process.poll() is None:
        available = memory_available()
        lowest_available = min(lowest_available, available)
        try:
            status = Path(f"/proc/{process.pid}/status").read_text().splitlines()
            rss = next((int(line.split()[1])*1024 for line in status if line.startswith("VmRSS:")),0)
            peak_rss = max(peak_rss, rss)
        except FileNotFoundError:
            pass
        if available < MIN_AVAILABLE or peak_rss > LIMIT_RSS:
            stop_reason = "system_available_below_64GiB" if available < MIN_AVAILABLE else "task_rss_above_96GiB"
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)
            break
        time.sleep(.1)
    exit_code = process.wait()
manifest.update(ended_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                elapsed_seconds=time.monotonic()-started, exit_code=exit_code,
                stop_reason=stop_reason, max_sampled_child_rss_bytes=peak_rss,
                lowest_system_available_bytes=lowest_available,
                child_ru_maxrss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                log_sha256=sha(RUN / "unittest.log"),
                source_identity_unchanged=all(sha(ROOT/path)==digest for path,digest in manifest["sources_sha256"].items()))
(RUN / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(RUN)
print((RUN / "unittest.log").read_text())
raise SystemExit(exit_code if stop_reason is None else 2)
