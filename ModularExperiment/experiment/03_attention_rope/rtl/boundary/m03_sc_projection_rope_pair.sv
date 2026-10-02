`timescale 1ns / 1ps

// Boundary-inclusive projection tail for one even/odd output pair.  The
// common pre-centered S21 correlations enter at the scale boundary; 128
// ScaleCode contributions are accumulated in the production S42 Q18.24
// format, finalized to S24 Q8.16, and passed to the production integer RoPE.
module m03_sc_projection_rope_pair #(
    parameter integer GROUPS = 128,
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
    input  wire [7:0]            in_act_scale_code,
    input  wire [5:0]            in_act_scale_shift,
    input  wire [7:0]            in_weight0_scale_code,
    input  wire [5:0]            in_weight0_scale_shift,
    input  wire [7:0]            in_weight1_scale_code,
    input  wire [5:0]            in_weight1_scale_shift,
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
    reg local_error_r;

    reg scale0_valid_r;
    reg signed [20:0] scale0_corr0_r;
    reg signed [20:0] scale0_corr1_r;
    reg [15:0] scale0_code0_r;
    reg [15:0] scale0_code1_r;
    reg [6:0] scale0_shift0_r;
    reg [6:0] scale0_shift1_r;
    reg scale0_first_r;
    reg scale0_last_r;

    reg scale1_valid_r;
    reg signed [36:0] scale1_raw0_r;
    reg signed [36:0] scale1_raw1_r;
    reg [6:0] scale1_shift0_r;
    reg [6:0] scale1_shift1_r;
    reg scale1_first_r;
    reg scale1_last_r;

    reg scale2_valid_r;
    reg signed [41:0] scale2_guard0_r;
    reg signed [41:0] scale2_guard1_r;
    reg scale2_first_r;
    reg scale2_last_r;

    reg signed [41:0] accum0_s42_r;
    reg signed [41:0] accum1_s42_r;
    reg signed [17:0] pair_cos_s18_r;
    reg signed [17:0] pair_sin_s18_r;
    reg final_valid_r;
    reg signed [23:0] final_x0_s24_r;
    reg signed [23:0] final_x1_s24_r;
    reg [31:0] projection_saturation_count_r;

    wire rope_in_ready;
    wire [31:0] rope_input_pair_count;
    wire [31:0] rope_saturation_count;
    wire rope_error;
    wire in_fire = in_valid && in_ready;
    wire rope_in_fire = final_valid_r && rope_in_ready;
    wire out_fire = out_valid && out_ready;

    assign in_ready = rst_n && !clear && !accept_cooldown_r &&
        !tail_inflight_r;
    assign saturation_count = projection_saturation_count_r +
        rope_saturation_count;
    assign error = local_error_r | rope_error;

    function automatic signed [41:0] align_scale_s37_to_s42_q24;
        input signed [36:0] value;
        input [6:0] total_shift;
        reg signed [41:0] extended;
        begin
            extended = {{5{value[36]}}, value};
            align_scale_s37_to_s42_q24 = value == 0 ? 42'sd0 :
                (extended >>> (total_shift - 7'd24));
        end
    endfunction

    function automatic signed [23:0] round_sat_s42_q24_to_s24_q16;
        input signed [41:0] value;
        reg [42:0] magnitude;
        reg [42:0] rounded_magnitude;
        reg signed [42:0] rounded_value;
        begin
            if (value < 0) begin
                magnitude = -$signed({value[41], value});
                rounded_magnitude = (magnitude + 43'd128) >> 8;
                rounded_value = -$signed(rounded_magnitude);
            end else begin
                magnitude = {1'b0, value};
                rounded_magnitude = (magnitude + 43'd128) >> 8;
                rounded_value = $signed(rounded_magnitude);
            end
            if (rounded_value > 43'sd8388607)
                round_sat_s42_q24_to_s24_q16 = 24'sh7f_ffff;
            else if (rounded_value < -43'sd8388608)
                round_sat_s42_q24_to_s24_q16 = -24'sd8388608;
            else
                round_sat_s42_q24_to_s24_q16 = rounded_value[23:0];
        end
    endfunction

    function automatic s42_q24_to_s24_saturates;
        input signed [41:0] value;
        reg [42:0] magnitude;
        reg [42:0] rounded_magnitude;
        reg signed [42:0] rounded_value;
        begin
            if (value < 0) begin
                magnitude = -$signed({value[41], value});
                rounded_magnitude = (magnitude + 43'd128) >> 8;
                rounded_value = -$signed(rounded_magnitude);
            end else begin
                magnitude = {1'b0, value};
                rounded_magnitude = (magnitude + 43'd128) >> 8;
                rounded_value = $signed(rounded_magnitude);
            end
            s42_q24_to_s24_saturates =
                (rounded_value > 43'sd8388607) ||
                (rounded_value < -43'sd8388608);
        end
    endfunction

    wire signed [42:0] next_accum0_ext =
        (scale2_first_r ? 43'sd0 :
            $signed({accum0_s42_r[41], accum0_s42_r})) +
        $signed({scale2_guard0_r[41], scale2_guard0_r});
    wire signed [42:0] next_accum1_ext =
        (scale2_first_r ? 43'sd0 :
            $signed({accum1_s42_r[41], accum1_s42_r})) +
        $signed({scale2_guard1_r[41], scale2_guard1_r});
    wire signed [41:0] next_accum0_s42 = next_accum0_ext[41:0];
    wire signed [41:0] next_accum1_s42 = next_accum1_ext[41:0];

    hap_rope_pair_s24 u_rope (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(final_valid_r), .in_ready(rope_in_ready),
        .in_x0_s24(final_x0_s24_r), .in_x1_s24(final_x1_s24_r),
        .in_cos_s18(pair_cos_s18_r), .in_sin_s18(pair_sin_s18_r),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_y0_s24(out_y0_s24), .out_y1_s24(out_y1_s24),
        .input_pair_count(rope_input_pair_count),
        .output_pair_count(output_pair_count),
        .saturation_count(rope_saturation_count), .error(rope_error));

    always @(posedge clk) begin
        if (in_fire) begin
            scale0_corr0_r <= in_corr0_s21;
            scale0_corr1_r <= in_corr1_s21;
            scale0_code0_r <= in_act_scale_code *
                in_weight0_scale_code;
            scale0_code1_r <= in_act_scale_code *
                in_weight1_scale_code;
            scale0_shift0_r <= {1'b0, in_act_scale_shift} +
                {1'b0, in_weight0_scale_shift};
            scale0_shift1_r <= {1'b0, in_act_scale_shift} +
                {1'b0, in_weight1_scale_shift};
            scale0_first_r <= in_first_group;
            scale0_last_r <= in_last_group;
        end
        if (scale0_valid_r) begin
            scale1_raw0_r <= scale0_corr0_r *
                $signed({1'b0, scale0_code0_r});
            scale1_raw1_r <= scale0_corr1_r *
                $signed({1'b0, scale0_code1_r});
            scale1_shift0_r <= scale0_shift0_r;
            scale1_shift1_r <= scale0_shift1_r;
            scale1_first_r <= scale0_first_r;
            scale1_last_r <= scale0_last_r;
        end
        if (scale1_valid_r) begin
            scale2_guard0_r <= align_scale_s37_to_s42_q24(
                scale1_raw0_r, scale1_shift0_r);
            scale2_guard1_r <= align_scale_s37_to_s42_q24(
                scale1_raw1_r, scale1_shift1_r);
            scale2_first_r <= scale1_first_r;
            scale2_last_r <= scale1_last_r;
        end
        if (scale2_valid_r) begin
            accum0_s42_r <= next_accum0_s42;
            accum1_s42_r <= next_accum1_s42;
            if (scale2_last_r) begin
                final_x0_s24_r <= round_sat_s42_q24_to_s24_q16(
                    next_accum0_s42);
                final_x1_s24_r <= round_sat_s42_q24_to_s24_q16(
                    next_accum1_s42);
            end
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            accept_cooldown_r <= 1'b0;
            tail_inflight_r <= 1'b0;
            expected_group_r <= '0;
            local_error_r <= 1'b0;
            scale0_valid_r <= 1'b0;
            scale1_valid_r <= 1'b0;
            scale2_valid_r <= 1'b0;
            final_valid_r <= 1'b0;
            pair_cos_s18_r <= '0;
            pair_sin_s18_r <= '0;
            input_group_count <= 32'd0;
            input_pair_count <= 32'd0;
            projection_saturation_count_r <= 32'd0;
        end else if (clear) begin
            accept_cooldown_r <= 1'b0;
            tail_inflight_r <= 1'b0;
            expected_group_r <= '0;
            local_error_r <= 1'b0;
            scale0_valid_r <= 1'b0;
            scale1_valid_r <= 1'b0;
            scale2_valid_r <= 1'b0;
            final_valid_r <= 1'b0;
            pair_cos_s18_r <= '0;
            pair_sin_s18_r <= '0;
            input_group_count <= 32'd0;
            input_pair_count <= 32'd0;
            projection_saturation_count_r <= 32'd0;
        end else begin
            scale0_valid_r <= in_fire;
            scale1_valid_r <= scale0_valid_r;
            scale2_valid_r <= scale1_valid_r;

            if (accept_cooldown_r)
                accept_cooldown_r <= 1'b0;
            if (in_fire)
                accept_cooldown_r <= 1'b1;

            if (in_fire) begin
                input_group_count <= input_group_count + 1'b1;
                if (in_first_group) begin
                    pair_cos_s18_r <= in_cos_s18;
                    pair_sin_s18_r <= in_sin_s18;
                end else if ((in_cos_s18 != pair_cos_s18_r) ||
                             (in_sin_s18 != pair_sin_s18_r)) begin
                    local_error_r <= 1'b1;
                end
                if ((in_first_group != (expected_group_r == 0)) ||
                    (in_last_group != (expected_group_r == GROUPS-1)))
                    local_error_r <= 1'b1;
                if ((in_act_scale_code == 0) ||
                    (in_weight0_scale_code == 0) ||
                    (in_weight1_scale_code == 0) ||
                    (({1'b0,in_act_scale_shift} +
                      {1'b0,in_weight0_scale_shift}) < 26) ||
                    (({1'b0,in_act_scale_shift} +
                      {1'b0,in_weight0_scale_shift}) > 47) ||
                    (({1'b0,in_act_scale_shift} +
                      {1'b0,in_weight1_scale_shift}) < 26) ||
                    (({1'b0,in_act_scale_shift} +
                      {1'b0,in_weight1_scale_shift}) > 47) ||
                    (in_cos_s18 > 18'sd65536) ||
                    (in_cos_s18 < -18'sd65536) ||
                    (in_sin_s18 > 18'sd65536) ||
                    (in_sin_s18 < -18'sd65536))
                    local_error_r <= 1'b1;
                if (expected_group_r == GROUPS-1)
                    expected_group_r <= '0;
                else
                    expected_group_r <= expected_group_r + 1'b1;
                if (in_last_group) begin
                    input_pair_count <= input_pair_count + 1'b1;
                    tail_inflight_r <= 1'b1;
                end
            end

            if (scale2_valid_r) begin
                if ((next_accum0_ext[42] != next_accum0_ext[41]) ||
                    (next_accum1_ext[42] != next_accum1_ext[41]))
                    local_error_r <= 1'b1;
                if (scale2_last_r) begin
                    final_valid_r <= 1'b1;
                    projection_saturation_count_r <=
                        projection_saturation_count_r +
                        s42_q24_to_s24_saturates(next_accum0_s42) +
                        s42_q24_to_s24_saturates(next_accum1_s42);
                end
            end
            if (rope_in_fire)
                final_valid_r <= 1'b0;
            if (out_fire)
                tail_inflight_r <= 1'b0;
            if (final_valid_r && !rope_in_ready && scale2_valid_r &&
                scale2_last_r)
                local_error_r <= 1'b1;
            if (rope_input_pair_count > input_pair_count)
                local_error_r <= 1'b1;
        end
    end

    initial begin
        if (GROUPS != 128)
            $error("M03 boundary workload requires 128 projection groups");
    end
endmodule
