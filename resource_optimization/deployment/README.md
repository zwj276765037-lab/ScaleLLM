# Deploy and reproduce the all-DSP VCU118 version

This guide targets the `Resource_optimization` branch and its released **all-DSP** image. The CPU still runs normalization, residuals, Down projection and the LM head; a VCU118 alone is not a complete inference system. A Windows x64 PCIe host, licensed model files, AMD programming tools and a compatible XDMA driver are required. Power measurement additionally requires a MAXPOWERTOOL002# PMBus adapter and the official PowerTool 2.32.27 runtime. [Pinned external dependency identities](dependencies/README.md) include model files, vendor software and adapter requirements.

**Repository deployment workflow prepared and CPU-validated.** The supplied all-DSP bitstream has the published November 15 board and power evidence. This update validates a fresh full-model export and an independent Windows source/Python environment. It does not repeat SRAM programming, ordinary inference, the full KV128 benchmark or twelve power windows through these new entry points. [Stage results](source/results.md) retain those `NOT_RUN` boundaries; a fresh-host driver installation and complete end-to-end deployment qualification have not been established.

## Obtain and verify the public files

```powershell
git clone --depth 1 --branch Resource_optimization https://github.com/zwj276765037-lab/ScaleLLM.git
cd ScaleLLM
py -3.12 tools/package_release.py verify
py -3.12 resource_optimization/verify_publication.py
```

The new bitstream is already included at `resource_optimization/hardware/bitstream/ScaleLLM_Final_Decode16_80MHz.bit`, **80,159,263 bytes**, SHA-256:

```text
5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7
```

The default deployment profile is `all-dsp`. The root `bitstream/` retains the historical `96df…` image. Selecting `legacy` in a local configuration is explicit and requires that historical image; a mismatched or arbitrary image is rejected by both Python and the programming Tcl. The published all-DSP KV128 benchmark requires `all-dsp`.

## Host and external dependencies

- Windows x64 with a PCIe-connected VCU118 / XCVU9P and its JTAG programming connection. One matching XDMA device is supported at a time.
- CPython 3.12 x64; the original board environment used 3.12.10. The deployment supports Python 3.10+ syntax, but the pinned Windows dependency bundle is for Python 3.12.
- Vivado Hardware Manager and `hw_server`; the original programming environment used 2022.2. A full Vivado implementation is not required to program the supplied bitstream.
- The specified Windows polling XDMA driver, PCI ID `10EE:9018`. Follow [driver source preparation, building and signing](../../deploy/driver/README.md). Installing a driver and fulfilling its license/signature requirements are explicit host setup steps; this application does not change boot policy or install a kernel driver.
- The exact licensed checkpoint identified below, and enough disk for the checkpoint, roughly 8.8 GB of exported assets, source and logs. The original 16 GiB host used an 8 GiB process guard and a 2 GiB available-memory floor. Leave additional room for captures and traces. The power workflow requires at least 40 GiB still free on its actual output volume after this preparation.

The numerical host path uses one BLAS thread and up to eight already-allowed CPUs, matching the measured numerical/runtime configuration. There is **no default cumulative wall-time termination**. Single-command and DMA fault timeouts remain active. A positive `wall_seconds` can be explicitly configured by the user; the default is `null`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r deploy\requirements-windows-py312.lock
.\.venv\Scripts\python.exe deploy\scalellm.py dry-run
.\.venv\Scripts\python.exe deploy\scalellm.py preflight
```

These initial checks do not open the board. A valid dry-run can still list missing model assets: it verifies the plan and the selected image, not a completed deployment.

## Export the exact model into a new directory

Model weights and tokenizer files are external licensed inputs. Obtain [Meta’s official `meta-llama/Llama-3.1-8B-Instruct` at revision `07eb05b21d191a58c577b4a45982fe0c049d0693`](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct/tree/07eb05b21d191a58c577b4a45982fe0c049d0693) after accepting its access and license terms. Do not substitute the current `main` revision: its tokenizer configuration differs. Download the fixed checkpoint content, including `config.json`, the safetensors index and four shards, tokenizer/control JSON files and `generation_config.json`. A model name alone is not a sufficient identity. The accepted aggregate identity is:

```text
8a09c60f3256779c16925f8209c9399ba4a1ee0406caf65bd2637ffd99287d6d
```

The pinned dependency set includes the Hugging Face CLI. After your account has access, download only the required files from the fixed revision:

```powershell
.\.venv\Scripts\hf.exe auth login
.\.venv\Scripts\hf.exe download meta-llama/Llama-3.1-8B-Instruct `
  --revision 07eb05b21d191a58c577b4a45982fe0c049d0693 `
  --include '*.safetensors' config.json model.safetensors.index.json tokenizer.json tokenizer_config.json special_tokens_map.json generation_config.json `
  --local-dir 'E:\models\Llama-3.1-8B-Instruct'

.\.venv\Scripts\python.exe deploy\export_model.py identity --model-dir 'E:\models\Llama-3.1-8B-Instruct'
.\.venv\Scripts\python.exe deploy\export_model.py export `
  --model-dir 'E:\models\Llama-3.1-8B-Instruct' `
  --output 'artifacts\llama31' `
  --expected-checkpoint-sha256 8a09c60f3256779c16925f8209c9399ba4a1ee0406caf65bd2637ffd99287d6d
```

The exporter checks the complete checkpoint before and after export. It writes relative-path FPGA and CPU manifests, with exact asset sizes/hashes. It does not silently substitute a similarly named model, download weights, or alter the checkpoint. The source files, host conversion and quantization must retain their published identities. A verified layer export may be resumed with `--resume`; existing host assets are not overwritten.

Copy `deploy/config.example.json` to `deploy/config.local.json`. Keep `deployment_profile` as `all-dsp` and configure `artifacts`, `host_assets`, `output_dir`, `bitstream`, `messages` and `requests`. Paths are relative to the configuration file; spaces and absolute paths are supported. Pin the SHA of your installed, verified driver through `expected_driver_sha256` when appropriate.

## Program, check and run ordinary inference

Discover your own exact JTAG target and device using Hardware Manager, and start the installed `hw_server`. Close other board applications before programming. Replace the following tool and target values with the discovered values; no author's cable serial is required.

```powershell
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json program `
  --vivado 'C:\AMD\Vivado\2022.2\bin\vivado.bat' `
  --server localhost:3121 --target 'YOUR_EXACT_TARGET' --device xcvu9p_0 `
  --receipt outputs\program.json

.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json preflight --models --device

.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json run `
  --program-receipt outputs\program.json --result outputs\chat16
```

The example requests are the original 16 prompts with 32 new tokens each. Custom text can be encoded with `prepare --messages FILE --result NEW_DIRECTORY`, then passed to ordinary `run --requests FILE`. Ordinary inference keeps EOS retirement and the 32-token limit.

The program receipt records the exact image/profile, tool invocation and native exit, target, host and OS boot. A receipt from another host or an earlier boot is rejected. Perform programming from the Windows execution host and use a new receipt after reboot. The hardware ABI is shared with the historical image: CSR checks do not prove which implementation was loaded and cannot detect an external reprogram within the same boot. Maintain exclusive board ownership after programming.

Programming affects volatile SRAM. Some hosts require PCIe device re-enumeration after SRAM programming. If CSR reads are all ones or the device is unavailable, stop the inference attempt and recover the **exact XDMA device** using the host's documented device-management procedure. Do not treat that read pattern as a successful identity check or restart a whole PCIe bridge automatically.

Successful deployment requires native exit zero, complete command/output/ACK records, final idle/error checks and closed handles. `run.json` reports `deployment_acceptance`; a `run` without a programming receipt remains explicitly `IMAGE_PROVENANCE_UNVERIFIED`, even if it produces tokens. `numerical_verification` retains its own scope; successful transport is not an independent full-model accuracy oracle.

## Reproduce the fixed-active16 KV128 benchmark

This is a separate policy, not a relaxation of ordinary inference validation. It keeps the original 16 prompts and greedy prediction, observes EOS without retiring slots, and executes exactly **128 input positions, 8192 commands**. Each generation budget is `129 - prompt_length`: the prediction from input position 127 is committed but never fed back as a position-128 input.

```powershell
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json benchmark-kv128 --dry-run
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json benchmark-kv128 `
  --program-receipt outputs\program.json --result outputs\kv128
```

The benchmark checks all **1784 generated token IDs**, twelve complete selected operator outputs at KV32/KV128 and the final 256 MiB KV image against published reference identities. It generates all needed captures and state locally; it does not fetch a private author snapshot. The capture hooks read the board at explicit quiescent boundaries and retain both successful and failed evidence.

Keep `run.json`, `benchmark_source.json`, `benchmark_summary.json`, `benchmark_commands.jsonl`, `benchmark_capture.json`, `requests.json`, outputs and the entire `captures/` directory together. The latter contains input/descriptor/KV/RoPE/output captures and `kv_snapshot.bin` used by the power workflow. Do not run another workload between the accepted state and a read-only power inspection; otherwise use the explicit checked restoration workflow.

FPGA timing remains `sum(DONE_CYCLES) / 80 MHz`. Whole-process wall time includes host work, asset checks, transfers and capture overhead. Hardware counters and host wall time are different metrics, and the published regression comparison does not establish an independent mathematical oracle for the entire model.

## Repeat or recompute seven-rail power

Follow the portable workflow in [the portable power guide](power/README.md) after the fresh KV128 benchmark. The official PowerTool installation path, adapter identity, stage/output directories, model manifests and programming receipt must be explicit. A new pilot determines the actual sampling target and gap threshold; the historical November 15 values were 150/450 ms.

Obtain and install the official PowerTool version from the [vendor links and identity record](dependencies/README.md#powertool-与适配器). Prepare its explicit runtime files in a new directory; this preparation does not open the adapter:

```powershell
& "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile `
  -File tools\power\prepare_powertool.ps1 `
  -SourceRoot 'C:\Program Files (x86)\Maxim Integrated Products\MaximDigitalPower' `
  -OutputRoot 'E:\ScaleLLM power\runtime'
```

Set `PowerToolRuntimeRoot` to that output directory. Follow the adapter vendor’s setup for its USB/D2XX driver and PMBus connection. The observed signed installer and runtime hashes are published; a fresh download of the installer timed out during the provenance audit, so successful reacquisition of that exact installer has not been claimed.

The four workloads and three repetitions follow the published measurement contract. Seven regulator outputs, common covered intervals, unavailable full-window means and unknown sensor aperture/accuracy retain their original meanings. Reproducing the workflow does not require another board or host to show identical power or wall-clock measurements.

For **offline recomputation of the published November 15 experiment**, the existing [power evidence release and instructions](../power_retest/README.md) require no board or proprietary runtime. Its original raw logs and results stay unchanged.

## Source rebuilding and historical results

The supplied bitstream supports deployment without a new implementation run. [The version guide](../README.md) separately contains the 106-input source closure, both DSP candidates, final routed checkpoint, timing and resource reports. Historical build scripts document the original implementation and are not proof of a new independent RTL rebuild. Do not use the root historical hardware recipe to claim a rebuild of the all-DSP image.

The [deployment source package and qualification records](https://github.com/zwj276765037-lab/ScaleLLM/releases/tag/resource-optimization-deployment-20261116) accompany this branch. The original hardware and power Releases remain separate from these deployment checks. Consult [stage results](source/results.md) for which new checks have actually run and which are still pending.
