# DSP leaf post-synthesis functional evidence

Both entries below use the actual candidate leaf source and a fresh Vivado 2025.2 functional netlist. This is leaf functional evidence; board synthesis and physical results are separate.

## dsp_raw_only

- Status: PASS; actual source SHA-256 `f14295ce66a8d72ebf26fcc96d79bb1a6b53166f5c2772a449cdd15bee7f6210`; normalized reference SHA-256 `18a2bad1a3b7df345abfaf3428a8a5bec245d9580dc3b336e6153736a23a9f6a`.
- Fresh netlist SHA-256 `157e2b741ac274993d7844cd3a23b45b15512f662f2a05705e626474eadf54ad`; DSP48E2 count 2; simulator compiled `unisims_ver.DSP48E2`.
- Gold and protocol: 567 directed, 131072 S17 encodings in each column, 4096 seeded random, 135747 accepted = 135741 emitted + 6 canceled, II=1, three-cycle handshake, backpressure, reset, clear, final drain.
- Results: `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/0_Hardware_supplementation_experiment/experiment/mlp_scalecode_dsp_board/functional/dsp_raw_only/result.json`; synth log: `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/0_Hardware_supplementation_experiment/experiment/mlp_scalecode_dsp_board/functional/dsp_raw_only/attempts/20261114T010004Z/synth/console.log`; simulation log: `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/0_Hardware_supplementation_experiment/experiment/mlp_scalecode_dsp_board/functional/dsp_raw_only/attempts/20261114T010004Z/sim/console.log`.

## dsp_all

- Status: PASS; actual source SHA-256 `f645dbf2e78f7ea2f1cc372cbe1cfd97c3b7ff3b63ca612a6dec29308786facb`; normalized reference SHA-256 `18a2bad1a3b7df345abfaf3428a8a5bec245d9580dc3b336e6153736a23a9f6a`.
- Fresh netlist SHA-256 `af72c088604b33be28d4c1bcae0e20898b09a67751db80a2df20a1847cf374c6`; DSP48E2 count 4; simulator compiled `unisims_ver.DSP48E2`.
- Gold and protocol: 567 directed, 131072 S17 encodings in each column, 4096 seeded random, 135747 accepted = 135741 emitted + 6 canceled, II=1, three-cycle handshake, backpressure, reset, clear, final drain.
- Results: `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/0_Hardware_supplementation_experiment/experiment/mlp_scalecode_dsp_board/functional/dsp_all/result.json`; synth log: `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/0_Hardware_supplementation_experiment/experiment/mlp_scalecode_dsp_board/functional/dsp_all/attempts/20261114T010405Z/synth/console.log`; simulation log: `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/0_Hardware_supplementation_experiment/experiment/mlp_scalecode_dsp_board/functional/dsp_all/attempts/20261114T010405Z/sim/console.log`.

The prior RTL run `mlp_sc_sim_20261113T081037Z_5219957a` was hash-checked and is recorded in each candidate result as reused prior evidence. It is distinct from these new netlist simulations.
