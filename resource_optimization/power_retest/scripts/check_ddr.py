import hashlib
import json
import sys
import time
from pathlib import Path

stage = Path(r"D:/ScaleLLM_final_model/final_96df1a5c_power_20261029_001")
root = Path(r"D:/ScaleLLM_final_model/dsp_all_power_20261115_001")
sys.path.insert(0, str(stage / "project/hardware"))
sys.path.append(str(stage / "deploy/vendor/runtime"))
from scalellm_windows_xdma import WindowsXdmaSession
from host.scalellm_final_abi import CSR
from host.scalellm_final_layout import tensor_spans
from host.scalellm_final_runtime import FinalBoardBackend

out = root / "health"
out.mkdir(exist_ok=False)
receipt = {"schema": "scalellm_dsp_ddr_health_v1", "status": "RUNNING", "tests": [], "transport_timeout_ms": 5000}
(out / "receipt.json").write_text(json.dumps(receipt, indent=2))
started = time.monotonic()
with WindowsXdmaSession(timeout_ms=5000, log_path=str(out / "transport.jsonl")) as session:
    backend = FinalBoardBackend(session, timeout_s=120)
    backend.require_quiescent()
    for name in ("attention_input", "mlp_input"):
        backend.require_quiescent()
        span = tensor_spans(5)[name]
        payload = hashlib.shake_256(("ScaleLLM DSP DDR health 20261115 " + name).encode()).digest(span.size)
        (out / (name + ".input.bin")).write_bytes(payload)
        count = session.h2c_write_local(span.channel, payload, span.address, 1 << 20)
        observed = session.c2h_read_local(span.channel, span.size, span.address, 1 << 20)
        (out / (name + ".readback.bin")).write_bytes(observed)
        record = {"name": name, "channel": span.channel, "local_address": span.address, "bytes": span.size,
                  "write_bytes": count, "read_bytes": len(observed), "expected_sha256": hashlib.sha256(payload).hexdigest(),
                  "readback_sha256": hashlib.sha256(observed).hexdigest(), "byte_exact": observed == payload,
                  "status": "PASS" if count == span.size and observed == payload else "FAIL"}
        receipt["tests"].append(record)
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2))
        print(json.dumps(record), flush=True)
        if record["status"] != "PASS":
            raise RuntimeError("DDR readback mismatch " + name)
    backend.require_quiescent()
    receipt["final_csr"] = {name: session.read32(CSR[name]) for name in ("STATUS", "ADMISSION_ERROR", "DONE_ERROR")}
    if any(receipt["final_csr"].values()):
        raise RuntimeError("DDR health left nonzero status/error")
receipt.update(status="PASS", seconds=time.monotonic() - started, session_closed=True)
(out / "receipt.json").write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt, indent=2), flush=True)
