`timescale 1ns / 1ps

// One-command gate/up -> product cache -> down MLP boundary.  A single
// dual-MIG W4 frontend is owned by exactly one phase at a time.  The complete
// product activation tensor is cached on chip so no gate/up transaction, CDC
// payload, or counter snapshot remains live when ownership moves to down.
module hap_mlp_serial_ddr_command16_s45 #(
    parameter integer AXI_ADDR_W = 32,
    parameter integer GATE_TILES = 1792,
    parameter integer HIDDEN_GROUPS = 128,
    parameter integer DOWN_GROUPS = GATE_TILES/4,
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
    input  wire                          command_valid,
    output wire                          command_ready,
    input  wire                          activation_bank,
    input  wire                          activation_bank_ready,
    input  wire [AXI_ADDR_W-1:0]         gate_ddr0_base_addr,
    input  wire [AXI_ADDR_W-1:0]         gate_ddr1_base_addr,
    input  wire [AXI_ADDR_W-1:0]         down_ddr0_base_addr,
    input  wire [AXI_ADDR_W-1:0]         down_ddr1_base_addr,

    output wire                          cache_rd_req_valid,
    input  wire                          cache_rd_req_ready,
    output wire                          cache_rd_req_bank,
    output wire [6:0]                    cache_rd_req_group,
    input  wire                          cache_rd_rsp_valid,
    output wire                          cache_rd_rsp_ready,
    input  wire                          cache_rd_rsp_bank,
    input  wire [6:0]                    cache_rd_rsp_group,
    input  wire [16*32*8-1:0]            cache_rd_rsp_u8x16x32,
    input  wire [16*24-1:0]              cache_rd_rsp_meta_u24x16,

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

    output reg  [31:0]                   gate_ddr0_raw_beats,
    output reg  [31:0]                   gate_ddr1_raw_beats,
    output reg  [31:0]                   gate_ddr0_elapsed_cycles,
    output reg  [31:0]                   gate_ddr1_elapsed_cycles,
    output reg  [31:0]                   gate_ddr0_bursts,
    output reg  [31:0]                   gate_ddr1_bursts,
    output reg  [31:0]                   gate_ddr0_ar_stalls,
    output reg  [31:0]                   gate_ddr1_ar_stalls,
    output reg  [31:0]                   gate_ddr0_r_backpressure,
    output reg  [31:0]                   gate_ddr1_r_backpressure,
    output reg  [31:0]                   gate_ddr0_response_idle,
    output reg  [31:0]                   gate_ddr1_response_idle,
    output reg  [31:0]                   gate_ddr0_max_outstanding,
    output reg  [31:0]                   gate_ddr1_max_outstanding,
    output reg  [63:0]                   gate_physical_bytes,
    output reg  [63:0]                   gate_useful_bytes,
    output reg  [31:0]                   down_ddr0_raw_beats,
    output reg  [31:0]                   down_ddr1_raw_beats,
    output reg  [31:0]                   down_ddr0_elapsed_cycles,
    output reg  [31:0]                   down_ddr1_elapsed_cycles,
    output reg  [31:0]                   down_ddr0_bursts,
    output reg  [31:0]                   down_ddr1_bursts,
    output reg  [31:0]                   down_ddr0_ar_stalls,
    output reg  [31:0]                   down_ddr1_ar_stalls,
    output reg  [31:0]                   down_ddr0_r_backpressure,
    output reg  [31:0]                   down_ddr1_r_backpressure,
    output reg  [31:0]                   down_ddr0_response_idle,
    output reg  [31:0]                   down_ddr1_response_idle,
    output reg  [31:0]                   down_ddr0_max_outstanding,
    output reg  [31:0]                   down_ddr1_max_outstanding,
    output reg  [63:0]                   down_physical_bytes,
    output reg  [63:0]                   down_useful_bytes,
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

    localparam integer GATE_TRANSACTIONS = GATE_TILES*HIDDEN_GROUPS;
    localparam integer DOWN_TRANSACTIONS = DOWN_GROUPS*DOWN_TILES;
    localparam [2:0] P_IDLE=3'd0, P_GATE_LAUNCH=3'd1,
        P_GATE_RUN=3'd2, P_DOWN_LAUNCH=3'd3, P_DOWN_RUN=3'd4;

    reg [2:0] state_r;
    reg active_bank_r;
    reg [AXI_ADDR_W-1:0] gate_base0_r, gate_base1_r;
    reg [AXI_ADDR_W-1:0] down_base0_r, down_base1_r;
    reg gate_compute_done_r, gate_ddr_done_r;
    reg down_projection_done_r, down_ddr_done_r;
    reg gate_started_r;
    reg sticky_error_r;

    wire frontend_command_ready;
    wire gate_command_ready, gate_done, gate_error, gate_busy;
    wire gate_weight_ready;
    wire down_weight_ready;
    wire launch_ready = state_r == P_GATE_LAUNCH ? gate_command_ready : 1'b1;
    // command_pause is a top-level admission barrier.  An accepted MLP
    // command must be allowed to launch both of its fixed-size DDR phases;
    // gating P_DOWN_LAUNCH would deadlock maintenance between gate and down.
    wire frontend_command_valid =
        (state_r == P_GATE_LAUNCH || state_r == P_DOWN_LAUNCH) &&
        launch_ready;
    wire [19:0] frontend_group_count = state_r == P_GATE_LAUNCH ?
        20'(GATE_TRANSACTIONS) : 20'(DOWN_TRANSACTIONS);
    wire [AXI_ADDR_W-1:0] frontend_base0 = state_r == P_GATE_LAUNCH ?
        gate_base0_r : down_base0_r;
    wire [AXI_ADDR_W-1:0] frontend_base1 = state_r == P_GATE_LAUNCH ?
        gate_base1_r : down_base1_r;
    wire frontend_command_fire = frontend_command_valid &&
        frontend_command_ready;
    wire frontend_busy, frontend_done, frontend_error;
    wire frontend_out_valid, frontend_out_ready;
    wire [2047:0] frontend_weights;
    wire [223:0] frontend_weight_meta;
    wire frontend_meta_valid = state_r == P_GATE_RUN ? gate_meta_valid :
        state_r == P_DOWN_RUN ? down_meta_valid : 1'b0;
    wire [223:0] frontend_meta = state_r == P_GATE_RUN ? gate_meta_u224 :
        down_meta_u224;
    wire frontend_meta_ready;
    wire [31:0] f_d0_raw, f_d1_raw, f_d0_elapsed, f_d1_elapsed;
    wire [31:0] f_d0_bursts, f_d1_bursts;
    wire [31:0] f_d0_ar_stall, f_d1_ar_stall;
    wire [31:0] f_d0_r_back, f_d1_r_back;
    wire [31:0] f_d0_idle, f_d1_idle;
    wire [31:0] f_d0_max, f_d1_max, f_useful_groups;
    wire [63:0] f_physical_bytes, f_useful_bytes;

    wire gate_activation_valid, gate_activation_ready;
    wire [4095:0] gate_activation_u8;
    wire [383:0] gate_activation_meta;
    wire [31:0] gate_activation_group_count, gate_saturation_count;

    wire gate_compute_valid, gate_compute_ready;
    wire gate_compute_first, gate_compute_last;
    wire signed [4607:0] gate_compute_activation;
    wire signed [2047:0] gate_compute_weights;
    wire [127:0] gate_compute_acode, gate_compute_wcode;
    wire [95:0] gate_compute_ashift, gate_compute_wshift;
    wire shared_gate_valid, shared_gate_ready;
    wire signed [6143:0] shared_gate_s24;

    wire activation_cache_full, activation_cache_error;
    wire down_activation_valid, down_activation_ready;
    wire [4095:0] down_activation_u8;
    wire [383:0] down_activation_meta;

    wire down_replay_valid, down_replay_ready;
    wire down_replay_first, down_replay_last;
    wire [DOWN_TILE_W-1:0] down_replay_tile;
    wire signed [4607:0] down_replay_activation;
    wire signed [2047:0] down_replay_weights;
    wire [127:0] down_replay_acode, down_replay_wcode;
    wire [95:0] down_replay_ashift, down_replay_wshift;
    wire down_engine_out_valid, down_engine_error;
    wire [31:0] down_engine_activation_count;
    wire [31:0] down_engine_saturation_count;
    wire [31:0] shared_input_count, shared_gate_output_count;
    wire shared_compute_ready, shared_compute_error;
    wire final_output_fire = out_valid && out_ready &&
        output_tile_count + 32'd1 == DOWN_TILES;

    assign command_ready = core_rst_n && !core_clear &&
        state_r == P_IDLE && activation_bank_ready;
    assign busy = state_r != P_IDLE;
    assign phase = state_r;
    assign gate_meta_ready = state_r == P_GATE_RUN && frontend_meta_ready;
    assign down_meta_ready = state_r == P_DOWN_RUN && frontend_meta_ready;
    assign frontend_out_ready = state_r == P_GATE_RUN ? gate_weight_ready :
        state_r == P_DOWN_RUN ? down_weight_ready : 1'b0;
    assign out_valid = state_r == P_DOWN_RUN && down_engine_out_valid;
    assign error = sticky_error_r || frontend_error || gate_error ||
        activation_cache_error || down_engine_error || shared_compute_error;
    assign saturation_count = gate_saturation_count +
        down_engine_saturation_count;
    assign gate_compute_ready = state_r == P_GATE_RUN &&
        shared_compute_ready;
    assign down_replay_ready = state_r == P_DOWN_RUN &&
        shared_compute_ready;

    hap_mlp_w4_dual_ddr_frontend #(
        .AXI_ADDR_W(AXI_ADDR_W),
        .OUTSTANDING_DEPTH(OUTSTANDING_DEPTH)
    ) u_w4_frontend (
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_clear(core_clear), .command_valid(frontend_command_valid),
        .command_ready(frontend_command_ready),
        .ddr0_base_addr(frontend_base0), .ddr1_base_addr(frontend_base1),
        .group_count(frontend_group_count),
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
        .meta_valid(frontend_meta_valid), .meta_ready(frontend_meta_ready),
        .meta_u224(frontend_meta), .out_valid(frontend_out_valid),
        .out_ready(frontend_out_ready), .weights_s4x16x32(frontend_weights),
        .weight_meta_u224(frontend_weight_meta), .busy(frontend_busy),
        .done(frontend_done), .error(frontend_error),
        .ddr0_raw_beat_snapshot(f_d0_raw),
        .ddr1_raw_beat_snapshot(f_d1_raw),
        .ddr0_elapsed_cycle_snapshot(f_d0_elapsed),
        .ddr1_elapsed_cycle_snapshot(f_d1_elapsed),
        .ddr0_burst_snapshot(f_d0_bursts),
        .ddr1_burst_snapshot(f_d1_bursts),
        .ddr0_ar_stall_snapshot(f_d0_ar_stall),
        .ddr1_ar_stall_snapshot(f_d1_ar_stall),
        .ddr0_r_backpressure_snapshot(f_d0_r_back),
        .ddr1_r_backpressure_snapshot(f_d1_r_back),
        .ddr0_response_idle_snapshot(f_d0_idle),
        .ddr1_response_idle_snapshot(f_d1_idle),
        .ddr0_max_outstanding_snapshot(f_d0_max),
        .ddr1_max_outstanding_snapshot(f_d1_max),
        .physical_read_byte_count(f_physical_bytes),
        .useful_weight_byte_count(f_useful_bytes),
        .useful_group_count(f_useful_groups)
    );
    assign weight_source_quiescent = command_pause &&
        !frontend_command_valid && !frontend_busy;

    hap_mlp_gate_up_external_scheduler16_q4 #(
        .PROJECTION_TILES(GATE_TILES), .GROUPS(HIDDEN_GROUPS),
        .SILU_LUT_FILE(SILU_LUT_FILE)
    ) u_gate_up (
        .clk(core_clk), .rst_n(core_rst_n), .clear(core_clear),
        .command_valid(state_r == P_GATE_LAUNCH &&
            frontend_command_ready && !gate_started_r),
        .command_ready(gate_command_ready),
        .activation_bank(active_bank_r),
        .activation_bank_ready(activation_bank_ready),
        .cache_rd_req_valid(cache_rd_req_valid),
        .cache_rd_req_ready(cache_rd_req_ready),
        .cache_rd_req_bank(cache_rd_req_bank),
        .cache_rd_req_group(cache_rd_req_group),
        .cache_rd_rsp_valid(cache_rd_rsp_valid),
        .cache_rd_rsp_ready(cache_rd_rsp_ready),
        .cache_rd_rsp_bank(cache_rd_rsp_bank),
        .cache_rd_rsp_group(cache_rd_rsp_group),
        .cache_rd_rsp_u8x16x32(cache_rd_rsp_u8x16x32),
        .cache_rd_rsp_meta_u24x16(cache_rd_rsp_meta_u24x16),
        .weight_valid(state_r == P_GATE_RUN && frontend_out_valid),
        .weight_ready(gate_weight_ready),
        .weights_s4x16x32(frontend_weights),
        .weight_meta_u224(frontend_weight_meta),
        .compute_valid(gate_compute_valid),
        .compute_ready(gate_compute_ready),
        .compute_first(gate_compute_first),
        .compute_last(gate_compute_last),
        .compute_activation_s9x16x32(gate_compute_activation),
        .compute_weights_s4x16x32(gate_compute_weights),
        .compute_activation_code_u8x16(gate_compute_acode),
        .compute_activation_shift_u6x16(gate_compute_ashift),
        .compute_weight_code_u8x16(gate_compute_wcode),
        .compute_weight_shift_u6x16(gate_compute_wshift),
        .projection_valid(shared_gate_valid),
        .projection_ready(shared_gate_ready),
        .projection_s24x16x16(shared_gate_s24),
        .activation_out_valid(gate_activation_valid),
        .activation_out_ready(gate_activation_ready),
        .activation_out_u8x16x32(gate_activation_u8),
        .activation_out_meta_u24x16(gate_activation_meta),
        .busy(gate_busy), .done(gate_done), .error(gate_error),
        .cache_request_count(gate_cache_request_count),
        .weight_group_count(gate_weight_group_count),
        .projection_tile_count(gate_projection_tile_count),
        .product_group_count(product_group_count),
        .activation_group_count(gate_activation_group_count)
    );

    hap_mlp_down_activation_cache16 #(.GROUPS(DOWN_GROUPS))
    u_down_activation_cache (
        .clk(core_clk), .rst_n(core_rst_n), .clear(core_clear),
        .in_valid(gate_activation_valid), .in_ready(gate_activation_ready),
        .in_u8x16x32(gate_activation_u8),
        .in_meta_u24x16(gate_activation_meta),
        .replay_enable(state_r == P_DOWN_RUN),
        .out_valid(down_activation_valid),
        .out_ready(down_activation_ready),
        .out_u8x16x32(down_activation_u8),
        .out_meta_u24x16(down_activation_meta), .full(activation_cache_full),
        .write_group_count(down_activation_write_count),
        .read_group_count(down_activation_read_count),
        .error(activation_cache_error)
    );

    hap_mlp_down_activation_replay16 #(
        .TILES(DOWN_TILES), .GROUPS(DOWN_GROUPS),
        .TILE_W(DOWN_TILE_W)
    ) u_down_replay (
        .clk(core_clk), .rst_n(core_rst_n), .clear(core_clear),
        .activation_valid(state_r == P_DOWN_RUN && down_activation_valid),
        .activation_ready(down_activation_ready),
        .activation_u8x16x32(down_activation_u8),
        .activation_meta_u24x16(down_activation_meta),
        .weight_valid(state_r == P_DOWN_RUN && frontend_out_valid),
        .weight_ready(down_weight_ready),
        .weights_s4x16x32(frontend_weights),
        .weight_meta_u224(frontend_weight_meta),
        .out_valid(down_replay_valid), .out_ready(down_replay_ready),
        .out_first_group(down_replay_first),
        .out_last_group(down_replay_last),
        .out_tile_index(down_replay_tile),
        .out_activation_s9x16x32(down_replay_activation),
        .out_weights_s4x16x32(down_replay_weights),
        .out_activation_code_u8x16(down_replay_acode),
        .out_activation_shift_u6x16(down_replay_ashift),
        .out_weight_code_u8x16(down_replay_wcode),
        .out_weight_shift_u6x16(down_replay_wshift),
        .activation_group_count(down_engine_activation_count),
        .weight_tile_count(down_weight_tile_count),
        .completed_group_count(), .error(down_engine_error)
    );

    hap_mlp_shared_dual_slice16x16_s43_s45 #(
        .DOWN_TILES(DOWN_TILES), .DOWN_GROUPS(DOWN_GROUPS),
        .TILE_W(DOWN_TILE_W)
    ) u_shared_compute (
        .clk(core_clk), .rst_n(core_rst_n), .clear(core_clear),
        .in_valid(state_r == P_GATE_RUN ? gate_compute_valid :
            state_r == P_DOWN_RUN ? down_replay_valid : 1'b0),
        .in_ready(shared_compute_ready), .in_down(state_r == P_DOWN_RUN),
        .in_first(state_r == P_GATE_RUN ? gate_compute_first :
            down_replay_first),
        .in_last(state_r == P_GATE_RUN ? gate_compute_last :
            down_replay_last),
        .in_tile(state_r == P_DOWN_RUN ? down_replay_tile : '0),
        .activation_s9x16x32(state_r == P_GATE_RUN ?
            gate_compute_activation : down_replay_activation),
        .weights_s4x16x32(state_r == P_GATE_RUN ?
            gate_compute_weights : down_replay_weights),
        .activation_code_u8x16(state_r == P_GATE_RUN ?
            gate_compute_acode : down_replay_acode),
        .activation_shift_u6x16(state_r == P_GATE_RUN ?
            gate_compute_ashift : down_replay_ashift),
        .weight_code_u8x16(state_r == P_GATE_RUN ?
            gate_compute_wcode : down_replay_wcode),
        .weight_shift_u6x16(state_r == P_GATE_RUN ?
            gate_compute_wshift : down_replay_wshift),
        .gate_valid(shared_gate_valid), .gate_ready(shared_gate_ready),
        .gate_s24x16x16(shared_gate_s24),
        .down_valid(down_engine_out_valid), .down_ready(out_ready),
        .down_tile(out_tile_index),
        .down_s24x16x16(projection_s24x16x16),
        .gate_saturation(gate_saturation_count),
        .down_saturation(down_engine_saturation_count),
        .input_transaction_count(shared_input_count),
        .gate_output_tile_count(shared_gate_output_count),
        .down_output_tile_count(output_tile_count), .error(shared_compute_error)
    );

    always @(posedge core_clk) begin
        if (!core_rst_n || core_clear) begin
            state_r <= P_IDLE;
            active_bank_r <= 1'b0;
            gate_compute_done_r <= 1'b0;
            gate_ddr_done_r <= 1'b0;
            down_projection_done_r <= 1'b0;
            down_ddr_done_r <= 1'b0;
            gate_started_r <= 1'b0;
            done <= 1'b0;
            sticky_error_r <= 1'b0;
            gate_ddr0_raw_beats <= 0; gate_ddr1_raw_beats <= 0;
            gate_ddr0_elapsed_cycles <= 0; gate_ddr1_elapsed_cycles <= 0;
            gate_ddr0_bursts <= 0; gate_ddr1_bursts <= 0;
            gate_ddr0_ar_stalls <= 0; gate_ddr1_ar_stalls <= 0;
            gate_ddr0_r_backpressure <= 0; gate_ddr1_r_backpressure <= 0;
            gate_ddr0_response_idle <= 0; gate_ddr1_response_idle <= 0;
            gate_ddr0_max_outstanding <= 0; gate_ddr1_max_outstanding <= 0;
            gate_physical_bytes <= 0; gate_useful_bytes <= 0;
            down_ddr0_raw_beats <= 0; down_ddr1_raw_beats <= 0;
            down_ddr0_elapsed_cycles <= 0; down_ddr1_elapsed_cycles <= 0;
            down_ddr0_bursts <= 0; down_ddr1_bursts <= 0;
            down_ddr0_ar_stalls <= 0; down_ddr1_ar_stalls <= 0;
            down_ddr0_r_backpressure <= 0; down_ddr1_r_backpressure <= 0;
            down_ddr0_response_idle <= 0; down_ddr1_response_idle <= 0;
            down_ddr0_max_outstanding <= 0; down_ddr1_max_outstanding <= 0;
            down_physical_bytes <= 0; down_useful_bytes <= 0;
        end else begin
            done <= 1'b0;
            if (command_valid && command_ready) begin
                active_bank_r <= activation_bank;
                gate_base0_r <= gate_ddr0_base_addr;
                gate_base1_r <= gate_ddr1_base_addr;
                down_base0_r <= down_ddr0_base_addr;
                down_base1_r <= down_ddr1_base_addr;
                gate_compute_done_r <= 1'b0;
                gate_ddr_done_r <= 1'b0;
                down_projection_done_r <= 1'b0;
                down_ddr_done_r <= 1'b0;
                gate_started_r <= 1'b0;
                sticky_error_r <= 1'b0;
                state_r <= P_GATE_LAUNCH;
            end
            if (state_r == P_GATE_LAUNCH && frontend_command_fire) begin
                gate_started_r <= 1'b1;
                state_r <= P_GATE_RUN;
            end
            if (state_r == P_GATE_RUN) begin
                if (gate_done) gate_compute_done_r <= 1'b1;
                if (frontend_done) begin
                    gate_ddr_done_r <= 1'b1;
                    gate_ddr0_raw_beats <= f_d0_raw;
                    gate_ddr1_raw_beats <= f_d1_raw;
                    gate_ddr0_elapsed_cycles <= f_d0_elapsed;
                    gate_ddr1_elapsed_cycles <= f_d1_elapsed;
                    gate_ddr0_bursts <= f_d0_bursts;
                    gate_ddr1_bursts <= f_d1_bursts;
                    gate_ddr0_ar_stalls <= f_d0_ar_stall;
                    gate_ddr1_ar_stalls <= f_d1_ar_stall;
                    gate_ddr0_r_backpressure <= f_d0_r_back;
                    gate_ddr1_r_backpressure <= f_d1_r_back;
                    gate_ddr0_response_idle <= f_d0_idle;
                    gate_ddr1_response_idle <= f_d1_idle;
                    gate_ddr0_max_outstanding <= f_d0_max;
                    gate_ddr1_max_outstanding <= f_d1_max;
                    gate_physical_bytes <= f_physical_bytes;
                    gate_useful_bytes <= f_useful_bytes;
                end
                if ((gate_compute_done_r || gate_done) &&
                    (gate_ddr_done_r || frontend_done) &&
                    activation_cache_full)
                    state_r <= P_DOWN_LAUNCH;
            end
            if (state_r == P_DOWN_LAUNCH && frontend_command_fire)
                state_r <= P_DOWN_RUN;
            if (state_r == P_DOWN_RUN) begin
                if (final_output_fire) down_projection_done_r <= 1'b1;
                if (frontend_done) begin
                    down_ddr_done_r <= 1'b1;
                    down_ddr0_raw_beats <= f_d0_raw;
                    down_ddr1_raw_beats <= f_d1_raw;
                    down_ddr0_elapsed_cycles <= f_d0_elapsed;
                    down_ddr1_elapsed_cycles <= f_d1_elapsed;
                    down_ddr0_bursts <= f_d0_bursts;
                    down_ddr1_bursts <= f_d1_bursts;
                    down_ddr0_ar_stalls <= f_d0_ar_stall;
                    down_ddr1_ar_stalls <= f_d1_ar_stall;
                    down_ddr0_r_backpressure <= f_d0_r_back;
                    down_ddr1_r_backpressure <= f_d1_r_back;
                    down_ddr0_response_idle <= f_d0_idle;
                    down_ddr1_response_idle <= f_d1_idle;
                    down_ddr0_max_outstanding <= f_d0_max;
                    down_ddr1_max_outstanding <= f_d1_max;
                    down_physical_bytes <= f_physical_bytes;
                    down_useful_bytes <= f_useful_bytes;
                end
                if ((down_projection_done_r || final_output_fire) &&
                    (down_ddr_done_r || frontend_done) &&
                    down_activation_read_count == DOWN_GROUPS) begin
                    state_r <= P_IDLE;
                    done <= 1'b1;
                end
            end
            if (frontend_error || gate_error || activation_cache_error ||
                down_engine_error || shared_compute_error ||
                (state_r == P_GATE_RUN && f_useful_groups > GATE_TRANSACTIONS) ||
                (state_r == P_DOWN_RUN && f_useful_groups > DOWN_TRANSACTIONS) ||
                down_engine_activation_count > DOWN_GROUPS)
                sticky_error_r <= 1'b1;
        end
    end

    initial begin
        if (HIDDEN_GROUPS != 128)
            $error("serial MLP hidden group count must be 128");
        if (GATE_TILES <= 0 || (GATE_TILES & 3) != 0 ||
            DOWN_GROUPS != GATE_TILES/4)
            $error("gate/down activation shape mismatch");
        if ((GATE_TRANSACTIONS & 7) != 0 ||
            (DOWN_TRANSACTIONS & 7) != 0 ||
            GATE_TRANSACTIONS >= (1 << 20) ||
            DOWN_TRANSACTIONS >= (1 << 20))
            $error("W4 transaction counts violate reader command contract");
    end

endmodule
