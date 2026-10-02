`timescale 1ns/1ps

// Native-FP baseline for raw Group32 Min/Max S35->A8.  U8/zp use the same
// ideal range and nearest-even rounding as the ScaleCode path; only the scale
// representation sent downstream is IEEE FP16/FP32.
module m11_native_fp_a8_quantizer_s35 #(
    parameter integer FP_W = 16
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire [32*35-1:0]      in_s35,
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
    localparam integer Q_LANES = 4;

    reg [3:0] state_r;
    reg [5:0] scan_lane_r;
    reg [5:0] quant_base_r;
    reg signed [34:0] source_mem [0:31];
    (* DONT_TOUCH = "yes" *) reg [7:0] source_capture_open_bank_r;
    reg signed [34:0] raw_min_r;
    reg signed [34:0] raw_max_r;
    reg signed [35:0] low_r;
    reg signed [35:0] high_r;
    reg [35:0] diff_r;
    reg [FP_W-1:0] scale_fp_r;
    reg scale_seen_r;
    reg [7:0] zero_point_r;
    reg zero_seen_r;
    reg [255:0] quant_data_r;

    reg [Q_LANES*44-1:0] q_numerator_r;
    wire [Q_LANES-1:0] q_busy_w;
    wire [Q_LANES-1:0] q_done_w;
    wire [Q_LANES-1:0] q_error_w;
    wire [Q_LANES*44-1:0] q_quotient_w;
    reg [43:0] zp_numerator_r;
    wire zp_busy_w;
    wire zp_done_w;
    wire zp_error_w;
    wire [43:0] zp_quotient_w;
    reg [43:0] scale_numerator_r;
    wire scale_busy_w;
    wire scale_done_w;
    wire scale_error_w;
    wire [43:0] scale_quotient_w;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire q_start = state_r == ST_QUANT_START;
    wire auxiliary_start = state_r == ST_SCALE_START;
    wire q_batch_done = &q_done_w;
    wire scale_issue = scale_done_w;
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
            m11_u44_div_u36_radix16 u_div (
                .clk(clk), .rst_n(rst_n), .clear(clear), .start(q_start),
                // q_numerator_r is the complete affine numerator; its
                // quotient already has the final U8 parity.
                .round_parity_offset(1'b0),
                .numerator(q_numerator_r[div_lane*44 +: 44]),
                .denominator(diff_r), .busy(q_busy_w[div_lane]),
                .done(q_done_w[div_lane]), .error(q_error_w[div_lane]),
                .quotient(q_quotient_w[div_lane*44 +: 44])
            );
        end
    endgenerate

    m11_u44_div_u36_radix16 u_zp_div (
        .clk(clk), .rst_n(rst_n), .clear(clear), .start(auxiliary_start),
        .round_parity_offset(1'b0),
        .numerator(zp_numerator_r), .denominator(diff_r),
        .busy(zp_busy_w), .done(zp_done_w), .error(zp_error_w),
        .quotient(zp_quotient_w)
    );

    m11_u44_div_u36_radix16 u_scale_div (
        .clk(clk), .rst_n(rst_n), .clear(clear), .start(auxiliary_start),
        .round_parity_offset(1'b0),
        .numerator(scale_numerator_r), .denominator(36'd255),
        .busy(scale_busy_w), .done(scale_done_w), .error(scale_error_w),
        .quotient(scale_quotient_w)
    );

    generate
        if (FP_W == 16) begin : g_scale_fp16
            wire stage1_valid;
            wire [31:0] stage1_result;
            m11_scale_q24_to_fp32_for_fp16 u_fixed_to_single (
                .aclk(clk), .s_axis_a_tvalid(scale_issue),
                .s_axis_a_tdata(scale_quotient_w[36:0]),
                .m_axis_result_tvalid(stage1_valid),
                .m_axis_result_tdata(stage1_result)
            );
            m11_scale_fp32_to_fp16 u_single_to_half (
                .aclk(clk), .s_axis_a_tvalid(stage1_valid),
                .s_axis_a_tdata(stage1_result),
                .m_axis_result_tvalid(scale_valid),
                .m_axis_result_tdata(scale_result)
            );
        end else begin : g_scale_fp32
            m11_scale_q24_to_fp32 u_fixed_to_single (
                .aclk(clk), .s_axis_a_tvalid(scale_issue),
                .s_axis_a_tdata(scale_quotient_w[36:0]),
                .m_axis_result_tvalid(scale_valid),
                .m_axis_result_tdata(scale_result)
            );
        end
    endgenerate

    integer lane;
    always @(posedge clk) begin
        for (lane = 0; lane < 32; lane = lane + 1)
            if (source_capture_open_bank_r[lane/4] && in_valid)
                source_mem[lane] <= in_s35[lane*35 +: 35];
    end

    always @(posedge clk or negedge rst_n) begin : p_control
        reg signed [34:0] sample;
        reg signed [35:0] low_now;
        reg signed [35:0] high_now;
        reg [35:0] diff_now;
        reg [43:0] quotient_now;
        reg signed [44:0] affine_numerator;
        reg signed [44:0] sample_wide;
        reg [43:0] maximum_numerator;
        reg [43:0] zero_point_term;
        reg [35:0] low_magnitude;
        if (!rst_n) begin
            state_r <= ST_IDLE;
            source_capture_open_bank_r <= 8'hff;
            scan_lane_r <= 6'd0;
            quant_base_r <= 6'd0;
            raw_min_r <= 35'sd0;
            raw_max_r <= 35'sd0;
            low_r <= 36'sd0;
            high_r <= 36'sd0;
            diff_r <= 36'd0;
            scale_fp_r <= '0;
            scale_seen_r <= 1'b0;
            zero_point_r <= 8'd0;
            zero_seen_r <= 1'b0;
            quant_data_r <= 256'd0;
            q_numerator_r <= '0;
            zp_numerator_r <= 44'd0;
            scale_numerator_r <= 44'd0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            cycle_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            state_r <= ST_IDLE;
            source_capture_open_bank_r <= 8'hff;
            scan_lane_r <= 6'd0;
            quant_base_r <= 6'd0;
            raw_min_r <= 35'sd0;
            raw_max_r <= 35'sd0;
            low_r <= 36'sd0;
            high_r <= 36'sd0;
            diff_r <= 36'd0;
            scale_fp_r <= '0;
            scale_seen_r <= 1'b0;
            zero_point_r <= 8'd0;
            zero_seen_r <= 1'b0;
            quant_data_r <= 256'd0;
            q_numerator_r <= '0;
            zp_numerator_r <= 44'd0;
            scale_numerator_r <= 44'd0;
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
            if ((|q_error_w) || zp_error_w || scale_error_w)
                error <= 1'b1;

            case (state_r)
                ST_IDLE: begin
                    if (in_fire) begin
                        source_capture_open_bank_r <= 8'd0;
                        input_group_count <= input_group_count + 1'b1;
                        scan_lane_r <= 6'd0;
                        raw_min_r <= 35'sd0;
                        raw_max_r <= 35'sd0;
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
                    low_now = $signed({raw_min_r[34], raw_min_r});
                    high_now = $signed({raw_max_r[34], raw_max_r});
                    diff_now = high_now - low_now;
                    low_r <= low_now;
                    high_r <= high_now;
                    diff_r <= diff_now;
                    quant_base_r <= 6'd0;
                    if (diff_now == 0) begin
                        scale_fp_r <= '0;
                        scale_seen_r <= 1'b1;
                        zero_point_r <= 8'd0;
                        zero_seen_r <= 1'b1;
                        quant_data_r <= 256'd0;
                        state_r <= ST_OUTPUT;
                    end else begin
                        scale_numerator_r <= {8'd0, diff_now} << 8;
                        low_magnitude = low_now < 0 ? -low_now : 36'd0;
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
                        {{36{1'b0}}, zero_point_r};
                    for (lane = 0; lane < Q_LANES; lane = lane + 1) begin
                        sample = source_mem[quant_base_r+lane];
                        sample_wide = {{10{sample[34]}}, sample};
                        affine_numerator = (sample_wide <<< 8) -
                            sample_wide +
                            $signed({1'b0, zero_point_term});
                        if (affine_numerator <= 0)
                            q_numerator_r[lane*44 +: 44] <= 44'd0;
                        else if (affine_numerator >= maximum_numerator)
                            q_numerator_r[lane*44 +: 44] <=
                                maximum_numerator;
                        else
                            q_numerator_r[lane*44 +: 44] <=
                                affine_numerator[43:0];
                    end
                    state_r <= ST_QUANT_START;
                end
                ST_QUANT_START: state_r <= ST_QUANT_WAIT;
                ST_QUANT_WAIT: begin
                    if (q_batch_done) begin
                        for (lane = 0; lane < Q_LANES; lane = lane + 1) begin
                            quotient_now = q_quotient_w[lane*44 +: 44];
                            quant_data_r[(quant_base_r+lane)*8 +: 8] <=
                                quotient_now > 255 ? 8'hff :
                                quotient_now[7:0];
                        end
                        if (quant_base_r == 28) begin
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
                        source_capture_open_bank_r <= 8'hff;
                        output_group_count <= output_group_count + 1'b1;
                        state_r <= ST_IDLE;
                    end
                end
                default: begin
                    source_capture_open_bank_r <= 8'hff;
                    error <= 1'b1;
                    state_r <= ST_IDLE;
                end
            endcase
        end
    end

    initial begin
        if ((FP_W != 16) && (FP_W != 32))
            $error("m11_native_fp_a8_quantizer_s35 FP_W must be 16 or 32");
    end
endmodule
