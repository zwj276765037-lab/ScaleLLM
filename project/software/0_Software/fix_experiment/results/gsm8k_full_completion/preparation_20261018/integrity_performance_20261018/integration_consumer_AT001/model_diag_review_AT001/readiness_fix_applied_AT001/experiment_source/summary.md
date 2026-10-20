# Post-diagnostic readiness correction — source

A010 engineering delivery after independent BF16/QDQ raw audits. Parent explicitly authorized the edit only after QDQ worker/guard naturally ended and the 16-source audit window was fixed.

Only `run_gsm8k_matrix.py:verify_readiness` and new `test_gsm8k_bytewise_readiness.py` changed. Explicit bytewise mode now requires canonical production paths and valid SHA identities for the worker, loader, protocol, original integrity helper and bytewise helper, then the existing loop compares every listed file with its live hash. Explicit null/unknown modes fail. Missing implementation preserves legacy behavior. Future full-matrix launch still needs the complete reviewed 16-source freeze/readiness boundary.

Current matrix SHA: `6e8a1241d4fc15d0cfa39b1afd1cf831f011ba1ee70e7ad68a2a6b56e2ed08c4`. New readiness test SHA: `9ff0a0ddc29228da15f840f0002b1c3411596b6fec1f3dbfc4e2cbafa36ced8a`. Worker/helper/protocol and all other 15 production files remain exactly at the BF16/QDQ diagnostic source identities. [Final source/evidence manifest](../final_source_manifest.json), [applied patch](../applied_readiness.patch), `source_frozen/`.
