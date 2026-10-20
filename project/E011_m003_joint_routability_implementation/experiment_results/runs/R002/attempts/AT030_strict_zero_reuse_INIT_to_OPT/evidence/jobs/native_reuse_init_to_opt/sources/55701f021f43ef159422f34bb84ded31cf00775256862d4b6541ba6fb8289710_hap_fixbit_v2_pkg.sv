`timescale 1ns / 1ps

package hap_fixbit_v2_pkg;
    localparam logic [31:0] HAP_ATTN_FIXBIT_V2_FORMAT_ID = 32'h4838_4102;
    localparam logic [31:0] HAP_ATTN_FIXBIT_V3_FORMAT_ID = 32'h4838_4103;
    localparam int GROUP_SIZE = 32;
    localparam int TENSOR_W = 24;
    localparam int HADAMARD_NORM_W = 27;
    localparam int INV_SQRT32_Q16 = 11585;
endpackage
