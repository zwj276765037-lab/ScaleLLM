# Build the current Decode16 hardware

Use `deploy/final/build_hardware.py` for the current sixteen-request, 80 MHz
design. It builds from RTL and Vivado-generated IP in a new output directory.
It does not consume old implementation checkpoints or IP caches.
`deploy/build_hardware.py` forwards to this current entry. The historical
prefill hardware and its builder remain in the `prefill` branch.

## Prerequisites

Use Linux, Python 3.10 or newer, `jq`, GNU `sha256sum`, Vivado 2025.2 with the
UltraScale+ device support and an appropriate synthesis license, and the
official VCU118 board files for `xilinx.com:vcu118:part0:2.0`. Supply the directory
containing `board.xml`, `part0_pins.xml` and `preset.xml`. Vendor tools, IP models,
board files and licenses are external dependencies; they are not redistributed.
The installed IP catalog supplies XDMA, DDR4, clock wizard, SmartConnect,
AXI register slices, reset and utility IP. XPM primitives come from Vivado.

From the repository root, set explicit local paths and prepare a new workspace:

```bash
python3 deploy/final/build_hardware.py check
python3 deploy/final/build_hardware.py prepare \
  --work /absolute/path/to/new-build \
  --vivado /absolute/path/to/Vivado/2025.2/bin/vivado \
  --board-files /absolute/path/to/boards/Xilinx/vcu118/2.0
python3 deploy/final/build_hardware.py stage \
  --work /absolute/path/to/new-build --stage validate
```

`check` verifies the frozen RTL/ROM/ABI/XDC and portable build-file hashes.
`prepare` copies those inputs into the independent workspace and records the
external board-file hashes. `validate` constructs and validates the block
design, checking clock and address-map settings, then stops before IP output
generation. It can be followed by a separate `create` in the same workspace.

```bash
python3 deploy/final/build_hardware.py stage --work /absolute/path/to/new-build --stage create
python3 deploy/final/build_hardware.py stage --work /absolute/path/to/new-build --stage elaborate
```

`create` generates all IP output products and the top wrapper. `elaborate`
performs native RTL elaboration. Neither command is a timing result.

## Full build

Full synthesis and implementation can take hours and require substantially more
memory than construction. Choose resource and wall-time limits suitable for
your machine before starting them. The following examples allow 3 hours for
synthesis, 8 hours for implementation, and 192 GiB tree RSS; they were not run
as part of the portable release check.

```bash
python3 deploy/final/build_hardware.py stage --work /absolute/path/to/new-build \
  --stage synth --timeout 10800 --rss-gib 192
python3 deploy/final/build_hardware.py stage --work /absolute/path/to/new-build \
  --stage impl --timeout 28800 --rss-gib 192
python3 deploy/final/build_hardware.py stage --work /absolute/path/to/new-build \
  --stage bitstream --timeout 2400 --rss-gib 192
```

Every stage uses one native run at a time and at most four threads on CPUs
`0,1,2,3`. Use `--cpus` for another set of at most four available CPUs, and
`--threads` to reduce the thread count. At least 64 GiB system RAM must remain
available; a guard terminates the owned process group on wall-time, RSS or
available-memory limits. Construction and elaboration are capped at 30 minutes
and 32 GiB. Each attempted stage directory is preserved and cannot be overwritten.
Logs, exit status, runtime, peak tree RSS and report hashes remain in that stage.

Synthesis writes its stitched checkpoint before reports. Implementation saves
checkpoints immediately after optimization, placement, physical optimization
and routing, before later reports. Implementation uses the native default
strategy, enables physical optimization and clears the incremental checkpoint.
The published bitstream additionally used incremental placement/routing and
native hold repair; its physical run is recorded as historical artifact evidence.
A fresh run can produce different placement, timing and bitstream bytes.

Bit generation requires the new workspace's routed checkpoint, complete routing,
zero routing errors, nonnegative global setup/hold/pulse margins, no failing
endpoints, and no Error/Critical Warning DRC findings. A timing failure retains
the checkpoint and reports, stops the stage, and does not produce a publishable
bitstream. The successful physical closure commands, their observed effects and explicit
portable `hold-sll` / `hold` stages are documented in
[PHYSICAL_CLOSURE.md](PHYSICAL_CLOSURE.md). This includes the original incremental
flow and its unavailable historical reference. No byte-identical or timing-identical
rebuild is promised.

## Verification status

The exact released artifact is
[`ScaleLLM_Final_Decode16_80MHz.bit`](../bitstream/ScaleLLM_Final_Decode16_80MHz.bit),
identified by [`final_decode16_manifest.json`](../bitstream/final_decode16_manifest.json).
The portable source identity is
[`hardware_source_manifest.json`](../deploy/final/hardware_source_manifest.json).
Fresh portable validation and complete project creation both passed under
Vivado 2025.2: validation took 335.707 seconds with 3,210,412,032 bytes peak tree
RSS; creation took 432.649 seconds with 3,467,943,936 bytes peak tree RSS.
Creation checked all generated IP outputs, the top wrapper, native compile
order and generated XCI settings. Inputs remained unchanged. Results and redacted
native logs are in [`build_validation.json`](evidence/final/build_validation.json).
Full RTL elaboration, synthesis, implementation and bit generation with this new
portable entry have not been run.

The included transport testbenches exercise reservation accounting, stalled
AR/output stability, response errors and legal ordered shared-channel schedules.
They are focused protocol checks and do not replace full model or board validation.

Run the focused checks from the repository root:

```bash
python3 -m unittest discover -s project/hardware/tests -p test_release_build.py -v
python3 project/hardware/tests/run_transport.py \
  --vivado /absolute/path/to/Vivado/2025.2/bin/vivado \
  --work /absolute/path/to/new-transport-test
```

The actual publication guard is CPU-tested against passing timing, negative
setup/hold/pulse margins, nonzero failing endpoints, incomplete/error routing,
critical DRC findings and malformed reports. The two transport testbenches passed
fresh XSim runs; coverage and input hashes are in
[`transport_tests.json`](evidence/final/transport_tests.json).

The explicit optional repair stages and `--source-dcp` bitstream selection were
added after the measured fresh create run. The constructor itself retains the
same tested hash. These later commands passed 27 CPU fixture/wiring cases across
11 test methods; they have not been executed through Vivado. Exact old driver
hashes and this later scope are separated in the build-validation manifest.
See [PHYSICAL_CLOSURE.md](PHYSICAL_CLOSURE.md) before selecting a repair method.
