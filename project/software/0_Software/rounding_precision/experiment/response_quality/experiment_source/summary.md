# R012 paired response generation source

Question: whether extra intermediate rounding changes actual freely generated answers under identical initial prompts.

Method: true 32-layer CURRENT and existing OUTPUT_ONLY arithmetic context; same quantized weights/KV12/LUT and shared FP32 head. Experimental cache and extended RoPE are isolated in this folder. Native <=128 behavior and cache/full-prefix outputs require bitwise GPU qualification before any answer generation. Greedy independent continuations, same caps, EOS/eot stops, per-arm multi-turn history, raw IDs and hashes are preserved.

Platform: existing Llama-3.1-8B-Instruct checkpoint and Python environment. Root exclusively admits GPU0 UUID; The user subsequently explicitly authorized trying GPU1; GPU0waiter was cancelled, and a new16GiBraw memory probe failed before any model work. CPU tests and pilot tokenizer preflight are complete. GPU1model remains unlaunched. Desired model gpt-6.1-sol/xhigh; actual serving metadata not independently available.

Inputs: benchmark files owned by dataset worker under `results/software_Error_Analysis/13_response_quality/datasets/`. Full benchmark size is not a measured generation result. See [protocol](protocol.md), [runner](../run_generation.py), [cache adapter](../cached_adapter.py), [controls](../generation_core.py). Resource/cost pilot must precede full-batch budget freeze.

Revision boundary: original run_generation.py/supervise.py and AT003frozen sources remain preserved. Isolated run_generation_v2.py/supervise_v2.py parameterize the exact device UUID, verify input SHA after actual worker wait, and stop only the owned worker group on external GPU occupancy. AT004raw probe has its own frozen source manifest.

Current execution entry: wait_for_gpu_v2.py → supervise_v2.py → run_generation_v2.py, GPU0UUIDonly. AT005source/input SHA freeze is complete; authoritative frozen_manifest.json and source_snapshot are under R012/runtime/AT005_wait_for_gpu0_after_gpu1_failure/. NewGPU0queue inherits the original2048context/512newtokens/chunk128/1800spilot budget with external-conflict own-stop and post-run input SHA checks. Originalv1/AT003sources and GPU1AT004failure remain preserved.
