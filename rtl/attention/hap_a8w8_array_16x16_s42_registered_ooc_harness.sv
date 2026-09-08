`timescale 1ns / 1ps

// Timing-only exception-free registered boundary for comparing the legacy
// monolithic Attention array with P1_ATTN_COL2_12_2.  Only clk is a top-level
// port.  Every functional source and sink bit is represented by a one-to-one
// resetless FF, including rst_n/clear, so no asynchronous-reset false path or
// abstract OOC PARTPIN delay is needed.  This harness is not production RTL.
module hap_a8w8_array_16x16_s42_registered_ooc_harness #(
    parameter integer USE_COL3 = 1
) (
    input wire clk
);
    localparam integer SRC_W = 13766;
    localparam integer SINK_W = 6275;
    localparam integer S_RST_N = 0;
    localparam integer S_CLEAR = 1;
    localparam integer S_IN_VALID = 2;
    localparam integer S_FIRST = 3;
    localparam integer S_LAST = 4;
    localparam integer S_REGION_ACT = 5;
    localparam integer S_ZERO = S_REGION_ACT + 8192;
    localparam integer S_ROW_CODE = S_ZERO + 1024;
    localparam integer S_ROW_SHIFT = S_ROW_CODE + 128;
    localparam integer S_WEIGHT = S_ROW_SHIFT + 96;
    localparam integer S_WEIGHT_CODE = S_WEIGHT + 4096;
    localparam integer S_WEIGHT_SHIFT = S_WEIGHT_CODE + 128;
    localparam integer S_OUT_READY = S_WEIGHT_SHIFT + 96;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SRC_W-1:0] src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SINK_W-1:0] sink_r;
    always @(posedge clk)
        src_r <= {src_r[SRC_W-2:0], ~src_r[SRC_W-1]};

    wire in_ready;
    wire out_valid;
    wire [6143:0] out_s24;
    wire [31:0] accepted_group_count;
    wire [31:0] accumulated_group_count;
    wire [31:0] output_tile_count;
    wire [31:0] saturation_count;
    wire error;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [SINK_W-1:0] dut_outputs = {
        error, saturation_count, output_tile_count,
        accumulated_group_count, accepted_group_count,
        out_s24, out_valid, in_ready
    };
    always @(posedge clk)
        sink_r <= dut_outputs;

    generate
        if (USE_COL3 != 0) begin : g_col3
            (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
            hap_a8w8_array_16x16_s42_col3 u_dut (
                .clk(clk), .rst_n(src_r[S_RST_N]),
                .clear(src_r[S_CLEAR]), .in_valid(src_r[S_IN_VALID]),
                .in_ready(in_ready), .in_first_group(src_r[S_FIRST]),
                .in_last_group(src_r[S_LAST]), .in_wave(1'b0),
                .region_act_u8(src_r[S_REGION_ACT +: 8192]),
                .lane_act_zero_point(src_r[S_ZERO +: 1024]),
                .row_act_scale_code(src_r[S_ROW_CODE +: 128]),
                .row_act_scale_shift(src_r[S_ROW_SHIFT +: 96]),
                .col_wgt_s8(src_r[S_WEIGHT +: 4096]),
                .col_wgt_scale_code(src_r[S_WEIGHT_CODE +: 128]),
                .col_wgt_scale_shift(src_r[S_WEIGHT_SHIFT +: 96]),
                .out_valid(out_valid), .out_ready(src_r[S_OUT_READY]),
                .out_wave(),
                .out_s24(out_s24),
                .accepted_group_count(accepted_group_count),
                .accumulated_group_count(accumulated_group_count),
                .output_tile_count(output_tile_count),
                .saturation_count(saturation_count), .error(error)
            );
        end else begin : g_reference
            (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
            hap_a8w8_array_16x16_s42 u_dut (
                .clk(clk), .rst_n(src_r[S_RST_N]),
                .clear(src_r[S_CLEAR]), .in_valid(src_r[S_IN_VALID]),
                .in_ready(in_ready), .in_first_group(src_r[S_FIRST]),
                .in_last_group(src_r[S_LAST]),
                .region_act_u8(src_r[S_REGION_ACT +: 8192]),
                .lane_act_zero_point(src_r[S_ZERO +: 1024]),
                .row_act_scale_code(src_r[S_ROW_CODE +: 128]),
                .row_act_scale_shift(src_r[S_ROW_SHIFT +: 96]),
                .col_wgt_s8(src_r[S_WEIGHT +: 4096]),
                .col_wgt_scale_code(src_r[S_WEIGHT_CODE +: 128]),
                .col_wgt_scale_shift(src_r[S_WEIGHT_SHIFT +: 96]),
                .out_valid(out_valid), .out_ready(src_r[S_OUT_READY]),
                .out_s24(out_s24),
                .accepted_group_count(accepted_group_count),
                .accumulated_group_count(accumulated_group_count),
                .output_tile_count(output_tile_count),
                .saturation_count(saturation_count), .error(error)
            );
        end
    endgenerate

    initial begin
        if (S_OUT_READY != SRC_W-1 || $bits(dut_outputs) != SINK_W)
            $error("Attention registered OOC vector layout mismatch");
    end
endmodule
