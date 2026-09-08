`timescale 1ns / 1ps

module hap_dual_ddr_weight_bridge_ooc (
    input  wire                  ddr0_clk,
    input  wire                  ddr0_rst_n,
    input  wire                  ddr1_clk,
    input  wire                  ddr1_rst_n,
    input  wire                  core_clk,
    input  wire                  core_rst_n,
    input  wire                  clear,
    input  wire                  ddr0_beat_valid,
    output wire                  ddr0_beat_ready,
    input  wire [511:0]          ddr0_beat_data,
    input  wire                  ddr0_beat_last,
    input  wire                  ddr1_beat_valid,
    output wire                  ddr1_beat_ready,
    input  wire [511:0]          ddr1_beat_data,
    input  wire                  ddr1_beat_last,
    input  wire                  meta_valid,
    output wire                  meta_ready,
    input  wire [9:0]            meta_tile,
    input  wire [6:0]            meta_group,
    input  wire [255:0]          meta16,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [9:0]            out_tile,
    output wire [6:0]            out_group,
    output wire [4095:0]         out_weight_s8,
    output wire [255:0]          out_meta16,
    output wire                  error
);

    wire ddr0_half_valid;
    wire ddr0_half_ready;
    wire [2047:0] ddr0_half_data;
    wire ddr1_half_valid;
    wire ddr1_half_ready;
    wire [2047:0] ddr1_half_data;
    wire error0;
    wire error1;
    wire assembler_error;

    hap_ddr512_halfgroup_async u_ddr0 (
        .ddr_clk(ddr0_clk), .ddr_rst_n(ddr0_rst_n), .ddr_clear(clear),
        .beat_valid(ddr0_beat_valid), .beat_ready(ddr0_beat_ready),
        .beat_data(ddr0_beat_data), .beat_last(ddr0_beat_last),
        .core_clk(core_clk), .core_rst_n(core_rst_n), .core_clear(clear),
        .half_valid(ddr0_half_valid), .half_ready(ddr0_half_ready),
        .half_data(ddr0_half_data), .ddr_beat_count(), .ddr_half_count(),
        .core_half_count(), .error(error0)
    );

    hap_ddr512_halfgroup_async u_ddr1 (
        .ddr_clk(ddr1_clk), .ddr_rst_n(ddr1_rst_n), .ddr_clear(clear),
        .beat_valid(ddr1_beat_valid), .beat_ready(ddr1_beat_ready),
        .beat_data(ddr1_beat_data), .beat_last(ddr1_beat_last),
        .core_clk(core_clk), .core_rst_n(core_rst_n), .core_clear(clear),
        .half_valid(ddr1_half_valid), .half_ready(ddr1_half_ready),
        .half_data(ddr1_half_data), .ddr_beat_count(), .ddr_half_count(),
        .core_half_count(), .error(error1)
    );

    hap_dual_ddr_weight_group_assembler u_assembler (
        .clk(core_clk), .rst_n(core_rst_n), .clear(clear),
        .ddr0_valid(ddr0_half_valid), .ddr0_ready(ddr0_half_ready),
        .ddr0_half(ddr0_half_data), .ddr1_valid(ddr1_half_valid),
        .ddr1_ready(ddr1_half_ready), .ddr1_half(ddr1_half_data),
        .meta_valid(meta_valid), .meta_ready(meta_ready),
        .meta_tile(meta_tile), .meta_group(meta_group), .meta16(meta16),
        .out_valid(out_valid), .out_ready(out_ready), .out_tile(out_tile),
        .out_group(out_group), .out_weight_s8(out_weight_s8),
        .out_meta16(out_meta16), .assembled_group_count(),
        .error(assembler_error)
    );

    assign error = error0 | error1 | assembler_error;
endmodule
