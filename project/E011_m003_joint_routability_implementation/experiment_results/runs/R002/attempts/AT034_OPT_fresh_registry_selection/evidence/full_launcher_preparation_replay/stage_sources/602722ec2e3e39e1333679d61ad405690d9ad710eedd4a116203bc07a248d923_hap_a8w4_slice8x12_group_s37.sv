`timescale 1ns / 1ps

// V5 physical MLP group kernel: 8 request rows x 12 output columns.
//
// The numerical leaf is unchanged from V4: one DSP48E2 packs two signed W4
// columns for one centered S9 activation.  Six pack2 lanes per row and 32 K
// positions therefore infer exactly 8*6*32 = 1536 DSP48E2 primitives.
//
// column_valid_u12 is a low-contiguous mask used only by the final 8-column
// (14336-wide matrices) or 4-column (4096-wide matrices) tail pass.  Invalid
// columns are zeroed before both the packed multiplier and ScaleCode recovery,
// so their guard is exactly zero without changing the lockstep pipeline.
// One S45 output bank provides the S37 Gate/Up view and S45 Down view.
module hap_a8w4_slice8x12_group_s37 #(
    parameter integer DOWN_MODE_ENABLE = 0
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire [7:0]                   clear_by_row,
    input  wire                         down_mode,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire signed [8*32*9-1:0]     activation_s9x8x32,
    input  wire signed [12*32*4-1:0]    weights_s4x12x32,
    input  wire [8*8-1:0]               activation_code_u8x8,
    input  wire [8*6-1:0]               activation_shift_u6x8,
    input  wire [12*8-1:0]              weight_code_u8x12,
    input  wire [12*6-1:0]              weight_shift_u6x12,
    input  wire [11:0]                  column_valid_u12,
    output wire                         out_valid,
    input  wire                         out_ready,
    output wire signed [8*12*37-1:0]    guard_s37x8x12,
    output reg signed [8*12*45-1:0]     guard_s45x8x12,
    output wire                         out_down,
    output wire                         guard_overflow,
    output wire [31:0]                  total_shift_format_count,
    output wire                         format_error,
    output reg [31:0]                   input_group_count,
    output reg [31:0]                   output_group_count,
    output reg                          error
);

    localparam integer ROWS = 8;
    localparam integer COLS = 12;
    localparam integer PAIRS = COLS/2;
    localparam integer LANES = ROWS*PAIRS;
    wire clear_summary = clear_by_row[0];

    wire [LANES-1:0] lane_in_ready;
    wire [LANES-1:0] lane_out_valid;
    wire [LANES-1:0] lane_error;
    wire [LANES-1:0] lane_guard_overflow;
    wire signed [LANES*2*45-1:0] lane_guard_s45x48x2;
    wire [LANES-1:0] lane_out_down;
    wire [LANES-1:0] lane_format_error;
    wire [31:0] lane_shift_format_count [0:LANES-1];
    wire [31:0] row_shift_format_count [0:ROWS-1];
    wire [31:0] shift_count2 [0:3];
    wire [31:0] shift_count4 [0:1];
    reg [ROWS-1:0] row_down_r;
    wire all_lane_out_valid = &lane_out_valid;
    wire any_lane_out_valid = |lane_out_valid;
    reg [ROWS-1:0] row_lane_error_r;
    // One valid owner and one capture predicate per row.  All rows remain
    // lockstep, but no single LUT output drives the complete 3552-bit guard
    // register.  This is a functional row-banked output stage, not a fanout
    // property or a clock-buffer waiver.
    reg [ROWS-1:0] row_out_valid_r;
    wire [ROWS-1:0] row_output_stage_ready;
    wire [ROWS-1:0] row_capture_fire;
    wire [LANES-1:0] lane_out_ready;
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    // Production accepts only full passes and the two formal matrix tails.
    // Keeping the legal set discrete also avoids turning a generic mask
    // arithmetic cone into global control at slice scale.
    wire mask_is_legal = column_valid_u12 == 12'hfff ||
        column_valid_u12 == 12'h0ff || column_valid_u12 == 12'h00f;

    // The input fork remains atomic, while each row owns its output credit.
    // This prevents one central ready predicate from becoming the CE owner
    // for all 3552 guard bits.
    // Lane 0 owns the lockstep input credit.  Every lane receives only the
    // accepted owner event and latches a local error if it cannot accept that
    // event, avoiding a 48-lane ready reduction followed by a global CE net.
    assign in_ready = rst_n && !clear_summary && lane_in_ready[0];
    assign out_valid = rst_n && !clear_summary && &row_out_valid_r;
    assign guard_overflow = |lane_guard_overflow;
    assign out_down = row_down_r[0];
    assign format_error = |lane_format_error;
    assign total_shift_format_count = shift_count4[0] + shift_count4[1];

    genvar output_row;
    generate
        for (output_row = 0; output_row < ROWS;
             output_row = output_row + 1) begin : gen_row_output_control
            assign row_output_stage_ready[output_row] =
                !row_out_valid_r[output_row] || out_fire;
            assign row_capture_fire[output_row] =
                row_output_stage_ready[output_row] &&
                lane_out_valid[output_row*PAIRS];
        end
    endgenerate

    genvar row;
    genvar pair;
    generate
        for (row = 0; row < ROWS; row = row + 1) begin : gen_row
            for (pair = 0; pair < PAIRS; pair = pair + 1) begin : gen_pair
                localparam integer LANE = row*PAIRS + pair;
                localparam integer COL0 = pair*2;
                localparam integer COL1 = pair*2 + 1;
                wire signed [32*4-1:0] weight0_s4x32 =
                    column_valid_u12[COL0] ?
                    weights_s4x12x32[COL0*32*4 +: 32*4] : '0;
                wire signed [32*4-1:0] weight1_s4x32 =
                    column_valid_u12[COL1] ?
                    weights_s4x12x32[COL1*32*4 +: 32*4] : '0;
                wire [7:0] weight0_code = column_valid_u12[COL0] ?
                    weight_code_u8x12[COL0*8 +: 8] : 8'd0;
                wire [7:0] weight1_code = column_valid_u12[COL1] ?
                    weight_code_u8x12[COL1*8 +: 8] : 8'd0;
                wire [5:0] weight0_shift = column_valid_u12[COL0] ?
                    weight_shift_u6x12[COL0*6 +: 6] : 6'd0;
                wire [5:0] weight1_shift = column_valid_u12[COL1] ?
                    weight_shift_u6x12[COL1*6 +: 6] : 6'd0;
                wire [31:0] unused_input_count;
                wire [31:0] unused_output_count;

                hap_a8w4_group32_lane2_s37 #(
                    .LOCKSTEP_EVENT_INPUT(1),
                    .DOWN_MODE_ENABLE(DOWN_MODE_ENABLE)
                ) u_lane (
                    .clk(clk), .rst_n(rst_n), .clear(clear_by_row[row]),
                    .down_mode(down_mode),
                    .in_valid(in_valid && in_ready),
                    .in_ready(lane_in_ready[LANE]),
                    .activation_s9x32(
                        activation_s9x8x32[row*32*9 +: 32*9]),
                    .weight0_s4x32(weight0_s4x32),
                    .weight1_s4x32(weight1_s4x32),
                    .activation_code_u8(
                        activation_code_u8x8[row*8 +: 8]),
                    .activation_shift_u6(
                        activation_shift_u6x8[row*6 +: 6]),
                    .weight0_code_u8(weight0_code),
                    .weight0_shift_u6(weight0_shift),
                    .weight1_code_u8(weight1_code),
                    .weight1_shift_u6(weight1_shift),
                    .out_valid(lane_out_valid[LANE]),
                    .out_ready(lane_out_ready[LANE]),
                    .guard0_s37(), .guard1_s37(),
                    .guard0_s45(
                        lane_guard_s45x48x2[(LANE*2)*45 +: 45]),
                    .guard1_s45(
                        lane_guard_s45x48x2[(LANE*2+1)*45 +: 45]),
                    .out_down(lane_out_down[LANE]),
                    .guard_overflow(lane_guard_overflow[LANE]),
                    .total_shift_format_count(lane_shift_format_count[LANE]),
                    .format_error(lane_format_error[LANE]),
                    .input_group_count(unused_input_count),
                    .output_group_count(unused_output_count),
                    .error(lane_error[LANE])
                );
            end
            assign row_shift_format_count[row] =
                (lane_shift_format_count[row*PAIRS+0] +
                 lane_shift_format_count[row*PAIRS+1]) +
                (lane_shift_format_count[row*PAIRS+2] +
                 lane_shift_format_count[row*PAIRS+3]) +
                (lane_shift_format_count[row*PAIRS+4] +
                 lane_shift_format_count[row*PAIRS+5]);
        end
        for (row = 0; row < 4; row = row + 1) begin : gen_shift_count2
            assign shift_count2[row] = row_shift_format_count[row*2] +
                row_shift_format_count[row*2+1];
        end
        for (row = 0; row < 2; row = row + 1) begin : gen_shift_count4
            assign shift_count4[row] = shift_count2[row*2] +
                shift_count2[row*2+1];
        end
        for (row = 0; row < ROWS*COLS; row = row + 1) begin : gen_guard_s37_view
            assign guard_s37x8x12[row*37 +: 37] =
                guard_s45x8x12[row*45 +: 37];
        end
    endgenerate

    generate
        for (row = 0; row < ROWS; row = row + 1) begin : gen_row_ready
            for (pair = 0; pair < PAIRS; pair = pair + 1) begin : gen_pair_ready
                localparam integer READY_LANE = row*PAIRS + pair;
                assign lane_out_ready[READY_LANE] =
                    row_output_stage_ready[row];
            end
        end
    endgenerate

    integer row_idx;
    integer pair_idx;
    integer lane_idx;
    always @(posedge clk) begin
        if (!rst_n) begin
            row_out_valid_r <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            error <= 1'b0;
            row_lane_error_r <= '0;
        end else begin
            for (row_idx = 0; row_idx < ROWS;
                 row_idx = row_idx + 1) begin
                if (clear_by_row[row_idx]) begin
                    row_out_valid_r[row_idx] <= 1'b0;
                    row_lane_error_r[row_idx] <= 1'b0;
                end else begin
                    if (row_output_stage_ready[row_idx]) begin
                        row_out_valid_r[row_idx] <=
                            lane_out_valid[row_idx*PAIRS];
                        if (row_capture_fire[row_idx]) begin
                            row_down_r[row_idx] <=
                                lane_out_down[row_idx*PAIRS];
                            for (pair_idx = 0; pair_idx < PAIRS;
                                 pair_idx = pair_idx + 1) begin
                                lane_idx = row_idx*PAIRS + pair_idx;
                                guard_s45x8x12[
                                    (row_idx*COLS+pair_idx*2)*45 +: 45] <=
                                    lane_guard_s45x48x2[
                                        (lane_idx*2)*45 +: 45];
                                guard_s45x8x12[
                                    (row_idx*COLS+pair_idx*2+1)*45 +: 45] <=
                                    lane_guard_s45x48x2[
                                        (lane_idx*2+1)*45 +: 45];
                                if (lane_out_down[lane_idx] !=
                                    lane_out_down[row_idx*PAIRS])
                                    error <= 1'b1;
                            end
                        end
                    end
                    row_lane_error_r[row_idx] <=
                        |lane_error[row_idx*PAIRS +: PAIRS];
                end
            end
            if (clear_summary) begin
                input_group_count <= 32'd0;
                output_group_count <= 32'd0;
                error <= 1'b0;
            end else begin
                if (in_fire) begin
                    input_group_count <= input_group_count + 32'd1;
                    if (!mask_is_legal)
                        error <= 1'b1;
                end
                if (out_fire) begin
                    output_group_count <= output_group_count + 32'd1;
                    if (row_down_r != {ROWS{row_down_r[0]}})
                        error <= 1'b1;
                end
                if (|row_lane_error_r)
                    error <= 1'b1;
            end
        end
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && clear_by_row != {ROWS{clear_summary}})
            $error("hap_a8w4_slice8x12 row clear divergence");
        if (rst_n && !clear_summary &&
            (lane_in_ready != {LANES{lane_in_ready[0]}}))
            $error("hap_a8w4_slice8x12 lane in_ready divergence");
        if (rst_n && !clear_summary && any_lane_out_valid &&
            !all_lane_out_valid)
            $error("hap_a8w4_slice8x12 lane out_valid divergence");
        if (rst_n && !clear_summary &&
            row_out_valid_r != {ROWS{row_out_valid_r[0]}})
            $error("hap_a8w4_slice8x12 row output-valid divergence");
    end
`endif

endmodule
