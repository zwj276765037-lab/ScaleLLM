import json,sys
from pathlib import Path
stage=Path(r"D:/ScaleLLM_final_model/final_96df1a5c_power_20261029_001")
sys.path.insert(0,str(stage/"project/hardware"))
sys.path.append(str(stage/"deploy/vendor/runtime"))
from scalellm_windows_xdma import WindowsXdmaSession
from host.scalellm_final_abi import CSR,IDS
with WindowsXdmaSession(open_dma=False) as session:
    values={name:session.read32(offset) for name,offset in CSR.items() if name in ("MAGIC","ABI","CORE_HZ","ATTENTION_LAYOUT","MLP_LAYOUT","ATTENTION_FORMAT","MLP_FORMAT","CAPABILITIES","STATUS","ADMISSION_ERROR","DONE_ERROR")}
    print(json.dumps({"stage":"preprogram_observation","csr":values,"csr_hex":{k:hex(v) for k,v in values.items()},"expected_ids":IDS},indent=2))
    sys.exit(0)
    for register,key in (("MAGIC","magic"),("ABI","abi"),("CORE_HZ","core_hz"),("ATTENTION_LAYOUT","attention_layout"),("MLP_LAYOUT","mlp_layout"),("ATTENTION_FORMAT","attention_format"),("MLP_FORMAT","mlp_format")):
        if values[register]!=IDS[key]:raise RuntimeError("Hardware identity mismatch "+register)
    if values["STATUS"]&7:raise RuntimeError("Hardware is busy or holds a completion/error")
    print(json.dumps({"status":"PASS","csr":values,"ids":IDS,"python":sys.version,"executable":sys.executable},indent=2))
