# ScaleLLM — Resource optimization

**`Resource_optimization` · VCU118 / XCVU9P · Decode16 · 80 MHz · validated 2026-11-15**

This branch publishes the **all-DSP ScaleCode recovery candidate**, including its tested bitstream, 106 frozen source inputs, final routed resource/timing reports and Dell board validation.

[Version guide](resource_optimization/README.md) · [Tested bitstream](resource_optimization/hardware/bitstream/ScaleLLM_Final_Decode16_80MHz.bit) · [Hardware source](resource_optimization/hardware/source/) · [Resource CSV](resource_optimization/results/resources.csv) · [Board audit](resource_optimization/results/board/inference/regression.json) · [512 token results](resource_optimization/results/board/inference/outputs.json) · [Raw evidence & checkpoint](https://github.com/zwj276765037-lab/ScaleLLM/releases/tag/resource-optimization-20261115)

## Final routed hardware

| Resource | Used | Utilization |
| --- | ---: | ---: |
| LUT | **632,446** | **53.50%** |
| CLB registers | **936,372** | **39.60%** |
| Occupied CLB | **136,026** | **92.05%** |
| DSP | **5,773** | **84.40%** |
| BRAM36 equivalent | **709** | **32.82%** |
| URAM | **304** | **31.67%** |

The final setup WNS is **+0.009 ns** and hold WHS **+0.008 ns**, with no failing setup/hold/pulse endpoints. All **1,625,124** routable nets are fully routed; routing errors and DRC Error/Critical Warning counts are zero. All **94 bus-skew constraints** are met.

The 96 recovery leaves use **384 DSPs** in total. In the same post-physopt build context, all-DSP recovery uses **12,824 fewer LUTs**, **192 more DSPs** and **3,510 more occupied CLBs** than moving only the wider recovery multiplications to DSPs. SLR1 occupied CLBs remain **99.11%**. **Down stays on the CPU**; adding it to the FPGA has not been established.

[Full resource, timing and comparison evidence](resource_optimization/README.md#final-routed-resources-and-timing)

## New bitstream board results

| Check | Result |
| --- | --- |
| SRAM programming and final hardware identity | PASS |
| Two DDR write/readback tests | Byte-exact |
| KV32/KV128 selected operator replays | **12/12 full outputs byte-exact** |
| Original 16-request regression | **512 generated tokens, 50 rounds, 3,200 commands** |
| Exact final output file | **Identical to the original sealed reference** |
| Descriptor, completion, ACK and retirement audit | PASS |
| Native process time including startup hashes | **56 min 8.985 s** |
| Final device state | Idle; handles closed; lease released |

The candidate remains in volatile SRAM. No configuration Flash was written and the installed driver was unchanged. These are regression results against the sealed reference; an independent whole-model mathematical oracle remains unestablished. No new power measurement or complete 128-step model run was performed on this image.

## Download and verify

The tested bitstream is 80,159,263 bytes, SHA-256:

```text
5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7
```

```bash
python3 resource_optimization/verify_publication.py
```

The [version guide](resource_optimization/README.md) documents source identity, strict SRAM programming, the raw evidence ZIP, the final routed DCP and offline audit commands.

## Historical baseline

The root `project/hardware`, `bitstream`, `deploy`, and their source manifests continue to identify the older **`96df1a5c…`** release. For the new hardware use the explicit `resource_optimization/` paths above. The original source/bitstream manifests and historical measurements retain their old identity. The repository packaging manifest includes both explicitly identified versions; the new version has its own complete file manifest.

[Baseline README and resources](https://github.com/zwj276765037-lab/ScaleLLM/blob/eaffbcaea8721dfadf9af3f1fae8bb4a0385c290/README.md) · [Historical KV128 board evidence](docs/evidence/kv128_chat16/README.md) · [Historical seven-rail power report](docs/evidence/kv128_sevenrail_power/REPORT.md) · [Experiment index](docs/EXPERIMENTS.md)
