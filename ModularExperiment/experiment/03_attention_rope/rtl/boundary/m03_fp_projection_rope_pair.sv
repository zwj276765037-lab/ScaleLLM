`timescale 1ns / 1ps

module m03_delay_bus #(
    parameter integer WIDTH = 1,
    parameter integer DEPTH = 1
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    input  wire [WIDTH-1:0]     in_data,
    output wire                 out_valid,
    output wire [WIDTH-1:0]     out_data
);
    reg [DEPTH-1:0] valid_r;
    reg [WIDTH-1:0] data_r [0:DEPTH-1];
    integer index;

    assign out_valid = valid_r[DEPTH-1];
    assign out_data = data_r[DEPTH-1];

    always @(posedge clk) begin
        if (!rst_n || clear)
            valid_r <= '0;
        else begin
            valid_r[0] <= in_valid;
            data_r[0] <= in_data;
            for (index = 1; index < DEPTH; index = index + 1) begin
                valid_r[index] <= valid_r[index-1];
                data_r[index] <= data_r[index-1];
            end
        end
    end

    initial begin
        if (WIDTH <= 0 || DEPTH <= 0)
            $error("m03_delay_bus requires positive WIDTH and DEPTH");
    end
endmodule


// Two native-FP scale-application lanes.  Both variants emit FP32 group
// contributions; FP16 performs S21->FP32->FP16, two half multiplies, and a
// final widen exactly as frozen in the workload manifest.
module m03_fp_scale_pair #(
    parameter integer FP_W = 16
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    input  wire signed [20:0]    in_corr0_s21,
    input  wire signed [20:0]    in_corr1_s21,
    input  wire [FP_W-1:0]       in_act_scale_fp,
    input  wire [FP_W-1:0]       in_weight0_scale_fp,
    input  wire [FP_W-1:0]       in_weight1_scale_fp,
    output wire                  out_valid,
    output wire [31:0]           out0_fp32,
    output wire [31:0]           out1_fp32,
    output wire                  error
);
    localparam integer INT_LAT = 6;
    wire int0_valid;
    wire int1_valid;
    wire meta_int_valid;
    wire [31:0] int0_fp32;
    wire [31:0] int1_fp32;
    wire [3*FP_W-1:0] meta_int;

    m03_int21_to_fp32 u_int0 (
        .aclk(clk), .s_axis_a_tvalid(in_valid),
        .s_axis_a_tdata({{3{in_corr0_s21[20]}},in_corr0_s21}),
        .m_axis_result_tvalid(int0_valid),
        .m_axis_result_tdata(int0_fp32));
    m03_int21_to_fp32 u_int1 (
        .aclk(clk), .s_axis_a_tvalid(in_valid),
        .s_axis_a_tdata({{3{in_corr1_s21[20]}},in_corr1_s21}),
        .m_axis_result_tvalid(int1_valid),
        .m_axis_result_tdata(int1_fp32));
    m03_delay_bus #(.WIDTH(3*FP_W), .DEPTH(INT_LAT)) u_int_meta (
        .clk(clk), .rst_n(rst_n), .clear(clear), .in_valid(in_valid),
        .in_data({in_weight1_scale_fp,in_weight0_scale_fp,
                  in_act_scale_fp}),
        .out_valid(meta_int_valid), .out_data(meta_int));

    generate
        if (FP_W == 32) begin : g_fp32
            localparam integer MUL_LAT = 8;
            wire mul0a_valid;
            wire mul1a_valid;
            wire weight_meta_valid;
            wire [31:0] mul0a_fp32;
            wire [31:0] mul1a_fp32;
            wire [63:0] weight_meta;
            wire mul0b_valid;
            wire mul1b_valid;

            m03_fp32_mul u_mul0a (
                .aclk(clk), .s_axis_a_tvalid(int0_valid),
                .s_axis_a_tdata(int0_fp32),
                .s_axis_b_tvalid(meta_int_valid),
                .s_axis_b_tdata(meta_int[0 +: 32]),
                .m_axis_result_tvalid(mul0a_valid),
                .m_axis_result_tdata(mul0a_fp32));
            m03_fp32_mul u_mul1a (
                .aclk(clk), .s_axis_a_tvalid(int1_valid),
                .s_axis_a_tdata(int1_fp32),
                .s_axis_b_tvalid(meta_int_valid),
                .s_axis_b_tdata(meta_int[0 +: 32]),
                .m_axis_result_tvalid(mul1a_valid),
                .m_axis_result_tdata(mul1a_fp32));
            m03_delay_bus #(.WIDTH(64), .DEPTH(MUL_LAT)) u_weight_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(meta_int_valid),
                .in_data({meta_int[64 +: 32],meta_int[32 +: 32]}),
                .out_valid(weight_meta_valid), .out_data(weight_meta));
            m03_fp32_mul u_mul0b (
                .aclk(clk), .s_axis_a_tvalid(mul0a_valid),
                .s_axis_a_tdata(mul0a_fp32),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[0 +: 32]),
                .m_axis_result_tvalid(mul0b_valid),
                .m_axis_result_tdata(out0_fp32));
            m03_fp32_mul u_mul1b (
                .aclk(clk), .s_axis_a_tvalid(mul1a_valid),
                .s_axis_a_tdata(mul1a_fp32),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[32 +: 32]),
                .m_axis_result_tvalid(mul1b_valid),
                .m_axis_result_tdata(out1_fp32));

            assign out_valid = mul0b_valid && mul1b_valid;
            assign error = (int0_valid != int1_valid) ||
                (int0_valid != meta_int_valid) ||
                (mul0a_valid != mul1a_valid) ||
                (mul0a_valid != weight_meta_valid) ||
                (mul0b_valid != mul1b_valid);
        end else begin : g_fp16
            localparam integer NARROW_LAT = 3;
            localparam integer MUL_LAT = 6;
            wire narrow0_valid;
            wire narrow1_valid;
            wire narrow_meta_valid;
            wire [15:0] narrow0_fp16;
            wire [15:0] narrow1_fp16;
            wire [47:0] narrow_meta;
            wire mul0a_valid;
            wire mul1a_valid;
            wire weight_meta_valid;
            wire [15:0] mul0a_fp16;
            wire [15:0] mul1a_fp16;
            wire [31:0] weight_meta;
            wire mul0b_valid;
            wire mul1b_valid;
            wire [15:0] mul0b_fp16;
            wire [15:0] mul1b_fp16;
            wire widen0_valid;
            wire widen1_valid;

            m03_fp32_to_fp16 u_narrow0 (
                .aclk(clk), .s_axis_a_tvalid(int0_valid),
                .s_axis_a_tdata(int0_fp32),
                .m_axis_result_tvalid(narrow0_valid),
                .m_axis_result_tdata(narrow0_fp16));
            m03_fp32_to_fp16 u_narrow1 (
                .aclk(clk), .s_axis_a_tvalid(int1_valid),
                .s_axis_a_tdata(int1_fp32),
                .m_axis_result_tvalid(narrow1_valid),
                .m_axis_result_tdata(narrow1_fp16));
            m03_delay_bus #(.WIDTH(48), .DEPTH(NARROW_LAT)) u_narrow_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(meta_int_valid), .in_data(meta_int),
                .out_valid(narrow_meta_valid), .out_data(narrow_meta));
            m03_fp16_mul u_mul0a (
                .aclk(clk), .s_axis_a_tvalid(narrow0_valid),
                .s_axis_a_tdata(narrow0_fp16),
                .s_axis_b_tvalid(narrow_meta_valid),
                .s_axis_b_tdata(narrow_meta[0 +: 16]),
                .m_axis_result_tvalid(mul0a_valid),
                .m_axis_result_tdata(mul0a_fp16));
            m03_fp16_mul u_mul1a (
                .aclk(clk), .s_axis_a_tvalid(narrow1_valid),
                .s_axis_a_tdata(narrow1_fp16),
                .s_axis_b_tvalid(narrow_meta_valid),
                .s_axis_b_tdata(narrow_meta[0 +: 16]),
                .m_axis_result_tvalid(mul1a_valid),
                .m_axis_result_tdata(mul1a_fp16));
            m03_delay_bus #(.WIDTH(32), .DEPTH(MUL_LAT)) u_weight_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(narrow_meta_valid),
                .in_data({narrow_meta[32 +: 16],narrow_meta[16 +: 16]}),
                .out_valid(weight_meta_valid), .out_data(weight_meta));
            m03_fp16_mul u_mul0b (
                .aclk(clk), .s_axis_a_tvalid(mul0a_valid),
                .s_axis_a_tdata(mul0a_fp16),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[0 +: 16]),
                .m_axis_result_tvalid(mul0b_valid),
                .m_axis_result_tdata(mul0b_fp16));
            m03_fp16_mul u_mul1b (
                .aclk(clk), .s_axis_a_tvalid(mul1a_valid),
                .s_axis_a_tdata(mul1a_fp16),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[16 +: 16]),
                .m_axis_result_tvalid(mul1b_valid),
                .m_axis_result_tdata(mul1b_fp16));
            m03_fp16_to_fp32 u_widen0 (
                .aclk(clk), .s_axis_a_tvalid(mul0b_valid),
                .s_axis_a_tdata(mul0b_fp16),
                .m_axis_result_tvalid(widen0_valid),
                .m_axis_result_tdata(out0_fp32));
            m03_fp16_to_fp32 u_widen1 (
                .aclk(clk), .s_axis_a_tvalid(mul1b_valid),
                .s_axis_a_tdata(mul1b_fp16),
                .m_axis_result_tvalid(widen1_valid),
                .m_axis_result_tdata(out1_fp32));

            assign out_valid = widen0_valid && widen1_valid;
            assign error = (int0_valid != int1_valid) ||
                (int0_valid != meta_int_valid) ||
                (narrow0_valid != narrow1_valid) ||
                (narrow0_valid != narrow_meta_valid) ||
                (mul0a_valid != mul1a_valid) ||
                (mul0a_valid != weight_meta_valid) ||
                (mul0b_valid != mul1b_valid) ||
                (widen0_valid != widen1_valid);
        end
    endgenerate

    initial begin
        if (FP_W != 16 && FP_W != 32)
            $error("m03_fp_scale_pair FP_W must be 16 or 32");
    end
endmodule


// Six interleaved FP32 states make the 11-cycle feedback adder compatible
// with one contribution every two clocks.  After the last group, the same
// two adders perform the frozen five-operation balanced reduction.
module m03_fp_projection_accum6 (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 start_pair,
    input  wire                 in_valid,
    input  wire                 in_last,
    input  wire [2:0]           in_bank,
    input  wire [31:0]          in0_fp32,
    input  wire [31:0]          in1_fp32,
    output reg                  out_valid,
    output reg  [31:0]          out0_fp32,
    output reg  [31:0]          out1_fp32,
    output reg                  error
);
    localparam integer ADD_LAT = 11;
    reg [31:0] state0_r [0:5];
    reg [31:0] state1_r [0:5];
    reg reduction_active_r;
    reg reduction_waiting_r;
    reg [2:0] reduction_step_r;
    reg [31:0] reduce0_01_r, reduce0_23_r, reduce0_45_r, reduce0_0123_r;
    reg [31:0] reduce1_01_r, reduce1_23_r, reduce1_45_r, reduce1_0123_r;
    wire reduce_issue = reduction_active_r && !reduction_waiting_r;
    wire add_issue = in_valid || reduce_issue;
    reg [31:0] reduce_a0, reduce_b0, reduce_a1, reduce_b1;

    always @* begin
        reduce_a0 = 32'd0;
        reduce_b0 = 32'd0;
        reduce_a1 = 32'd0;
        reduce_b1 = 32'd0;
        case (reduction_step_r)
            3'd0: begin
                reduce_a0 = state0_r[0]; reduce_b0 = state0_r[1];
                reduce_a1 = state1_r[0]; reduce_b1 = state1_r[1];
            end
            3'd1: begin
                reduce_a0 = state0_r[2]; reduce_b0 = state0_r[3];
                reduce_a1 = state1_r[2]; reduce_b1 = state1_r[3];
            end
            3'd2: begin
                reduce_a0 = state0_r[4]; reduce_b0 = state0_r[5];
                reduce_a1 = state1_r[4]; reduce_b1 = state1_r[5];
            end
            3'd3: begin
                reduce_a0 = reduce0_01_r; reduce_b0 = reduce0_23_r;
                reduce_a1 = reduce1_01_r; reduce_b1 = reduce1_23_r;
            end
            default: begin
                reduce_a0 = reduce0_0123_r; reduce_b0 = reduce0_45_r;
                reduce_a1 = reduce1_0123_r; reduce_b1 = reduce1_45_r;
            end
        endcase
    end

    wire [31:0] add_a0 = reduce_issue ? reduce_a0 : state0_r[in_bank];
    wire [31:0] add_b0 = reduce_issue ? reduce_b0 : in0_fp32;
    wire [31:0] add_a1 = reduce_issue ? reduce_a1 : state1_r[in_bank];
    wire [31:0] add_b1 = reduce_issue ? reduce_b1 : in1_fp32;
    wire add0_valid;
    wire add1_valid;
    wire [31:0] add0_result;
    wire [31:0] add1_result;
    wire tag_valid;
    wire [4:0] add_tag;
    wire [4:0] issue_tag = reduce_issue ?
        {1'b1,1'b0,reduction_step_r} : {1'b0,in_last,in_bank};

    m03_fp32_add u_add0 (
        .aclk(clk), .s_axis_a_tvalid(add_issue), .s_axis_a_tdata(add_a0),
        .s_axis_b_tvalid(add_issue), .s_axis_b_tdata(add_b0),
        .m_axis_result_tvalid(add0_valid),
        .m_axis_result_tdata(add0_result));
    m03_fp32_add u_add1 (
        .aclk(clk), .s_axis_a_tvalid(add_issue), .s_axis_a_tdata(add_a1),
        .s_axis_b_tvalid(add_issue), .s_axis_b_tdata(add_b1),
        .m_axis_result_tvalid(add1_valid),
        .m_axis_result_tdata(add1_result));
    m03_delay_bus #(.WIDTH(5), .DEPTH(ADD_LAT)) u_add_tag (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(add_issue), .in_data(issue_tag),
        .out_valid(tag_valid), .out_data(add_tag));

    integer bank;
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            for (bank = 0; bank < 6; bank = bank + 1) begin
                state0_r[bank] <= 32'd0;
                state1_r[bank] <= 32'd0;
            end
            reduction_active_r <= 1'b0;
            reduction_waiting_r <= 1'b0;
            reduction_step_r <= 3'd0;
            out_valid <= 1'b0;
            out0_fp32 <= 32'd0;
            out1_fp32 <= 32'd0;
            error <= 1'b0;
        end else begin
            out_valid <= 1'b0;
            if (start_pair) begin
                for (bank = 0; bank < 6; bank = bank + 1) begin
                    state0_r[bank] <= 32'd0;
                    state1_r[bank] <= 32'd0;
                end
            end
            if (reduce_issue)
                reduction_waiting_r <= 1'b1;

            if (tag_valid && add0_valid && add1_valid) begin
                if (!add_tag[4]) begin
                    if (add_tag[2:0] < 6) begin
                        state0_r[add_tag[2:0]] <= add0_result;
                        state1_r[add_tag[2:0]] <= add1_result;
                    end else
                        error <= 1'b1;
                    if (add_tag[3]) begin
                        reduction_active_r <= 1'b1;
                        reduction_waiting_r <= 1'b0;
                        reduction_step_r <= 3'd0;
                    end
                end else begin
                    reduction_waiting_r <= 1'b0;
                    case (add_tag[2:0])
                        3'd0: begin
                            reduce0_01_r <= add0_result;
                            reduce1_01_r <= add1_result;
                            reduction_step_r <= 3'd1;
                        end
                        3'd1: begin
                            reduce0_23_r <= add0_result;
                            reduce1_23_r <= add1_result;
                            reduction_step_r <= 3'd2;
                        end
                        3'd2: begin
                            reduce0_45_r <= add0_result;
                            reduce1_45_r <= add1_result;
                            reduction_step_r <= 3'd3;
                        end
                        3'd3: begin
                            reduce0_0123_r <= add0_result;
                            reduce1_0123_r <= add1_result;
                            reduction_step_r <= 3'd4;
                        end
                        3'd4: begin
                            out0_fp32 <= add0_result;
                            out1_fp32 <= add1_result;
                            out_valid <= 1'b1;
                            reduction_active_r <= 1'b0;
                            reduction_step_r <= 3'd0;
                        end
                        default: error <= 1'b1;
                    endcase
                end
            end

            if ((tag_valid != add0_valid) || (add0_valid != add1_valid) ||
                (in_valid && reduction_active_r) ||
                (in_valid && in_bank >= 6) ||
                (start_pair && reduction_active_r))
                error <= 1'b1;
        end
    end
endmodule


module m03_s18_coeff_pair_to_fp #(
    parameter integer FP_W = 16
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    input  wire signed [17:0]   in_cos_s18,
    input  wire signed [17:0]   in_sin_s18,
    output wire                 out_valid,
    output wire [FP_W-1:0]      out_cos_fp,
    output wire [FP_W-1:0]      out_sin_fp,
    output wire                 error
);
    wire cos32_valid;
    wire sin32_valid;
    wire [31:0] cos_fp32;
    wire [31:0] sin_fp32;

    m03_s18q16_to_fp32 u_cos (
        .aclk(clk), .s_axis_a_tvalid(in_valid),
        .s_axis_a_tdata({{6{in_cos_s18[17]}},in_cos_s18}),
        .m_axis_result_tvalid(cos32_valid),
        .m_axis_result_tdata(cos_fp32));
    m03_s18q16_to_fp32 u_sin (
        .aclk(clk), .s_axis_a_tvalid(in_valid),
        .s_axis_a_tdata({{6{in_sin_s18[17]}},in_sin_s18}),
        .m_axis_result_tvalid(sin32_valid),
        .m_axis_result_tdata(sin_fp32));

    generate
        if (FP_W == 32) begin : g_fp32
            assign out_valid = cos32_valid && sin32_valid;
            assign out_cos_fp = cos_fp32;
            assign out_sin_fp = sin_fp32;
            assign error = cos32_valid != sin32_valid;
        end else begin : g_fp16
            wire cos16_valid;
            wire sin16_valid;
            m03_fp32_to_fp16 u_cos_narrow (
                .aclk(clk), .s_axis_a_tvalid(cos32_valid),
                .s_axis_a_tdata(cos_fp32),
                .m_axis_result_tvalid(cos16_valid),
                .m_axis_result_tdata(out_cos_fp));
            m03_fp32_to_fp16 u_sin_narrow (
                .aclk(clk), .s_axis_a_tvalid(sin32_valid),
                .s_axis_a_tdata(sin_fp32),
                .m_axis_result_tvalid(sin16_valid),
                .m_axis_result_tdata(out_sin_fp));
            assign out_valid = cos16_valid && sin16_valid;
            assign error = (cos32_valid != sin32_valid) ||
                (cos16_valid != sin16_valid);
        end
    endgenerate
endmodule


module m03_fp_rope_from_projection #(
    parameter integer FP_W = 16
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 coeff_valid,
    input  wire [FP_W-1:0]      coeff_cos_fp,
    input  wire [FP_W-1:0]      coeff_sin_fp,
    input  wire                 projection_valid,
    input  wire [31:0]          projection0_fp32,
    input  wire [31:0]          projection1_fp32,
    output wire                 out_valid,
    input  wire                 out_ready,
    output wire signed [23:0]   out_y0_s24,
    output wire signed [23:0]   out_y1_s24,
    output wire [31:0]          rope_input_pair_count,
    output wire [31:0]          output_pair_count,
    output wire                 error
);
    reg [FP_W-1:0] coeff_cos_r;
    reg [FP_W-1:0] coeff_sin_r;
    reg coeff_ready_r;
    wire rope_in_ready;
    wire rope_error;

    generate
        if (FP_W == 32) begin : g_fp32
            reg pending_valid_r;
            reg [31:0] pending0_r;
            reg [31:0] pending1_r;
            wire rope_fire = pending_valid_r && rope_in_ready;

            m5_fp32_rope u_rope (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(pending_valid_r), .in_ready(rope_in_ready),
                .in_x0_fp32(pending0_r), .in_x1_fp32(pending1_r),
                .in_cos_fp32(coeff_cos_r), .in_sin_fp32(coeff_sin_r),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_y0_s24(out_y0_s24), .out_y1_s24(out_y1_s24),
                .input_pair_count(rope_input_pair_count),
                .output_pair_count(output_pair_count), .error(rope_error));

            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    pending_valid_r <= 1'b0;
                    pending0_r <= 32'd0;
                    pending1_r <= 32'd0;
                end else if (clear) begin
                    pending_valid_r <= 1'b0;
                    pending0_r <= 32'd0;
                    pending1_r <= 32'd0;
                end else begin
                    if (projection_valid) begin
                        pending_valid_r <= 1'b1;
                        pending0_r <= projection0_fp32;
                        pending1_r <= projection1_fp32;
                    end
                    if (rope_fire)
                        pending_valid_r <= 1'b0;
                end
            end
            assign error = rope_error ||
                (projection_valid && pending_valid_r && !rope_fire) ||
                (projection_valid && !coeff_ready_r);
        end else begin : g_fp16
            wire narrow0_valid;
            wire narrow1_valid;
            wire [15:0] narrow0_fp16;
            wire [15:0] narrow1_fp16;
            reg pending_valid_r;
            reg [15:0] pending0_r;
            reg [15:0] pending1_r;
            wire rope_fire = pending_valid_r && rope_in_ready;

            m03_fp32_to_fp16 u_projection0_narrow (
                .aclk(clk), .s_axis_a_tvalid(projection_valid),
                .s_axis_a_tdata(projection0_fp32),
                .m_axis_result_tvalid(narrow0_valid),
                .m_axis_result_tdata(narrow0_fp16));
            m03_fp32_to_fp16 u_projection1_narrow (
                .aclk(clk), .s_axis_a_tvalid(projection_valid),
                .s_axis_a_tdata(projection1_fp32),
                .m_axis_result_tvalid(narrow1_valid),
                .m_axis_result_tdata(narrow1_fp16));
            m5_fp16_rope u_rope (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(pending_valid_r), .in_ready(rope_in_ready),
                .in_x0_fp16(pending0_r), .in_x1_fp16(pending1_r),
                .in_cos_fp16(coeff_cos_r), .in_sin_fp16(coeff_sin_r),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_y0_s24(out_y0_s24), .out_y1_s24(out_y1_s24),
                .input_pair_count(rope_input_pair_count),
                .output_pair_count(output_pair_count), .error(rope_error));

            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    pending_valid_r <= 1'b0;
                    pending0_r <= 16'd0;
                    pending1_r <= 16'd0;
                end else if (clear) begin
                    pending_valid_r <= 1'b0;
                    pending0_r <= 16'd0;
                    pending1_r <= 16'd0;
                end else begin
                    if (narrow0_valid && narrow1_valid) begin
                        pending_valid_r <= 1'b1;
                        pending0_r <= narrow0_fp16;
                        pending1_r <= narrow1_fp16;
                    end
                    if (rope_fire)
                        pending_valid_r <= 1'b0;
                end
            end
            assign error = rope_error || (narrow0_valid != narrow1_valid) ||
                (narrow0_valid && pending_valid_r && !rope_fire) ||
                (projection_valid && !coeff_ready_r);
        end
    endgenerate

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            coeff_cos_r <= '0;
            coeff_sin_r <= '0;
            coeff_ready_r <= 1'b0;
        end else if (clear) begin
            coeff_cos_r <= '0;
            coeff_sin_r <= '0;
            coeff_ready_r <= 1'b0;
        end else if (coeff_valid) begin
            coeff_cos_r <= coeff_cos_fp;
            coeff_sin_r <= coeff_sin_fp;
            coeff_ready_r <= 1'b1;
        end
    end
endmodule


module m03_fp_projection_rope_pair #(
    parameter integer FP_W = 16,
    parameter integer GROUPS = 128,
    parameter integer SCALE_LAT = FP_W == 16 ? 23 : 22,
    parameter integer GROUP_W = (GROUPS <= 2) ? 1 : $clog2(GROUPS)
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire                  in_first_group,
    input  wire                  in_last_group,
    input  wire signed [20:0]    in_corr0_s21,
    input  wire signed [20:0]    in_corr1_s21,
    input  wire [FP_W-1:0]       in_act_scale_fp,
    input  wire [FP_W-1:0]       in_weight0_scale_fp,
    input  wire [FP_W-1:0]       in_weight1_scale_fp,
    input  wire signed [17:0]    in_cos_s18,
    input  wire signed [17:0]    in_sin_s18,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire signed [23:0]    out_y0_s24,
    output wire signed [23:0]    out_y1_s24,
    output reg  [31:0]           input_group_count,
    output reg  [31:0]           input_pair_count,
    output wire [31:0]           output_pair_count,
    output wire [31:0]           saturation_count,
    output wire                  error
);
    reg accept_cooldown_r;
    reg tail_inflight_r;
    reg [GROUP_W-1:0] expected_group_r;
    reg [2:0] input_bank_r;
    reg local_error_r;
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    assign in_ready = rst_n && !clear && !accept_cooldown_r &&
        !tail_inflight_r;
    assign saturation_count = 32'd0;

    wire scale_valid;
    wire [31:0] contribution0_fp32;
    wire [31:0] contribution1_fp32;
    wire scale_error;
    wire scale_tag_valid;
    wire [3:0] scale_tag;
    wire [2:0] input_issue_bank = in_first_group ? 3'd0 : input_bank_r;
    m03_fp_scale_pair #(.FP_W(FP_W)) u_scale (
        .clk(clk), .rst_n(rst_n), .clear(clear), .in_valid(in_fire),
        .in_corr0_s21(in_corr0_s21), .in_corr1_s21(in_corr1_s21),
        .in_act_scale_fp(in_act_scale_fp),
        .in_weight0_scale_fp(in_weight0_scale_fp),
        .in_weight1_scale_fp(in_weight1_scale_fp),
        .out_valid(scale_valid), .out0_fp32(contribution0_fp32),
        .out1_fp32(contribution1_fp32), .error(scale_error));
    m03_delay_bus #(.WIDTH(4), .DEPTH(SCALE_LAT)) u_scale_tag (
        .clk(clk), .rst_n(rst_n), .clear(clear), .in_valid(in_fire),
        .in_data({in_last_group,input_issue_bank}),
        .out_valid(scale_tag_valid), .out_data(scale_tag));

    wire projection_valid;
    wire [31:0] projection0_fp32;
    wire [31:0] projection1_fp32;
    wire accumulator_error;
    m03_fp_projection_accum6 u_accumulator (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .start_pair(in_fire && in_first_group),
        .in_valid(scale_valid && scale_tag_valid),
        .in_last(scale_tag[3]), .in_bank(scale_tag[2:0]),
        .in0_fp32(contribution0_fp32), .in1_fp32(contribution1_fp32),
        .out_valid(projection_valid), .out0_fp32(projection0_fp32),
        .out1_fp32(projection1_fp32), .error(accumulator_error));

    wire coeff_valid;
    wire [FP_W-1:0] coeff_cos_fp;
    wire [FP_W-1:0] coeff_sin_fp;
    wire coeff_error;
    m03_s18_coeff_pair_to_fp #(.FP_W(FP_W)) u_coeff (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_fire && in_first_group),
        .in_cos_s18(in_cos_s18), .in_sin_s18(in_sin_s18),
        .out_valid(coeff_valid), .out_cos_fp(coeff_cos_fp),
        .out_sin_fp(coeff_sin_fp), .error(coeff_error));

    wire [31:0] rope_input_pair_count;
    wire rope_error;
    m03_fp_rope_from_projection #(.FP_W(FP_W)) u_rope (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .coeff_valid(coeff_valid), .coeff_cos_fp(coeff_cos_fp),
        .coeff_sin_fp(coeff_sin_fp),
        .projection_valid(projection_valid),
        .projection0_fp32(projection0_fp32),
        .projection1_fp32(projection1_fp32),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_y0_s24(out_y0_s24), .out_y1_s24(out_y1_s24),
        .rope_input_pair_count(rope_input_pair_count),
        .output_pair_count(output_pair_count), .error(rope_error));

    assign error = local_error_r | scale_error | accumulator_error |
        coeff_error | rope_error;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            accept_cooldown_r <= 1'b0;
            tail_inflight_r <= 1'b0;
            expected_group_r <= '0;
            input_bank_r <= 3'd0;
            local_error_r <= 1'b0;
            input_group_count <= 32'd0;
            input_pair_count <= 32'd0;
        end else if (clear) begin
            accept_cooldown_r <= 1'b0;
            tail_inflight_r <= 1'b0;
            expected_group_r <= '0;
            input_bank_r <= 3'd0;
            local_error_r <= 1'b0;
            input_group_count <= 32'd0;
            input_pair_count <= 32'd0;
        end else begin
            if (accept_cooldown_r)
                accept_cooldown_r <= 1'b0;
            if (in_fire)
                accept_cooldown_r <= 1'b1;
            if (in_fire) begin
                input_group_count <= input_group_count + 1'b1;
                if ((in_first_group != (expected_group_r == 0)) ||
                    (in_last_group != (expected_group_r == GROUPS-1)) ||
                    (in_cos_s18 > 18'sd65536) ||
                    (in_cos_s18 < -18'sd65536) ||
                    (in_sin_s18 > 18'sd65536) ||
                    (in_sin_s18 < -18'sd65536))
                    local_error_r <= 1'b1;
                if (expected_group_r == GROUPS-1)
                    expected_group_r <= '0;
                else
                    expected_group_r <= expected_group_r + 1'b1;
                if (in_last_group)
                    input_bank_r <= 3'd0;
                else if (input_issue_bank == 5)
                    input_bank_r <= 3'd0;
                else
                    input_bank_r <= input_issue_bank + 1'b1;
                if (in_last_group) begin
                    input_pair_count <= input_pair_count + 1'b1;
                    tail_inflight_r <= 1'b1;
                end
            end
            if (out_fire)
                tail_inflight_r <= 1'b0;
            if (scale_valid != scale_tag_valid)
                local_error_r <= 1'b1;
            if (rope_input_pair_count > input_pair_count ||
                output_pair_count > input_pair_count)
                local_error_r <= 1'b1;
        end
    end

    initial begin
        if (FP_W != 16 && FP_W != 32)
            $error("m03_fp_projection_rope_pair FP_W must be 16 or 32");
        if (GROUPS != 128)
            $error("M03 boundary workload requires 128 projection groups");
    end
endmodule


module m03_fp16_projection_rope_pair (
    input wire clk, rst_n, clear, in_valid,
    output wire in_ready,
    input wire in_first_group, in_last_group,
    input wire signed [20:0] in_corr0_s21, in_corr1_s21,
    input wire [15:0] in_act_scale_fp, in_weight0_scale_fp,
    input wire [15:0] in_weight1_scale_fp,
    input wire signed [17:0] in_cos_s18, in_sin_s18,
    output wire out_valid,
    input wire out_ready,
    output wire signed [23:0] out_y0_s24, out_y1_s24,
    output wire [31:0] input_group_count, input_pair_count,
    output_pair_count, saturation_count,
    output wire error
);
    m03_fp_projection_rope_pair #(.FP_W(16)) u_core (.*);
endmodule


module m03_fp32_projection_rope_pair (
    input wire clk, rst_n, clear, in_valid,
    output wire in_ready,
    input wire in_first_group, in_last_group,
    input wire signed [20:0] in_corr0_s21, in_corr1_s21,
    input wire [31:0] in_act_scale_fp, in_weight0_scale_fp,
    input wire [31:0] in_weight1_scale_fp,
    input wire signed [17:0] in_cos_s18, in_sin_s18,
    output wire out_valid,
    input wire out_ready,
    output wire signed [23:0] out_y0_s24, out_y1_s24,
    output wire [31:0] input_group_count, input_pair_count,
    output_pair_count, saturation_count,
    output wire error
);
    m03_fp_projection_rope_pair #(.FP_W(32)) u_core (.*);
endmodule
