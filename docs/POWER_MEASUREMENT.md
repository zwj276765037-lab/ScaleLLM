# Power evidence: current VCCINT telemetry and historical seven-rail integration

The latest [fixed-active16 KV128 run](evidence/kv128_chat16/README.md) records
VCCINT conditional telemetry during the real inference needed to build KV128.
The older seven-rail experiment covers the complete 16-request × 32-token
wall-clock workload, including ten-second idle windows before and after it.
Both use the VCU118 J39 PMBus connection independently of XDMA, but their
electrical scope, time windows and statistical summaries differ.

| Evidence | Electrical and time scope | Available result |
| --- | --- | --- |
| Current KV32/KV128 observation windows | VCCINT only; sequential V/I read pairs contained in command BUSY windows | Conditional sample distributions; no strict active mean or energy |
| Historical 16×32 continuous recording | Seven selected regulator outputs over the full model wall-clock window | 11.3648 W time-weighted telemetry sum and 39,130.65 J integrated telemetry |
| Whole-board supply input | All actual board supply inputs | Not measured |

Neither **5.525 W** from the current conditional samples nor the historical
**11.3648 W** is a whole-board input-power measurement. The historical integral
includes initialization, CPU work, transfers and host gaps; it is not an
FPGA-command-only energy integral.

## Current command-window observations

The same original sixteen prompts were run through position 127 while retaining
all slots. The sampler observed the position31 and position127 target steps,
each with 32 Attention and 32 MLP commands. The current path uses the official
read-only telemetry interface, recorded VOUT_MODE/READ_VOUT/READ_IOUT words,
shared host QPC timestamps, and each command's conservative BUSY window.

| KV | Command | Eligible V/I pairs | Commands with pairs | V×I median / W | Range / W |
| --- | --- | ---: | ---: | ---: | ---: |
| 32 | Attention | 24 | 24/32 | 5.7375 | 5.525–8.925 |
| 32 | MLP | 17 | 17/32 | 5.5250 | 5.525–11.050 |
| 128 | Attention | 87 | 32/32 | 5.5250 | 5.525–8.925 |
| 128 | MLP | 10 | 10/32 | 5.5250 | 5.525–5.525 |

There are 27,953 and 30,547 raw V/I pairs respectively; 41 and 97 qualify,
covering 41/64 and 42/64 target commands. The complete envelope of both reads
must fit inside one command. The values remain sequential, non-simultaneous
telemetry products, with unequal samples per command and no time integration.
The median pair duration is about 10.6 ms. The sensor's measurement history,
update lag and absolute accuracy are not established: an in-BUSY transaction
does not prove an entirely in-BUSY sensor aperture.

The observed IOUT code spacing is 0.5 A and VOUT is 0.85 V, yielding a 0.425 W
product-code spacing; READ_POUT codes include 6/8/10/12 W. Code spacing is not
an instrument accuracy specification, and V×I's extra decimal places do not
prove better physical precision. The two windows occur sequentially in one
run, with no randomized repeat or independent temperature control. Neither a
lower sample median nor repeated 5.525 W values establish a lower true KV128
active power.

Both raw collectors completed, and independent PID/birth-time observations
confirmed their processes had exited. Their original launcher receipts still
say `SAMPLING`, `exit_code=null`; the final status is
`RAW_COMPLETE_EXIT_CODE_UNKNOWN`. No normal exit code is invented. Strict
command-period mean power, energy, J/token, a new seven-rail sum and whole-board
input power remain `NOT_ESTABLISHED`/null.

See [raw/derived board evidence and downloads](evidence/kv128_chat16/README.md),
[power summary](evidence/kv128_chat16/results/power_summary.json),
[KV32 pairs](evidence/kv128_chat16/results/power_kv32.csv) and
[KV128 pairs](evidence/kv128_chat16/results/power_kv128.csv). The validated current
VID/V×I collection came from the run's sealed as-run scripts in that evidence
package; it is not a claim that the older working-tree sampler below has been
updated to this method.

## MAX20751 voltage decoding correction

For the observed `VOUT_MODE=0x20` (VID, VR12.0), the MAX20751 guide gives
`V = (raw16 - 1) / 200 + 0.25`. Little-endian bytes `79 00` give code 121 and
**0.85 V**; the other historical MAX20751 codes 131 and 191 give 0.90 and 1.20 V.
This follows the manufacturer's
[PMBus guide, §7.4/Table 9 and Eq. 28](https://www.analog.com/media/en/technical-documentation/user-guides/max20751-pmbus-implementation-guide.pdf),
with the read mode checked before applying that interpretation.

The historical `sample_power.ps1` instead used `raw/512` and called the result
`feedback_voltage_v`; its feedback-node/divider interpretation was incorrect.
The old `analyze_model_power.py` and frozen summaries retain that legacy wording.
Those fields must not be used as current rail-voltage evidence. The old
seven-rail power sum used READ_POUT for all three MAX20751 rails, so correcting
this unused voltage interpretation does not change the published 11.3648 W
integral. Frozen raw records and their original status remain unchanged.

The following electrical table, sampler commands and recomputation instructions
describe that **historical seven-rail READ_POUT-based workflow**. This publication
does not change the old scripts' numerical behavior or source identity.

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
to fill a missing voltage measurement. The historical power calculation uses
READ_POUT for the three MAX20751 regulators; their legacy voltage-display
fields have the decoding error described above.

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

## Historical seven-rail recording entry

These commands invoke the old public seven-rail sampler and orchestration.
They are not the as-run KV128 conditional-telemetry method, and their legacy
MAX20751 voltage fields remain unsuitable for voltage interpretation. Use them
only within that documented scope; do not infer strict command-active coverage
or current VID/V×I validation from a successful run of this entry.

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

## Recompute the historical seven-rail measurement

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
