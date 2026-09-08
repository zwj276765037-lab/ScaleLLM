`timescale 1ns / 1ps

// V5 cohort16 gate/up projection candidate with physical accumulator closure.
//
// One logical input transaction is captured once and independently delivered
// to two 8-row branches.  Each branch closes its 3456-bit S36 kernel boundary
// into a local 96-lane S43 accumulator.  The wrapper joins only the two
// completed 2304-bit S24 halves, so no 6912-bit S36 bus is required between
// the two physical branch hierarchies.
//
// This is an independent V5 candidate.  It does not replace the V4 production
// wrapper or hap_mlp_gate_up_dual_slice16x12_s43.
module hap_mlp_gate_up_dual_local_accum16x12_s43 (
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

    // The pending fork keeps one stable physical copy beside each branch.
    // A branch clears only its own pending bit on its actual ready/valid
    // handshake.  When the final old pending branch accepts, the stage may
    // capture the next logical transaction at the same edge (steady II=1).
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

    wire branch0_in_ready;
    wire branch1_in_ready;
    wire branch0_out_valid;
    wire branch1_out_valid;
    wire branch0_out_ready;
    wire branch1_out_ready;
    wire signed [8*12*24-1:0] branch0_projection_s24;
    wire signed [8*12*24-1:0] branch1_projection_s24;
    wire [31:0] branch0_input_group_count;
    wire [31:0] branch1_input_group_count;
    wire [31:0] branch0_output_pass_count;
    wire [31:0] branch1_output_pass_count;
    wire [31:0] branch0_saturation_count;
    wire [31:0] branch1_saturation_count;
    wire branch0_error;
    wire branch1_error;

    wire branch0_accept = stage_valid_r && stage_pending0_r &&
        branch0_in_ready;
    wire branch1_accept = stage_valid_r && stage_pending1_r &&
        branch1_in_ready;
    wire staged_done = stage_valid_r &&
        (!stage_pending0_r || branch0_in_ready) &&
        (!stage_pending1_r || branch1_in_ready);
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;

    // Empty-stage capture and old-stage pop/new-stage push are both legal.
    assign in_ready = rst_n && !clear &&
        (!stage_valid_r || staged_done);

    // The two local accumulators may finish on different cycles.  Join their
    // completed S24 payloads atomically and hold both stable under backpressure.
    assign out_valid = rst_n && !clear &&
        branch0_out_valid && branch1_out_valid;
    assign branch0_out_ready = out_ready && branch1_out_valid;
    assign branch1_out_ready = out_ready && branch0_out_valid;
    assign projection_s24x16x12[0 +: 8*12*24] =
        branch0_projection_s24;
    assign projection_s24x16x12[8*12*24 +: 8*12*24] =
        branch1_projection_s24;
    assign saturation_count = branch0_saturation_count +
        branch1_saturation_count;

    (* keep_hierarchy = "yes" *)
    hap_mlp_gate_up_local_slice8x12_s43 u_branch0 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(stage_valid_r && stage_pending0_r),
        .in_ready(branch0_in_ready),
        .in_first_group(stage_first_r),
        .in_last_group(stage_last_r),
        .activation_s9x8x32(stage_activation0_r),
        .weights_s4x12x32(stage_weights0_r),
        .activation_code_u8x8(stage_activation_code0_r),
        .activation_shift_u6x8(stage_activation_shift0_r),
        .weight_code_u8x12(stage_weight_code0_r),
        .weight_shift_u6x12(stage_weight_shift0_r),
        .column_valid_u12(stage_mask0_r),
        .out_valid(branch0_out_valid),
        .out_ready(branch0_out_ready),
        .projection_s24x8x12(branch0_projection_s24),
        .input_group_count(branch0_input_group_count),
        .output_pass_count(branch0_output_pass_count),
        .saturation_count(branch0_saturation_count),
        .error(branch0_error)
    );

    (* keep_hierarchy = "yes" *)
    hap_mlp_gate_up_local_slice8x12_s43 u_branch1 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(stage_valid_r && stage_pending1_r),
        .in_ready(branch1_in_ready),
        .in_first_group(stage_first_r),
        .in_last_group(stage_last_r),
        .activation_s9x8x32(stage_activation1_r),
        .weights_s4x12x32(stage_weights1_r),
        .activation_code_u8x8(stage_activation_code1_r),
        .activation_shift_u6x8(stage_activation_shift1_r),
        .weight_code_u8x12(stage_weight_code1_r),
        .weight_shift_u6x12(stage_weight_shift1_r),
        .column_valid_u12(stage_mask1_r),
        .out_valid(branch1_out_valid),
        .out_ready(branch1_out_ready),
        .projection_s24x8x12(branch1_projection_s24),
        .input_group_count(branch1_input_group_count),
        .output_pass_count(branch1_output_pass_count),
        .saturation_count(branch1_saturation_count),
        .error(branch1_error)
    );

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            stage_valid_r <= 1'b0;
            stage_pending0_r <= 1'b0;
            stage_pending1_r <= 1'b0;
            input_group_count <= 32'd0;
            output_pass_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (branch0_accept)
                stage_pending0_r <= 1'b0;
            if (branch1_accept)
                stage_pending1_r <= 1'b0;

            if (staged_done && !in_fire) begin
                stage_valid_r <= 1'b0;
                stage_pending0_r <= 1'b0;
                stage_pending1_r <= 1'b0;
            end

            // This assignment intentionally follows staged_done handling.
            // On simultaneous pop/push it installs the new payload and both
            // new pending bits for delivery beginning in the next cycle.
            if (in_fire) begin
                stage_valid_r <= 1'b1;
                stage_pending0_r <= 1'b1;
                stage_pending1_r <= 1'b1;
                stage_first_r <= in_first_group;
                stage_last_r <= in_last_group;
                stage_activation0_r <=
                    activation_s9x16x32[0 +: 8*32*9];
                stage_activation1_r <=
                    activation_s9x16x32[8*32*9 +: 8*32*9];
                stage_weights0_r <= weights_s4x12x32;
                stage_weights1_r <= weights_s4x12x32;
                stage_activation_code0_r <=
                    activation_code_u8x16[0 +: 8*8];
                stage_activation_code1_r <=
                    activation_code_u8x16[8*8 +: 8*8];
                stage_activation_shift0_r <=
                    activation_shift_u6x16[0 +: 8*6];
                stage_activation_shift1_r <=
                    activation_shift_u6x16[8*6 +: 8*6];
                stage_weight_code0_r <= weight_code_u8x12;
                stage_weight_code1_r <= weight_code_u8x12;
                stage_weight_shift0_r <= weight_shift_u6x12;
                stage_weight_shift1_r <= weight_shift_u6x12;
                stage_mask0_r <= column_valid_u12;
                stage_mask1_r <= column_valid_u12;
                input_group_count <= input_group_count + 32'd1;
            end

            if (out_fire)
                output_pass_count <= output_pass_count + 32'd1;
            if (branch0_error || branch1_error)
                error <= 1'b1;
        end
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !clear && !stage_valid_r &&
            (branch0_input_group_count != branch1_input_group_count))
            $error("V5 gate local branches diverged while fork idle");
        if (rst_n && !clear &&
            (branch0_output_pass_count != branch1_output_pass_count) &&
            !(branch0_out_valid ^ branch1_out_valid))
            $error("V5 gate local branch output counts diverged");
    end
`endif

endmodule


// One physical V5 gate/up branch.  The S36 guard never leaves this hierarchy:
// the local kernel feeds one local 96-lane S43 accumulator, and only the
// completed S24 pass is exported.
module hap_mlp_gate_up_local_slice8x12_s43 (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire                         in_first_group,
    input  wire                         in_last_group,
    input  wire signed [8*32*9-1:0]     activation_s9x8x32,
    input  wire signed [12*32*4-1:0]    weights_s4x12x32,
    input  wire [8*8-1:0]               activation_code_u8x8,
    input  wire [8*6-1:0]               activation_shift_u6x8,
    input  wire [12*8-1:0]              weight_code_u8x12,
    input  wire [12*6-1:0]              weight_shift_u6x12,
    input  wire [11:0]                  column_valid_u12,
    output wire                         out_valid,
    input  wire                         out_ready,
    output wire signed [8*12*24-1:0]    projection_s24x8x12,
    output wire [31:0]                  input_group_count,
    output wire [31:0]                  output_pass_count,
    output wire [31:0]                  saturation_count,
    output wire                         error
);

    localparam integer LANES = 8*12;

    wire kernel_in_ready;
    wire kernel_out_valid;
    wire accum_in_ready;
    wire signed [LANES*36-1:0] guard_s36x8x12;
    wire [31:0] kernel_input_count;
    wire [31:0] kernel_output_count;
    wire kernel_error;
    wire accum_error;

    // First/last tags follow actual kernel acceptance.  The independent tag
    // FIFO is essential because the two wrapper branches are allowed to see
    // different ready values for a cycle.
    reg tag_first_mem [0:31];
    reg tag_last_mem [0:31];
    reg [4:0] tag_wr_ptr_r;
    reg [4:0] tag_rd_ptr_r;
    reg [5:0] tag_count_r;
    wire tag_full = tag_count_r == 32;
    wire tag_empty = tag_count_r == 0;
    wire kernel_in_fire = in_valid && in_ready;
    wire kernel_out_fire = kernel_out_valid && accum_in_ready &&
        !tag_empty;

    assign in_ready = rst_n && !clear && !tag_full && kernel_in_ready;

    (* keep_hierarchy = "yes" *)
    hap_a8w4_slice8x12_group_s36 u_kernel (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid && !tag_full),
        .in_ready(kernel_in_ready),
        .activation_s9x8x32(activation_s9x8x32),
        .weights_s4x12x32(weights_s4x12x32),
        .activation_code_u8x8(activation_code_u8x8),
        .activation_shift_u6x8(activation_shift_u6x8),
        .weight_code_u8x12(weight_code_u8x12),
        .weight_shift_u6x12(weight_shift_u6x12),
        .column_valid_u12(column_valid_u12),
        .out_valid(kernel_out_valid),
        .out_ready(accum_in_ready && !tag_empty),
        .guard_s36x8x12(guard_s36x8x12),
        .input_group_count(kernel_input_count),
        .output_group_count(kernel_output_count),
        .error(kernel_error)
    );

    (* keep_hierarchy = "yes" *)
    hap_mlp_tile_accum_s36 #(
        .LANES(LANES), .ACC_W(43), .GROUPS(128),
        .ALLOW_V5_96_LANES(1)
    ) u_accum (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(kernel_out_valid && !tag_empty),
        .in_ready(accum_in_ready),
        .in_first_group(tag_first_mem[tag_rd_ptr_r]),
        .in_last_group(tag_last_mem[tag_rd_ptr_r]),
        .in_guard_s36(guard_s36x8x12),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_projection_s24(projection_s24x8x12),
        .input_group_count(input_group_count),
        .output_tile_count(output_pass_count),
        .saturation_count(saturation_count),
        .error(accum_error)
    );

    assign error = kernel_error || accum_error;

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            tag_wr_ptr_r <= '0;
            tag_rd_ptr_r <= '0;
            tag_count_r <= '0;
        end else begin
            if (kernel_in_fire) begin
                tag_first_mem[tag_wr_ptr_r] <= in_first_group;
                tag_last_mem[tag_wr_ptr_r] <= in_last_group;
                tag_wr_ptr_r <= tag_wr_ptr_r + 1'b1;
            end
            if (kernel_out_fire)
                tag_rd_ptr_r <= tag_rd_ptr_r + 1'b1;
            case ({kernel_in_fire, kernel_out_fire})
                2'b10: tag_count_r <= tag_count_r + 1'b1;
                2'b01: tag_count_r <= tag_count_r - 1'b1;
                default: tag_count_r <= tag_count_r;
            endcase
        end
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !clear && kernel_out_valid && tag_empty)
            $error("V5 gate local kernel produced a guard without a tag");
        if (rst_n && !clear &&
            kernel_output_count > kernel_input_count)
            $error("V5 gate local kernel output count exceeded input count");
    end
`endif

endmodule
