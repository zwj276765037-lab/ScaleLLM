# GPU1 repair investigation — status

Updated 2026-10-18T04:47:00.968495+00:00; owner A012 /root/gpu1_repair.

- execution_state: completed; current task: GPU1 finite diagnostic evidence; stage: terminal audit / integration.
- verdict: GPU-visible byte preservation failed with system and matching libcuda; no verified repair. AT003 rules out pure full-buffer D2H-only faults for the observed byte errors.
- applicability: GPU1 raw synthetic byte integrity, CPU18,19, 20GiB data allocation; no model load.
- review: engineering self-audit per attempt, independent review pending.
- repair_state: blocked_on_maintenance_decision. Last inventory shows Xorg on both GPUs; reset/display-service/system changes require separate controller handling and fresh eligibility checks; none executed here.
- next step: Publish evidence, independent review, controller maintenance decision; no further scans or production qualification.

Original GPU1 flock and per-step ≥8GiB GPU free / ≥80GiB host available checks retained. Read actual [comparison](../comparison.json), each launch/terminal/status and actual-library receipt for version boundaries.
