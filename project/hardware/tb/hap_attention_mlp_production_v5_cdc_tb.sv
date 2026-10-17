`timescale 1ns / 1ps
`include "tb/hap_attention_mlp_production_v5_joint_tb.sv"

// Full production port exercise with different relative phases. Leaf malformed
// framing/reset negatives belong to the separately owned paired-WRR CDC bench.
module hap_attention_mlp_production_v5_cdc_tb;
  hap_attention_mlp_production_v5_joint_tb #(
    .BFM_CORE_PHASE_NS(0.250), .BFM_DDR0_PHASE_NS(1.125), .BFM_DDR1_PHASE_NS(4.000)
  ) u_joint();
endmodule
