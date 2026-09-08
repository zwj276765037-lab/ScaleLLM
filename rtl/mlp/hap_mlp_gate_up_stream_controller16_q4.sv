`timescale 1ns / 1ps

// Gate/up stream scheduler for one cohort16 MLP command.  The activation
// cache is walked tile-major (128 hidden groups per projection tile) while a
// matching W4 stream is consumed in the same order.  Four completed S24
// projection tiles are tagged gate0/up0/gate1/up1 and transformed into one
// group32 down activation by the SwiGLU/Hadamard/Robust-A8 frontend.
module hap_mlp_gate_up_stream_controller16_q4 #(
    parameter integer PROJECTION_TILES = 1792,
    parameter integer GROUPS = 128,
    parameter integer TILE_W =
        (PROJECTION_TILES <= 2) ? 1 : $clog2(PROJECTION_TILES),
    parameter SILU_LUT_FILE = "data/mlp_silu_q16.mem"
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          clear,
    input  wire                          command_valid,
    output wire                          command_ready,
    input  wire                          activation_bank,
    input  wire                          activation_bank_ready,

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

    input  wire                          weight_valid,
    output wire                          weight_ready,
    input  wire signed [16*32*4-1:0]     weights_s4x16x32,
    input  wire [223:0]                  weight_meta_u224,

    output wire                          activation_out_valid,
    input  wire                          activation_out_ready,
    output wire [16*32*8-1:0]            activation_out_u8x16x32,
    output wire [16*24-1:0]              activation_out_meta_u24x16,
    output wire                          busy,
    output reg                           done,
    output reg                           error,
    output reg  [31:0]                   cache_request_count,
    output reg  [31:0]                   weight_group_count,
    output wire [31:0]                   projection_tile_count,
    output wire [31:0]                   product_group_count,
    output wire [31:0]                   activation_group_count,
    output wire [31:0]                   saturation_count
);

    reg active_r;
    reg active_bank_r;
    reg [TILE_W-1:0] request_tile_r;
    reg [6:0] request_group_r;
    reg [TILE_W-1:0] compute_tile_r;
    reg [6:0] compute_group_r;
    reg [TILE_W-1:0] projection_output_tile_r;

    wire signed [16*32*9-1:0] centered_activation_s9;
    wire [16*8-1:0] activation_code_u8;
    wire [16*6-1:0] activation_shift_u6;
    wire gate_up_in_ready;
    wire gate_up_in_valid = active_r && cache_rd_rsp_valid && weight_valid;
    wire gate_up_in_fire = gate_up_in_valid && gate_up_in_ready;
    wire gate_up_out_valid;
    wire gate_up_out_ready;
    wire signed [16*16*24-1:0] projection_s24;
    wire gate_up_error;
    wire [31:0] gate_up_input_groups;
    wire [31:0] gate_up_output_tiles;

    wire swiglu_in_ready;
    wire swiglu_error;
    wire swiglu_out_fire = activation_out_valid && activation_out_ready;
    wire cache_req_fire = cache_rd_req_valid && cache_rd_req_ready;

    assign command_ready = rst_n && !clear && !active_r &&
        activation_bank_ready;
    assign busy = active_r;
    assign cache_rd_req_valid = active_r &&
        cache_request_count < PROJECTION_TILES*GROUPS;
    assign cache_rd_req_bank = active_bank_r;
    assign cache_rd_req_group = request_group_r;
    assign cache_rd_rsp_ready = active_r && weight_valid &&
        gate_up_in_ready;
    assign weight_ready = active_r && cache_rd_rsp_valid &&
        gate_up_in_ready;
    assign gate_up_out_ready = swiglu_in_ready;

    genvar row;
    genvar lane;
    generate
        for (row = 0; row < 16; row = row + 1) begin : gen_center_row
            wire [7:0] zero_point =
                cache_rd_rsp_meta_u24x16[row*24 +: 8];
            assign activation_code_u8[row*8 +: 8] =
                cache_rd_rsp_meta_u24x16[row*24+8 +: 8];
            assign activation_shift_u6[row*6 +: 6] =
                cache_rd_rsp_meta_u24x16[row*24+16 +: 6];
            for (lane = 0; lane < 32; lane = lane + 1) begin : gen_center_lane
                wire [7:0] activation_u8 = cache_rd_rsp_u8x16x32[
                    (row*32+lane)*8 +: 8];
                assign centered_activation_s9[(row*32+lane)*9 +: 9] =
                    $signed({1'b0, activation_u8}) -
                    $signed({1'b0, zero_point});
            end
        end
    endgenerate

    hap_mlp_gate_up_dual_slice16x16_s43 u_gate_up (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(gate_up_in_valid), .in_ready(gate_up_in_ready),
        .in_first_group(compute_group_r == 0),
        .in_last_group(compute_group_r == GROUPS-1),
        .activation_s9x16x32(centered_activation_s9),
        .weights_s4x16x32(weights_s4x16x32),
        .activation_code_u8x16(activation_code_u8),
        .activation_shift_u6x16(activation_shift_u6),
        .weight_code_u8x16(weight_meta_u224[127:0]),
        .weight_shift_u6x16(weight_meta_u224[223:128]),
        .out_valid(gate_up_out_valid), .out_ready(gate_up_out_ready),
        .projection_s24x16x16(projection_s24),
        .input_group_count(gate_up_input_groups),
        .output_tile_count(gate_up_output_tiles),
        .saturation_count(saturation_count), .error(gate_up_error)
    );

    hap_mlp_swiglu_product_frontend16_q4 #(
        .SILU_LUT_FILE(SILU_LUT_FILE)
    ) u_swiglu_frontend (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(gate_up_out_valid), .in_ready(swiglu_in_ready),
        .in_is_up(projection_output_tile_r[0]),
        .in_second_half(projection_output_tile_r[1]),
        .projection_s24x16x16(projection_s24),
        .out_valid(activation_out_valid),
        .out_ready(activation_out_ready),
        .activation_u8x16x32(activation_out_u8x16x32),
        .activation_meta_u24x16(activation_out_meta_u24x16),
        .input_tile_count(), .product_group_count(product_group_count),
        .activation_group_count(activation_group_count),
        .frontend_busy_cycle_count(), .error(swiglu_error)
    );

    assign projection_tile_count = gate_up_output_tiles;

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            active_r <= 1'b0;
            active_bank_r <= 1'b0;
            request_tile_r <= '0;
            request_group_r <= 7'd0;
            compute_tile_r <= '0;
            compute_group_r <= 7'd0;
            projection_output_tile_r <= '0;
            done <= 1'b0;
            error <= 1'b0;
            cache_request_count <= 32'd0;
            weight_group_count <= 32'd0;
        end else begin
            done <= 1'b0;
            if (command_valid && command_ready) begin
                active_r <= 1'b1;
                active_bank_r <= activation_bank;
                request_tile_r <= '0;
                request_group_r <= 7'd0;
                compute_tile_r <= '0;
                compute_group_r <= 7'd0;
                projection_output_tile_r <= '0;
                cache_request_count <= 32'd0;
                weight_group_count <= 32'd0;
            end

            if (cache_req_fire) begin
                cache_request_count <= cache_request_count + 32'd1;
                if (request_group_r == GROUPS-1) begin
                    request_group_r <= 7'd0;
                    if (request_tile_r != PROJECTION_TILES-1)
                        request_tile_r <= request_tile_r + 1'b1;
                end else begin
                    request_group_r <= request_group_r + 1'b1;
                end
            end

            if (gate_up_in_fire) begin
                weight_group_count <= weight_group_count + 32'd1;
                if (cache_rd_rsp_bank != active_bank_r ||
                    cache_rd_rsp_group != compute_group_r ||
                    cache_rd_rsp_meta_u24x16[383:382] != 0)
                    error <= 1'b1;
                if (compute_group_r == GROUPS-1) begin
                    compute_group_r <= 7'd0;
                    if (compute_tile_r != PROJECTION_TILES-1)
                        compute_tile_r <= compute_tile_r + 1'b1;
                end else begin
                    compute_group_r <= compute_group_r + 1'b1;
                end
            end

            if (gate_up_out_valid && gate_up_out_ready) begin
                if (projection_output_tile_r != PROJECTION_TILES-1)
                    projection_output_tile_r <=
                        projection_output_tile_r + 1'b1;
            end

            if (swiglu_out_fire &&
                activation_group_count + 32'd1 == PROJECTION_TILES/4) begin
                active_r <= 1'b0;
                done <= 1'b1;
            end

            if (gate_up_error || swiglu_error ||
                weight_group_count > cache_request_count ||
                gate_up_input_groups > weight_group_count ||
                gate_up_output_tiles > PROJECTION_TILES)
                error <= 1'b1;
        end
    end

    initial begin
        if (GROUPS != 128)
            $error("gate/up production hidden group count must be 128");
        if (PROJECTION_TILES <= 0 || (PROJECTION_TILES & 3) != 0)
            $error("gate/up projection tile count must be positive/multiple of 4");
    end

endmodule
