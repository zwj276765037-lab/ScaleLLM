# Final inference behavior and evidence

`deploy/scalellm.py` selects the final sixteen-slot, 80 MHz runtime. Follow
[DEPLOYMENT.md](DEPLOYMENT.md) to export licensed model assets, prepare text,
program the exact bitstream and run on a local Windows XDMA host.

A request record has this shape:

```json
{"slot": 0, "prompt_token_ids": [128000, 128006, 882, 128007, 271, 13347, 128009, 128006, 78191, 128007, 271], "max_new_tokens": 32}
```

Prefer preparing messages through the model's original tokenizer and chat
template. `examples/messages16.json` contains the sixteen short English prompts
used for the reported board run; `examples/requests16.json` is their frozen token
form. Its prompt lengths are 16–19 tokens. The longest prompt and a 32-token
budget require at most `19 + 32 - 1 = 50` full-layer rounds when no EOS occurs.
Each round issues one Attention and one MLP command per layer, for 64 commands.

## Slot and KV lifecycle

Each of sixteen fixed rows belongs to one independent slot. A slot has its own
request epoch, absolute position, prompt and generated token list. Inactive rows
are canonical zero. Request rows can therefore prefill or generate at different
positions in the same hardware command. Context is limited to 128 positions;
there is no sliding window or automatic context truncation.

The runtime consumes one prompt token per full-layer round. The last prompt
round produces the first new token. Later rounds feed the previous generated
token while retaining that slot's FPGA KV history. Every round traverses all
32 layers. Position and token lists are committed together only after the
complete layer stack and Host LM head succeed.

Decoding uses the existing deterministic greedy top-1 calculation. Equal logits
prefer the lower token ID. The model and generation configuration supply the
original EOS IDs (`128001`, `128008`, `128009` for the verified checkpoint).
A generated EOS immediately finishes that slot; otherwise it finishes at its
requested length limit. There is no switch to ignore EOS or to force a minimum
output length. The model's sampling defaults are not substituted for this
reported greedy path.

Attention weights and metadata for all 32 layers remain resident in DDR0. GU
metadata remains resident in DDR1; GU weights are staged into the canonical
window for each layer. Actual transferred payloads are SHA-checked against the
export and read back from DDR. RoPE is rebuilt for each row's own absolute
position with the original Llama scaling and packing.

## CPU and FPGA boundaries

| Operation | Execution |
| --- | --- |
| Tokenizer/chat template, embedding, RMSNorm, residual | CPU |
| Attention online H32/A8 before Q/K/V and output projections, quantized Attention, persistent KV | FPGA |
| MLP online H32/A8, quantized Gate/Up, scale recovery, SiLU × Up | FPGA |
| Post-product H32/A8 and integer Down | CPU |
| Final norm and streaming FP32 LM head | CPU |

Normalized inputs are packed as sixteen rows of S24/F16. Attention outputs use
that same 196,608-byte layout. MLP produces 917,504 bytes of tile16-major
S32/F16 products for the CPU Down boundary. The final ABI and layouts are in
`project/hardware/source/final/abi.json` and
`project/hardware/host/scalellm_final_layout.py`. The original weight-manifest
schema's historical ABI fields describe the weight layout; live command
admission uses the separate final ABI.

## Completion and failure handling

One local XDMA session owns the device. Before issuing a command, the backend
requires quiescent hardware and verifies final identity. It checks admission,
the full completion descriptor, errors, transfer lengths and inactive output
rows. It copies the complete output, rechecks completion identity, then ACKs the
matching command. The Python runtime records the pending descriptor until that
sequence succeeds.

Any timeout, short transfer, completion mismatch or device error stops the run.
The program preserves the error and pending identity instead of automatically
resetting or retrying START. A full external reset invalidates old assets and KV;
start a fresh process and explicit request history after manual recovery. A
saved decode checkpoint is an observation, not a supported resume image.

## Result files

Each run writes a new directory:

| File | Contents |
| --- | --- |
| `run.json` | Current/final execution state, configuration, source/asset/request hashes, slot state, command receipts and resource summaries |
| `progress.jsonl` | Command/layer/position events with wall timestamps and resource observations |
| `xdma.jsonl` | Actual local transfer boundaries, lengths and payload SHA256 |
| `decode_checkpoint_*.json` | Generated IDs and readable text at observed generation boundaries |
| `outputs.txt` | Readable final text and stop reason per occupied slot |

A successful run reports `execution: COMPLETE`, `final_quiescent: true` and
`handles_closed: true`. `decoded[slot].stop_reason` is `eos` or `length_limit`.
The manifest checks, DDR readbacks, command identity and lifecycle checks establish
execution/integrity coverage. `numerical_verification: NOT_RUN` remains explicit:
the full real-model path does not run an independent whole-model numerical oracle
or save every raw activation for such an audit.

External sampler logs supplied by `--power-log` are recorded under
`external_power_logs`. A snapshot hash describes the bytes present when the run
ends; a sampler that continues writing will change that file. These references
alone do not establish time alignment, instrument coverage or full-run energy.

## Published validation boundary

The [README result gallery](../README.md#16-requests--their-recorded-outputs)
displays all sixteen prompts and captured outputs from the newer fixed-KV128
measurement: 1,784 generated tokens, with all 16 requests retained through
position 127. See [all recorded responses](evidence/kv128_chat16/REQUESTS_AND_OUTPUTS.md)
and [measurement methods](evidence/kv128_chat16/README.md) for that run's separate
fixed-length capture setup. This does not change the portable runtime behavior
specified above.

The earlier 32-token-per-request run is retained in
[outputs.json](evidence/inference_chat16/outputs.json) and the
[plain-text record](evidence/inference_chat16/outputs.txt). Its requests retire
at their individual length limits, unlike the fixed-active-count KV128 plot.

The original board run produced 512 readable English tokens from sixteen
independent requests, 50 complete rounds and 3,200 hardware commands. Every
request reached the 32-token limit; none ended with EOS. Earlier independent
hardware diagnostics passed their stated numerical checks. These diagnostics
and the successful execution do not turn the unperformed whole-model oracle
into a numerical PASS.

The public wrapper's tests cover CPU imports, source identity rejection, moved
paths with spaces, request bounds, original BF16 conversion, read-only final ABI
checks and mock command wiring. The extracted LM-head function has the same AST
as the original function and matched every returned value on four deterministic
small-array cases. Chat preparation has a small synthetic tokenizer test.
The CPU check record is [runtime_validation.json](evidence/final/runtime_validation.json).
No newly exported complete model or new physical board run was performed with
this portable wrapper. Hardware building has its own separate validation status
in [BUILD_HARDWARE.md](BUILD_HARDWARE.md).
