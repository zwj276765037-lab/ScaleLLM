`timescale 1ns / 1ps

// V5 full MLP boundary.  Dell supplies one post-residual/RMSNorm S24 cohort16
// tensor; this wrapper quantizes/caches it, owns the cache bank for the whole
// gate/up-product-down command, and releases it only after the V5 serial engine
// and output stream complete.  External control and telemetry match the V4
// wrapper so production integration can select V5 without changing software
// register semantics.
//
// The independent V5 production manifest may override only this module-name
// macro to satisfy the frozen V4 resource-top ABI.  Normal compilation keeps
// the explicit V5 name, so V4 and all existing V5 leaf regressions remain
// unambiguous and no V4 source file has to be edited.
`ifndef HAP_MLP_FULL_COMMAND_V5_MODULE
`define HAP_MLP_FULL_COMMAND_V5_MODULE hap_mlp_full_command16_v5_s45
`endif
module `HAP_MLP_FULL_COMMAND_V5_MODULE #(
    parameter integer AXI_ADDR_W = 32,
    parameter integer INTERMEDIATE_COLUMNS = 14336,
    parameter integer HIDDEN_GROUPS = 128,
    parameter integer DOWN_GROUPS = INTERMEDIATE_COLUMNS/32,
    parameter integer DOWN_TILES = 256,
    parameter integer DOWN_TILE_W =
        (DOWN_TILES <= 2) ? 1 : $clog2(DOWN_TILES),
    parameter integer OUTSTANDING_DEPTH = 8,
    parameter SILU_LUT_FILE = "data/mlp_silu_q16.mem"
) (
    input  wire                          core_clk,
    input  wire                          core_rst_n,
    input  wire                          core_clear,
    input  wire                          command_pause,
    output wire                          weight_source_quiescent,

    input  wire                          input_valid,
    output wire                          input_ready,
    input  wire                          input_bank,
    input  wire [6:0]                    input_group,
    input  wire [16*32*24-1:0]           input_s24x16x32,
    output wire [1:0]                    input_bank_ready,

    input  wire                          command_valid,
    output wire                          command_ready,
    input  wire                          command_bank,
    input  wire [AXI_ADDR_W-1:0]         gate_ddr0_base_addr,
    input  wire [AXI_ADDR_W-1:0]         gate_ddr1_base_addr,
    input  wire [AXI_ADDR_W-1:0]         down_ddr0_base_addr,
    input  wire [AXI_ADDR_W-1:0]         down_ddr1_base_addr,

    input  wire                          gate_meta_valid,
    output wire                          gate_meta_ready,
    input  wire [223:0]                  gate_meta_u224,
    input  wire                          down_meta_valid,
    output wire                          down_meta_ready,
    input  wire [223:0]                  down_meta_u224,

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
    output wire [DOWN_TILE_W-1:0]        out_tile_index,
    output wire signed [16*16*24-1:0]    projection_s24x16x16,
    output wire                          busy,
    output reg                           done,
    output wire                          error,
    output wire [2:0]                    phase,

    output wire [31:0]                   input_group_count,
    output wire [31:0]                   input_cache_read_count,
    output wire [31:0]                   input_cache_release_count,
    output wire [31:0]                   input_hadamard_saturation_count,
    output wire [31:0]                   gate_ddr0_raw_beats,
    output wire [31:0]                   gate_ddr1_raw_beats,
    output wire [31:0]                   gate_ddr0_elapsed_cycles,
    output wire [31:0]                   gate_ddr1_elapsed_cycles,
    output wire [31:0]                   gate_ddr0_bursts,
    output wire [31:0]                   gate_ddr1_bursts,
    output wire [31:0]                   gate_ddr0_ar_stalls,
    output wire [31:0]                   gate_ddr1_ar_stalls,
    output wire [31:0]                   gate_ddr0_r_backpressure,
    output wire [31:0]                   gate_ddr1_r_backpressure,
    output wire [31:0]                   gate_ddr0_response_idle,
    output wire [31:0]                   gate_ddr1_response_idle,
    output wire [31:0]                   gate_ddr0_max_outstanding,
    output wire [31:0]                   gate_ddr1_max_outstanding,
    output wire [63:0]                   gate_physical_bytes,
    output wire [63:0]                   gate_useful_bytes,
    output wire [31:0]                   down_ddr0_raw_beats,
    output wire [31:0]                   down_ddr1_raw_beats,
    output wire [31:0]                   down_ddr0_elapsed_cycles,
    output wire [31:0]                   down_ddr1_elapsed_cycles,
    output wire [31:0]                   down_ddr0_bursts,
    output wire [31:0]                   down_ddr1_bursts,
    output wire [31:0]                   down_ddr0_ar_stalls,
    output wire [31:0]                   down_ddr1_ar_stalls,
    output wire [31:0]                   down_ddr0_r_backpressure,
    output wire [31:0]                   down_ddr1_r_backpressure,
    output wire [31:0]                   down_ddr0_response_idle,
    output wire [31:0]                   down_ddr1_response_idle,
    output wire [31:0]                   down_ddr0_max_outstanding,
    output wire [31:0]                   down_ddr1_max_outstanding,
    output wire [63:0]                   down_physical_bytes,
    output wire [63:0]                   down_useful_bytes,
    output wire [31:0]                   gate_cache_request_count,
    output wire [31:0]                   gate_weight_group_count,
    output wire [31:0]                   gate_projection_tile_count,
    output wire [31:0]                   product_group_count,
    output wire [31:0]                   down_activation_write_count,
    output wire [31:0]                   down_activation_read_count,
    output wire [31:0]                   down_weight_tile_count,
    output wire [31:0]                   output_tile_count,
    output wire [31:0]                   saturation_count
);

    localparam [2:0] W_IDLE = 3'd0;
    localparam [2:0] W_CLEAR = 3'd1;
    localparam [2:0] W_LAUNCH = 3'd2;
    localparam [2:0] W_RUN = 3'd3;
    localparam [2:0] W_RELEASE_ISSUE = 3'd4;
    localparam [2:0] W_RELEASE_WAIT = 3'd5;

    reg [2:0] state_r;
    reg active_bank_r;
    reg [AXI_ADDR_W-1:0] gate_base0_r;
    reg [AXI_ADDR_W-1:0] gate_base1_r;
    reg [AXI_ADDR_W-1:0] down_base0_r;
    reg [AXI_ADDR_W-1:0] down_base1_r;
    reg [31:0] release_count_before_r;
    reg sticky_error_r;

    wire cache_rd_req_valid;
    wire cache_rd_req_ready;
    wire cache_rd_req_bank;
    wire [6:0] cache_rd_req_group;
    wire cache_rd_rsp_valid;
    wire cache_rd_rsp_ready;
    wire cache_rd_rsp_bank;
    wire [6:0] cache_rd_rsp_group;
    wire [16*32*8-1:0] cache_rd_rsp_u8;
    wire [16*24-1:0] cache_rd_rsp_meta;
    wire cache_release_ready;
    wire input_frontend_error;
    wire serial_command_ready;
    wire serial_busy;
    wire serial_done;
    wire serial_error;
    wire command_fire = command_valid && command_ready;
    wire serial_clear = core_clear || state_r == W_CLEAR;
    wire serial_command_valid = state_r == W_LAUNCH;
    wire serial_command_fire = serial_command_valid && serial_command_ready;
    wire cache_release_valid = state_r == W_RELEASE_ISSUE;

    assign command_ready = core_rst_n && !core_clear && !command_pause &&
        state_r == W_IDLE && input_bank_ready[command_bank];
    assign busy = state_r != W_IDLE;
    assign error = sticky_error_r || input_frontend_error || serial_error;

    hap_mlp_input_frontend16_compact_cache u_input_frontend (
        .clk(core_clk), .rst_n(core_rst_n), .clear(core_clear),
        .in_valid(input_valid), .in_ready(input_ready), .in_bank(input_bank),
        .in_group(input_group), .in_s24x16x32(input_s24x16x32),
        .rd_req_valid(cache_rd_req_valid),
        .rd_req_ready(cache_rd_req_ready), .rd_req_bank(cache_rd_req_bank),
        .rd_req_group(cache_rd_req_group), .rd_rsp_valid(cache_rd_rsp_valid),
        .rd_rsp_ready(cache_rd_rsp_ready), .rd_rsp_bank(cache_rd_rsp_bank),
        .rd_rsp_group(cache_rd_rsp_group),
        .rd_rsp_u8x16x32(cache_rd_rsp_u8),
        .rd_rsp_meta_u24x16(cache_rd_rsp_meta),
        .release_valid(cache_release_valid),
        .release_ready(cache_release_ready), .release_bank(active_bank_r),
        .bank_ready(input_bank_ready),
        .input_group_count(input_group_count),
        .read_group_count(input_cache_read_count),
        .release_count(input_cache_release_count),
        .hadamard_saturation_count(input_hadamard_saturation_count),
        .error(input_frontend_error)
    );

    hap_mlp_serial_ddr_command16_v5_s45 #(
        .AXI_ADDR_W(AXI_ADDR_W),
        .INTERMEDIATE_COLUMNS(INTERMEDIATE_COLUMNS),
        .HIDDEN_GROUPS(HIDDEN_GROUPS), .DOWN_GROUPS(DOWN_GROUPS),
        .DOWN_OUTPUT_RECORDS(DOWN_TILES),
        .OUTSTANDING_DEPTH(OUTSTANDING_DEPTH),
        .SILU_LUT_FILE(SILU_LUT_FILE)
    ) u_serial_command (
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_clear(serial_clear), .command_pause(command_pause),
        .weight_source_quiescent(weight_source_quiescent),
        .command_valid(serial_command_valid),
        .command_ready(serial_command_ready), .activation_bank(active_bank_r),
        .activation_bank_ready(input_bank_ready[active_bank_r]),
        .gate_ddr0_base_addr(gate_base0_r),
        .gate_ddr1_base_addr(gate_base1_r),
        .down_ddr0_base_addr(down_base0_r),
        .down_ddr1_base_addr(down_base1_r),
        .cache_rd_req_valid(cache_rd_req_valid),
        .cache_rd_req_ready(cache_rd_req_ready),
        .cache_rd_req_bank(cache_rd_req_bank),
        .cache_rd_req_group(cache_rd_req_group),
        .cache_rd_rsp_valid(cache_rd_rsp_valid),
        .cache_rd_rsp_ready(cache_rd_rsp_ready),
        .cache_rd_rsp_bank(cache_rd_rsp_bank),
        .cache_rd_rsp_group(cache_rd_rsp_group),
        .cache_rd_rsp_u8x16x32(cache_rd_rsp_u8),
        .cache_rd_rsp_meta_u24x16(cache_rd_rsp_meta),
        .gate_meta_valid(gate_meta_valid), .gate_meta_ready(gate_meta_ready),
        .gate_meta_u224(gate_meta_u224),
        .down_meta_valid(down_meta_valid), .down_meta_ready(down_meta_ready),
        .down_meta_u224(down_meta_u224),
        .ddr0_clk(ddr0_clk), .ddr0_rst_n(ddr0_rst_n),
        .ddr0_axi_arvalid(ddr0_axi_arvalid),
        .ddr0_axi_arready(ddr0_axi_arready),
        .ddr0_axi_araddr(ddr0_axi_araddr), .ddr0_axi_arlen(ddr0_axi_arlen),
        .ddr0_axi_arsize(ddr0_axi_arsize),
        .ddr0_axi_arburst(ddr0_axi_arburst),
        .ddr0_axi_rvalid(ddr0_axi_rvalid), .ddr0_axi_rready(ddr0_axi_rready),
        .ddr0_axi_rdata(ddr0_axi_rdata), .ddr0_axi_rresp(ddr0_axi_rresp),
        .ddr0_axi_rlast(ddr0_axi_rlast),
        .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n),
        .ddr1_axi_arvalid(ddr1_axi_arvalid),
        .ddr1_axi_arready(ddr1_axi_arready),
        .ddr1_axi_araddr(ddr1_axi_araddr), .ddr1_axi_arlen(ddr1_axi_arlen),
        .ddr1_axi_arsize(ddr1_axi_arsize),
        .ddr1_axi_arburst(ddr1_axi_arburst),
        .ddr1_axi_rvalid(ddr1_axi_rvalid), .ddr1_axi_rready(ddr1_axi_rready),
        .ddr1_axi_rdata(ddr1_axi_rdata), .ddr1_axi_rresp(ddr1_axi_rresp),
        .ddr1_axi_rlast(ddr1_axi_rlast),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_tile_index(out_tile_index),
        .projection_s24x16x16(projection_s24x16x16),
        .busy(serial_busy), .done(serial_done), .error(serial_error),
        .phase(phase),
        .gate_ddr0_raw_beats(gate_ddr0_raw_beats),
        .gate_ddr1_raw_beats(gate_ddr1_raw_beats),
        .gate_ddr0_elapsed_cycles(gate_ddr0_elapsed_cycles),
        .gate_ddr1_elapsed_cycles(gate_ddr1_elapsed_cycles),
        .gate_ddr0_bursts(gate_ddr0_bursts),
        .gate_ddr1_bursts(gate_ddr1_bursts),
        .gate_ddr0_ar_stalls(gate_ddr0_ar_stalls),
        .gate_ddr1_ar_stalls(gate_ddr1_ar_stalls),
        .gate_ddr0_r_backpressure(gate_ddr0_r_backpressure),
        .gate_ddr1_r_backpressure(gate_ddr1_r_backpressure),
        .gate_ddr0_response_idle(gate_ddr0_response_idle),
        .gate_ddr1_response_idle(gate_ddr1_response_idle),
        .gate_ddr0_max_outstanding(gate_ddr0_max_outstanding),
        .gate_ddr1_max_outstanding(gate_ddr1_max_outstanding),
        .gate_physical_bytes(gate_physical_bytes),
        .gate_useful_bytes(gate_useful_bytes),
        .down_ddr0_raw_beats(down_ddr0_raw_beats),
        .down_ddr1_raw_beats(down_ddr1_raw_beats),
        .down_ddr0_elapsed_cycles(down_ddr0_elapsed_cycles),
        .down_ddr1_elapsed_cycles(down_ddr1_elapsed_cycles),
        .down_ddr0_bursts(down_ddr0_bursts),
        .down_ddr1_bursts(down_ddr1_bursts),
        .down_ddr0_ar_stalls(down_ddr0_ar_stalls),
        .down_ddr1_ar_stalls(down_ddr1_ar_stalls),
        .down_ddr0_r_backpressure(down_ddr0_r_backpressure),
        .down_ddr1_r_backpressure(down_ddr1_r_backpressure),
        .down_ddr0_response_idle(down_ddr0_response_idle),
        .down_ddr1_response_idle(down_ddr1_response_idle),
        .down_ddr0_max_outstanding(down_ddr0_max_outstanding),
        .down_ddr1_max_outstanding(down_ddr1_max_outstanding),
        .down_physical_bytes(down_physical_bytes),
        .down_useful_bytes(down_useful_bytes),
        .gate_cache_request_count(gate_cache_request_count),
        .gate_weight_group_count(gate_weight_group_count),
        .gate_projection_tile_count(gate_projection_tile_count),
        .product_group_count(product_group_count),
        .down_activation_write_count(down_activation_write_count),
        .down_activation_read_count(down_activation_read_count),
        .down_weight_tile_count(down_weight_tile_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count)
    );

    always @(posedge core_clk) begin
        if (!core_rst_n || core_clear) begin
            state_r <= W_IDLE;
            active_bank_r <= 1'b0;
            gate_base0_r <= '0;
            gate_base1_r <= '0;
            down_base0_r <= '0;
            down_base1_r <= '0;
            release_count_before_r <= 32'd0;
            done <= 1'b0;
            sticky_error_r <= 1'b0;
        end else begin
            done <= 1'b0;
            if (command_fire) begin
                active_bank_r <= command_bank;
                gate_base0_r <= gate_ddr0_base_addr;
                gate_base1_r <= gate_ddr1_base_addr;
                down_base0_r <= down_ddr0_base_addr;
                down_base1_r <= down_ddr1_base_addr;
                state_r <= W_CLEAR;
                sticky_error_r <= 1'b0;
            end
            if (state_r == W_CLEAR)
                state_r <= W_LAUNCH;
            if (serial_command_fire)
                state_r <= W_RUN;
            if (state_r == W_RUN && serial_done)
                state_r <= W_RELEASE_ISSUE;
            if (state_r == W_RELEASE_ISSUE && cache_release_ready) begin
                release_count_before_r <= input_cache_release_count;
                state_r <= W_RELEASE_WAIT;
            end
            if (state_r == W_RELEASE_WAIT &&
                input_cache_release_count != release_count_before_r) begin
                state_r <= W_IDLE;
                done <= 1'b1;
            end
            if (input_frontend_error || serial_error ||
                (state_r == W_RUN && !serial_busy && !serial_done) ||
                ((state_r == W_RELEASE_ISSUE || state_r == W_RELEASE_WAIT) &&
                 serial_busy))
                sticky_error_r <= 1'b1;
        end
    end

    initial begin
        if (INTERMEDIATE_COLUMNS != 14336 || HIDDEN_GROUPS != 128 ||
            DOWN_GROUPS != 448 || DOWN_TILES != 256)
            $error("V5 full command frozen shape mismatch");
    end

endmodule
