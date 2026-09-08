`timescale 1ns / 1ps

// Command-level group-major down subsystem.  One command launches the dual
// MIG W4 reader for GROUPS*TILES transactions while cohort16 U8 product
// activation groups arrive from the SwiGLU/Hadamard/A8 frontend.  Completion
// requires both an atomic DDR counter snapshot and all TILES S24 projection
// outputs; neither reader completion nor final compute output alone is enough.
module hap_mlp_down_ddr_command16_s45 #(
    parameter integer AXI_ADDR_W = 32,
    parameter integer TILES = 256,
    parameter integer GROUPS = 448,
    parameter integer TILE_W = (TILES <= 2) ? 1 : $clog2(TILES),
    parameter integer OUTSTANDING_DEPTH = 8
) (
    input  wire                          core_clk,
    input  wire                          core_rst_n,
    input  wire                          core_clear,
    input  wire                          command_valid,
    output wire                          command_ready,
    input  wire [AXI_ADDR_W-1:0]         ddr0_base_addr,
    input  wire [AXI_ADDR_W-1:0]         ddr1_base_addr,

    input  wire                          activation_valid,
    output wire                          activation_ready,
    input  wire [16*32*8-1:0]            activation_u8x16x32,
    input  wire [16*24-1:0]              activation_meta_u24x16,
    input  wire                          weight_meta_valid,
    output wire                          weight_meta_ready,
    input  wire [223:0]                  weight_meta_u224,

    input  wire                          ddr0_clk,
    input  wire                          ddr0_rst_n,
    output wire                          ddr0_axi_arvalid,
    input  wire                          ddr0_axi_arready,
    output wire [AXI_ADDR_W-1:0]         ddr0_axi_araddr,
    output wire [7:0]                    ddr0_axi_arlen,
    output wire [2:0]                    ddr0_axi_arsize,
    output wire [1:0]                    ddr0_axi_arburst,
    input  wire                          ddr0_axi_rvalid,
    output wire                          ddr0_axi_rready,
    input  wire [511:0]                  ddr0_axi_rdata,
    input  wire [1:0]                    ddr0_axi_rresp,
    input  wire                          ddr0_axi_rlast,

    input  wire                          ddr1_clk,
    input  wire                          ddr1_rst_n,
    output wire                          ddr1_axi_arvalid,
    input  wire                          ddr1_axi_arready,
    output wire [AXI_ADDR_W-1:0]         ddr1_axi_araddr,
    output wire [7:0]                    ddr1_axi_arlen,
    output wire [2:0]                    ddr1_axi_arsize,
    output wire [1:0]                    ddr1_axi_arburst,
    input  wire                          ddr1_axi_rvalid,
    output wire                          ddr1_axi_rready,
    input  wire [511:0]                  ddr1_axi_rdata,
    input  wire [1:0]                    ddr1_axi_rresp,
    input  wire                          ddr1_axi_rlast,

    output wire                          out_valid,
    input  wire                          out_ready,
    output wire [TILE_W-1:0]             out_tile_index,
    output wire signed [16*16*24-1:0]    projection_s24x16x16,
    output wire                          busy,
    output reg                           done,
    output wire                          error,
    output wire [31:0]                   activation_group_count,
    output wire [31:0]                   weight_tile_count,
    output wire [31:0]                   output_tile_count,
    output wire [31:0]                   saturation_count,
    output wire [31:0]                   ddr0_raw_beat_snapshot,
    output wire [31:0]                   ddr1_raw_beat_snapshot,
    output wire [31:0]                   ddr0_elapsed_cycle_snapshot,
    output wire [31:0]                   ddr1_elapsed_cycle_snapshot,
    output wire [63:0]                   physical_read_byte_count,
    output wire [63:0]                   useful_weight_byte_count
);

    localparam integer WEIGHT_TRANSACTIONS = GROUPS*TILES;
    reg active_r;
    reg ddr_complete_r;
    reg projection_complete_r;
    wire frontend_command_ready;
    wire frontend_done;
    wire frontend_error;
    wire frontend_busy;
    wire weight_valid;
    wire weight_ready;
    wire [2047:0] weights_s4x16x32;
    wire [223:0] frontend_weight_meta;
    wire engine_activation_ready;
    wire engine_out_valid;
    wire engine_error;
    wire [31:0] frontend_useful_groups;
    wire command_fire = command_valid && command_ready;
    wire out_fire = out_valid && out_ready;
    wire final_output_fire = out_fire &&
        output_tile_count + 32'd1 == TILES;

    assign command_ready = core_rst_n && !core_clear && !active_r &&
        frontend_command_ready;
    assign busy = active_r;
    assign activation_ready = active_r && engine_activation_ready;
    assign out_valid = active_r && engine_out_valid;
    assign error = frontend_error || engine_error ||
        frontend_useful_groups > WEIGHT_TRANSACTIONS;

    hap_mlp_w4_dual_ddr_frontend #(
        .AXI_ADDR_W(AXI_ADDR_W),
        .OUTSTANDING_DEPTH(OUTSTANDING_DEPTH)
    ) u_weight_frontend (
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_clear(core_clear),
        .command_valid(command_valid && command_ready),
        .command_ready(frontend_command_ready),
        .ddr0_base_addr(ddr0_base_addr), .ddr1_base_addr(ddr1_base_addr),
        .group_count(20'(WEIGHT_TRANSACTIONS)),
        .ddr0_clk(ddr0_clk), .ddr0_rst_n(ddr0_rst_n),
        .ddr0_axi_arvalid(ddr0_axi_arvalid),
        .ddr0_axi_arready(ddr0_axi_arready),
        .ddr0_axi_araddr(ddr0_axi_araddr),
        .ddr0_axi_arlen(ddr0_axi_arlen),
        .ddr0_axi_arsize(ddr0_axi_arsize),
        .ddr0_axi_arburst(ddr0_axi_arburst),
        .ddr0_axi_rvalid(ddr0_axi_rvalid),
        .ddr0_axi_rready(ddr0_axi_rready),
        .ddr0_axi_rdata(ddr0_axi_rdata),
        .ddr0_axi_rresp(ddr0_axi_rresp), .ddr0_axi_rlast(ddr0_axi_rlast),
        .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n),
        .ddr1_axi_arvalid(ddr1_axi_arvalid),
        .ddr1_axi_arready(ddr1_axi_arready),
        .ddr1_axi_araddr(ddr1_axi_araddr),
        .ddr1_axi_arlen(ddr1_axi_arlen),
        .ddr1_axi_arsize(ddr1_axi_arsize),
        .ddr1_axi_arburst(ddr1_axi_arburst),
        .ddr1_axi_rvalid(ddr1_axi_rvalid),
        .ddr1_axi_rready(ddr1_axi_rready),
        .ddr1_axi_rdata(ddr1_axi_rdata),
        .ddr1_axi_rresp(ddr1_axi_rresp), .ddr1_axi_rlast(ddr1_axi_rlast),
        .meta_valid(active_r && weight_meta_valid),
        .meta_ready(weight_meta_ready), .meta_u224(weight_meta_u224),
        .out_valid(weight_valid), .out_ready(weight_ready),
        .weights_s4x16x32(weights_s4x16x32),
        .weight_meta_u224(frontend_weight_meta),
        .busy(frontend_busy), .done(frontend_done),
        .error(frontend_error),
        .ddr0_raw_beat_snapshot(ddr0_raw_beat_snapshot),
        .ddr1_raw_beat_snapshot(ddr1_raw_beat_snapshot),
        .ddr0_elapsed_cycle_snapshot(ddr0_elapsed_cycle_snapshot),
        .ddr1_elapsed_cycle_snapshot(ddr1_elapsed_cycle_snapshot),
        .ddr0_burst_snapshot(), .ddr1_burst_snapshot(),
        .ddr0_ar_stall_snapshot(), .ddr1_ar_stall_snapshot(),
        .ddr0_r_backpressure_snapshot(),
        .ddr1_r_backpressure_snapshot(),
        .ddr0_response_idle_snapshot(), .ddr1_response_idle_snapshot(),
        .ddr0_max_outstanding_snapshot(),
        .ddr1_max_outstanding_snapshot(),
        .physical_read_byte_count(physical_read_byte_count),
        .useful_weight_byte_count(useful_weight_byte_count),
        .useful_group_count(frontend_useful_groups)
    );

    hap_mlp_down_group_major_engine16_s45 #(
        .TILES(TILES), .GROUPS(GROUPS), .TILE_W(TILE_W)
    ) u_down_engine (
        .clk(core_clk), .rst_n(core_rst_n), .clear(core_clear),
        .activation_valid(active_r && activation_valid),
        .activation_ready(engine_activation_ready),
        .activation_u8x16x32(activation_u8x16x32),
        .activation_meta_u24x16(activation_meta_u24x16),
        .weight_valid(active_r && weight_valid), .weight_ready(weight_ready),
        .weights_s4x16x32(weights_s4x16x32),
        .weight_meta_u224(frontend_weight_meta),
        .out_valid(engine_out_valid), .out_ready(out_ready),
        .out_tile_index(out_tile_index),
        .projection_s24x16x16(projection_s24x16x16),
        .activation_group_count(activation_group_count),
        .weight_tile_count(weight_tile_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count), .error(engine_error)
    );

    always @(posedge core_clk) begin
        if (!core_rst_n || core_clear) begin
            active_r <= 1'b0;
            ddr_complete_r <= 1'b0;
            projection_complete_r <= 1'b0;
            done <= 1'b0;
        end else begin
            done <= 1'b0;
            if (command_fire) begin
                active_r <= 1'b1;
                ddr_complete_r <= 1'b0;
                projection_complete_r <= 1'b0;
            end
            if (frontend_done)
                ddr_complete_r <= 1'b1;
            if (final_output_fire)
                projection_complete_r <= 1'b1;
            if (active_r &&
                (ddr_complete_r || frontend_done) &&
                (projection_complete_r || final_output_fire)) begin
                active_r <= 1'b0;
                done <= 1'b1;
            end
        end
    end

    initial begin
        if (WEIGHT_TRANSACTIONS <= 0 ||
            (WEIGHT_TRANSACTIONS & 7) != 0)
            $error("GROUPS*TILES must be positive and divisible by 8");
        if (WEIGHT_TRANSACTIONS >= (1 << 20))
            $error("GROUPS*TILES does not fit W4 reader command field");
    end

endmodule
