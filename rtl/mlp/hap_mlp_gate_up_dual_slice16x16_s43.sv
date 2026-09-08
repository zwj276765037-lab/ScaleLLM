`timescale 1ns / 1ps

// Cohort16 gate/up projection kernel.  One W4 group is accepted at the top,
// captured into two local physical copies and delivered independently to two
// 8x16 slices.  Each slice completes S36 -> local S43 accumulation -> S24
// inside its own hierarchy; only completed S24 tiles are atomically joined.
module hap_mlp_gate_up_dual_slice16x16_s43 (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          clear,
    input  wire                          in_valid,
    output wire                          in_ready,
    input  wire                          in_first_group,
    input  wire                          in_last_group,
    input  wire signed [16*32*9-1:0]     activation_s9x16x32,
    input  wire signed [16*32*4-1:0]     weights_s4x16x32,
    input  wire [16*8-1:0]               activation_code_u8x16,
    input  wire [16*6-1:0]               activation_shift_u6x16,
    input  wire [16*8-1:0]               weight_code_u8x16,
    input  wire [16*6-1:0]               weight_shift_u6x16,
    output wire                          out_valid,
    input  wire                          out_ready,
    output wire signed [16*16*24-1:0]    projection_s24x16x16,
    output reg  [31:0]                   input_group_count,
    output reg  [31:0]                   output_tile_count,
    output wire [31:0]                   saturation_count,
    output reg                           error
);

    reg stage_valid_r;
    reg stage_pending0_r;
    reg stage_pending1_r;
    reg stage_first_group_r;
    reg stage_last_group_r;
    reg signed [8*32*9-1:0] stage_activation0_s9x8x32_r;
    reg signed [8*32*9-1:0] stage_activation1_s9x8x32_r;
    (* keep = "true" *) reg signed [16*32*4-1:0]
        stage_weights0_s4x16x32_r;
    (* keep = "true" *) reg signed [16*32*4-1:0]
        stage_weights1_s4x16x32_r;
    reg [8*8-1:0] stage_activation_code0_u8x8_r;
    reg [8*8-1:0] stage_activation_code1_u8x8_r;
    reg [8*6-1:0] stage_activation_shift0_u6x8_r;
    reg [8*6-1:0] stage_activation_shift1_u6x8_r;
    (* keep = "true" *) reg [16*8-1:0] stage_weight_code0_u8x16_r;
    (* keep = "true" *) reg [16*8-1:0] stage_weight_code1_u8x16_r;
    (* keep = "true" *) reg [16*6-1:0] stage_weight_shift0_u6x16_r;
    (* keep = "true" *) reg [16*6-1:0] stage_weight_shift1_u6x16_r;

    wire slice0_in_ready;
    wire slice1_in_ready;
    wire slice0_out_valid;
    wire slice1_out_valid;
    wire slice0_out_ready;
    wire slice1_out_ready;
    wire signed [8*16*24-1:0] slice0_projection_s24;
    wire signed [8*16*24-1:0] slice1_projection_s24;
    wire [31:0] slice0_input_group_count;
    wire [31:0] slice1_input_group_count;
    wire [31:0] slice0_output_tile_count;
    wire [31:0] slice1_output_tile_count;
    wire [31:0] slice0_saturation_count;
    wire [31:0] slice1_saturation_count;
    wire slice0_error;
    wire slice1_error;

    wire slice0_accept = stage_valid_r && stage_pending0_r &&
        slice0_in_ready;
    wire slice1_accept = stage_valid_r && stage_pending1_r &&
        slice1_in_ready;
    wire staged_group_done = stage_valid_r &&
        (!stage_pending0_r || slice0_in_ready) &&
        (!stage_pending1_r || slice1_in_ready);
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;

    assign in_ready = rst_n && !clear &&
        (!stage_valid_r || staged_group_done);
    assign out_valid = rst_n && !clear &&
        slice0_out_valid && slice1_out_valid;
    assign slice0_out_ready = out_ready && slice1_out_valid;
    assign slice1_out_ready = out_ready && slice0_out_valid;
    assign projection_s24x16x16[0 +: 8*16*24] =
        slice0_projection_s24;
    assign projection_s24x16x16[8*16*24 +: 8*16*24] =
        slice1_projection_s24;
    assign saturation_count = slice0_saturation_count +
        slice1_saturation_count;

    (* keep_hierarchy = "yes" *)
    hap_mlp_gate_up_slice8x16_s43 u_slice0 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(stage_valid_r && stage_pending0_r),
        .in_ready(slice0_in_ready),
        .in_first_group(stage_first_group_r),
        .in_last_group(stage_last_group_r),
        .activation_s9x8x32(stage_activation0_s9x8x32_r),
        .weights_s4x16x32(stage_weights0_s4x16x32_r),
        .activation_code_u8x8(stage_activation_code0_u8x8_r),
        .activation_shift_u6x8(stage_activation_shift0_u6x8_r),
        .weight_code_u8x16(stage_weight_code0_u8x16_r),
        .weight_shift_u6x16(stage_weight_shift0_u6x16_r),
        .out_valid(slice0_out_valid), .out_ready(slice0_out_ready),
        .projection_s24x8x16(slice0_projection_s24),
        .input_group_count(slice0_input_group_count),
        .output_tile_count(slice0_output_tile_count),
        .saturation_count(slice0_saturation_count),
        .error(slice0_error)
    );

    (* keep_hierarchy = "yes" *)
    hap_mlp_gate_up_slice8x16_s43 u_slice1 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(stage_valid_r && stage_pending1_r),
        .in_ready(slice1_in_ready),
        .in_first_group(stage_first_group_r),
        .in_last_group(stage_last_group_r),
        .activation_s9x8x32(stage_activation1_s9x8x32_r),
        .weights_s4x16x32(stage_weights1_s4x16x32_r),
        .activation_code_u8x8(stage_activation_code1_u8x8_r),
        .activation_shift_u6x8(stage_activation_shift1_u6x8_r),
        .weight_code_u8x16(stage_weight_code1_u8x16_r),
        .weight_shift_u6x16(stage_weight_shift1_u6x16_r),
        .out_valid(slice1_out_valid), .out_ready(slice1_out_ready),
        .projection_s24x8x16(slice1_projection_s24),
        .input_group_count(slice1_input_group_count),
        .output_tile_count(slice1_output_tile_count),
        .saturation_count(slice1_saturation_count),
        .error(slice1_error)
    );

    always @(posedge clk) begin
        if (!rst_n) begin
            stage_valid_r <= 1'b0;
            stage_pending0_r <= 1'b0;
            stage_pending1_r <= 1'b0;
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            stage_valid_r <= 1'b0;
            stage_pending0_r <= 1'b0;
            stage_pending1_r <= 1'b0;
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (slice0_accept)
                stage_pending0_r <= 1'b0;
            if (slice1_accept)
                stage_pending1_r <= 1'b0;
            if (staged_group_done && !in_fire) begin
                stage_valid_r <= 1'b0;
                stage_pending0_r <= 1'b0;
                stage_pending1_r <= 1'b0;
            end
            if (in_fire) begin
                stage_valid_r <= 1'b1;
                stage_pending0_r <= 1'b1;
                stage_pending1_r <= 1'b1;
                stage_first_group_r <= in_first_group;
                stage_last_group_r <= in_last_group;
                stage_activation0_s9x8x32_r <=
                    activation_s9x16x32[0 +: 8*32*9];
                stage_activation1_s9x8x32_r <=
                    activation_s9x16x32[8*32*9 +: 8*32*9];
                stage_weights0_s4x16x32_r <= weights_s4x16x32;
                stage_weights1_s4x16x32_r <= weights_s4x16x32;
                stage_activation_code0_u8x8_r <=
                    activation_code_u8x16[0 +: 8*8];
                stage_activation_code1_u8x8_r <=
                    activation_code_u8x16[8*8 +: 8*8];
                stage_activation_shift0_u6x8_r <=
                    activation_shift_u6x16[0 +: 8*6];
                stage_activation_shift1_u6x8_r <=
                    activation_shift_u6x16[8*6 +: 8*6];
                stage_weight_code0_u8x16_r <= weight_code_u8x16;
                stage_weight_code1_u8x16_r <= weight_code_u8x16;
                stage_weight_shift0_u6x16_r <= weight_shift_u6x16;
                stage_weight_shift1_u6x16_r <= weight_shift_u6x16;
                input_group_count <= input_group_count + 32'd1;
            end
            if (out_fire)
                output_tile_count <= output_tile_count + 32'd1;
            if (slice0_error || slice1_error)
                error <= 1'b1;
        end
    end

`ifndef SYNTHESIS
    // A temporary count difference is legal while the fork has delivered the
    // staged group to only one branch.  Compare only when no split delivery
    // is outstanding; otherwise a legal independent-ready cycle would turn
    // into a false sticky hardware error.
    always @(posedge clk) begin
        if (rst_n && !clear && !stage_valid_r &&
            (slice0_input_group_count != slice1_input_group_count))
            $error("gate/up dual-slice input count divergence while idle");
        if (rst_n && !clear &&
            (slice0_output_tile_count != slice1_output_tile_count) &&
            !(slice0_out_valid ^ slice1_out_valid))
            $error("gate/up dual-slice output tile count divergence");
    end
`endif

endmodule
