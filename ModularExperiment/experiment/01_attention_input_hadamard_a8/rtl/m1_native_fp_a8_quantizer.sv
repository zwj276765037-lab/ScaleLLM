`timescale 1ns/1ps

// Native-FP baseline for raw Group32 Min/Max A8.  The U8 and zero point are
// generated from the same ideal range as the ScaleCode path, with nearest-
// even rounding.  Only the transmitted scale representation differs.
module m1_native_fp_a8_quantizer #(
    parameter integer FP_W = 16
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire [32*27-1:0]      in_s27,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [32*8-1:0]       out_u8,
    output wire [FP_W+8-1:0]     out_meta,
    output reg  [31:0]           input_group_count,
    output reg  [31:0]           output_group_count,
    output reg  [31:0]           cycle_count,
    output reg                   error
);
    localparam [3:0] ST_IDLE        = 4'd0;
    localparam [3:0] ST_MINMAX      = 4'd1;
    localparam [3:0] ST_RANGE       = 4'd2;
    localparam [3:0] ST_SCALE_START = 4'd3;
    localparam [3:0] ST_QUANT_PREP  = 4'd4;
    localparam [3:0] ST_QUANT_START = 4'd5;
    localparam [3:0] ST_QUANT_WAIT  = 4'd6;
    localparam [3:0] ST_WAIT_SCALE  = 4'd7;
    localparam [3:0] ST_OUTPUT      = 4'd8;
    localparam [3:0] ST_WAIT_ZP     = 4'd9;
    // Three eight-cycle quotient units are the measured minimum that sustains
    // the production bundle rate used by the original matched experiment.
    localparam integer Q_LANES = 3;

    reg [3:0] state_r;
    reg [5:0] scan_lane_r;
    reg [5:0] quant_base_r;
    reg signed [26:0] source_mem [0:31];
    reg signed [26:0] raw_min_r;
    reg signed [26:0] raw_max_r;
    reg signed [27:0] low_r;
    reg signed [27:0] high_r;
    reg [27:0] diff_r;
    reg [27:0] scale_q24_r;
    reg [FP_W-1:0] scale_fp_r;
    reg scale_seen_r;
    reg [7:0] zero_point_r;
    reg zero_seen_r;
    reg [255:0] quant_data_r;

    reg [Q_LANES*36-1:0] q_numerator_r;
    wire [Q_LANES-1:0] q_busy_w;
    wire [Q_LANES-1:0] q_done_w;
    wire [Q_LANES-1:0] q_error_w;
    wire [Q_LANES*36-1:0] q_quotient_w;
    reg [35:0] zp_numerator_r;
    wire zp_busy_w;
    wire zp_done_w;
    wire zp_error_w;
    wire [35:0] zp_quotient_w;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire q_start = state_r == ST_QUANT_START;
    wire zp_start = state_r == ST_SCALE_START;
    wire q_batch_done = &q_done_w;
    wire scale_issue = state_r == ST_SCALE_START;
    wire scale_valid;
    wire [FP_W-1:0] scale_result;

    assign in_ready = rst_n && !clear && (state_r == ST_IDLE);
    assign out_valid = rst_n && !clear && (state_r == ST_OUTPUT);
    assign out_u8 = quant_data_r;
    assign out_meta = {scale_fp_r, zero_point_r};

    genvar div_lane;
    generate
        for (div_lane = 0; div_lane < Q_LANES;
             div_lane = div_lane + 1) begin : g_div
            m1_u36_div_u28_seq u_div (
                .clk(clk), .rst_n(rst_n), .clear(clear), .start(q_start),
                // q_numerator_r already contains the complete affine
                // numerator (x*255 + zp*diff), so quotient parity is the
                // final U8 parity.  No decomposed-rounding offset applies.
                .round_parity_offset(1'b0),
                .numerator(q_numerator_r[div_lane*36 +: 36]),
                .denominator(diff_r), .busy(q_busy_w[div_lane]),
                .done(q_done_w[div_lane]), .error(q_error_w[div_lane]),
                .quotient(q_quotient_w[div_lane*36 +: 36])
            );
        end
    endgenerate

    m1_u36_div_u28_seq u_zp_div (
        .clk(clk), .rst_n(rst_n), .clear(clear), .start(zp_start),
        .round_parity_offset(1'b0),
        .numerator(zp_numerator_r), .denominator(diff_r),
        .busy(zp_busy_w), .done(zp_done_w), .error(zp_error_w),
        .quotient(zp_quotient_w)
    );

    generate
        if (FP_W == 16) begin : g_scale_fp16
            wire stage1_valid;
            wire [31:0] stage1_result;
            m1_scale_q24_to_fp32_for_fp16 u_fixed_to_single (
                .aclk(clk), .s_axis_a_tvalid(scale_issue),
                .s_axis_a_tdata(scale_q24_r),
                .m_axis_result_tvalid(stage1_valid),
                .m_axis_result_tdata(stage1_result)
            );
            m1_scale_fp32_to_fp16 u_single_to_half (
                .aclk(clk), .s_axis_a_tvalid(stage1_valid),
                .s_axis_a_tdata(stage1_result),
                .m_axis_result_tvalid(scale_valid),
                .m_axis_result_tdata(scale_result)
            );
        end else begin : g_scale_fp32
            m1_scale_q24_to_fp32 u_fixed_to_single (
                .aclk(clk), .s_axis_a_tvalid(scale_issue),
                .s_axis_a_tdata(scale_q24_r),
                .m_axis_result_tvalid(scale_valid),
                .m_axis_result_tdata(scale_result)
            );
        end
    endgenerate

    integer lane;
    always @(posedge clk) begin
        if (in_fire)
            for (lane = 0; lane < 32; lane = lane + 1)
                source_mem[lane] <= in_s27[lane*27 +: 27];
    end

    always @(posedge clk or negedge rst_n) begin : p_control
        reg signed [26:0] sample;
        reg signed [27:0] low_now;
        reg signed [27:0] high_now;
        reg [27:0] diff_now;
        reg [35:0] quotient_now;
        reg signed [36:0] affine_numerator;
        reg signed [36:0] sample_wide;
        reg [35:0] maximum_numerator;
        reg [35:0] zero_point_term;
        reg [35:0] scale_dividend;
        reg [27:0] low_magnitude;
        if (!rst_n) begin
            state_r <= ST_IDLE;
            scan_lane_r <= 6'd0;
            quant_base_r <= 6'd0;
            raw_min_r <= 27'sd0;
            raw_max_r <= 27'sd0;
            low_r <= 28'sd0;
            high_r <= 28'sd0;
            diff_r <= 28'd0;
            scale_q24_r <= 28'd0;
            scale_fp_r <= '0;
            scale_seen_r <= 1'b0;
            zero_point_r <= 8'd0;
            zero_seen_r <= 1'b0;
            quant_data_r <= 256'd0;
            q_numerator_r <= '0;
            zp_numerator_r <= 36'd0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            cycle_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            state_r <= ST_IDLE;
            scan_lane_r <= 6'd0;
            quant_base_r <= 6'd0;
            raw_min_r <= 27'sd0;
            raw_max_r <= 27'sd0;
            low_r <= 28'sd0;
            high_r <= 28'sd0;
            diff_r <= 28'd0;
            scale_q24_r <= 28'd0;
            scale_fp_r <= '0;
            scale_seen_r <= 1'b0;
            zero_point_r <= 8'd0;
            zero_seen_r <= 1'b0;
            quant_data_r <= 256'd0;
            q_numerator_r <= '0;
            zp_numerator_r <= 36'd0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            cycle_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (state_r != ST_IDLE && state_r != ST_OUTPUT)
                cycle_count <= cycle_count + 1'b1;
            if (scale_valid) begin
                scale_fp_r <= scale_result;
                scale_seen_r <= 1'b1;
            end
            if (zp_done_w) begin
                zero_point_r <= zp_quotient_w > 255 ? 8'hff :
                    zp_quotient_w[7:0];
                zero_seen_r <= 1'b1;
            end
            if ((|q_error_w) || zp_error_w)
                error <= 1'b1;

            case (state_r)
                ST_IDLE: begin
                    if (in_fire) begin
                        input_group_count <= input_group_count + 1'b1;
                        scan_lane_r <= 6'd0;
                        raw_min_r <= 27'sd0;
                        raw_max_r <= 27'sd0;
                        quant_data_r <= 256'd0;
                        scale_seen_r <= 1'b0;
                        zero_seen_r <= 1'b0;
                        state_r <= ST_MINMAX;
                    end
                end
                ST_MINMAX: begin
                    sample = source_mem[scan_lane_r];
                    if (sample < raw_min_r)
                        raw_min_r <= sample;
                    if (sample > raw_max_r)
                        raw_max_r <= sample;
                    if (scan_lane_r == 31)
                        state_r <= ST_RANGE;
                    else
                        scan_lane_r <= scan_lane_r + 1'b1;
                end
                ST_RANGE: begin
                    low_now = $signed({raw_min_r[26], raw_min_r});
                    high_now = $signed({raw_max_r[26], raw_max_r});
                    diff_now = high_now - low_now;
                    low_r <= low_now;
                    high_r <= high_now;
                    diff_r <= diff_now;
                    quant_base_r <= 6'd0;
                    if (diff_now == 0) begin
                        scale_q24_r <= 28'd0;
                        scale_fp_r <= '0;
                        scale_seen_r <= 1'b1;
                        zero_point_r <= 8'd0;
                        zero_seen_r <= 1'b1;
                        quant_data_r <= 256'd0;
                        state_r <= ST_OUTPUT;
                    end else begin
                        scale_dividend = ({8'd0, diff_now} << 8) + 36'd127;
                        scale_q24_r <= scale_dividend / 36'd255;
                        low_magnitude = low_now < 0 ? -low_now : 28'd0;
                        zp_numerator_r <=
                            ({8'd0, low_magnitude} << 8) -
                            {8'd0, low_magnitude};
                        state_r <= ST_SCALE_START;
                    end
                end
                ST_SCALE_START: state_r <= ST_WAIT_ZP;
                ST_WAIT_ZP: begin
                    if (zp_done_w) begin
                        if (zp_error_w) begin
                            error <= 1'b1;
                            state_r <= ST_OUTPUT;
                        end else begin
                            zero_point_r <= zp_quotient_w > 255 ? 8'hff :
                                zp_quotient_w[7:0];
                            zero_seen_r <= 1'b1;
                            state_r <= ST_QUANT_PREP;
                        end
                    end
                end
                ST_QUANT_PREP: begin
                    maximum_numerator = ({8'd0, diff_r} << 8) -
                        {8'd0, diff_r};
                    zero_point_term = {8'd0, diff_r} *
                        {{28{1'b0}}, zero_point_r};
                    for (lane = 0; lane < Q_LANES; lane = lane + 1) begin
                        if ((quant_base_r + lane) < 32) begin
                            sample = source_mem[quant_base_r+lane];
                            sample_wide = {{10{sample[26]}}, sample};
                            affine_numerator = (sample_wide <<< 8) -
                                sample_wide +
                                $signed({1'b0, zero_point_term});
                            if (affine_numerator <= 0)
                                q_numerator_r[lane*36 +: 36] <= 36'd0;
                            else if (affine_numerator >= maximum_numerator)
                                q_numerator_r[lane*36 +: 36] <=
                                    maximum_numerator;
                            else
                                q_numerator_r[lane*36 +: 36] <=
                                    affine_numerator[35:0];
                        end else begin
                            q_numerator_r[lane*36 +: 36] <= 36'd0;
                        end
                    end
                    state_r <= ST_QUANT_START;
                end
                ST_QUANT_START: state_r <= ST_QUANT_WAIT;
                ST_QUANT_WAIT: begin
                    if (q_batch_done) begin
                        for (lane = 0; lane < Q_LANES; lane = lane + 1) begin
                            if ((quant_base_r + lane) < 32) begin
                                quotient_now =
                                    q_quotient_w[lane*36 +: 36];
                                quant_data_r[(quant_base_r+lane)*8 +: 8]
                                    <= quotient_now > 255 ? 8'hff :
                                    quotient_now[7:0];
                            end
                        end
                        if ((quant_base_r + Q_LANES) >= 32) begin
                            if (scale_seen_r || scale_valid)
                                state_r <= ST_OUTPUT;
                            else
                                state_r <= ST_WAIT_SCALE;
                        end else begin
                            quant_base_r <= quant_base_r + Q_LANES;
                            state_r <= ST_QUANT_PREP;
                        end
                    end
                end
                ST_WAIT_SCALE: begin
                    if (scale_seen_r || scale_valid)
                        state_r <= ST_OUTPUT;
                end
                ST_OUTPUT: begin
                    if (out_fire) begin
                        output_group_count <= output_group_count + 1'b1;
                        state_r <= ST_IDLE;
                    end
                end
                default: begin
                    error <= 1'b1;
                    state_r <= ST_IDLE;
                end
            endcase
        end
    end

    initial begin
        if ((FP_W != 16) && (FP_W != 32))
            $error("m1_native_fp_a8_quantizer FP_W must be 16 or 32");
    end
endmodule
