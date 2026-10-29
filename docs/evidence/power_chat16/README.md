# Synchronized seven-rail model power data

The measured quantities are selected FPGA regulator outputs, not whole-board input or isolated chip power. Model wall timestamps are an energy integration axis; only DONE_CYCLES/80MHz describes FPGA command time.

telemetry.jsonl.gz preserves every complete sweep, raw words, conversion sources, per-rail timings and validity, with deterministic gzip mtime=0. receipt.json and device/ contain only the actual fields required by the analysis; private process/device identities and machine paths were omitted. reference_run.json contains prior actual generated IDs for repeatability, not gold. No vendor executable/driver is included.

The inference completed successfully, but the original overall stage is FAIL: the sampler exceeded its finalization timeout after all observed windows. Its native exit is unknown (null), never replaced with0. The explicit exception below accepts only this exact failure with a clean model/release, valid complete sweeps and100% coverage of all three windows.

Recompute using a new output directory:

```text
python tools/power/analyze_model_power.py --measurement <dataset-dir> --reference-run <dataset-dir>/reference_run.json --public-dir <new-output-dir> --allow-sampler-finalization-timeout
```

Adjacent sample midpoints are integrated with clipped linear trapezoids. Gaps above the reported threshold and unobserved boundary time are excluded and reported; no defaults fill missing measurements. The +/-3W sum and +/-6W difference numbers cover only the three coarse READ_POUT channels. The other four rails and additional sensor errors are not fully evaluated. Roughly1s sampling cannot resolve millisecond kernel peaks or justify full-duty extrapolation.
