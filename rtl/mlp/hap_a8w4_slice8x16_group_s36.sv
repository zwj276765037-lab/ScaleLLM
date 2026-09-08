`timescale 1ns / 1ps

// One physical MLP group kernel: 8 request rows x 16 output columns.
//
// A single W4 group is shared by all eight rows.  Each of the 64 production
// two-column lanes remains lockstep; the slice adds a registered output stage
// so the 4,608-bit guard bus does not expose lane barrel-shifter paths at the
// hierarchy boundary.
module hap_a8w4_slice8x16_group_s36 (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire signed [8*32*9-1:0]     activation_s9x8x32,
    input  wire signed [16*32*4-1:0]    weights_s4x16x32,
    input  wire [8*8-1:0]               activation_code_u8x8,
    input  wire [8*6-1:0]               activation_shift_u6x8,
    input  wire [16*8-1:0]              weight_code_u8x16,
    input  wire [16*6-1:0]              weight_shift_u6x16,
    output reg                          out_valid,
    input  wire                         out_ready,
    output reg signed [8*16*36-1:0]     guard_s36x8x16,
    output reg [31:0]                   input_group_count,
    output reg [31:0]                   output_group_count,
    output reg                          error
);

    wire [63:0] lane_in_ready;
    wire [63:0] lane_out_valid;
    wire [63:0] lane_error;
    wire signed [64*2*36-1:0] lane_guard_s36x64x2;
    wire all_lane_out_valid = &lane_out_valid;
    wire any_lane_out_valid = |lane_out_valid;
    reg [7:0] row_lane_error_r;
    wire output_stage_ready = !out_valid || out_ready;
    // All lanes accept exactly the same transaction and have identical FIFO
    // depths.  Use lane0 for functional flow control; the all-lane reductions
    // remain only as divergence monitors.  This removes two 64-way reductions
    // from the timing-critical ready/valid path.
    wire lane_out_ready = output_stage_ready;
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;

    assign in_ready = rst_n && !clear && lane_in_ready[0];

    genvar row;
    genvar pair;
    generate
        for (row = 0; row < 8; row = row + 1) begin : gen_row
            for (pair = 0; pair < 8; pair = pair + 1) begin : gen_pair
                localparam integer LANE = row*8 + pair;
                localparam integer COL0 = pair*2;
                localparam integer COL1 = pair*2 + 1;
                wire [31:0] unused_input_count;
                wire [31:0] unused_output_count;
                hap_a8w4_group32_lane2_s36 #(
                    .LOCKSTEP_EVENT_INPUT(1)
                ) u_lane (
                    .clk(clk), .rst_n(rst_n), .clear(clear),
                    .in_valid(in_valid && in_ready),
                    .in_ready(lane_in_ready[LANE]),
                    .activation_s9x32(
                        activation_s9x8x32[row*32*9 +: 32*9]),
                    .weight0_s4x32(
                        weights_s4x16x32[COL0*32*4 +: 32*4]),
                    .weight1_s4x32(
                        weights_s4x16x32[COL1*32*4 +: 32*4]),
                    .activation_code_u8(
                        activation_code_u8x8[row*8 +: 8]),
                    .activation_shift_u6(
                        activation_shift_u6x8[row*6 +: 6]),
                    .weight0_code_u8(
                        weight_code_u8x16[COL0*8 +: 8]),
                    .weight0_shift_u6(
                        weight_shift_u6x16[COL0*6 +: 6]),
                    .weight1_code_u8(
                        weight_code_u8x16[COL1*8 +: 8]),
                    .weight1_shift_u6(
                        weight_shift_u6x16[COL1*6 +: 6]),
                    .out_valid(lane_out_valid[LANE]),
                    .out_ready(lane_out_ready),
                    .guard0_s36(
                        lane_guard_s36x64x2[(LANE*2)*36 +: 36]),
                    .guard1_s36(
                        lane_guard_s36x64x2[(LANE*2+1)*36 +: 36]),
                    .input_group_count(unused_input_count),
                    .output_group_count(unused_output_count),
                    .error(lane_error[LANE])
                );
            end
        end
    endgenerate

    integer row_idx;
    integer pair_idx;
    integer lane_idx;
    always @(posedge clk) begin
        if (!rst_n) begin
            out_valid <= 1'b0;
            guard_s36x8x16 <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            error <= 1'b0;
            row_lane_error_r <= '0;
        end else if (clear) begin
            out_valid <= 1'b0;
            guard_s36x8x16 <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            error <= 1'b0;
            row_lane_error_r <= '0;
        end else begin
            if (output_stage_ready) begin
                out_valid <= lane_out_valid[0];
                if (lane_out_valid[0]) begin
                    for (row_idx = 0; row_idx < 8; row_idx = row_idx + 1)
                        for (pair_idx = 0; pair_idx < 8;
                             pair_idx = pair_idx + 1) begin
                            lane_idx = row_idx*8 + pair_idx;
                            guard_s36x8x16[
                                (row_idx*16+pair_idx*2)*36 +: 36] <=
                                lane_guard_s36x64x2[
                                (lane_idx*2)*36 +: 36];
                            guard_s36x8x16[
                                (row_idx*16+pair_idx*2+1)*36 +: 36] <=
                                lane_guard_s36x64x2[
                                (lane_idx*2+1)*36 +: 36];
                        end
                end
            end
            if (in_fire)
                input_group_count <= input_group_count + 32'd1;
            if (out_fire)
                output_group_count <= output_group_count + 32'd1;
            // Two-level registered error reduction avoids a 64-lane
            // combinational cone into one sticky error flop.
            for (row_idx = 0; row_idx < 8; row_idx = row_idx + 1)
                row_lane_error_r[row_idx] <=
                    |lane_error[row_idx*8 +: 8];
            if (|row_lane_error_r)
                error <= 1'b1;
        end
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !clear &&
            (lane_in_ready != {64{lane_in_ready[0]}}))
            $error("hap_a8w4_slice8x16 lane in_ready divergence");
        if (rst_n && !clear && any_lane_out_valid && !all_lane_out_valid)
            $error("hap_a8w4_slice8x16 lane out_valid divergence");
    end
`endif

endmodule
