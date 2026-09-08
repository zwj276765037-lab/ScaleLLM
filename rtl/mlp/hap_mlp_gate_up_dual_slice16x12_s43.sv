`timescale 1ns / 1ps

// V5 cohort16 gate/up projection leaf.  One 12-column W4 transaction is
// captured once and physically copied into two 8-row kernel branches.  Their
// S36 guards are joined atomically and terminate in one row-major 192-lane
// S43 accumulator.  A later physical revision may split the accumulator by
// SLR; this functional leaf first freezes exact cohort16 row ordering.
module hap_mlp_gate_up_dual_slice16x12_s43 (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          clear,
    input  wire                          in_valid,
    output wire                          in_ready,
    input  wire                          in_first_group,
    input  wire                          in_last_group,
    input  wire signed [16*32*9-1:0]     activation_s9x16x32,
    input  wire signed [12*32*4-1:0]     weights_s4x12x32,
    input  wire [16*8-1:0]               activation_code_u8x16,
    input  wire [16*6-1:0]               activation_shift_u6x16,
    input  wire [12*8-1:0]               weight_code_u8x12,
    input  wire [12*6-1:0]               weight_shift_u6x12,
    input  wire [11:0]                   column_valid_u12,
    output wire                          out_valid,
    input  wire                          out_ready,
    output wire signed [16*12*24-1:0]    projection_s24x16x12,
    output reg  [31:0]                   input_group_count,
    output reg  [31:0]                   output_pass_count,
    output wire [31:0]                   saturation_count,
    output reg                           error
);

    reg stage_valid_r;
    reg stage_pending0_r;
    reg stage_pending1_r;
    reg stage_first_r;
    reg stage_last_r;
    reg signed [8*32*9-1:0] stage_activation0_r;
    reg signed [8*32*9-1:0] stage_activation1_r;
    (* keep = "true" *) reg signed [12*32*4-1:0] stage_weights0_r;
    (* keep = "true" *) reg signed [12*32*4-1:0] stage_weights1_r;
    reg [8*8-1:0] stage_activation_code0_r;
    reg [8*8-1:0] stage_activation_code1_r;
    reg [8*6-1:0] stage_activation_shift0_r;
    reg [8*6-1:0] stage_activation_shift1_r;
    (* keep = "true" *) reg [12*8-1:0] stage_weight_code0_r;
    (* keep = "true" *) reg [12*8-1:0] stage_weight_code1_r;
    (* keep = "true" *) reg [12*6-1:0] stage_weight_shift0_r;
    (* keep = "true" *) reg [12*6-1:0] stage_weight_shift1_r;
    reg [11:0] stage_mask0_r;
    reg [11:0] stage_mask1_r;

    // First/last tags follow the elastic kernel output, not the currently
    // staged next input.  Each kernel branch has its own tag FIFO because its
    // ready may diverge for a cycle before the atomic guard join.
    reg tag0_first_mem [0:31], tag0_last_mem [0:31];
    reg tag1_first_mem [0:31], tag1_last_mem [0:31];
    reg [4:0] tag0_wr_r, tag0_rd_r, tag1_wr_r, tag1_rd_r;
    reg [5:0] tag0_count_r, tag1_count_r;

    wire slice0_ready, slice1_ready;
    wire slice0_valid, slice1_valid;
    wire signed [8*12*36-1:0] slice0_guard, slice1_guard;
    wire signed [16*12*36-1:0] joined_guard = {slice1_guard, slice0_guard};
    wire accum_ready;
    wire accum_error;
    wire kernel_error0, kernel_error1;
    // The slice valid stays asserted while its pending bit is set.  A branch
    // can therefore consume only on the actual valid/ready handshake.
    // Both identical branches use the same clock and elastic shape.  Accept
    // each staged payload atomically to prevent one branch from replaying a
    // stale stage word while the other advances.
    wire branches_ready = slice0_ready && slice1_ready &&
        tag0_count_r != 32 && tag1_count_r != 32;
    wire branch_issue = stage_valid_r && branches_ready;
    wire slice0_accept = branch_issue;
    wire slice1_accept = branch_issue;
    wire staged_done = slice0_accept;
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;

    // Do not refill the stage in the same cycle its last branch consumes the
    // old payload.  That old V4 shortcut leaves the pending bits asserted
    // against the stale payload for one cycle and duplicates every FIFO-depth
    // window under a deeply pipelined kernel.
    assign in_ready = rst_n && !clear && !stage_valid_r;
    wire guard_fire = slice0_valid && slice1_valid && accum_ready &&
        tag0_count_r != 0 && tag1_count_r != 0;
    wire tag_match = tag0_first_mem[tag0_rd_r] == tag1_first_mem[tag1_rd_r] &&
        tag0_last_mem[tag0_rd_r] == tag1_last_mem[tag1_rd_r];

    (* keep_hierarchy = "yes" *)
    hap_a8w4_slice8x12_group_s36 u_slice0 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(branch_issue),
        .in_ready(slice0_ready),
        .activation_s9x8x32(stage_activation0_r),
        .weights_s4x12x32(stage_weights0_r),
        .activation_code_u8x8(stage_activation_code0_r),
        .activation_shift_u6x8(stage_activation_shift0_r),
        .weight_code_u8x12(stage_weight_code0_r),
        .weight_shift_u6x12(stage_weight_shift0_r),
        .column_valid_u12(stage_mask0_r),
        .out_valid(slice0_valid), .out_ready(accum_ready && slice1_valid && tag0_count_r != 0 && tag1_count_r != 0),
        .guard_s36x8x12(slice0_guard), .input_group_count(),
        .output_group_count(), .error(kernel_error0)
    );

    (* keep_hierarchy = "yes" *)
    hap_a8w4_slice8x12_group_s36 u_slice1 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(branch_issue),
        .in_ready(slice1_ready),
        .activation_s9x8x32(stage_activation1_r),
        .weights_s4x12x32(stage_weights1_r),
        .activation_code_u8x8(stage_activation_code1_r),
        .activation_shift_u6x8(stage_activation_shift1_r),
        .weight_code_u8x12(stage_weight_code1_r),
        .weight_shift_u6x12(stage_weight_shift1_r),
        .column_valid_u12(stage_mask1_r),
        .out_valid(slice1_valid), .out_ready(accum_ready && slice0_valid && tag0_count_r != 0 && tag1_count_r != 0),
        .guard_s36x8x12(slice1_guard), .input_group_count(),
        .output_group_count(), .error(kernel_error1)
    );

    hap_mlp_tile_accum_s36 #(
        .LANES(192), .ACC_W(43), .GROUPS(128),
        .ALLOW_V5_96_LANES(2)
    ) u_accum (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(slice0_valid && slice1_valid && tag0_count_r != 0 && tag1_count_r != 0), .in_ready(accum_ready),
        .in_first_group(tag0_first_mem[tag0_rd_r]),
        .in_last_group(tag0_last_mem[tag0_rd_r]),
        .in_guard_s36(joined_guard), .out_valid(out_valid),
        .out_ready(out_ready), .out_projection_s24(projection_s24x16x12),
        .input_group_count(), .output_tile_count(),
        .saturation_count(saturation_count), .error(accum_error)
    );

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            stage_valid_r <= 1'b0;
            stage_pending0_r <= 1'b0;
            stage_pending1_r <= 1'b0;
            tag0_wr_r <= 0; tag0_rd_r <= 0; tag0_count_r <= 0;
            tag1_wr_r <= 0; tag1_rd_r <= 0; tag1_count_r <= 0;
            input_group_count <= 32'd0;
            output_pass_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (slice0_accept) stage_pending0_r <= 1'b0;
            if (slice1_accept) stage_pending1_r <= 1'b0;
            if (staged_done && !in_fire) begin
                stage_valid_r <= 1'b0;
                stage_pending0_r <= 1'b0;
                stage_pending1_r <= 1'b0;
            end
            if (staged_done) begin
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
                stage_activation0_r <= activation_s9x16x32[0 +: 8*32*9];
                stage_activation1_r <= activation_s9x16x32[8*32*9 +: 8*32*9];
                stage_weights0_r <= weights_s4x12x32;
                stage_weights1_r <= weights_s4x12x32;
                stage_activation_code0_r <= activation_code_u8x16[0 +: 8*8];
                stage_activation_code1_r <= activation_code_u8x16[8*8 +: 8*8];
                stage_activation_shift0_r <= activation_shift_u6x16[0 +: 8*6];
                stage_activation_shift1_r <= activation_shift_u6x16[8*6 +: 8*6];
                stage_weight_code0_r <= weight_code_u8x12;
                stage_weight_code1_r <= weight_code_u8x12;
                stage_weight_shift0_r <= weight_shift_u6x12;
                stage_weight_shift1_r <= weight_shift_u6x12;
                stage_mask0_r <= column_valid_u12;
                stage_mask1_r <= column_valid_u12;
                input_group_count <= input_group_count + 1'b1;
            end
            if (slice0_accept) begin
                tag0_first_mem[tag0_wr_r] <= stage_first_r;
                tag0_last_mem[tag0_wr_r] <= stage_last_r;
                tag0_wr_r <= tag0_wr_r + 1'b1;
            end
            if (slice1_accept) begin
                tag1_first_mem[tag1_wr_r] <= stage_first_r;
                tag1_last_mem[tag1_wr_r] <= stage_last_r;
                tag1_wr_r <= tag1_wr_r + 1'b1;
            end
            if (guard_fire) begin tag0_rd_r <= tag0_rd_r + 1'b1; tag1_rd_r <= tag1_rd_r + 1'b1; end
            case ({slice0_accept,guard_fire}) 2'b10:tag0_count_r<=tag0_count_r+1'b1; 2'b01:tag0_count_r<=tag0_count_r-1'b1; default:tag0_count_r<=tag0_count_r; endcase
            case ({slice1_accept,guard_fire}) 2'b10:tag1_count_r<=tag1_count_r+1'b1; 2'b01:tag1_count_r<=tag1_count_r-1'b1; default:tag1_count_r<=tag1_count_r; endcase
            if (out_fire) output_pass_count <= output_pass_count + 1'b1;
            if (kernel_error0 || kernel_error1 || accum_error ||
                (guard_fire && !tag_match))
                error <= 1'b1;
        end
    end
endmodule
