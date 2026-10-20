# GPU1 repair investigation — results

Updated 2026-10-18T04:47:00.968495+00:00. Engineering self-audit evidence; independent review separately owned.

Bad byte counts use first read only per allocation and pattern, never add duplicate read count. Repeat-read changes are separate. Different patterns are separate observations, not a single union of bad physical cells.

## AT001

execution_state: completed.

| Pattern | Complete reads | Wrong bytes, first read | Failed allocations | Set / clear bytes | Repeated-read changes |
| --- | ---: | ---: | --- | ---: | ---: |
| h2d_00 | 160 | 203008 | 46,47,48,49,50 | 203008 / 0 | 0 |
| h2d_ff | 160 | 0 | none | 0 / 0 | 0 |
| h2d_55 | 160 | 212992 | 46,47,48,49,50 | 212992 / 0 | 4 |
| h2d_aa | 160 | 212992 | 46,47,48,49,50 | 212992 / 0 | 0 |
| h2d_ramp | 160 | 212272 | 46,47,48,49,50 | 212272 / 0 | 0 |
| device_memset_00 | 160 | 212992 | 46,47,48,49,50 | 212992 / 0 | 0 |
| device_memset_ff | 160 | 0 | none | 0 / 0 | 0 |
| device_memset_55 | 160 | 212992 | 46,47,48,49,50 | 212992 / 0 | 0 |
| device_memset_aa | 160 | 212992 | 46,47,48,49,50 | 212992 / 0 | 0 |

Evidence: [AT001 raw status](../AT001/status.json), [launch](../AT001/launch.json), [actual CUDA library](../AT001/actual_cuda_library.json).

## AT002

execution_state: completed.

| Pattern | Complete reads | Wrong bytes, first read | Failed allocations | Set / clear bytes | Repeated-read changes |
| --- | ---: | ---: | --- | ---: | ---: |
| h2d_00 | 160 | 212966 | 46,47,48,49,50 | 212966 / 0 | 0 |
| h2d_ff | 160 | 26 | 46,47,48,49,50 | 0 / 26 | 0 |
| h2d_55 | 160 | 212992 | 46,47,48,49,50 | 212992 / 13 | 0 |
| h2d_aa | 160 | 212992 | 46,47,48,49,50 | 212992 / 0 | 0 |
| h2d_ramp | 160 | 212272 | 46,47,48,49,50 | 212272 / 8 | 0 |
| device_memset_00 | 160 | 212992 | 46,47,48,49,50 | 212992 / 0 | 0 |
| device_memset_ff | 160 | 0 | none | 0 / 0 | 0 |
| device_memset_55 | 160 | 212992 | 46,47,48,49,50 | 212992 / 0 | 0 |
| device_memset_aa | 160 | 212992 | 46,47,48,49,50 | 212992 / 0 | 0 |

Evidence: [AT002 raw status](../AT002/status.json), [launch](../AT002/launch.json), [actual CUDA library](../AT002/actual_cuda_library.json).

## AT003

execution_state: completed.

| Pattern | Complete reads | Wrong bytes, first read | Failed allocations | Set / clear bytes | Repeated-read changes |
| --- | ---: | ---: | --- | ---: | ---: |
| device_memset_00 | 160 | 212992 | 46,47,48,49,50 | 212992 / 0 | 0 |
| device_memset_ff | 160 | 0 | none | 0 / 0 | 0 |

Evidence: [AT003 raw status](../AT003/status.json), [launch](../AT003/launch.json), [actual CUDA library](../AT003/actual_cuda_library.json).

GPU-internal observer controls passed: True.
[{"test_id": "device_memset_00", "complete": true, "whole_chunk_reads": 160, "bad_bytes_first_read_only": 212992, "failing_allocations": [46, 47, 48, 49, 50], "set_bit_bytes_first_read": 212992, "cleared_bit_bytes_first_read": 0, "changed_bytes_between_repeated_reads": 0, "gpu_internal_bad_bytes_first_read": 212992, "gpu_internal_failing_allocations": [46, 47, 48, 49, 50], "gpu_cpu_count_disagreeing_reads": 0}, {"test_id": "device_memset_ff", "complete": true, "whole_chunk_reads": 160, "bad_bytes_first_read_only": 0, "failing_allocations": [], "set_bit_bytes_first_read": 0, "cleared_bit_bytes_first_read": 0, "changed_bytes_between_repeated_reads": 0, "gpu_internal_bad_bytes_first_read": 0, "gpu_internal_failing_allocations": [], "gpu_cpu_count_disagreeing_reads": 0}]

Current causal boundary: raw CUDA errors do not require model loading or inference. A matching user-space CUDA library alone has not removed the observed errors. Device memset errors exclude an H2D-only explanation. AT003 completed validated native GPU observer controls and all320GPU/CPU count, direction, first coordinate and value comparisons match. GPU-internal reads see212992wrong bytes on device00 and0onff, excluding a pure full-buffer D2H-only explanation for those faults. Physical DRAM/controller/kernel-driver causes remain distinct.

No production repair release. No reset, reboot, system driver install or GPU0 experiment run by A012. Maintenance steps are reviewable in [maintenance_candidate.md](../maintenance_candidate.md).
