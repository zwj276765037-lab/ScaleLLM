# MLP Down S32/F16 硬件迁移审计

状态：`migration_incomplete`（4/15）

该审计只检查硬件/Host ABI 是否完整迁移，不把 8-block 诊断替代为全量精度签核。

| 检查项 | 模块 | 结果 | 当前观察 | 必须动作 |
|---|---|---|---|---|
| down_finalizer_s32_f16 | Down S46/F24 accumulator finalizer | FAIL | current source still exports LANES*24 and saturate_s24 | Replace only the Down terminal S24 saturation/output with S32/F16; keep S46/F24 accumulation. |
| shared_gate_s24_preserved | Shared Gate/Up result boundary | PASS | present | Do not widen the Gate/Up path while migrating Down. |
| shared_down_s32 | Shared Down result boundary | FAIL | current down_s24x16x12 | Widen the Down-only shared slice and its elastic/output queue to 32 bits per element. |
| down_scheduler_repack_s32 | Down scheduler and 12→16 inverse repack | FAIL | current scheduler/repack ports remain S24 | Add a Down-specific S32 repacker and keep the Gate/Up S24 repacker unchanged. |
| serial_command_s32 | serial command | FAIL | current 16x16x24 S24 port | Propagate the Down S32 payload through the serial command ABI. |
| full_command_s32 | full command | FAIL | current 16x16x24 S24 port | Propagate the Down S32 payload through the full command ABI. |
| resource_top_s32 | resource top | FAIL | current 16x16x24 S24 port | Propagate the Down S32 payload through the resource top ABI. |
| production_core_s32 | Production core wiring | FAIL | current wire is 6144-bit S24 | Widen and rename the active production-core Down output net and DMA connection. |
| tensor_dma_s32_payload | MLP tensor DMA output | FAIL | current 6144-bit tile and 24 beats/tile | Change only output packing to 32 beats/tile and make every terminal count/bank/mask consistent. |
| tensor_dma_input_s24_preserved | MLP tensor DMA input | PASS | present | Keep the proven post-RMSNorm input ABI unchanged. |
| host_s32_output_boundary | Host C2H MLP output boundary | FAIL | current shared 192 KiB S24 buffer and unpack_s24_q16 path | Split H2C input and C2H output payload sizes; decode int32/2^16 before FP32 residual. |
| host_s24_input_preserved | Host H2C post-RMSNorm input | PASS | present | Keep S24/F16 input packing separate from the new S32/F16 output path. |
| format_id_v4_synchronized | RTL/Host/artifact incompatible ABI identity | FAIL | rtl_04=False; host_04=False; artifact=0x48384602 | Bump all three identities together; never expose S32 output under format-v3 ID 0x48384603. |
| down_s32_saturation_telemetry | Down S32 terminal saturation observability | FAIL | no dedicated exported Down terminal saturation counter | Export a dedicated counter and make non-zero saturation a fail-closed run status. |
| production_source_closure | Active V5 production manifest | PASS | 8/8 required sources present | Add every new S32 repack/adapter source to the active production manifest and rerun this audit. |
