`timescale 1ns / 1ps

module m12_fp32_state_bank #(
    parameter integer TILES = 342,
    parameter integer TILE_W = (TILES <= 2) ? 1 : $clog2(TILES)
) (
    input  wire                  clk,
    input  wire                  read_enable,
    input  wire [TILE_W-1:0]     read_address,
    output reg  [31:0]           read_data,
    input  wire                  write_enable,
    input  wire [TILE_W-1:0]     write_address,
    input  wire [31:0]           write_data
);
    (* ram_style = "block" *) reg [31:0] memory [0:TILES-1];

    always @(posedge clk) begin
        if (read_enable)
            read_data <= memory[read_address];
        if (write_enable)
            memory[write_address] <= write_data;
    end
endmodule


// Full 16-row x 12-column native-FP Down core with group-major tile state.
// Every accepted request computes 192 FP contributions.  One FP32 state bank
// per logical output lane preserves all 342 tile sums across 448 groups.
module m12_fp_down_group_major #(
    parameter integer FP_W = 16,
    parameter integer TILES = 342,
    parameter integer GROUPS = 448,
    parameter integer TILE_W = (TILES <= 2) ? 1 : $clog2(TILES),
    parameter integer TAG_DEPTH = 64
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          clear,
    input  wire                          in_valid,
    output wire                          in_ready,
    input  wire                          in_first_group,
    input  wire                          in_last_group,
    input  wire [TILE_W-1:0]             in_tile_index,
    input  wire signed [16*32*9-1:0]     activation_s9x16x32,
    input  wire signed [12*32*4-1:0]     weights_s4x12x32,
    input  wire [16*FP_W-1:0]            activation_scale_fpx16,
    input  wire [12*FP_W-1:0]            weight_scale_fpx12,
    input  wire [11:0]                   column_valid_u12,
    output wire                          out_valid,
    input  wire                          out_ready,
    output wire [TILE_W-1:0]             out_tile_index,
    output wire signed [16*12*24-1:0]    projection_s24x16x12,
    output reg  [31:0]                   input_transaction_count,
    output reg  [31:0]                   input_group_count,
    output reg  [31:0]                   output_tile_count,
    output reg                           error
);
    localparam integer ROWS = 16;
    localparam integer COLS = 12;
    localparam integer PAIRS = 6;
    localparam integer PAIR_LANES = ROWS*PAIRS;
    localparam integer OUTPUT_LANES = ROWS*COLS;
    localparam integer TAG_PTR_W = $clog2(TAG_DEPTH);
    localparam integer TAG_COUNT_W = $clog2(TAG_DEPTH+1);
    localparam integer TAG_W = TILE_W+2;
    localparam integer GROUP_W = (GROUPS <= 2) ? 1 : $clog2(GROUPS);
    localparam integer ADD_LAT = 11;
    localparam integer FIXED_LAT = 6;

    wire [PAIR_LANES-1:0] lane_in_ready;
    wire [PAIR_LANES-1:0] lane_out_valid;
    wire [PAIR_LANES-1:0] lane_error;
    wire [PAIR_LANES*2*32-1:0] partial_fp32;
    reg [TAG_W-1:0] tag_mem [0:TAG_DEPTH-1];
    reg [TAG_PTR_W-1:0] tag_wr_ptr_r;
    reg [TAG_PTR_W-1:0] tag_rd_ptr_r;
    reg [TAG_COUNT_W-1:0] tag_count_r;
    wire tag_full = tag_count_r == TAG_DEPTH;
    wire tag_empty = tag_count_r == 0;
    wire in_fire = in_valid && in_ready;
    wire partial_fire = &lane_out_valid;
    wire [TAG_W-1:0] partial_tag = tag_mem[tag_rd_ptr_r];
    wire partial_first = partial_tag[TILE_W];
    wire partial_last = partial_tag[TILE_W+1];
    wire [TILE_W-1:0] partial_tile = partial_tag[0 +: TILE_W];

    assign in_ready = rst_n && !clear && !tag_full && lane_in_ready[0];

    genvar row;
    genvar pair;
    generate
        for (row = 0; row < ROWS; row = row + 1) begin : g_row
            for (pair = 0; pair < PAIRS; pair = pair + 1) begin : g_pair
                localparam integer LANE = row*PAIRS+pair;
                localparam integer COL0 = pair*2;
                localparam integer COL1 = pair*2+1;
                wire signed [32*4-1:0] weight0 =
                    column_valid_u12[COL0] ?
                    weights_s4x12x32[COL0*32*4 +: 32*4] : '0;
                wire signed [32*4-1:0] weight1 =
                    column_valid_u12[COL1] ?
                    weights_s4x12x32[COL1*32*4 +: 32*4] : '0;
                wire [FP_W-1:0] weight0_scale =
                    column_valid_u12[COL0] ?
                    weight_scale_fpx12[COL0*FP_W +: FP_W] : '0;
                wire [FP_W-1:0] weight1_scale =
                    column_valid_u12[COL1] ?
                    weight_scale_fpx12[COL1*FP_W +: FP_W] : '0;

                m12_fp_a8w4_lane2_partial #(.FP_W(FP_W)) u_lane (
                    .clk(clk), .rst_n(rst_n), .clear(clear),
                    .in_valid(in_valid && in_ready),
                    .in_ready(lane_in_ready[LANE]),
                    .activation_s9x32(
                        activation_s9x16x32[row*32*9 +: 32*9]),
                    .weight0_s4x32(weight0), .weight1_s4x32(weight1),
                    .activation_scale_fp(
                        activation_scale_fpx16[row*FP_W +: FP_W]),
                    .weight0_scale_fp(weight0_scale),
                    .weight1_scale_fp(weight1_scale),
                    .out_valid(lane_out_valid[LANE]),
                    .out0_fp32(partial_fp32[(LANE*2)*32 +: 32]),
                    .out1_fp32(partial_fp32[(LANE*2+1)*32 +: 32]),
                    .error(lane_error[LANE])
                );
            end
        end
    endgenerate

    reg state_valid_r;
    reg state_first_r;
    reg state_last_r;
    reg [TILE_W-1:0] state_tile_r;
    reg [OUTPUT_LANES*32-1:0] state_partial_r;
    wire [OUTPUT_LANES*32-1:0] state_read_fp32;
    wire [OUTPUT_LANES*32-1:0] add_result_fp32;
    wire [OUTPUT_LANES-1:0] add_result_valid;
    wire add_all_valid = &add_result_valid;
    wire add_tag_valid;
    wire [TILE_W:0] add_tag;
    wire add_last = add_tag[TILE_W];
    wire [TILE_W-1:0] add_tile = add_tag[0 +: TILE_W];

    m12_delay_bus #(.WIDTH(TILE_W+1), .DEPTH(ADD_LAT)) u_add_tag (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(state_valid_r), .in_data({state_last_r,state_tile_r}),
        .out_valid(add_tag_valid), .out_data(add_tag));

    genvar output_lane;
    generate
        for (output_lane = 0; output_lane < OUTPUT_LANES;
             output_lane = output_lane + 1) begin : g_state
            wire [31:0] old_value = state_first_r ? 32'd0 :
                state_read_fp32[output_lane*32 +: 32];
            m12_fp32_state_bank #(.TILES(TILES), .TILE_W(TILE_W)) u_bank (
                .clk(clk), .read_enable(partial_fire),
                .read_address(partial_tile),
                .read_data(state_read_fp32[output_lane*32 +: 32]),
                .write_enable(add_all_valid && add_tag_valid),
                .write_address(add_tile),
                .write_data(add_result_fp32[output_lane*32 +: 32]));
            m12_fp32_add u_add (
                .aclk(clk),
                .s_axis_a_tvalid(state_valid_r), .s_axis_a_tdata(old_value),
                .s_axis_b_tvalid(state_valid_r),
                .s_axis_b_tdata(
                    state_partial_r[output_lane*32 +: 32]),
                .m_axis_result_tvalid(add_result_valid[output_lane]),
                .m_axis_result_tdata(
                    add_result_fp32[output_lane*32 +: 32]));
        end
    endgenerate

    wire [OUTPUT_LANES-1:0] fixed_valid;
    wire signed [OUTPUT_LANES*24-1:0] fixed_result_s24;
    wire fixed_all_valid = &fixed_valid;
    wire fixed_tag_valid;
    wire [TILE_W-1:0] fixed_tile;
    m12_delay_bus #(.WIDTH(TILE_W), .DEPTH(FIXED_LAT)) u_fixed_tag (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(add_all_valid && add_tag_valid && add_last),
        .in_data(add_tile), .out_valid(fixed_tag_valid),
        .out_data(fixed_tile));

    generate
        for (output_lane = 0; output_lane < OUTPUT_LANES;
             output_lane = output_lane + 1) begin : g_fixed
            m12_fp32_to_s24 u_fixed (
                .aclk(clk),
                .s_axis_a_tvalid(add_all_valid && add_tag_valid && add_last),
                .s_axis_a_tdata(
                    add_result_fp32[output_lane*32 +: 32]),
                .m_axis_result_tvalid(fixed_valid[output_lane]),
                .m_axis_result_tdata(
                    fixed_result_s24[output_lane*24 +: 24]));
        end
    endgenerate

    reg out_valid_r;
    reg [TILE_W-1:0] out_tile_r;
    reg signed [OUTPUT_LANES*24-1:0] out_projection_r;
    reg [TILE_W-1:0] expected_input_tile_r;
    reg [GROUP_W-1:0] expected_input_group_r;
    reg [TILE_W-1:0] expected_output_tile_r;
    wire out_fire = out_valid && out_ready;
    wire result_push = fixed_all_valid && fixed_tag_valid;
    wire expected_mask = in_tile_index == TILES-1 ?
        column_valid_u12 == 12'h00f : column_valid_u12 == 12'hfff;

    assign out_valid = rst_n && !clear && out_valid_r;
    assign out_tile_index = out_tile_r;
    assign projection_s24x16x12 = out_projection_r;

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            tag_wr_ptr_r <= '0;
            tag_rd_ptr_r <= '0;
            tag_count_r <= '0;
            state_valid_r <= 1'b0;
            state_first_r <= 1'b0;
            state_last_r <= 1'b0;
            state_tile_r <= '0;
            out_valid_r <= 1'b0;
            out_tile_r <= '0;
            expected_input_tile_r <= '0;
            expected_input_group_r <= '0;
            expected_output_tile_r <= '0;
            input_transaction_count <= 32'd0;
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            error <= 1'b0;
        end else begin
            state_valid_r <= partial_fire && !tag_empty;
            if (partial_fire && !tag_empty) begin
                state_first_r <= partial_first;
                state_last_r <= partial_last;
                state_tile_r <= partial_tile;
                state_partial_r <= partial_fp32;
                tag_rd_ptr_r <= tag_rd_ptr_r + 1'b1;
            end

            if (in_fire) begin
                tag_mem[tag_wr_ptr_r] <= {
                    in_last_group,in_first_group,in_tile_index};
                tag_wr_ptr_r <= tag_wr_ptr_r + 1'b1;
                input_transaction_count <= input_transaction_count + 1'b1;
                if (in_tile_index != expected_input_tile_r ||
                    in_first_group != (expected_input_group_r == 0) ||
                    in_last_group != (expected_input_group_r == GROUPS-1) ||
                    !expected_mask)
                    error <= 1'b1;
                if (expected_input_tile_r == TILES-1) begin
                    expected_input_tile_r <= '0;
                    input_group_count <= input_group_count + 1'b1;
                    if (expected_input_group_r == GROUPS-1)
                        expected_input_group_r <= '0;
                    else
                        expected_input_group_r <= expected_input_group_r + 1'b1;
                end else
                    expected_input_tile_r <= expected_input_tile_r + 1'b1;
            end
            case ({in_fire,partial_fire && !tag_empty})
                2'b10: tag_count_r <= tag_count_r + 1'b1;
                2'b01: tag_count_r <= tag_count_r - 1'b1;
                default: tag_count_r <= tag_count_r;
            endcase

            case ({result_push,out_fire})
                2'b10: out_valid_r <= 1'b1;
                2'b01: out_valid_r <= 1'b0;
                2'b11: out_valid_r <= 1'b1;
                default: out_valid_r <= out_valid_r;
            endcase
            if (result_push) begin
                out_tile_r <= fixed_tile;
                out_projection_r <= fixed_result_s24;
                if (fixed_tile != expected_output_tile_r)
                    error <= 1'b1;
                if (expected_output_tile_r == TILES-1)
                    expected_output_tile_r <= '0;
                else
                    expected_output_tile_r <= expected_output_tile_r + 1'b1;
            end
            if (out_fire)
                output_tile_count <= output_tile_count + 1'b1;

            if (|lane_error ||
                lane_in_ready != {PAIR_LANES{lane_in_ready[0]}} ||
                ((|lane_out_valid) &&
                    lane_out_valid != {PAIR_LANES{lane_out_valid[0]}}) ||
                ((|add_result_valid) && !add_all_valid) ||
                ((|fixed_valid) && !fixed_all_valid) ||
                (partial_fire && tag_empty) || tag_count_r > TAG_DEPTH ||
                (add_all_valid != add_tag_valid) ||
                (fixed_all_valid != fixed_tag_valid) ||
                (result_push && out_valid_r && !out_ready))
                error <= 1'b1;
        end
    end

    initial begin
        if (FP_W != 16 && FP_W != 32)
            $error("m12 FP_W must be 16 or 32");
        if (TILES < ADD_LAT+2)
            $error("m12 TILES must exceed FP add read/modify/write latency");
        if (TAG_DEPTH < 32 || (TAG_DEPTH & (TAG_DEPTH-1)) != 0)
            $error("m12 TAG_DEPTH must be a power of two >=32");
    end
endmodule


module m12_fp16_down_group_major #(
    parameter integer TILES = 342,
    parameter integer GROUPS = 448,
    parameter integer TILE_W = (TILES <= 2) ? 1 : $clog2(TILES)
) (
    input wire clk, rst_n, clear, in_valid,
    output wire in_ready,
    input wire in_first_group, in_last_group,
    input wire [TILE_W-1:0] in_tile_index,
    input wire signed [16*32*9-1:0] activation_s9x16x32,
    input wire signed [12*32*4-1:0] weights_s4x12x32,
    input wire [16*16-1:0] activation_scale_fpx16,
    input wire [12*16-1:0] weight_scale_fpx12,
    input wire [11:0] column_valid_u12,
    output wire out_valid,
    input wire out_ready,
    output wire [TILE_W-1:0] out_tile_index,
    output wire signed [16*12*24-1:0] projection_s24x16x12,
    output wire [31:0] input_transaction_count,
    output wire [31:0] input_group_count,
    output wire [31:0] output_tile_count,
    output wire error
);
    m12_fp_down_group_major #(
        .FP_W(16), .TILES(TILES), .GROUPS(GROUPS), .TILE_W(TILE_W)
    ) u_core (.*);
endmodule


module m12_fp32_down_group_major #(
    parameter integer TILES = 342,
    parameter integer GROUPS = 448,
    parameter integer TILE_W = (TILES <= 2) ? 1 : $clog2(TILES)
) (
    input wire clk, rst_n, clear, in_valid,
    output wire in_ready,
    input wire in_first_group, in_last_group,
    input wire [TILE_W-1:0] in_tile_index,
    input wire signed [16*32*9-1:0] activation_s9x16x32,
    input wire signed [12*32*4-1:0] weights_s4x12x32,
    input wire [16*32-1:0] activation_scale_fpx16,
    input wire [12*32-1:0] weight_scale_fpx12,
    input wire [11:0] column_valid_u12,
    output wire out_valid,
    input wire out_ready,
    output wire [TILE_W-1:0] out_tile_index,
    output wire signed [16*12*24-1:0] projection_s24x16x12,
    output wire [31:0] input_transaction_count,
    output wire [31:0] input_group_count,
    output wire [31:0] output_tile_count,
    output wire error
);
    m12_fp_down_group_major #(
        .FP_W(32), .TILES(TILES), .GROUPS(GROUPS), .TILE_W(TILE_W)
    ) u_core (.*);
endmodule
