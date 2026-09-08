`timescale 1ns / 1ps

// Cohort16 V5 group kernel built from exactly two physical 8x12 slices.
// The W4 payload and metadata are captured into one local copy per slice;
// completed row halves are joined atomically.  Full-pass steady-state II=1.
module hap_a8w4_dual_slice16x12_group_s36 (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          clear,
    input  wire                          in_valid,
    output wire                          in_ready,
    input  wire signed [16*32*9-1:0]     activation_s9x16x32,
    input  wire signed [12*32*4-1:0]     weights_s4x12x32,
    input  wire [16*8-1:0]               activation_code_u8x16,
    input  wire [16*6-1:0]               activation_shift_u6x16,
    input  wire [12*8-1:0]               weight_code_u8x12,
    input  wire [12*6-1:0]               weight_shift_u6x12,
    input  wire [11:0]                   column_valid_u12,
    output wire                          out_valid,
    input  wire                          out_ready,
    output wire signed [16*12*36-1:0]    guard_s36x16x12,
    output reg  [31:0]                   input_group_count,
    output reg  [31:0]                   output_group_count,
    output reg                           error
);

    reg stage_valid_r;
    reg stage_pending0_r;
    reg stage_pending1_r;
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
    reg [11:0] stage_column_valid_r;

    wire slice0_in_ready;
    wire slice1_in_ready;
    wire slice0_out_valid;
    wire slice1_out_valid;
    wire slice0_out_ready;
    wire slice1_out_ready;
    wire signed [8*12*36-1:0] slice0_guard;
    wire signed [8*12*36-1:0] slice1_guard;
    wire [31:0] slice0_input_count;
    wire [31:0] slice1_input_count;
    wire [31:0] slice0_output_count;
    wire [31:0] slice1_output_count;
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
    assign guard_s36x16x12[0 +: 8*12*36] = slice0_guard;
    assign guard_s36x16x12[8*12*36 +: 8*12*36] = slice1_guard;

    (* keep_hierarchy = "yes" *)
    hap_a8w4_slice8x12_group_s36 u_slice0 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(stage_valid_r && stage_pending0_r),
        .in_ready(slice0_in_ready),
        .activation_s9x8x32(stage_activation0_r),
        .weights_s4x12x32(stage_weights0_r),
        .activation_code_u8x8(stage_activation_code0_r),
        .activation_shift_u6x8(stage_activation_shift0_r),
        .weight_code_u8x12(stage_weight_code0_r),
        .weight_shift_u6x12(stage_weight_shift0_r),
        .column_valid_u12(stage_column_valid_r),
        .out_valid(slice0_out_valid), .out_ready(slice0_out_ready),
        .guard_s36x8x12(slice0_guard),
        .input_group_count(slice0_input_count),
        .output_group_count(slice0_output_count), .error(slice0_error)
    );

    (* keep_hierarchy = "yes" *)
    hap_a8w4_slice8x12_group_s36 u_slice1 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(stage_valid_r && stage_pending1_r),
        .in_ready(slice1_in_ready),
        .activation_s9x8x32(stage_activation1_r),
        .weights_s4x12x32(stage_weights1_r),
        .activation_code_u8x8(stage_activation_code1_r),
        .activation_shift_u6x8(stage_activation_shift1_r),
        .weight_code_u8x12(stage_weight_code1_r),
        .weight_shift_u6x12(stage_weight_shift1_r),
        .column_valid_u12(stage_column_valid_r),
        .out_valid(slice1_out_valid), .out_ready(slice1_out_ready),
        .guard_s36x8x12(slice1_guard),
        .input_group_count(slice1_input_count),
        .output_group_count(slice1_output_count), .error(slice1_error)
    );

    always @(posedge clk) begin
        if (!rst_n) begin
            stage_valid_r <= 1'b0;
            stage_pending0_r <= 1'b0;
            stage_pending1_r <= 1'b0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            stage_valid_r <= 1'b0;
            stage_pending0_r <= 1'b0;
            stage_pending1_r <= 1'b0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
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
                stage_column_valid_r <= column_valid_u12;
                input_group_count <= input_group_count + 32'd1;
            end
            if (out_fire)
                output_group_count <= output_group_count + 32'd1;
            if (slice0_error || slice1_error)
                error <= 1'b1;
        end
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !clear &&
            (slice0_input_count > input_group_count ||
             slice1_input_count > input_group_count))
            $error("dual 16x12 slice input count exceeded accepted groups");
        if (rst_n && !clear &&
            (slice0_output_count > slice0_input_count ||
             slice1_output_count > slice1_input_count))
            $error("dual 16x12 slice output count exceeded slice input");
    end
`endif

endmodule

