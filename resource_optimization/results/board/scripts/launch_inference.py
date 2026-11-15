import json
import ctypes
import os
import runpy
import sys
from pathlib import Path

root = Path(r"D:/ScaleLLM_final_model/dsp_all_board_20261115_001")
config = json.loads((root / "candidate_execution_config.json").read_text())
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
handle = kernel.GetCurrentProcess()
process_mask = ctypes.c_size_t()
system_mask = ctypes.c_size_t()
if not kernel.GetProcessAffinityMask(handle, ctypes.byref(process_mask), ctypes.byref(system_mask)):
    raise ctypes.WinError(ctypes.get_last_error())
allowed = [index for index in range(ctypes.sizeof(ctypes.c_size_t) * 8) if process_mask.value & (1 << index)]
selected = allowed[:8]
selected_mask = sum(1 << index for index in selected)
if not selected or not kernel.SetProcessAffinityMask(handle, selected_mask):
    raise ctypes.WinError(ctypes.get_last_error())
if not kernel.GetProcessAffinityMask(handle, ctypes.byref(process_mask), ctypes.byref(system_mask)) or process_mask.value != selected_mask:
    raise RuntimeError("CPU affinity did not match the selected allowed processors")
for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    if os.environ.get(name) != "1":
        raise RuntimeError("Expected one numerical worker per library")
receipt = dict(schema="scalellm_dsp_inference_launch_v1", pid=os.getpid(),
               allowed_cpus=allowed, selected_cpus=selected,
               full_startup_hashes=True, fixed_wall_time_termination=False,
               command_timeout_seconds=config["command_timeout_seconds"],
               transport_timeout_ms=config["transport_timeout_ms"])
(root / "environment/inference_launch.json").write_text(json.dumps(receipt, indent=2))
sys.argv = [config["runner"], "--artifacts", config["artifacts"], "--assets", config["assets"],
            "--requests", config["requests"], "--result", config["result"],
            "--command-timeout-seconds", str(config["command_timeout_seconds"])]
runpy.run_path(config["runner"], run_name="__main__")
