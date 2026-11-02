# Deploy the final 16-slot, 80 MHz image

The public entry is `deploy/scalellm.py`. It uses a local Windows x64 CPU host,
PCIe XDMA and a VCU118 (`xcvu9p-flga2104-2L-e`). The final image runs its core at
80 MHz and both DDR controllers at 200 MHz. Hardware rebuilding is separate;
see [BUILD_HARDWARE.md](BUILD_HARDWARE.md).

On the FPGA, Attention and Gate/Up include the online H32/A8 input boundary;
Gate/Up also performs scale recovery and SiLU × Up. The CPU performs embedding,
normalization, residual additions, post-product H32/A8, integer Down and the
FP32 LM head. There is no GPU dependency. The runtime retains incremental KV
for sixteen independent request slots with a 128-position context.

The latest [board measurement](evidence/kv128_chat16/README.md) retained this
image and completed 128 steps, 8,192 commands and 1,784 generated tokens with all
16 requests active through position 127. Its separate fixed-length capture
wrapper retained the original prompts, greedy predictions and precision while
disabling EOS retirement and extending each request's length budget. No EOS
actually occurred. This does not change the public CLI's request limits or EOS
behavior documented below, and did not require programming the board again.

The earlier 16×32-token run remains a separate baseline: 512 generated tokens,
50 rounds, with requests retiring at their own length limits. Twelve selected
KV32/KV128 commands now have complete byte-exact sealed-RTL replays, but an
independent whole-model numerical oracle remains unestablished. The portable
wrapper has CPU/mock checks and has **not** been run on a second physical host.
See [INFERENCE.md](INFERENCE.md) and the
[performance report](PERFORMANCE_AND_RESOURCES.md) for these distinct scopes.

## Host prerequisites

- A local Windows x64 host and one PCIe-connected VCU118. The tested host used
  Windows 10 22H2, an i7-12700 and 16 GiB RAM. The process limits itself to up to
  eight already-allowed logical CPUs, one BLAS thread, 8 GiB RSS and at least
  2 GiB available system RAM.
- CPython 3.12 x64; the board run used 3.12.10. Linux 3.12.3 can run the CPU
  checks and model export, but local board execution uses Windows XDMA.
- Vivado Hardware Manager and `hw_server` for SRAM programming; the board
  workflow used 2022.2. Building RTL uses Vivado 2025.2. Install AMD tools
  separately under their licenses.
- The documented Windows polling XDMA driver for PCI ID `10EE:9018`, interface
  GUID `74c7e4a9-6d5d-4a70-bc0d-20691dff9e9d`, DMA `POLL_MODE=1`, with user IRQ0
  masked by the driver fix. Read [driver/README.md](../deploy/driver/README.md)
  before building, signing or installing it. The public source archive identity
  of the observed driver baseline is still unresolved; this is a manual
  deployment dependency. No driver binary, certificate or private key is included.
- Licensed Llama-3.1-8B-Instruct checkpoint files and at least 40 GB free disk
  space for the original checkpoint, exported assets, tools and results.

The transport requires exactly one matching active XDMA interface and opens
its nodes exclusively. Close other board applications and JTAG programming
sessions before inference. Multiple identical connected boards are unsupported.

## Install Python dependencies

Run these PowerShell commands from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r deploy\requirements-windows-py312.lock
.\.venv\Scripts\python.exe deploy\scalellm.py dry-run
.\.venv\Scripts\python.exe deploy\scalellm.py preflight
```

`dry-run` uses only the standard library and validates configuration, source
hashes and the example token requests. It lists missing model/bitstream paths.
`preflight` additionally checks the pinned NumPy 1.26.4, tokenizers 0.20.3 and
Jinja2 3.1.6 dependencies and imports the numerical runtime. Both commands leave
the device closed. CPU checks on Linux can install `deploy/requirements.txt`.
Torch and Transformers are not required by the exporter or runtime.

## Acquire and export your model

Obtain **Llama-3.1-8B-Instruct** with the applicable Meta authorization and
license. Supply `config.json`, `model.safetensors.index.json`, all referenced
safetensors shards, `tokenizer.json`, `tokenizer_config.json`,
`special_tokens_map.json` and `generation_config.json`. Model weights and
model tokenizer files are not distributed here. The exporter does not download
anything or alter the source checkpoint.

```powershell
.\.venv\Scripts\python.exe deploy\export_model.py identity --model-dir 'E:\models\Llama-3.1-8B-Instruct'
.\.venv\Scripts\python.exe deploy\export_model.py export `
  --model-dir 'E:\models\Llama-3.1-8B-Instruct' `
  --output 'artifacts\llama31' `
  --expected-checkpoint-sha256 8a09c60f3256779c16925f8209c9399ba4a1ee0406caf65bd2637ffd99287d6d
```

The expected SHA is a strict identity over configuration, tokenizer identities,
the safetensors index and complete shard contents. A model with different bytes
is rejected for this release. The containing folder may have another name.
`generation_config.json` EOS IDs must also match the model configuration.

Export writes the original quantized weight layout, 32 × 9 hardware records
and RoPE into `artifacts/llama31/scalecode_manifest.json`, with relative file
paths. Hardware payloads total 4,596,965,376 bytes. It also writes
`artifacts/llama31/host_assets/manifest.json`, including exact BF16-to-FP32
embedding/LM-head conversion in bounded 256-row chunks. These two CPU matrices
total 4,202,692,608 bytes and are opened as read-only memory maps at inference.
The source identity is checked again after export.

Use a new output directory. `--resume` can resume verified completed hardware
layers after an interrupted export; an existing `host_assets` directory is
never overwritten. The portable exporter wrapper has bounded conversion tests;
a complete model export was not repeated for this release. The original board
run used the previously frozen full-model assets.

## Configure paths and prepare text requests

Copy `deploy/config.example.json` to `deploy/config.local.json`. Paths in this
file are relative to the **configuration file**, with environment variables and
absolute paths supported. Set `artifacts`, `host_assets`, `bitstream` and
`output_dir` for your host. The default bitstream is
`bitstream/ScaleLLM_Final_Decode16_80MHz.bit`.

`expected_driver_sha256` can pin your own installed `XDMA.sys`. Record its value
with `Get-FileHash "$env:SystemRoot\System32\drivers\XDMA.sys" -Algorithm SHA256`
and compare it with the driver package you built and signed. If the field is
null, the program records the installed file's SHA without an expected digest
comparison. It does not install a driver or change Windows signing policy.

Edit `examples/messages16.json` or provide another JSON file containing 1–16
records with `slot`, `messages` and `max_new_tokens`. Messages use `role` and text
`content`; each conversation ends in a user message. Slots are unique integers
0–15. Each generation budget is 1–32, and prompt tokens plus that budget must
fit 128 positions. Then prepare a **new** result directory:

```powershell
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json prepare `
  --messages examples\messages16.json --result outputs\prepared16
```

Preparation uses the model's own `tokenizer_config.chat_template`, requests the
assistant header, and encodes with `add_special_tokens=False` because the
rendered template already includes BOS. It verifies the tokenizer/control files
against the Host manifest and writes `requests.json`, `requests_text.json` and
`tokenizer_metadata.json`. The provided `examples/requests16.json` contains the
exact token-ID requests from the reported board run; custom text must be prepared
with your verified model tokenizer.

These are the original 32-new-token request records. The KV128 measurement used
the same prompt IDs with a separate benchmark length/EOS policy; copying its
110–113-token budgets into this public CLI is not a documented reproduction
path. Its captured configuration and execution evidence are published with the
[fixed-length run](evidence/kv128_chat16/README.md).

## Program the exact released image

The released bitstream is **80,159,263 bytes**, SHA256:

```text
96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85
```

Use Hardware Manager to find the full target name and device name on your own
JTAG chain. Supply both explicitly; there is no fixed cable serial or default
first-device selection. Start your installed `hw_server`, then inspect the
programming command:

```powershell
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json program `
  --vivado 'C:\AMD\Vivado\2022.2\bin\vivado.bat' --server 'localhost:3121' `
  --target 'YOUR_EXACT_TARGET_NAME' --device 'xcvu9p_0' --dry-run
```

Remove `--dry-run` to execute the displayed command. Python and Tcl both check
the exact bitstream size/SHA. The script requires one `xcvu9p` on the selected
target and programs volatile SRAM. PCIe may need re-enumeration after programming;
perform any required host recovery manually before opening XDMA.

## Check and run

```powershell
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json preflight `
  --models --device --requests outputs\prepared16\requests.json
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json run `
  --requests outputs\prepared16\requests.json --result outputs\chat16
```

`--models` hashes all exported hardware and CPU files. `--device` opens only the
user CSR node, checks the final magic/ABI, 80 MHz clock, formats, layouts,
capabilities and idle/error state, then closes it without writing a CSR.
DDR transfer readiness is checked by the runtime's actual write/readback; the
read-only ABI check does not prove DDR calibration or complete transfers.

`run` verifies assets again, loads resident weights with full DDR readback, and
runs all 32 layers for each active position. The configured default wall limit
is 7200 seconds and the command timeout is 120 seconds. Resource/wall limits are
checked at progress boundaries; each transport operation has a bounded timeout.
No automatic reset, retry, driver takeover or system reboot is performed.

If `--result` is omitted, a unique `AT_*_decode16` directory is created under
`output_dir`. Existing result directories are rejected. Keep the terminal open
until the native process exits. Inspect `run.json`, `progress.jsonl`,
`xdma.jsonl`, decode checkpoints and `outputs.txt`; an exit code alone does not
establish numerical verification. See [INFERENCE.md](INFERENCE.md) for result
fields and recovery boundaries.

An independently started power sampler can be referenced with repeated
`--power-log 'path\to\samples.csv'` arguments. The program records references and
end-of-run file snapshots. It does not start/stop that sampler or infer complete
measurement coverage from a filename. Finalize the sampler log and use the power
analysis tooling separately.

The older `tools/power/measure_full_run.ps1`, `sample_power.ps1` and
`analyze_model_power.py` describe the historical seven-rail READ_POUT-based
recording/recomputation workflow. Their MAX20751 `feedback_voltage_v` field uses
an obsolete decoding interpretation and is not current rail-voltage evidence.
The new VID/V×I observations came from the sealed KV128 as-run scripts and
published evidence, not an update to those old working-tree tools. See
[the decoding correction and measurement scopes](POWER_MEASUREMENT.md).
