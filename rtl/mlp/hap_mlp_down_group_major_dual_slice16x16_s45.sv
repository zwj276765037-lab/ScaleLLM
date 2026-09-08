`timescale 1ns / 1ps

// Cohort16 group-major down projection.  A single logical W4 tile is captured
// into two physical copies, one beside each 8x16 slice/accumulator hierarchy.
// Both slices receive each transaction independently through a pending fork;
// their completed S24 output tiles are joined atomically.
module hap_mlp_down_group_major_dual_slice16x16_s45 #(
    parameter integer TILES = 256,
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
    input  wire signed [16*32*4-1:0]     weights_s4x16x32,
    input  wire [16*8-1:0]               activation_code_u8x16,
    input  wire [16*6-1:0]               activation_shift_u6x16,
    input  wire [16*8-1:0]               weight_code_u8x16,
    input  wire [16*6-1:0]               weight_shift_u6x16,
    output wire                          out_valid,
    input  wire                          out_ready,
    output wire [TILE_W-1:0]             out_tile_index,
    output wire signed [16*16*24-1:0]    projection_s24x16x16,
    output reg  [31:0]                   input_tile_count,
    output reg  [31:0]                   output_tile_count,
    output wire [31:0]                   saturation_count,
    output reg                           error
);

    reg stage_valid_r;
    reg stage_pending0_r;
    reg stage_pending1_r;
    reg stage_first_r;
    reg stage_last_r;
    reg [TILE_W-1:0] stage_tile_r;
    reg signed [8*32*9-1:0] stage_activation0_r;
    reg signed [8*32*9-1:0] stage_activation1_r;
    (* keep = "true" *) reg signed [16*32*4-1:0] stage_weights0_r;
    (* keep = "true" *) reg signed [16*32*4-1:0] stage_weights1_r;
    reg [8*8-1:0] stage_activation_code0_r;
    reg [8*8-1:0] stage_activation_code1_r;
    reg [8*6-1:0] stage_activation_shift0_r;
    reg [8*6-1:0] stage_activation_shift1_r;
    (* keep = "true" *) reg [16*8-1:0] stage_weight_code0_r;
    (* keep = "true" *) reg [16*8-1:0] stage_weight_code1_r;
    (* keep = "true" *) reg [16*6-1:0] stage_weight_shift0_r;
    (* keep = "true" *) reg [16*6-1:0] stage_weight_shift1_r;

    wire slice0_in_ready;
    wire slice1_in_ready;
    wire slice0_out_valid;
    wire slice1_out_valid;
    wire slice0_out_ready;
    wire slice1_out_ready;
    wire [TILE_W-1:0] slice0_out_tile;
    wire [TILE_W-1:0] slice1_out_tile;
    wire signed [8*16*24-1:0] slice0_projection;
    wire signed [8*16*24-1:0] slice1_projection;
    wire [31:0] slice0_input_tiles;
    wire [31:0] slice1_input_tiles;
    wire [31:0] slice0_input_groups;
    wire [31:0] slice1_input_groups;
    wire [31:0] slice0_output_tiles;
    wire [31:0] slice1_output_tiles;
    wire [31:0] slice0_saturation;
    wire [31:0] slice1_saturation;
    wire slice0_error;
    wire slice1_error;

    wire slice0_accept = stage_valid_r && stage_pending0_r &&
        slice0_in_ready;
    wire slice1_accept = stage_valid_r && stage_pending1_r &&
        slice1_in_ready;
    wire staged_done = stage_valid_r &&
        (!stage_pending0_r || slice0_in_ready) &&
        (!stage_pending1_r || slice1_in_ready);
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;

    assign in_ready = rst_n && !clear && (!stage_valid_r || staged_done);
    assign out_valid = rst_n && !clear &&
        slice0_out_valid && slice1_out_valid;
    assign slice0_out_ready = out_ready && slice1_out_valid;
    assign slice1_out_ready = out_ready && slice0_out_valid;
    assign out_tile_index = slice0_out_tile;
    assign projection_s24x16x16[0 +: 8*16*24] = slice0_projection;
    assign projection_s24x16x16[8*16*24 +: 8*16*24] =
        slice1_projection;
    assign saturation_count = slice0_saturation + slice1_saturation;

    (* keep_hierarchy = "yes" *)
    hap_mlp_down_group_major_slice8x16_s45 #(
        .TILES(TILES), .GROUPS(GROUPS), .TILE_W(TILE_W)
    ) u_slice0 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(stage_valid_r && stage_pending0_r),
        .in_ready(slice0_in_ready),
        .in_first_group(stage_first_r),
        .in_last_group(stage_last_r),
        .in_tile_index(stage_tile_r),
        .activation_s9x8x32(stage_activation0_r),
        .weights_s4x16x32(stage_weights0_r),
        .activation_code_u8x8(stage_activation_code0_r),
        .activation_shift_u6x8(stage_activation_shift0_r),
        .weight_code_u8x16(stage_weight_code0_r),
        .weight_shift_u6x16(stage_weight_shift0_r),
        .out_valid(slice0_out_valid), .out_ready(slice0_out_ready),
        .out_tile_index(slice0_out_tile),
        .projection_s24x8x16(slice0_projection),
        .input_tile_count(slice0_input_tiles),
        .input_group_count(slice0_input_groups),
        .output_tile_count(slice0_output_tiles),
        .saturation_count(slice0_saturation), .error(slice0_error)
    );

    (* keep_hierarchy = "yes" *)
    hap_mlp_down_group_major_slice8x16_s45 #(
        .TILES(TILES), .GROUPS(GROUPS), .TILE_W(TILE_W)
    ) u_slice1 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(stage_valid_r && stage_pending1_r),
        .in_ready(slice1_in_ready),
        .in_first_group(stage_first_r),
        .in_last_group(stage_last_r),
        .in_tile_index(stage_tile_r),
        .activation_s9x8x32(stage_activation1_r),
        .weights_s4x16x32(stage_weights1_r),
        .activation_code_u8x8(stage_activation_code1_r),
        .activation_shift_u6x8(stage_activation_shift1_r),
        .weight_code_u8x16(stage_weight_code1_r),
        .weight_shift_u6x16(stage_weight_shift1_r),
        .out_valid(slice1_out_valid), .out_ready(slice1_out_ready),
        .out_tile_index(slice1_out_tile),
        .projection_s24x8x16(slice1_projection),
        .input_tile_count(slice1_input_tiles),
        .input_group_count(slice1_input_groups),
        .output_tile_count(slice1_output_tiles),
        .saturation_count(slice1_saturation), .error(slice1_error)
    );

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            stage_valid_r <= 1'b0;
            stage_pending0_r <= 1'b0;
            stage_pending1_r <= 1'b0;
            input_tile_count <= 32'd0;
            output_tile_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (slice0_accept)
                stage_pending0_r <= 1'b0;
            if (slice1_accept)
                stage_pending1_r <= 1'b0;
            if (staged_done && !in_fire) begin
                stage_valid_r <= 1'b0;
                stage_pending0_r <= 1'b0;
                stage_pending1_r <= 1'b0;
            end
            if (in_fire) begin
                stage_valid_r <= 1'b1;
                stage_pending0_r <= 1'b1;
                stage_pending1_r <= 1'b1;
                stage_first_r <= in_first_group;
                stage_last_r <= in_last_group;
                stage_tile_r <= in_tile_index;
                stage_activation0_r <= activation_s9x16x32[0 +: 8*32*9];
                stage_activation1_r <=
                    activation_s9x16x32[8*32*9 +: 8*32*9];
                stage_weights0_r <= weights_s4x16x32;
                stage_weights1_r <= weights_s4x16x32;
                stage_activation_code0_r <= activation_code_u8x16[0 +: 8*8];
                stage_activation_code1_r <= activation_code_u8x16[8*8 +: 8*8];
                stage_activation_shift0_r <= activation_shift_u6x16[0 +: 8*6];
                stage_activation_shift1_r <= activation_shift_u6x16[8*6 +: 8*6];
                stage_weight_code0_r <= weight_code_u8x16;
                stage_weight_code1_r <= weight_code_u8x16;
                stage_weight_shift0_r <= weight_shift_u6x16;
                stage_weight_shift1_r <= weight_shift_u6x16;
                input_tile_count <= input_tile_count + 32'd1;
            end
            if (out_fire)
                output_tile_count <= output_tile_count + 32'd1;
            if (slice0_error || slice1_error ||
                (slice0_out_valid && slice1_out_valid &&
                 slice0_out_tile != slice1_out_tile))
                error <= 1'b1;
        end
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !clear && !stage_valid_r &&
            slice0_input_tiles != slice1_input_tiles)
            $error("group-major dual down input count divergence");
        if (rst_n && !clear && slice0_out_valid && slice1_out_valid &&
            slice0_out_tile != slice1_out_tile)
            $error("group-major dual down output tile divergence");
    end
`endif

endmodule
