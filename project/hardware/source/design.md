# Core Specification

This concise specification preserves the current source contract. Authority:
`/home/user/EDA-202/zhuowenjun/ScaleLLM/1_Hardware/source/design.md`, sections2-3
and the current production manifests. Its identity is indexed in
`migration/external_dependencies.json`; historical management text is not copied.

## Model And Architecture

Llama-3.1-8B-Instruct, 32 layers, hidden4096, intermediate14336, Group32/Hadamard32.
Host retains embedding, LM head, FP32 RMSNorm and residuals. Hardware retains
all Attention and MLP operators and resident W8/W4 weights. There are two
distinct cohort16 contexts. One Attention physical8-row array executes two waves
per cohort; those waves are not two independent cohorts. Hardware context limit
is128. Preserve cohort/layer/buffer/owner/generation and ready/valid semantics.

VCU118 / `xcvu9p-flga2104-2L-e`; core100 MHz, independent DDR0/DDR1 UI200 MHz.
These are targets, not measured timing or board operation. Full-board defines:

```text
HAP_BOARD_BUILD
HAP_BOARD_V5
HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s54
HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core
```

## Numerical Boundaries

MLP format `0x48384605`, command ABI `0x00050000`. Attention retains its own
format `0x48384103` / ABI `0x00020000`; do not globally rename Attention to05.

| Boundary | Representation |
| --- | --- |
| Host input / Gate / Up | S24/F16 |
| Input H32 intermediate / normalized | S29 / S27/F16 |
| Gate/Up guard / accumulator / output | S37/F24 / S44/F24 over128 groups / S24/F16 |
| SwiGLU product / Down H32 intermediate / normalized | S32/F16 / S37 / S35/F16 |
| Down guard / accumulator / output | S45/F24 / S54/F24 over448 groups / S32/F16 |

H32 uses five signed butterfly stages, then multiply11585 and signed half-away
division65536. Online quantization uses raw min/max including zero, Group32,
ties-to-even ScaleCode/q/zp, canonical zero metadata and no source preclip.
Gate/Up total shifts20..44; Down12..44. Sign-extend before left shift; right
shift is arithmetic. Sum full F24 groups before one half-away `/256` and declared
terminal saturation. Preserve overflow/format/saturation telemetry.

SwiGLU sign-extends packed S24, uses the8193-entry SiLU LUT at1/256 spacing,
multiplies into S48/F32 and half-away shifts16 to S32/F16. Never truncate Down
input to S24. Offline weight quantization keeps its existing floating normalized
FWHT, positive half-up ScaleCode, signed half-away and W4/W8 terminal bounds.

Attention keeps A8W8 shifts26..47, S42 accumulation and S24 output; GQA32/8 heads,
head dim128; Q/K pair permutation, separately rounded RoPE products, KV12,
QK +/-16 clamp, Softmax delta[-16,0] clamp/257-entry U17 LUT/all-masked fault,
PV and Wo rounding/saturation are unchanged.

## Transport And Memory

`before_attention`/`after_attention`: row-major signed24/F16.
MLP H2C: Group32-major `(group*16+row)*32+lane`, LE S24,
128 groups*48 AXI256 beats =6144 beats=192KiB.
MLP C2H: tile16-major `(tile*16+row)*16+lane`, LE S32,
256 tiles*32 beats =8192 beats=256KiB. Down tile is8192 bits.

External W4 first value stays in the low nibble. MLP16-column metadata keeps
code128 bits then shift96 bits,28 bytes+4 zero bytes; internal12-column tiling
does not change external packets. DDR has2GiB local/channel,31-bit local
addresses, Host bases0/0x80000000. Each channel reserves32*62MiB weights and
64MiB runtime; six1MiB activation slots are two cohorts*three slots.

Keep CSR layout and checks in `host/scalellm_hardware.py` and
`rtl/integration/hap_mlp_axil_control.sv`, including0x2AC Down saturation,
0x2B0 shift-format faults and0x2B4 numeric status. Faults require the existing
terminal/reset policy; no relaxed assertions, fault bypass or waived timing.

## Version Boundary

Copied RTL/manifests/XDC/build scripts are byte-identical to their indexed
sources. No functional, CDC, synthesis, route, bitstream or board qualification
is transferred by the copy. Native025 is an unrouted failed diagnostic; the
preserved route entry still uses `impl_1` and cannot deploy that candidate.
