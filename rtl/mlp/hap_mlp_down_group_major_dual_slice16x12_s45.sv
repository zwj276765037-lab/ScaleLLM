`timescale 1ns / 1ps

// V5 cohort16 down projection leaf.  Internal tiles are 12 columns wide and
// TILES=342 for the formal Llama shape.  Each 8-row slice owns 96 independent
// S45 accumulator lanes; only completed S24 passes cross the hierarchy.
module hap_mlp_down_group_major_dual_slice16x12_s45 #(
    parameter integer TILES = 342,
    parameter integer GROUPS = 448,
    parameter integer TILE_W = (TILES <= 2) ? 1 : $clog2(TILES)
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
    input  wire [16*8-1:0]               activation_code_u8x16,
    input  wire [16*6-1:0]               activation_shift_u6x16,
    input  wire [12*8-1:0]               weight_code_u8x12,
    input  wire [12*6-1:0]               weight_shift_u6x12,
    input  wire [11:0]                   column_valid_u12,
    output wire                          out_valid,
    input  wire                          out_ready,
    output wire [TILE_W-1:0]             out_tile_index,
    output wire signed [16*12*24-1:0]    projection_s24x16x12,
    output reg  [31:0]                   input_tile_count,
    output reg  [31:0]                   output_pass_count,
    output wire [31:0]                   saturation_count,
    output reg                           error
);
    localparam integer LANES = 96;
    reg stage_valid_r, stage_pending0_r, stage_pending1_r;
    reg stage_first_r, stage_last_r;
    reg [TILE_W-1:0] stage_tile_r;
    reg signed [8*32*9-1:0] stage_activation0_r, stage_activation1_r;
    (* keep = "true" *) reg signed [12*32*4-1:0] stage_weights0_r, stage_weights1_r;
    reg [8*8-1:0] stage_activation_code0_r, stage_activation_code1_r;
    reg [8*6-1:0] stage_activation_shift0_r, stage_activation_shift1_r;
    (* keep = "true" *) reg [12*8-1:0] stage_weight_code0_r, stage_weight_code1_r;
    (* keep = "true" *) reg [12*6-1:0] stage_weight_shift0_r, stage_weight_shift1_r;
    reg [11:0] stage_mask0_r, stage_mask1_r;

    wire slice0_kernel_ready, slice1_kernel_ready;
    wire slice0_guard_valid, slice1_guard_valid;
    wire slice0_accum_ready, slice1_accum_ready;
    wire signed [LANES*36-1:0] slice0_guard, slice1_guard;
    wire slice0_valid, slice1_valid;
    wire [TILE_W-1:0] slice0_tile, slice1_tile;
    wire signed [LANES*24-1:0] slice0_projection, slice1_projection;
    wire [31:0] slice0_saturation, slice1_saturation;
    wire slice0_kernel_error, slice1_kernel_error;
    wire slice0_accum_error, slice1_accum_error;

    // Kernel tags are paired by the staging register.  The 12-column kernel
    // is currently an elastic one-group pipeline; each branch may accept the
    // staged item independently but the next top item waits for both.
    reg tag0_first[0:31], tag0_last[0:31];
    reg [TILE_W-1:0] tag0_tile[0:31];
    reg [4:0] tag0_wr, tag0_rd; reg [5:0] tag0_count;
    reg tag1_first[0:31], tag1_last[0:31];
    reg [TILE_W-1:0] tag1_tile[0:31];
    reg [4:0] tag1_wr, tag1_rd; reg [5:0] tag1_count;

    wire slice0_accept = stage_valid_r && stage_pending0_r &&
        slice0_kernel_ready && tag0_count != 32;
    wire slice1_accept = stage_valid_r && stage_pending1_r &&
        slice1_kernel_ready && tag1_count != 32;
    wire staged_done = stage_valid_r &&
        (!stage_pending0_r || slice0_accept) &&
        (!stage_pending1_r || slice1_accept);
    wire in_fire = in_valid && in_ready;
    wire slice0_guard_fire = slice0_guard_valid && slice0_accum_ready && tag0_count != 0;
    wire slice1_guard_fire = slice1_guard_valid && slice1_accum_ready && tag1_count != 0;
    wire out_fire = out_valid && out_ready;

    assign in_ready = rst_n && !clear && (!stage_valid_r || staged_done);
    assign out_valid = rst_n && !clear && slice0_valid && slice1_valid;
    assign out_tile_index = slice0_tile;
    assign projection_s24x16x12[0 +: LANES*24] = slice0_projection;
    assign projection_s24x16x12[LANES*24 +: LANES*24] = slice1_projection;
    assign saturation_count = slice0_saturation + slice1_saturation;

    (* keep_hierarchy = "yes" *) hap_a8w4_slice8x12_group_s36 u_kernel0 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(stage_valid_r && stage_pending0_r && tag0_count != 32),
        .in_ready(slice0_kernel_ready),
        .activation_s9x8x32(stage_activation0_r), .weights_s4x12x32(stage_weights0_r),
        .activation_code_u8x8(stage_activation_code0_r), .activation_shift_u6x8(stage_activation_shift0_r),
        .weight_code_u8x12(stage_weight_code0_r), .weight_shift_u6x12(stage_weight_shift0_r),
        .column_valid_u12(stage_mask0_r), .out_valid(slice0_guard_valid),
        .out_ready(slice0_accum_ready && tag0_count != 0), .guard_s36x8x12(slice0_guard),
        .input_group_count(), .output_group_count(), .error(slice0_kernel_error));
    (* keep_hierarchy = "yes" *) hap_a8w4_slice8x12_group_s36 u_kernel1 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(stage_valid_r && stage_pending1_r && tag1_count != 32),
        .in_ready(slice1_kernel_ready),
        .activation_s9x8x32(stage_activation1_r), .weights_s4x12x32(stage_weights1_r),
        .activation_code_u8x8(stage_activation_code1_r), .activation_shift_u6x8(stage_activation_shift1_r),
        .weight_code_u8x12(stage_weight_code1_r), .weight_shift_u6x12(stage_weight_shift1_r),
        .column_valid_u12(stage_mask1_r), .out_valid(slice1_guard_valid),
        .out_ready(slice1_accum_ready && tag1_count != 0), .guard_s36x8x12(slice1_guard),
        .input_group_count(), .output_group_count(), .error(slice1_kernel_error));

    hap_mlp_down_group_major_accum_s45 #(.LANES(LANES), .TILES(TILES), .GROUPS(GROUPS), .TILE_W(TILE_W)) u_accum0 (
        .clk(clk), .rst_n(rst_n), .clear(clear), .in_valid(slice0_guard_valid && tag0_count != 0),
        .in_ready(slice0_accum_ready), .in_first_group(tag0_first[tag0_rd]), .in_last_group(tag0_last[tag0_rd]),
        .in_tile_index(tag0_tile[tag0_rd]), .in_guard_s36(slice0_guard), .out_valid(slice0_valid),
        .out_ready(out_ready && slice1_valid), .out_tile_index(slice0_tile), .out_projection_s24(slice0_projection),
        .input_tile_count(), .input_group_count(), .output_tile_count(), .saturation_count(slice0_saturation), .error(slice0_accum_error));
    hap_mlp_down_group_major_accum_s45 #(.LANES(LANES), .TILES(TILES), .GROUPS(GROUPS), .TILE_W(TILE_W)) u_accum1 (
        .clk(clk), .rst_n(rst_n), .clear(clear), .in_valid(slice1_guard_valid && tag1_count != 0),
        .in_ready(slice1_accum_ready), .in_first_group(tag1_first[tag1_rd]), .in_last_group(tag1_last[tag1_rd]),
        .in_tile_index(tag1_tile[tag1_rd]), .in_guard_s36(slice1_guard), .out_valid(slice1_valid),
        .out_ready(out_ready && slice0_valid), .out_tile_index(slice1_tile), .out_projection_s24(slice1_projection),
        .input_tile_count(), .input_group_count(), .output_tile_count(), .saturation_count(slice1_saturation), .error(slice1_accum_error));

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            stage_valid_r <= 0; stage_pending0_r <= 0; stage_pending1_r <= 0;
            tag0_wr <= 0; tag0_rd <= 0; tag0_count <= 0;
            tag1_wr <= 0; tag1_rd <= 0; tag1_count <= 0;
            input_tile_count <= 0; output_pass_count <= 0; error <= 0;
        end else begin
            if (slice0_accept) begin tag0_first[tag0_wr] <= stage_first_r; tag0_last[tag0_wr] <= stage_last_r; tag0_tile[tag0_wr] <= stage_tile_r; tag0_wr <= tag0_wr+1'b1; stage_pending0_r <= 0; end
            if (slice1_accept) begin tag1_first[tag1_wr] <= stage_first_r; tag1_last[tag1_wr] <= stage_last_r; tag1_tile[tag1_wr] <= stage_tile_r; tag1_wr <= tag1_wr+1'b1; stage_pending1_r <= 0; end
            if (slice0_guard_fire) tag0_rd <= tag0_rd+1'b1;
            if (slice1_guard_fire) tag1_rd <= tag1_rd+1'b1;
            case ({slice0_accept,slice0_guard_fire}) 2'b10:tag0_count<=tag0_count+1'b1; 2'b01:tag0_count<=tag0_count-1'b1; default:tag0_count<=tag0_count; endcase
            case ({slice1_accept,slice1_guard_fire}) 2'b10:tag1_count<=tag1_count+1'b1; 2'b01:tag1_count<=tag1_count-1'b1; default:tag1_count<=tag1_count; endcase
            if (staged_done && !in_fire) begin stage_valid_r<=0; stage_pending0_r<=0; stage_pending1_r<=0; end
            if (in_fire) begin
                stage_valid_r<=1; stage_pending0_r<=1; stage_pending1_r<=1;
                stage_first_r<=in_first_group; stage_last_r<=in_last_group; stage_tile_r<=in_tile_index;
                stage_activation0_r<=activation_s9x16x32[0 +: 8*32*9]; stage_activation1_r<=activation_s9x16x32[8*32*9 +: 8*32*9];
                stage_weights0_r<=weights_s4x12x32; stage_weights1_r<=weights_s4x12x32;
                stage_activation_code0_r<=activation_code_u8x16[0 +: 8*8]; stage_activation_code1_r<=activation_code_u8x16[8*8 +: 8*8];
                stage_activation_shift0_r<=activation_shift_u6x16[0 +: 8*6]; stage_activation_shift1_r<=activation_shift_u6x16[8*6 +: 8*6];
                stage_weight_code0_r<=weight_code_u8x12; stage_weight_code1_r<=weight_code_u8x12;
                stage_weight_shift0_r<=weight_shift_u6x12; stage_weight_shift1_r<=weight_shift_u6x12;
                stage_mask0_r<=column_valid_u12; stage_mask1_r<=column_valid_u12; input_tile_count<=input_tile_count+1'b1;
            end
            if (out_fire) output_pass_count<=output_pass_count+1'b1;
            if (slice0_kernel_error||slice1_kernel_error||slice0_accum_error||slice1_accum_error||
                (slice0_valid&&slice1_valid&&slice0_tile!=slice1_tile)) error<=1;
        end
    end
endmodule
