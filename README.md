# ScaleLLM — 16-request FPGA inference

ScaleLLM runs Llama-3.1-8B-Instruct with **16 independent incremental-KV request slots** on an AMD/Xilinx VCU118. This release includes the tested **80 MHz bitstream**, RTL and Vivado project generator, Windows inference program, model exporter, resource/timing reports, and measurements with their analysis tools.

The measured workload contains sixteen ordinary text prompts and generates **32 new tokens per request, 512 tokens in total**. See the [inputs and outputs](docs/evidence/inference_chat16/outputs.txt) and [complete token records](docs/evidence/inference_chat16/outputs.json). All requests reached the configured length limit; some answers are truncated. The context capacity is 128 positions per slot.

## Hardware and host boundary

| FPGA, 80 MHz core | CPU host |
| --- | --- |
| Attention projections, RoPE, per-request KV, attention and output projection | Embedding, normalization and residual additions |
| MLP online Hadamard H32 → A8 quantization → Gate/Up with scale recovery → SiLU(gate) × Up | Post-product H32/A8, **Down matrix multiplication**, final normalization and LM head |

Each request has its own KV position and epoch. A round processes one new position for each active request through all 32 layers. Requests share the accelerator; their generated tokens are committed at the round boundary. Down is performed on the CPU. There is no GPU dependency. See [architecture and numeric boundaries](docs/HARDWARE_ARCHITECTURE.md).

## Measured FPGA speed and resources

**All speed figures below use FPGA command cycle counters.** They exclude CPU Down, host processing, and transfers/waits outside the hardware command. They are not full-model end-to-end throughput.

| 16 active requests, all 32 layers | Attention | MLP frontend/Gate-Up/SiLU×Up | Total FPGA command time |
| --- | ---: | ---: | ---: |
| KV length 20, decode | 0.5464 s | 0.5868 s | **1.1331 s/round** |
| KV length 32, decode | 0.6459 s | 0.5867 s | **1.2327 s/round** |
| KV length 47, decode | 0.7698 s | 0.5868 s | **1.3566 s/round** |

Across the complete recorded run, 3,200 commands consumed **58.2232 seconds** of FPGA command time, including prompt processing. Raw counters, analysis commands, resource reports, and continuous full-inference power measurements are in [Performance, resources and power](docs/PERFORMANCE_AND_RESOURCES.md).

Continuous sampling over the complete inference observed **11.36 W average**
and **39.13 kJ**, summing seven FPGA-related regulator outputs, with 100% window
coverage. This is not whole-board input or host power. The sampler timed out
during redundant final console output; complete streaming data survived and was independently
checked. The [power report](docs/PERFORMANCE_AND_RESOURCES.md#full-inference-power)
preserves that failure and explains sensor resolution and the host-idle gaps.

The placed design uses **701,775 LUTs, 954,554 FFs, 709 BRAM36-equivalent tiles, 304 URAMs and 5,389 DSPs**. Final routed timing reports **WNS +0.017 ns, WHS +0.002 ns**, with no failing setup, hold or pulse-width endpoints. Resource counts are from placement; final routed utilization was not separately reported.

## Run the supplied bitstream

Clone this repository and verify the files:

```bash
git clone --branch main https://github.com/zwj276765037-lab/ScaleLLM.git
cd ScaleLLM
python3 tools/package_release.py verify
python3 deploy/scalellm.py dry-run
```

For physical inference use a Windows x64 host, PCIe-connected VCU118, the documented XDMA driver, and your licensed Llama-3.1-8B-Instruct checkpoint. Follow [Deployment](docs/DEPLOYMENT.md) for exact Python dependencies, model export, configuration, SRAM programming and device checks. After setup, the main commands are:

```powershell
.\.venv\Scripts\python.exe deploy/scalellm.py --config deploy/config.local.json prepare --messages examples/messages16.json --result outputs/prepared16
.\.venv\Scripts\python.exe deploy/scalellm.py --config deploy/config.local.json preflight --models --device --requests outputs/prepared16/requests.json
.\.venv\Scripts\python.exe deploy/scalellm.py --config deploy/config.local.json run --requests outputs/prepared16/requests.json --result outputs/chat16
```

Use [examples/requests16.json](examples/requests16.json) to replay the exact measured token inputs. Read [Inference](docs/INFERENCE.md) for outputs, stopping rules, counters and power-log association. The driver requires externally obtained vendor source and a suitable signing environment; its known source-provenance limitation is documented in [driver preparation](deploy/driver/README.md).

The board-tested artifact is [ScaleLLM_Final_Decode16_80MHz.bit](bitstream/ScaleLLM_Final_Decode16_80MHz.bit), **80,159,263 bytes**:

```text
96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85
```

## Rebuild and verify

[Build hardware](docs/BUILD_HARDWARE.md) documents Vivado 2025.2, board files, fresh project creation, synthesis, implementation and bit generation. Fresh project validation, IP generation and wrapper/compile-order checks passed. A complete new synthesis/place-and-route run was not repeated for this packaging release. Physical results may differ between rebuilds; the supplied tested bitstream has a fixed identity.

On Linux, create a test environment for the CPU/runtime checks:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r deploy/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
python3 -m unittest discover -s project/hardware/tests -p 'test_*.py' -v
python3 deploy/final/build_hardware.py check
python3 tools/analyze_performance.py docs/evidence/inference_chat16/run.json --output outputs/recomputed
python3 tools/package_release.py build --output dist/ScaleLLM_Final_Decode16_80MHz
```

The portable runtime passed CPU/protocol/numerical-preservation checks; it has not been independently deployed on a second host. The original board runtime completed the reported generations. Whole-model comparison against an independent numerical oracle was not performed. [Runtime validation](docs/evidence/final/runtime_validation.json) and [release review](docs/evidence/final/release_validation.json) distinguish these scopes.

## Project contents and license

See [Workspace layout](docs/WORKSPACE_LAYOUT.md) for the file map and release manifest. The `prefill` branch preserves the previous design; `main` contains this final incremental version.

Project-authored source is licensed under [Apache-2.0](LICENSE). Llama weights and tokenizer assets, AMD tools/IP/board files, power-tool binaries and signed drivers are external dependencies and retain their own terms; see [NOTICE](NOTICE). They are not redistributed with this project.
