`timescale 1ns / 1ps

// ModularExperiment-only drop-in for the production S35 quantizer module
// name.  Raw Group32 Min/Max includes zero; ideal-range zp/U8 and ScaleCode
// encoding use round-to-nearest, ties-to-even.  No valid lane is clipped.
module hap_mlp_robust_a8_quantizer_s35 (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire [32*35-1:0]      in_s35,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [32*8-1:0]       out_u8,
    output wire [23:0]           out_meta,
    output reg  [31:0]           input_group_count,
    output reg  [31:0]           output_group_count,
    output reg  [31:0]           cycle_count,
    output reg  [31:0]           format_error_count,
    output reg                   error
);
    localparam [3:0] ST_IDLE        = 4'd0;
    localparam [3:0] ST_MINMAX      = 4'd1;
    localparam [3:0] ST_RANGE       = 4'd2;
    localparam [3:0] ST_SCALE_SCAN  = 4'd3;
    localparam [3:0] ST_SCALE_START = 4'd4;
    localparam [3:0] ST_SCALE_WAIT  = 4'd5;
    localparam [3:0] ST_ZP_PREP     = 4'd6;
    localparam [3:0] ST_ZP_START    = 4'd7;
    localparam [3:0] ST_ZP_WAIT     = 4'd8;
    localparam [3:0] ST_QUANT_PREP  = 4'd9;
    localparam [3:0] ST_QUANT_START = 4'd10;
    localparam [3:0] ST_QUANT_WAIT  = 4'd11;
    localparam [3:0] ST_OUTPUT      = 4'd12;

    localparam [35:0] SCALE_DENOM_Q16 = 36'd16711680;
    localparam [35:0] SCALE_EXACT_LIMIT_Q16 = 36'd4261478400;
    localparam [35:0] SCALE_ROUND_LIMIT_Q16 = 36'd4269834239;

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
    reg [35:0] scale_shifted_diff_r;
    reg [5:0] scale_shift_r;
    reg [7:0] scale_code_r;
    reg [7:0] zero_point_r;
    reg [255:0] quant_data_r;

    reg [7:0] div_active_r;
    reg [8*44-1:0] div_numerator_r;
    reg [35:0] div_denominator_r;
    wire [7:0] div_busy_w;
    wire [7:0] div_done_w;
    wire [7:0] div_error_w;
    wire [8*44-1:0] div_quotient_w;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire div_start = (state_r == ST_SCALE_START) ||
        (state_r == ST_ZP_START) || (state_r == ST_QUANT_START);
    wire div_batch_done = &((~div_active_r) | div_done_w);
    wire div_batch_error = |(div_active_r & div_error_w);

    assign in_ready = rst_n && !clear && (state_r == ST_IDLE);
    assign out_valid = rst_n && !clear && (state_r == ST_OUTPUT);
    assign out_u8 = quant_data_r;
    assign out_meta = {2'b00, scale_shift_r, scale_code_r, zero_point_r};

    genvar div_lane;
    generate
        for (div_lane = 0; div_lane < 8; div_lane = div_lane + 1) begin : g_div
            m11_u44_div_u36_radix16 u_div (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .start(div_start && div_active_r[div_lane]),
                .round_parity_offset(1'b0),
                .numerator(div_numerator_r[div_lane*44 +: 44]),
                .denominator(div_denominator_r),
                .busy(div_busy_w[div_lane]), .done(div_done_w[div_lane]),
                .error(div_error_w[div_lane]),
                .quotient(div_quotient_w[div_lane*44 +: 44])
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
            scale_shifted_diff_r <= 36'd0;
            scale_shift_r <= 6'd0;
            scale_code_r <= 8'd0;
            zero_point_r <= 8'd0;
            quant_data_r <= 256'd0;
            div_active_r <= 8'd0;
            div_numerator_r <= 352'd0;
            div_denominator_r <= 36'd1;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            cycle_count <= 32'd0;
            format_error_count <= 32'd0;
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
            scale_shifted_diff_r <= 36'd0;
            scale_shift_r <= 6'd0;
            scale_code_r <= 8'd0;
            zero_point_r <= 8'd0;
            quant_data_r <= 256'd0;
            div_active_r <= 8'd0;
            div_numerator_r <= 352'd0;
            div_denominator_r <= 36'd1;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            cycle_count <= 32'd0;
            format_error_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (state_r != ST_IDLE && state_r != ST_OUTPUT)
                cycle_count <= cycle_count + 1'b1;
            case (state_r)
                ST_IDLE: begin
                    if (in_fire) begin
                        source_capture_open_bank_r <= 8'd0;
                        input_group_count <= input_group_count + 1'b1;
                        scan_lane_r <= 6'd0;
                        raw_min_r <= 35'sd0;
                        raw_max_r <= 35'sd0;
                        quant_data_r <= 256'd0;
                        div_active_r <= 8'd0;
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
                    scale_shifted_diff_r <= diff_now;
                    scale_shift_r <= 6'd0;
                    scale_code_r <= 8'd0;
                    zero_point_r <= 8'd0;
                    quant_base_r <= 6'd0;
                    if (diff_now == 0) begin
                        quant_data_r <= 256'd0;
                        state_r <= ST_OUTPUT;
                    end else begin
                        if (diff_now > SCALE_ROUND_LIMIT_Q16) begin
                            format_error_count <= format_error_count + 1'b1;
                        end
                        state_r <= ST_SCALE_SCAN;
                    end
                end
                ST_SCALE_SCAN: begin
                    if ((scale_shift_r < 63) &&
                        (({1'b0, scale_shifted_diff_r} << 1) <=
                         {1'b0, SCALE_EXACT_LIMIT_Q16})) begin
                        scale_shifted_diff_r <= scale_shifted_diff_r << 1;
                        scale_shift_r <= scale_shift_r + 1'b1;
                    end else begin
                        div_numerator_r <= 352'd0;
                        div_numerator_r[43:0] <=
                            {8'd0, scale_shifted_diff_r};
                        div_denominator_r <= SCALE_DENOM_Q16;
                        div_active_r <= 8'b0000_0001;
                        state_r <= ST_SCALE_START;
                    end
                end
                ST_SCALE_START: state_r <= ST_SCALE_WAIT;
                ST_SCALE_WAIT: begin
                    if (div_batch_done) begin
                        div_active_r <= 8'd0;
                        if (div_batch_error) begin
                            error <= 1'b1;
                            state_r <= ST_OUTPUT;
                        end else begin
                            quotient_now = div_quotient_w[43:0];
                            if (quotient_now == 0)
                                scale_code_r <= 8'd1;
                            else if (quotient_now > 255)
                                scale_code_r <= 8'd255;
                            else
                                scale_code_r <= quotient_now[7:0];
                            state_r <= ST_ZP_PREP;
                        end
                    end
                end
                ST_ZP_PREP: begin
                    div_numerator_r <= 352'd0;
                    if (low_r < 0) begin
                        low_magnitude = -low_r;
                        div_numerator_r[43:0] <=
                            ({8'd0, low_magnitude} << 8) -
                            {8'd0, low_magnitude};
                    end
                    div_denominator_r <= diff_r;
                    div_active_r <= 8'b0000_0001;
                    state_r <= ST_ZP_START;
                end
                ST_ZP_START: state_r <= ST_ZP_WAIT;
                ST_ZP_WAIT: begin
                    if (div_batch_done) begin
                        div_active_r <= 8'd0;
                        if (div_batch_error) begin
                            error <= 1'b1;
                            state_r <= ST_OUTPUT;
                        end else begin
                            quotient_now = div_quotient_w[43:0];
                            zero_point_r <= quotient_now > 255 ? 8'hff :
                                quotient_now[7:0];
                            quant_base_r <= 6'd0;
                            state_r <= ST_QUANT_PREP;
                        end
                    end
                end
                ST_QUANT_PREP: begin
                    maximum_numerator = ({8'd0, diff_r} << 8) -
                        {8'd0, diff_r};
                    zero_point_term = {8'd0, diff_r} *
                        {{36{1'b0}}, zero_point_r};
                    for (lane = 0; lane < 8; lane = lane + 1) begin
                        sample = source_mem[quant_base_r+lane];
                        sample_wide = {{10{sample[34]}}, sample};
                        affine_numerator = (sample_wide <<< 8) -
                            sample_wide + $signed({1'b0, zero_point_term});
                        if (affine_numerator <= 0)
                            div_numerator_r[lane*44 +: 44] <= 44'd0;
                        else if (affine_numerator >= maximum_numerator)
                            div_numerator_r[lane*44 +: 44] <=
                                maximum_numerator;
                        else
                            div_numerator_r[lane*44 +: 44] <=
                                affine_numerator[43:0];
                    end
                    div_denominator_r <= diff_r;
                    div_active_r <= 8'hff;
                    state_r <= ST_QUANT_START;
                end
                ST_QUANT_START: state_r <= ST_QUANT_WAIT;
                ST_QUANT_WAIT: begin
                    if (div_batch_done) begin
                        div_active_r <= 8'd0;
                        if (div_batch_error) begin
                            error <= 1'b1;
                            state_r <= ST_OUTPUT;
                        end else begin
                            for (lane = 0; lane < 8; lane = lane + 1) begin
                                quotient_now =
                                    div_quotient_w[lane*44 +: 44];
                                quant_data_r[(quant_base_r+lane)*8 +: 8]
                                    <= quotient_now > 255 ? 8'hff :
                                    quotient_now[7:0];
                            end
                            if (quant_base_r == 24)
                                state_r <= ST_OUTPUT;
                            else begin
                                quant_base_r <= quant_base_r + 6'd8;
                                state_r <= ST_QUANT_PREP;
                            end
                        end
                    end
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
endmodule
