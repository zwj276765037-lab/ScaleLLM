`timescale 1ns / 1ps

module hap_pv_tile16_s43 (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire                  in_first_key,
    input  wire                  in_last_key,
    input  wire [15:0]           in_prob_u16,
    input  wire [16*12-1:0]      in_v16_s12,
    input  wire [15:0]           in_v_meta16,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [16*24-1:0]      out_context16_s24,
    output reg  [31:0]           input_key_count,
    output reg  [31:0]           output_row_count,
    output reg  [31:0]           saturation_count,
    output reg                    error
);

    localparam [1:0] ST_INPUT = 2'd0;
    localparam [1:0] ST_DRAIN = 2'd1;
    localparam [1:0] ST_OUTPUT = 2'd2;
    localparam [1:0] ST_ERROR = 2'd3;
    reg [1:0] state_r;
    reg [7:0] accepted_in_row_r;
    reg s0_valid_r;
    reg s0_first_r;
    reg s0_last_r;
    reg [15:0] s0_prob_u16_r;
    reg [5:0] s0_align_shift_r;
    reg s1_valid_r;
    reg s1_first_r;
    reg s1_last_r;
    reg [5:0] s1_align_shift_r;
    reg s2_valid_r;
    reg s2_first_r;
    reg s2_last_r;
    reg signed [42:0] accum_s43_r [0:15];
    reg signed [23:0] context_s24_r [0:15];
    (* use_dsp = "yes" *) reg signed [19:0] s0_vcode_s20_r [0:15];
    (* use_dsp = "yes" *) reg signed [35:0] s1_raw_s36_r [0:15];
    reg signed [35:0] s2_term_s36_r [0:15];
    wire signed [42:0] final_accum_s43_w [0:15];
    wire [15:0] final_saturation_w;
    integer lane;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire [7:0] in_code_u8 = in_v_meta16[7:0];
    wire [5:0] in_shift_u6 = in_v_meta16[13:8];
    wire in_meta_reserved_error = |in_v_meta16[15:14];
    wire in_zero_scale = (in_code_u8 == 0);

    assign in_ready = rst_n && !clear && (state_r == ST_INPUT);
    assign out_valid = rst_n && !clear && (state_r == ST_OUTPUT);
    generate
        genvar output_lane;
        for (output_lane = 0; output_lane < 16; output_lane = output_lane + 1) begin : g_output
            assign out_context16_s24[output_lane*24 +: 24] =
                context_s24_r[output_lane];
        end
    endgenerate

    function automatic signed [23:0] round_sat_s43_to_s24;
        input signed [42:0] value;
        reg signed [43:0] value_ext;
        reg [43:0] magnitude;
        reg signed [43:0] rounded;
        begin
            value_ext = {value[42], value};
            if (value_ext >= 0)
                rounded = (value_ext + 44'sd128) >>> 8;
            else begin
                magnitude = -value_ext;
                rounded = -$signed((magnitude + 44'd128) >> 8);
            end
            if (rounded > 44'sd8388607)
                round_sat_s43_to_s24 = 24'sh7fffff;
            else if (rounded < -44'sd8388608)
                round_sat_s43_to_s24 = 24'sh800000;
            else
                round_sat_s43_to_s24 = rounded[23:0];
        end
    endfunction

    function automatic s43_to_s24_saturates;
        input signed [42:0] value;
        reg signed [43:0] value_ext;
        reg [43:0] magnitude;
        reg signed [43:0] rounded;
        begin
            value_ext = {value[42], value};
            if (value_ext >= 0)
                rounded = (value_ext + 44'sd128) >>> 8;
            else begin
                magnitude = -value_ext;
                rounded = -$signed((magnitude + 44'd128) >> 8);
            end
            s43_to_s24_saturates = (rounded > 44'sd8388607) ||
                (rounded < -44'sd8388608);
        end
    endfunction

    function automatic [4:0] popcount16;
        input [15:0] bits;
        integer bit_index;
        begin
            popcount16 = 5'd0;
            for (bit_index = 0; bit_index < 16; bit_index = bit_index + 1)
                popcount16 = popcount16 + bits[bit_index];
        end
    endfunction

    generate
        genvar final_lane;
        for (final_lane = 0; final_lane < 16; final_lane = final_lane + 1) begin : g_final
            assign final_accum_s43_w[final_lane] = s2_first_r ?
                {{7{s2_term_s36_r[final_lane][35]}}, s2_term_s36_r[final_lane]} :
                (accum_s43_r[final_lane] +
                    {{7{s2_term_s36_r[final_lane][35]}}, s2_term_s36_r[final_lane]});
            assign final_saturation_w[final_lane] =
                s43_to_s24_saturates(final_accum_s43_w[final_lane]);
        end
    endgenerate

    always @(posedge clk) begin
        if (in_fire) begin
            for (lane = 0; lane < 16; lane = lane + 1)
                s0_vcode_s20_r[lane] <=
                    $signed(in_v16_s12[lane*12 +: 12]) *
                    $signed({1'b0, in_code_u8});
            s0_prob_u16_r <= in_prob_u16;
            s0_align_shift_r <= in_zero_scale ? 6'd0 : in_shift_u6 - 6'd8;
        end
        if (s0_valid_r) begin
            for (lane = 0; lane < 16; lane = lane + 1)
                s1_raw_s36_r[lane] <= s0_vcode_s20_r[lane] *
                    $signed({1'b0, s0_prob_u16_r});
            s1_align_shift_r <= s0_align_shift_r;
        end
        if (s1_valid_r) begin
            for (lane = 0; lane < 16; lane = lane + 1)
                s2_term_s36_r[lane] <=
                    s1_raw_s36_r[lane] >>> s1_align_shift_r;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_INPUT;
            accepted_in_row_r <= 8'd0;
            s0_valid_r <= 1'b0;
            s1_valid_r <= 1'b0;
            s2_valid_r <= 1'b0;
            s0_first_r <= 1'b0;
            s0_last_r <= 1'b0;
            s1_first_r <= 1'b0;
            s1_last_r <= 1'b0;
            s2_first_r <= 1'b0;
            s2_last_r <= 1'b0;
            input_key_count <= 32'd0;
            output_row_count <= 32'd0;
            saturation_count <= 32'd0;
            error <= 1'b0;
            for (lane = 0; lane < 16; lane = lane + 1) begin
                accum_s43_r[lane] <= 43'sd0;
                context_s24_r[lane] <= 24'sd0;
            end
        end else if (clear) begin
            state_r <= ST_INPUT;
            accepted_in_row_r <= 8'd0;
            s0_valid_r <= 1'b0;
            s1_valid_r <= 1'b0;
            s2_valid_r <= 1'b0;
            input_key_count <= 32'd0;
            output_row_count <= 32'd0;
            saturation_count <= 32'd0;
            error <= 1'b0;
            for (lane = 0; lane < 16; lane = lane + 1)
                accum_s43_r[lane] <= 43'sd0;
        end else begin
            s0_valid_r <= in_fire;
            s1_valid_r <= s0_valid_r;
            s2_valid_r <= s1_valid_r;
            if (in_fire) begin
                s0_first_r <= in_first_key;
                s0_last_r <= in_last_key;
                input_key_count <= input_key_count + 32'd1;
                if (in_first_key != (accepted_in_row_r == 0) ||
                    in_meta_reserved_error ||
                    (!in_zero_scale && ((in_shift_u6 < 8) ||
                        (in_shift_u6 > 32))) ||
                    (in_zero_scale && (in_shift_u6 != 0)))
                    error <= 1'b1;
                for (lane = 0; lane < 16; lane = lane + 1)
                    if (($signed(in_v16_s12[lane*12 +: 12]) == -12'sd2048) ||
                        (in_zero_scale &&
                            ($signed(in_v16_s12[lane*12 +: 12]) != 0)))
                        error <= 1'b1;
                if (in_last_key) begin
                    accepted_in_row_r <= 8'd0;
                    state_r <= ST_DRAIN;
                end else begin
                    accepted_in_row_r <= accepted_in_row_r + 1'b1;
                end
            end
            if (s0_valid_r) begin
                s1_first_r <= s0_first_r;
                s1_last_r <= s0_last_r;
            end
            if (s1_valid_r) begin
                s2_first_r <= s1_first_r;
                s2_last_r <= s1_last_r;
            end
            if (s2_valid_r) begin
                for (lane = 0; lane < 16; lane = lane + 1) begin
                    if (s2_first_r)
                        accum_s43_r[lane] <=
                            {{7{s2_term_s36_r[lane][35]}}, s2_term_s36_r[lane]};
                    else
                        accum_s43_r[lane] <= accum_s43_r[lane] +
                            {{7{s2_term_s36_r[lane][35]}}, s2_term_s36_r[lane]};
                    if (s2_last_r) begin
                        context_s24_r[lane] <=
                            round_sat_s43_to_s24(final_accum_s43_w[lane]);
                    end
                end
                if (s2_last_r) begin
                    saturation_count <= saturation_count +
                        popcount16(final_saturation_w);
                    state_r <= ST_OUTPUT;
                end
            end
            if (out_fire) begin
                output_row_count <= output_row_count + 32'd1;
                state_r <= ST_INPUT;
            end
            if (error)
                state_r <= ST_ERROR;
        end
    end

endmodule
