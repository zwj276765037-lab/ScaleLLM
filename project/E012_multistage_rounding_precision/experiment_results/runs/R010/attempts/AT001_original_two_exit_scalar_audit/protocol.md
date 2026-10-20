# R010 original lastlayer scalar audit

Original production index31 o_proj/down_proj only. Fixed R006 15-audit-document roster, current complete PreparedActivation01/03, 1746 tokens, 14303232 output scalars; no model assembly or prefix forward. Original quantizer in128-row chunks, immutable checkpoint matrices.

Observer exports original finite-width accumulator before finalcut8, original saturated integer output, exact quotient/remainder unrounded result and independent same-F16 common exit. Full active-group right/left/total-shift and nonzero-lost-remainder counters are separate from output denominators. Inactive pairs excluded. Discarded one bits counted separately from requested shift bits.

Definitions: final_cut8 compares accumulator/2^24 against half-away rounded code/2^16 before saturation. Total_rounding compares current saturated code/2^16 against same-input exact unrounded sum. Additional_intermediate compares current vs same-F16 OUTPUT_ONLY; saturation and actual intcode to HostFP32 decoding reported separately. Pointwise relative denominator abs(original), no epsilon; exact integer >0.1/1/5/10percent tests among nonzero originals; zeros separate, all outputs retained. RMS-normalized thresholds and energy shares included. Selected before/after witnesses labelled deterministic or diagnostic extrema.

CPU Fraction qualification precedes GPU. Synthetic GPU qualification checks original outputs/counters, independent reference, arbitrary-precision oracle and all histogram totals before real inputs. All15 real inputs compare original kernel, unchanged exact reference, R006 witness dependencies/codes and old local aggregate. Full output raw NPZ saved for independent CPU复算. No overall32layer causal inference and no scalar-1024 extrapolation.

GPU0 exact UUID, one worker/CPU1/RSS8GiB/GPU24GiB/900seconds/512MiB; launchfree30GiB/runtimefree8GiB/RAM32GiB. Parent supervisor waits/reaps actual worker and records external native exit; failed attempts frozen and preserved. No production/old consumed sources modified.
