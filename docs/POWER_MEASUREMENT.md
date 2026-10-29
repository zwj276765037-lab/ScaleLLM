# Continuous inference power measurement

The published experiment records the complete 16-request × 32-token workload,
with ten seconds of idle before it and ten seconds after it. Power is sampled
through the VCU118 J39 PMBus connection, independently of the XDMA inference
connection. The model window includes initialization, host work, transfers and
all generation rounds. Its wall-clock duration is used to integrate energy;
FPGA speed still comes only from hardware cycle counters.

## Electrical scope

The seven measured regulator outputs are identified by the VCU118's
[UG1224 board guide, Tables 3-33/3-34](https://docs.amd.com/v/u/en-US/ug1224-vcu118-eval-bd).
They are read through the regulator addresses, not the separate INA226 addresses.

| PMBus address | Rail | Regulator | Power source used |
| --- | --- | --- | --- |
| `0x70` | VCCINT_FPGA | MAX20751 | READ_POUT |
| `0x11` | VCC1V8_FPGA | MAX15301 | Measured VOUT × IOUT |
| `0x12` | VADJ_1V8_FPGA | MAX15301 | Measured VOUT × IOUT |
| `0x15` | VCCINTIO_BRAM_FPGA | MAX15301 | Measured VOUT × IOUT |
| `0x14` | VCC1V2_FPGA | MAX15301 | Measured VOUT × IOUT |
| `0x72` | MGTAVCC_FPGA | MAX20751 | READ_POUT |
| `0x73` | MGTAVTT_FPGA | MAX20751 | READ_POUT |

The sum is **selected FPGA-related regulator output power**, not isolated chip
total power, whole-board 12 V input power or host-system power. It omits other
rails/loads and conversion losses. No nominal voltage is multiplied by current
to fill a missing voltage measurement. MAX20751 READ_VOUT observations refer to
the feedback node; the sampler uses READ_POUT for those three regulators.

## External software and preparation

Use the board's USB-to-PMBus adapter, its vendor driver, 32-bit Windows PowerShell,
and separately obtained [Analog Devices Digital PowerTool 2.32.27](https://www.analog.com/en/resources/evaluation-hardware-and-software/evaluation-boards-kits/maxpowertool002.html).
The observed official `MaximDigitalPower.exe` has SHA-256
`d5749e5ebb80b4ad7c81c73cc9863467bb988915922a9337da75bb304fc23f31`.
The vendor download must be independently obtained; a matching version label
alone does not prove matching bytes.

Prepare a new local runtime from your own official installation. This copies
only the explicit dependency list and extracts two embedded XML descriptions,
requiring their identities to match the recorded originals. It does not start
the GUI, open USB/PMBus, install drivers or change vendor-installed files.

```powershell
& "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive `
  -File tools\power\prepare_powertool.ps1 `
  -SourceRoot 'C:\Program Files (x86)\Maxim Integrated Products\MaximDigitalPower' `
  -OutputRoot 'E:\measurement\powertool-runtime'
```

[Runtime identities](../tools/power/powertool_runtime_manifest.json) bind the
executable, eight DLLs and the MAX20751 / 004328 XML descriptions. The repository
does not distribute these vendor binaries, XML files or USB driver.

The **continuous reference run used a previously modified 2.32.27 executable**,
SHA `ca0cebc63364312c56c3949655b40352758177b243b56eadc1c7bfff30f08e68`.
It was rebuilt as 32-bit with an added GUI resource-name mapping and changes to
GUI device-loss/rescan handling. The original IL was also normalized for
assembly of infinity/NaN constants. It is not the official download. The
telemetry script directly uses `DonglePacketizer`, `MemoryDescriptor` and the
external XML; it does not construct the modified GUI/device-list path. This
provenance is retained instead of relabeling the measured dependency as stock.

The official runtime preparation passed with all eight DLL identities and both
XML hashes matching. After the full measurement had stopped and released its
resources, a bounded **three-sweep read using the official executable passed**
(native exit 0, 5.779 seconds). It opened no GUI, issued no FPGA commands, and
left no owned processes or lease. This validates the official dependency's
short read path; the full continuous reference data still came from the
modified executable identified above.

The public sampler's streaming completion path also passed a focused Windows
check with 3,000 synthetic JSONL sweeps, no accumulated sample history, and a
small final summary. This tests the repair for the reference run's bulk-save
timeout; it is not a second complete inference measurement. See
[power-tool validation](evidence/final/power_tool_validation.json).

## Record a new run

First complete [deployment](DEPLOYMENT.md), verify the final image and prepare
requests. Leave the board idle and close other PMBus programs. Obtain your own
adapter serial from its normal vendor enumeration; no machine-specific serial
is embedded in the project. Use a new result directory.

From 64-bit Windows PowerShell in the repository root:

```powershell
.\tools\power\measure_full_run.ps1 `
  -RuntimeRoot 'E:\measurement\powertool-runtime' `
  -AdapterSerial 'YOUR_ADAPTER_SERIAL' `
  -Config 'deploy\config.local.json' `
  -Requests 'examples\requests16.json' `
  -Output 'outputs\power16' `
  -BoardLease 'outputs\board.lock' `
  -Python (Resolve-Path '.\.venv\Scripts\python.exe').Path
```

Add `-PlanOnly` to inspect the command without opening a device or creating
results. Use the same lease file for cooperating board jobs. This launcher
requires CPUs 0–7 to be available, an 8 GiB process-tree memory ceiling and at
least 2 GiB free RAM, matching the measured host contract. Its whole-stage limit
is 7,500 seconds. The portable orchestration has Windows parser/argument/cleanup
checks and a real CLI dry-run; a complete board run through this new wrapper
has not been performed. The reference run used the original frozen orchestration.

The launcher collects an idle baseline, invokes the public inference CLI, then
collects idle-after samples. It records UTC and the shared Windows performance
counter frequency/ticks for phase boundaries. The sampler writes every complete
sweep to JSONL as it is collected and records individual rail-read timestamps,
raw words, conversion sources and validity gates. A stale or failed sampler
prevents the run from being reported as a successful complete measurement process.
The launcher manages only its own children and stops them on bounded failures.
It does not program the FPGA or reset the board.

The read command allowlist is `VOUT_MODE (0x20)`, `READ_VOUT (0x8B)`,
`READ_IOUT (0x8C)` and, where used, `READ_POUT (0x96)`. It does not change rail
settings, clear faults or scan unlisted addresses. The MAX15301 command formats
and need for current calibration are documented in the manufacturer's
[PMBus command guide](https://www.analog.com/media/en/technical-documentation/user-guides/max15301-pmbus-command-set-users-guide.pdf).

## Recompute the published measurement

No hardware or vendor software is needed to analyze the included evidence:

```bash
python3 tools/power/analyze_model_power.py \
  --measurement docs/evidence/power_chat16 \
  --reference-run docs/evidence/power_chat16/reference_run.json \
  --public-dir outputs/recomputed_power \
  --allow-sampler-finalization-timeout
```

The supplied reference recording has a documented **post-window sampler
finalization timeout**: inference succeeded and streaming JSONL covers every
window, and the complete evidence JSON was saved, but the redundant console copy did
not finish before the guard stopped it.
The command above explicitly enables analysis of that specific failure. It
requires complete window coverage, successful model execution and verified
cleanup; other failures remain rejected. The original wrapper state stays
`FAIL` and sampler native exit stays unknown. This option does not turn a failed
process into a successful one. See [reported results](PERFORMANCE_AND_RESOURCES.md#full-inference-power).

The analyzer accepts raw or gzip-compressed JSONL without discarding samples.
It validates the recorded clock, complete sweeps, rail sums, command/round
counts, native exit results and final runtime state. The published subset
retains all numerical inputs needed to repeat this calculation while removing
adapter serials, personal paths and process identifiers.

A sweep is positioned at the midpoint of its actual start/end counter ticks.
Adjacent sweep sums are integrated with piecewise-linear trapezoids, clipped
to each measured window. Intervals above `max(3 seconds, 3 × median interval)`
are excluded and reported as missing coverage. Unobserved boundaries are not
extrapolated. The result includes covered time, integrated joules, time-weighted
mean watts, gaps, idle means and the FPGA counter-time fraction of the model
window. Sequential rail readings are not simultaneous samples.

The three READ_POUT channels have observed **2 W steps**. Their combined
half-step quantization contribution is **±3 W** to the sum and **±6 W** to an
active-minus-idle difference. These are not complete error bars: the four V×I
channels, calibration, timing skew and other sensor errors have not been fully
characterized. Averaging does not remove an unknown systematic quantization
error. Near-zero negative measurements and quantized zeros are preserved.

The sampling cadence is approximately one second; actual intervals are in the
data. It cannot resolve individual millisecond kernel peaks. Full-run average
power includes host/transfer idle gaps; dividing by FPGA duty or extrapolating
to continuous full-load power is not justified by this experiment.

## Figures

The standalone SVG/PNG figures use Matplotlib (rendered with 3.6.3). Install it
in a separate plotting environment if needed; inference and numerical analysis
do not depend on it.

```bash
python3 tools/plot_reports.py --inference docs/evidence/inference_chat16 --power docs/evidence/power_chat16 --outputs docs/evidence/inference_chat16
```

The FPGA plot uses only cycle-derived seconds. The English power line chart
shows non-overlapping 60-second time-weighted averages at each interval's center,
with the full-run mean as a dashed reference. The final interval covers only the
remaining inference time. All observations, including spikes, contribute via
the same linear interpolation and gap rule as the numerical report; the sum of
interval energies is checked against the published integral. It includes
host/transfer gaps and represents the seven measured regulator outputs. The
complete time series and individual rail values remain available in
`power_sweeps.csv` and `summary.json`.
Four additional PNG/SVG pages show all sixteen actual prompts and outputs,
read directly from `outputs.json` with the original 32-token endings preserved.
