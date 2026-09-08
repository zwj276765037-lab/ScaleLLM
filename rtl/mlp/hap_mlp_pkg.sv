`timescale 1ns / 1ps

package hap_mlp_pkg;
    // V1 was the historical W8/S42/S52 exploration.  V2 is the implemented
    // A8W4/S36/S43/S45 group-major contract and must never accept V1 files.
    localparam logic [31:0] HAP_MLP_FIXBIT_V1_FORMAT_ID = 32'h4838_4d01;
    localparam logic [31:0] HAP_FULL_FIXBIT_V1_FORMAT_ID = 32'h4838_4601;
    localparam logic [31:0] HAP_MLP_FIXBIT_V2_FORMAT_ID = 32'h4838_4d02;
    localparam logic [31:0] HAP_FULL_FIXBIT_V2_FORMAT_ID = 32'h4838_4602;

    localparam int MLP_QUERY_ROWS = 8;
    localparam int MLP_HIDDEN_DIM = 4096;
    localparam int MLP_INTERMEDIATE_DIM = 14336;
    localparam int MLP_GROUP_SIZE = 32;
    localparam int MLP_OUTPUT_COLS = 16;

    localparam int MLP_INPUT_GROUPS = 128;
    localparam int MLP_INTERMEDIATE_GROUPS = 448;
    localparam int MLP_GATE_UP_TILES = 896;
    localparam int MLP_DOWN_TILES = 256;

    localparam int MLP_TENSOR_W = 24;
    localparam int MLP_PRODUCT_W = 32;
    // Post-audit widths.  S36 is the group guard; S43/S45 are the two
    // projection accumulator widths frozen in source/09.
    localparam int MLP_GROUP_GUARD_W = 36;
    localparam int MLP_GATE_UP_ACCUM_W = 43;
    localparam int MLP_DOWN_ACCUM_W = 45;

    localparam int MLP_SILU_LUT_STEPS_PER_ONE = 256;
    localparam int MLP_SILU_LUT_ENTRIES = 8193;
    localparam int MLP_SILU_POSITIVE_BYPASS_Q16 = 16 <<< 16;
    localparam int MLP_SILU_NEGATIVE_ZERO_Q16 = -(16 <<< 16);
endpackage
