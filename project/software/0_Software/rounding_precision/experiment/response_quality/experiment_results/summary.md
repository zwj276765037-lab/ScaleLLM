# R012 generation preparation and GPU1 probe results

CPU generation controls: five tests passed; native tokenizer preflight passed for alpaca_eval:199 (14prompt tokens, context2048, response cap512, stop IDs128001/128008/128009), CUDA uninitialized in CPU check.

GPU0 AT002 launch admission found external occupancy and created no worker. AT003 finite waiting queue was actually started then cancelled under the latest user instruction to try GPU1; verified PID1071314/create_time1792484020.22/PGID1071314, no GPU worker ever launched, final/proc absent and cancellation receipts preserved.

GPU1 AT004 actually allocated64×256MiB=16GiB simultaneously through raw CUDA Driver API. The first device_memset_00 pattern failed at allocation46/read0:27082wrong bytes in a268435456-byte chunk, first offset75500800, expected0/observed255. All27082error coordinates and values are preserved in first_byte_mismatch.npz.93complete chunk readbacks were checked before the first mismatch. Remaining patterns, small compute controls and all model work were skipped as required at first error.

Worker naturally exited1 after13.507s; supervisor actually waited/reaped it after15.546s, stop_reason=null, no owned survivors/proc. All64cuMemFree calls and context destroy returned0. Source/admission SHA unchanged; targeted nvidia-after observation is preserved. This is infrastructure failure. CURRENT/OUTPUT_ONLY answer quality remains unmeasured. The allocation index does not identify the same physical pages as historical failure.

Evidence: project/E012_multistage_rounding_precision/experiment_results/runs/R012/runtime/AT004_gpu1_memory_probe/{actual_launch.json,probe/allocation_manifest.json,probe/byte_checks.jsonl,probe/first_byte_mismatch.json,probe/first_byte_mismatch.npz,probe/result.json,external_wait_receipt.json,nvidia_after.json,raw_evidence_checks.json}. Independent audit is owned by A019. No GPU1 model pilot may proceed from this failed qualification.

After independent GPU1failure review, Root authorized returning to GPU0. New AT005waiting queue is real (PID1083509) and bounded; it is pending resource admission, with zero generated answer pairs so far. See runtime/AT005_wait_for_gpu0_after_gpu1_failure/current_status.json.

Final local handoff: AT005freeze completed with 28source identities and 12input identities. Actual phase=waiting_for_gpu0; waiter1083509identity verified, no worker launch at this handoff. handoff_state.json records the bounded running queue.
