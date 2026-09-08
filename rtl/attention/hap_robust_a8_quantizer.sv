`timescale 1ns / 1ps

module hap_robust_a8_quantizer (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire [32*27-1:0]      in_s27,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [32*8-1:0]       out_u8,
    output wire [23:0]           out_meta,
    output reg  [31:0]           input_group_count,
    output reg  [31:0]           output_group_count,
    output reg  [31:0]           cycle_count,
    output reg                   error
);

    localparam [4:0] ST_IDLE             = 5'd0;
    localparam [4:0] ST_ABS_SCAN         = 5'd1;
    localparam [4:0] ST_ABS_THR_MUL      = 5'd2;
    localparam [4:0] ST_ABS_THR_CAPTURE  = 5'd3;
    localparam [4:0] ST_CLIP_SCAN        = 5'd4;
    localparam [4:0] ST_BOUNDS_MUL       = 5'd5;
    localparam [4:0] ST_BOUNDS_CAPTURE   = 5'd6;
    localparam [4:0] ST_SCALE_INIT       = 5'd7;
    localparam [4:0] ST_SCALE_SCAN       = 5'd8;
    localparam [4:0] ST_ZP_PREP          = 5'd9;
    localparam [4:0] ST_ZP_START         = 5'd10;
    localparam [4:0] ST_ZP_WAIT          = 5'd11;
    localparam [4:0] ST_QUANT_PREP       = 5'd12;
    localparam [4:0] ST_QUANT_START      = 5'd13;
    localparam [4:0] ST_QUANT_WAIT       = 5'd14;
    localparam [4:0] ST_OUTPUT           = 5'd15;
    localparam [4:0] ST_CLIP_DRAIN       = 5'd16;
    localparam [4:0] ST_QUANT_RATIO      = 5'd17;
    localparam [4:0] ST_ABS_THR_DIFF     = 5'd18;
    localparam [4:0] ST_SCALE_CODE_START = 5'd19;
    localparam [4:0] ST_SCALE_CODE_WAIT  = 5'd20;

    localparam [15:0] ABS_Q9999_Q16 = 16'd65333;
    localparam [15:0] CLIP_Q001_Q16 = 16'd2032;
    localparam [15:0] CLIP_Q999_Q16 = 16'd63504;
    localparam [32:0] SCALE_SHIFT_LIMIT = 33'd4269834239;
    localparam [23:0] SCALE_DENOM_HALF = 24'd8355840;

    reg [4:0] state_r;
    reg [5:0] scan_lane_r;
    reg [5:0] quant_base_r;
    reg [5:0] scale_shift_r;
    reg [32:0] scale_shifted_diff_r;

    reg signed [26:0] source_mem [0:31];
    reg signed [26:0] clipped_mem [0:31];
    reg [26:0] abs_max1_r;
    reg [26:0] abs_max2_r;
    reg signed [26:0] min1_r;
    reg signed [26:0] min2_r;
    reg signed [26:0] max1_r;
    reg signed [26:0] max2_r;
    // Register the clipped sample before updating the four extrema.  The
    // former single-cycle path started at scan_lane_r, traversed the dynamic
    // source read and clip arithmetic, then crossed an SLR into min/max CE.
    // This remains an II=1 scan: cycle N fetches lane N while processing lane
    // N-1, followed by one drain cycle for lane 31.
    reg signed [26:0] clip_scan_value_r;
    // Register the difference before the fixed-point percentile multiply.
    // The complete Attention post-route path previously combined the
    // 27-bit subtract and constant multiply in one cycle (15 logic levels).
    reg [26:0] abs_diff_r;
    reg [42:0] interp_product0_r;
    reg [42:0] interp_product1_r;
    reg [26:0] abs_threshold_r;
    reg signed [27:0] clip_low_r;
    reg signed [27:0] clip_high_r;
    reg [27:0] diff_r;
    reg [7:0] scale_code_r;
    reg [7:0] zero_point_r;
    reg [255:0] quant_data_r;

    reg [7:0] div_start_r;
    reg [7:0] div_active_r;
    reg [8*16-1:0] div_numerator_r;
    wire [7:0] div_busy_w;
    wire [7:0] div_done_w;
    wire [7:0] div_error_w;
    wire [8*16-1:0] div_quotient_w;
    reg [7:0] quant_negative_r;
    reg [7:0] quant_saturated_r;
    // Split the indexed clipped-memory read/clamp from prepare_ratio.  In the
    // complete Attention route the old single-cycle path started at
    // quant_base_r, crossed the dynamic read plus the full shift/add/
    // saturation network, and ended at div_active_r after 21 logic levels.
    // Four batches are still processed serially; this boundary adds one
    // cycle per batch without changing any arithmetic value.
    reg signed [27:0] quant_value_r [0:7];

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire div_batch_done = &((~div_active_r) | div_done_w);
    wire div_batch_error = |(div_active_r & div_error_w);

    assign in_ready = rst_n && !clear && (state_r == ST_IDLE);
    assign out_valid = rst_n && !clear && (state_r == ST_OUTPUT);
    assign out_u8 = quant_data_r;
    assign out_meta = {2'b00, scale_shift_r, scale_code_r, zero_point_r};

    function automatic [26:0] abs_s27;
        input signed [26:0] value;
        begin
            abs_s27 = value[26] ? -value : value;
        end
    endfunction

    function automatic signed [26:0] clip_abs_s27;
        input signed [26:0] value;
        input [26:0] threshold;
        reg signed [27:0] value_ext;
        reg signed [27:0] threshold_ext;
        begin
            value_ext = value;
            threshold_ext = $signed({1'b0, threshold});
            if (value_ext > threshold_ext)
                clip_abs_s27 = threshold[26:0];
            else if (value_ext < -threshold_ext)
                clip_abs_s27 = -threshold_ext;
            else
                clip_abs_s27 = value;
        end
    endfunction

    function automatic [26:0] nonnegative_diff_s27;
        input signed [26:0] high_value;
        input signed [26:0] low_value;
        reg signed [27:0] difference;
        begin
            difference = $signed({high_value[26], high_value}) -
                $signed({low_value[26], low_value});
            nonnegative_diff_s27 = difference <= 0 ? 27'd0 :
                difference[26:0];
        end
    endfunction

    function automatic [64:0] prepare_ratio;
        input signed [27:0] value;
        input [7:0] code;
        input [5:0] shift;
        reg [27:0] magnitude;
        reg [63:0] shifted_magnitude;
        reg [63:0] adjusted;
        reg [63:0] saturation_threshold;
        begin
            magnitude = value[27] ? -value : value;
            shifted_magnitude = {36'd0, magnitude} << shift;
            adjusted = shifted_magnitude + ({56'd0, code} << 15);
            // Keep the exact code*255 threshold in LUT carry logic under every
            // synthesis directive instead of consuming one DSP per row.
            saturation_threshold = ({56'd0, code} << 24) -
                ({56'd0, code} << 16);
            if (adjusted >= saturation_threshold)
                prepare_ratio = {1'b1, 64'd0};
            else
                prepare_ratio = {1'b0, 48'd0, adjusted[31:16]};
        end
    endfunction

    // Reuse lane 0's iterative divider for scale-code /255.  The former
    // encode_scale_code function inferred a 19-level combinational divider
    // from scale_shifted_diff_r to scale_code_r and became the complete
    // Attention post-route worst path.  SCALE_SHIFT_LIMIT guarantees the
    // rounded numerator is <= 65279, so the existing u16/u8 divider is exact.
    wire [7:0] div_denominator =
        ((state_r == ST_SCALE_CODE_START) ||
         (state_r == ST_SCALE_CODE_WAIT)) ? 8'd255 : scale_code_r;

    genvar div_lane;
    generate
        for (div_lane = 0; div_lane < 8; div_lane = div_lane + 1) begin : g_div
            hap_u16_div_u8_seq u_div (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .start(div_start_r[div_lane]),
                .numerator(div_numerator_r[div_lane*16 +: 16]),
                .denominator(div_denominator),
                .busy(div_busy_w[div_lane]), .done(div_done_w[div_lane]),
                .error(div_error_w[div_lane]),
                .quotient(div_quotient_w[div_lane*16 +: 16])
            );
        end
    endgenerate

    integer lane;
    always @(posedge clk) begin
        if (in_fire) begin
            for (lane = 0; lane < 32; lane = lane + 1)
                source_mem[lane] <= in_s27[lane*27 +: 27];
        end

        // Keep the clipped sample memory off the asynchronous reset tree.  Its
        // contents are only consumed after ST_CLIP_SCAN has overwritten all
        // 32 lanes, so stale power-up/reset data is never observable.
        if (rst_n && !clear) begin
            if ((state_r == ST_CLIP_SCAN) && (scan_lane_r != 0))
                clipped_mem[scan_lane_r-1'b1] <= clip_scan_value_r;
            else if (state_r == ST_CLIP_DRAIN)
                clipped_mem[31] <= clip_scan_value_r;
        end
    end

    always @(posedge clk or negedge rst_n) begin : p_control
        reg [26:0] magnitude;
        reg signed [26:0] clipped_value;
        reg signed [27:0] clipped_ext;
        reg [27:0] diff_now;
        reg [64:0] prepared;
        reg [31:0] quotient_magnitude;
        if (!rst_n) begin
            state_r <= ST_IDLE;
            scan_lane_r <= 6'd0;
            quant_base_r <= 6'd0;
            scale_shift_r <= 6'd0;
            scale_shifted_diff_r <= 33'd0;
            abs_max1_r <= 27'd0;
            abs_max2_r <= 27'd0;
            min1_r <= 27'sd0;
            min2_r <= 27'sd0;
            max1_r <= 27'sd0;
            max2_r <= 27'sd0;
            clip_scan_value_r <= 27'sd0;
            abs_diff_r <= 27'd0;
            interp_product0_r <= 43'd0;
            interp_product1_r <= 43'd0;
            abs_threshold_r <= 27'd0;
            clip_low_r <= 28'sd0;
            clip_high_r <= 28'sd0;
            diff_r <= 28'd0;
            scale_code_r <= 8'd0;
            zero_point_r <= 8'd0;
            quant_data_r <= 256'd0;
            div_start_r <= 8'd0;
            div_active_r <= 8'd0;
            div_numerator_r <= '0;
            quant_negative_r <= 8'd0;
            quant_saturated_r <= 8'd0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            cycle_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            state_r <= ST_IDLE;
            scan_lane_r <= 6'd0;
            quant_base_r <= 6'd0;
            scale_shift_r <= 6'd0;
            scale_shifted_diff_r <= 33'd0;
            scale_code_r <= 8'd0;
            zero_point_r <= 8'd0;
            quant_data_r <= 256'd0;
            div_start_r <= 8'd0;
            div_active_r <= 8'd0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            cycle_count <= 32'd0;
            error <= 1'b0;
        end else begin
            div_start_r <= 8'd0;
            if (state_r != ST_IDLE && state_r != ST_OUTPUT)
                cycle_count <= cycle_count + 32'd1;

            case (state_r)
                ST_IDLE: begin
                    if (in_fire) begin
                        input_group_count <= input_group_count + 32'd1;
                        scan_lane_r <= 6'd0;
                        abs_max1_r <= 27'd0;
                        abs_max2_r <= 27'd0;
                        quant_data_r <= 256'd0;
                        state_r <= ST_ABS_SCAN;
                    end
                end

                ST_ABS_SCAN: begin
                    magnitude = abs_s27(source_mem[scan_lane_r]);
                    if (magnitude >= abs_max1_r) begin
                        abs_max2_r <= abs_max1_r;
                        abs_max1_r <= magnitude;
                    end else if (magnitude > abs_max2_r) begin
                        abs_max2_r <= magnitude;
                    end
                    if (scan_lane_r == 31) begin
                        state_r <= ST_ABS_THR_DIFF;
                    end else begin
                        scan_lane_r <= scan_lane_r + 1'b1;
                    end
                end

                ST_ABS_THR_DIFF: begin
                    abs_diff_r <= abs_max1_r - abs_max2_r;
                    state_r <= ST_ABS_THR_MUL;
                end

                ST_ABS_THR_MUL: begin
                    interp_product0_r <= abs_diff_r * ABS_Q9999_Q16;
                    state_r <= ST_ABS_THR_CAPTURE;
                end

                ST_ABS_THR_CAPTURE: begin
                    abs_threshold_r <= abs_max2_r +
                        interp_product0_r[42:16];
                    scan_lane_r <= 6'd0;
                    min1_r <= 27'sd67108863;
                    min2_r <= 27'sd67108863;
                    max1_r <= -27'sd67108864;
                    max2_r <= -27'sd67108864;
                    state_r <= ST_CLIP_SCAN;
                end

                ST_CLIP_SCAN: begin
                    clip_scan_value_r <= clip_abs_s27(
                        source_mem[scan_lane_r], abs_threshold_r);
                    if (scan_lane_r != 0) begin
                        clipped_value = clip_scan_value_r;
                        if (clipped_value <= min1_r) begin
                            min2_r <= min1_r;
                            min1_r <= clipped_value;
                        end else if (clipped_value < min2_r) begin
                            min2_r <= clipped_value;
                        end
                        if (clipped_value >= max1_r) begin
                            max2_r <= max1_r;
                            max1_r <= clipped_value;
                        end else if (clipped_value > max2_r) begin
                            max2_r <= clipped_value;
                        end
                    end
                    if (scan_lane_r == 31) begin
                        state_r <= ST_CLIP_DRAIN;
                    end else begin
                        scan_lane_r <= scan_lane_r + 1'b1;
                    end
                end

                ST_CLIP_DRAIN: begin
                    clipped_value = clip_scan_value_r;
                    if (clipped_value <= min1_r) begin
                        min2_r <= min1_r;
                        min1_r <= clipped_value;
                    end else if (clipped_value < min2_r) begin
                        min2_r <= clipped_value;
                    end
                    if (clipped_value >= max1_r) begin
                        max2_r <= max1_r;
                        max1_r <= clipped_value;
                    end else if (clipped_value > max2_r) begin
                        max2_r <= clipped_value;
                    end
                    state_r <= ST_BOUNDS_MUL;
                end

                ST_BOUNDS_MUL: begin
                    interp_product0_r <=
                        nonnegative_diff_s27(min2_r, min1_r) *
                        CLIP_Q001_Q16;
                    interp_product1_r <=
                        nonnegative_diff_s27(max1_r, max2_r) *
                        CLIP_Q999_Q16;
                    state_r <= ST_BOUNDS_CAPTURE;
                end

                ST_BOUNDS_CAPTURE: begin
                    clip_low_r <= $signed(min1_r) +
                        $signed({1'b0, interp_product0_r[42:16]});
                    clip_high_r <= $signed(max2_r) +
                        $signed({1'b0, interp_product1_r[42:16]});
                    state_r <= ST_SCALE_INIT;
                end

                ST_SCALE_INIT: begin
                    diff_now = (clip_high_r > clip_low_r) ?
                        clip_high_r - clip_low_r : 28'd0;
                    diff_r <= diff_now;
                    scale_shift_r <= 6'd0;
                    scale_shifted_diff_r <= {5'd0, diff_now};
                    if (diff_now == 0) begin
                        scale_code_r <= 8'd0;
                        zero_point_r <= 8'd0;
                        quant_data_r <= 256'd0;
                        state_r <= ST_OUTPUT;
                    end else begin
                        state_r <= ST_SCALE_SCAN;
                    end
                end

                ST_SCALE_SCAN: begin
                    if ((scale_shift_r == 63) ||
                        ((scale_shifted_diff_r << 1) > SCALE_SHIFT_LIMIT)) begin
                        // Exact numerator from the former encode_scale_code:
                        // (shifted_diff + 255*2^15) >> 16.  Lane 0 performs
                        // the remaining unsigned divide by 255 iteratively.
                        div_numerator_r[15:0] <=
                            (scale_shifted_diff_r +
                             {9'd0, SCALE_DENOM_HALF}) >> 16;
                        div_active_r <= 8'b0000_0001;
                        state_r <= ST_SCALE_CODE_START;
                    end else begin
                        scale_shifted_diff_r <= scale_shifted_diff_r << 1;
                        scale_shift_r <= scale_shift_r + 1'b1;
                    end
                end

                ST_SCALE_CODE_START: begin
                    div_start_r <= div_active_r;
                    state_r <= ST_SCALE_CODE_WAIT;
                end

                ST_SCALE_CODE_WAIT: begin
                    if (div_batch_done) begin
                        div_active_r <= 8'd0;
                        if (div_batch_error) begin
                            error <= 1'b1;
                            state_r <= ST_OUTPUT;
                        end else begin
                            if (div_quotient_w[15:0] == 0)
                                scale_code_r <= 8'd1;
                            else if (div_quotient_w[15:0] > 255)
                                scale_code_r <= 8'd255;
                            else
                                scale_code_r <= div_quotient_w[7:0];
                            state_r <= ST_ZP_PREP;
                        end
                    end
                end

                ST_ZP_PREP: begin
                    div_active_r <= 8'd0;
                    if (clip_low_r >= 0) begin
                        zero_point_r <= 8'd0;
                        quant_base_r <= 6'd0;
                        state_r <= ST_QUANT_PREP;
                    end else begin
                        prepared = prepare_ratio(clip_low_r,
                            scale_code_r, scale_shift_r);
                        if (prepared[64]) begin
                            zero_point_r <= 8'hff;
                            quant_base_r <= 6'd0;
                            state_r <= ST_QUANT_PREP;
                        end else begin
                            div_numerator_r[15:0] <= prepared[15:0];
                            div_active_r[0] <= 1'b1;
                            state_r <= ST_ZP_START;
                        end
                    end
                end

                ST_ZP_START: begin
                    div_start_r <= div_active_r;
                    state_r <= ST_ZP_WAIT;
                end

                ST_ZP_WAIT: begin
                    if (div_batch_done) begin
                        div_active_r <= 8'd0;
                        if (div_batch_error) begin
                            error <= 1'b1;
                            state_r <= ST_OUTPUT;
                        end else begin
                            zero_point_r <= (div_quotient_w[15:0] > 255) ?
                                8'hff : div_quotient_w[7:0];
                            quant_base_r <= 6'd0;
                            state_r <= ST_QUANT_PREP;
                        end
                    end
                end

                ST_QUANT_PREP: begin
                    div_active_r <= 8'd0;
                    for (lane = 0; lane < 8; lane = lane + 1) begin
                        clipped_ext = clipped_mem[quant_base_r+lane];
                        if (clipped_ext < clip_low_r)
                            clipped_ext = clip_low_r;
                        else if (clipped_ext > clip_high_r)
                            clipped_ext = clip_high_r;
                        quant_value_r[lane] <= clipped_ext;
                    end
                    state_r <= ST_QUANT_RATIO;
                end

                ST_QUANT_RATIO: begin
                    div_active_r <= 8'd0;
                    for (lane = 0; lane < 8; lane = lane + 1) begin
                        prepared = prepare_ratio(quant_value_r[lane],
                            scale_code_r, scale_shift_r);
                        quant_negative_r[lane] <= quant_value_r[lane][27];
                        quant_saturated_r[lane] <= prepared[64];
                        div_numerator_r[lane*16 +: 16] <= prepared[15:0];
                        if (!prepared[64])
                            div_active_r[lane] <= 1'b1;
                    end
                    state_r <= ST_QUANT_START;
                end

                ST_QUANT_START: begin
                    div_start_r <= div_active_r;
                    state_r <= ST_QUANT_WAIT;
                end

                ST_QUANT_WAIT: begin
                    if (div_batch_done) begin
                        div_active_r <= 8'd0;
                        if (div_batch_error) begin
                            error <= 1'b1;
                            state_r <= ST_OUTPUT;
                        end else begin
                            for (lane = 0; lane < 8; lane = lane + 1) begin
                                quotient_magnitude = quant_saturated_r[lane] ?
                                    32'd255 : {16'd0,
                                    div_quotient_w[lane*16 +: 16]};
                                if (quant_negative_r[lane]) begin
                                    quant_data_r[(quant_base_r+lane)*8 +: 8]
                                        <= (quotient_magnitude >= zero_point_r) ?
                                        8'd0 : zero_point_r -
                                        quotient_magnitude[7:0];
                                end else begin
                                    quant_data_r[(quant_base_r+lane)*8 +: 8]
                                        <= (quotient_magnitude + zero_point_r >= 255) ?
                                        8'hff : quotient_magnitude[7:0] +
                                        zero_point_r;
                                end
                            end
                            if (quant_base_r == 24) begin
                                state_r <= ST_OUTPUT;
                            end else begin
                                quant_base_r <= quant_base_r + 8;
                                state_r <= ST_QUANT_PREP;
                            end
                        end
                    end
                end

                ST_OUTPUT: begin
                    if (out_fire) begin
                        output_group_count <= output_group_count + 32'd1;
                        state_r <= ST_IDLE;
                    end
                end

                default: begin
                    error <= 1'b1;
                    state_r <= ST_OUTPUT;
                end
            endcase
        end
    end

endmodule
