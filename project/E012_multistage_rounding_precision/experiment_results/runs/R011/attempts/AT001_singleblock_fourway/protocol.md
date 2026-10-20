# R011 singleblock31 targeted diagnostic

Three predeclared formal R006 cases with paired hidden30: c4:6896 T128,imdb_test:10960 T128,ag_news_test:4667 T43. No dev/model-wide rerun, earlier31 layers, LM head, logits or ACC/PPL. Construct only original seven V5 linears, original norms/RoPE/SiLU/Softmax LUT.

A CURRENT(Hc), B OUTPUT_ONLY(Hr), C OUTPUT_ONLY(Hc), D CURRENT(Hr); dynamic encoding recomputed every arm. A/B must reproduce saved hidden31/finalnorm and PreparedActivation/KV raw exactly.36 stages include normalized activations, projections, RoPE/KV/QK/Softmax/PV, attention residual, gate/up,SiLU,gated product,Down and final residual/norm. Every stage records absolute error/signal energies and RMSE/RMS, relativeL2,max; causal mask applied QK/probability. No percentage subtraction for attribution.

Report exact vector A-B=(A-C)+(C-B) and cross term; residual error vector includes separately measured FP32 addition roundoff difference, not silently called exact real addition. Signal cancellation and error cross term measured.

Existing independent full1024 evidence motivates exactly two predeclared conditional reference-trajectory cuts: gated_product and down_proj. Change one stage in current path, recompute all suffix; all3cases/allcuts retained. Down cut must equal literal FP32 current_attention_residual+reference_MLP_output bitwise. These are diagnostics, not deployed corrections or unique/additive causal percentages.

CPU context restoration and vector identity before launch. Frozen-source GPU unobserved/observed bitwise qualification and exception restoration before actual cases. Full source/input/weights identities, decisive raw stages and dynamic arrays saved,512MiB limit. One GPU0UUID,CPU1,RSS8GiB/GPU24GiB,900sec,launchfree30/runtimefree8/RAM32GiB. Supervisor records true PIDs and native wait/reaped evidence. Routine failure gets a new attempt, source frozen once consumed.
