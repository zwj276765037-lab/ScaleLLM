`timescale 1ns / 1ps

// Native-FP PV farm beginning at the common U16 probability + S12x16 V +
// ScaleCode metadata boundary.  The front end converts probability and V to
// FP, reconstructs the exact code/2^shift scale as FP32, applies that scale
// to every V lane, and only then enters the previously validated FP farm.
module m07_fp_pv_boundary #(
    parameter integer FP_W = 16,
    parameter integer CASE_ID = 1,
    parameter integer FIFO_DEPTH = 64,
    parameter integer PTR_W = $clog2(FIFO_DEPTH)
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    output wire                 in_ready,
    input  wire                 in_first_key,
    input  wire                 in_last_key,
    input  wire [15:0]          in_prob_u16,
    input  wire [16*12-1:0]     in_v16_s12,
    input  wire [15:0]          in_v_meta16,
    output wire                 out_valid,
    input  wire                 out_ready,
    output wire [16*24-1:0]     out_context16_s24,
    output reg  [31:0]          input_key_count,
    output reg  [31:0]          conversion_key_count,
    output reg  [31:0]          core_input_key_count,
    output wire [31:0]          output_row_count,
    output wire [31:0]          saturation_count,
    output reg                  error
);
    localparam integer META_W = 34;
    localparam integer ALIGN_W = FP_W + 2;
    localparam integer FINAL_W = 17*FP_W + 2;

    reg [META_W-1:0] meta_fifo [0:FIFO_DEPTH-1];
    reg [1:0] narrow_side_fifo [0:FIFO_DEPTH-1];
    reg [ALIGN_W-1:0] align_fifo [0:FIFO_DEPTH-1];
    reg [FINAL_W-1:0] final_fifo [0:FIFO_DEPTH-1];
    reg [PTR_W-1:0] meta_write_pointer_r;
    reg [PTR_W-1:0] meta_read_pointer_r;
    reg [PTR_W-1:0] narrow_write_pointer_r;
    reg [PTR_W-1:0] narrow_read_pointer_r;
    reg [PTR_W-1:0] align_write_pointer_r;
    reg [PTR_W-1:0] align_read_pointer_r;
    reg [PTR_W-1:0] final_write_pointer_r;
    reg [PTR_W-1:0] final_read_pointer_r;
    reg [PTR_W:0] reserved_count_r;
    reg [PTR_W:0] final_fifo_count_r;

    wire [7:0] scale_code = in_v_meta16[7:0];
    wire [5:0] scale_shift = in_v_meta16[13:8];
    wire scale_reserved_error = |in_v_meta16[15:14];
    wire zero_scale = scale_code == 0;

    function automatic [31:0] scale_meta_to_fp32;
        input [7:0] code;
        input [5:0] shift;
        integer bit_index;
        integer msb_index;
        integer biased_exponent;
        reg [31:0] normalized;
        begin
            if (code == 0) begin
                scale_meta_to_fp32 = 32'd0;
            end else begin
                msb_index = 0;
                for (bit_index = 0; bit_index < 8;
                        bit_index = bit_index + 1)
                    if (code[bit_index])
                        msb_index = bit_index;
                biased_exponent = msb_index - shift + 127;
                normalized = {24'd0,code} << (23-msb_index);
                scale_meta_to_fp32 = {
                    1'b0,biased_exponent[7:0],normalized[22:0]
                };
            end
        end
    endfunction

    wire [31:0] input_scale_fp32 =
        scale_meta_to_fp32(scale_code,scale_shift);
    wire in_fire = in_valid && in_ready;

    wire prob32_valid;
    wire [31:0] probability_fp32;
    wire [15:0] value32_valid;
    wire [16*32-1:0] value_fp32;
    m07_boundary_u17q16_to_fp32 u_probability_fixed (
        .aclk(clk),
        .s_axis_a_tvalid(in_fire),
        .s_axis_a_tdata({1'b0,in_prob_u16}),
        .m_axis_result_tvalid(prob32_valid),
        .m_axis_result_tdata(probability_fp32));
    genvar conversion_lane;
    generate
        for (conversion_lane = 0; conversion_lane < 16;
                conversion_lane = conversion_lane + 1) begin : g_value_fixed
            m07_boundary_s12_to_fp32 u_value_fixed (
                .aclk(clk),
                .s_axis_a_tvalid(in_fire),
                .s_axis_a_tdata(
                    in_v16_s12[conversion_lane*12 +: 12]),
                .m_axis_result_tvalid(value32_valid[conversion_lane]),
                .m_axis_result_tdata(
                    value_fp32[conversion_lane*32 +: 32]));
        end
    endgenerate
    wire fixed_event = prob32_valid && (&value32_valid);
    wire fixed_valid_mismatch =
        value32_valid != {16{prob32_valid}};

    wire [META_W-1:0] selected_meta =
        meta_fifo[meta_read_pointer_r];
    wire [1:0] selected_meta_side = selected_meta[33:32];
    wire [31:0] selected_meta_scale = selected_meta[31:0];

    wire probability16_valid;
    wire [15:0] probability_fp16;
    wire scale16_valid;
    wire [15:0] scale_fp16;
    wire [15:0] value16_valid;
    wire [16*16-1:0] value_fp16;
    generate
        if (FP_W == 16) begin : g_fp16_prepare
            m07_boundary_fp32_to_fp16 u_probability_narrow (
                .aclk(clk),
                .s_axis_a_tvalid(fixed_event),
                .s_axis_a_tdata(probability_fp32),
                .m_axis_result_tvalid(probability16_valid),
                .m_axis_result_tdata(probability_fp16));
            m07_boundary_fp32_to_fp16 u_scale_narrow (
                .aclk(clk),
                .s_axis_a_tvalid(fixed_event),
                .s_axis_a_tdata(selected_meta_scale),
                .m_axis_result_tvalid(scale16_valid),
                .m_axis_result_tdata(scale_fp16));
            for (conversion_lane = 0; conversion_lane < 16;
                    conversion_lane = conversion_lane + 1) begin : g_value_narrow
                m07_boundary_fp32_to_fp16 u_value_narrow (
                    .aclk(clk),
                    .s_axis_a_tvalid(fixed_event),
                    .s_axis_a_tdata(
                        value_fp32[conversion_lane*32 +: 32]),
                    .m_axis_result_tvalid(
                        value16_valid[conversion_lane]),
                    .m_axis_result_tdata(
                        value_fp16[conversion_lane*16 +: 16]));
            end
        end else begin : g_no_narrow
            assign probability16_valid = 1'b0;
            assign probability_fp16 = 16'd0;
            assign scale16_valid = 1'b0;
            assign scale_fp16 = 16'd0;
            assign value16_valid = 16'd0;
            assign value_fp16 = 256'd0;
        end
    endgenerate

    wire narrow_event = probability16_valid && scale16_valid &&
        (&value16_valid);
    wire narrow_valid_mismatch = FP_W == 16 &&
        ((scale16_valid != probability16_valid) ||
         (value16_valid != {16{probability16_valid}}));
    wire prepared_valid = FP_W == 16 ? narrow_event : fixed_event;
    wire [1:0] prepared_side = FP_W == 16 ?
        narrow_side_fifo[narrow_read_pointer_r] : selected_meta_side;
    wire [FP_W-1:0] prepared_probability = FP_W == 16 ?
        probability_fp16 : probability_fp32;
    wire [FP_W-1:0] prepared_scale = FP_W == 16 ?
        scale_fp16 : selected_meta_scale;
    wire [16*FP_W-1:0] prepared_value = FP_W == 16 ?
        value_fp16 : value_fp32;

    wire [15:0] value_scaled_valid;
    wire [16*FP_W-1:0] value_scaled;
    generate
        for (conversion_lane = 0; conversion_lane < 16;
                conversion_lane = conversion_lane + 1) begin : g_value_scale
            if (FP_W == 16) begin : g_fp16
                m9_f16_mul u_scale_mul (
                    .aclk(clk),
                    .s_axis_a_tvalid(prepared_valid),
                    .s_axis_a_tdata(
                        prepared_value[conversion_lane*FP_W +: FP_W]),
                    .s_axis_b_tvalid(prepared_valid),
                    .s_axis_b_tdata(prepared_scale),
                    .m_axis_result_tvalid(
                        value_scaled_valid[conversion_lane]),
                    .m_axis_result_tdata(
                        value_scaled[conversion_lane*FP_W +: FP_W]));
            end else begin : g_fp32
                m9_f32_mul u_scale_mul (
                    .aclk(clk),
                    .s_axis_a_tvalid(prepared_valid),
                    .s_axis_a_tdata(
                        prepared_value[conversion_lane*FP_W +: FP_W]),
                    .s_axis_b_tvalid(prepared_valid),
                    .s_axis_b_tdata(prepared_scale),
                    .m_axis_result_tvalid(
                        value_scaled_valid[conversion_lane]),
                    .m_axis_result_tdata(
                        value_scaled[conversion_lane*FP_W +: FP_W]));
            end
        end
    endgenerate
    wire conversion_event = &value_scaled_valid;
    wire scale_valid_mismatch =
        value_scaled_valid != {16{value_scaled_valid[0]}};

    wire [ALIGN_W-1:0] selected_align =
        align_fifo[align_read_pointer_r];
    wire [1:0] converted_side =
        selected_align[FP_W+1:FP_W];
    wire [FP_W-1:0] converted_probability =
        selected_align[FP_W-1:0];

    wire [FINAL_W-1:0] selected_final =
        final_fifo[final_read_pointer_r];
    wire [1:0] core_side =
        selected_final[FINAL_W-1 -: 2];
    wire [FP_W-1:0] core_probability =
        selected_final[16*FP_W +: FP_W];
    wire [16*FP_W-1:0] core_value =
        selected_final[0 +: 16*FP_W];
    wire core_in_valid = final_fifo_count_r != 0;
    wire core_in_ready;
    wire core_in_fire = core_in_valid && core_in_ready;
    wire core_error;

    generate
        if (FP_W == 16) begin : g_fp16_farm
            m9_fp16_pv_x19 u_core (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(core_in_valid), .in_ready(core_in_ready),
                .in_first_key(core_side[1]),
                .in_last_key(core_side[0]),
                .in_prob(core_probability), .in_v(core_value),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_context16_s24(out_context16_s24),
                .input_key_count(),
                .output_row_count(output_row_count),
                .saturation_count(saturation_count),
                .error(core_error));
        end else begin : g_fp32_farm
            m9_fp32_pv_x21 u_core (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(core_in_valid), .in_ready(core_in_ready),
                .in_first_key(core_side[1]),
                .in_last_key(core_side[0]),
                .in_prob(core_probability), .in_v(core_value),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_context16_s24(out_context16_s24),
                .input_key_count(),
                .output_row_count(output_row_count),
                .saturation_count(saturation_count),
                .error(core_error));
        end
    endgenerate

    assign in_ready = rst_n && !clear &&
        reserved_count_r < FIFO_DEPTH-2;

    integer input_lane;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            meta_write_pointer_r <= '0;
            meta_read_pointer_r <= '0;
            narrow_write_pointer_r <= '0;
            narrow_read_pointer_r <= '0;
            align_write_pointer_r <= '0;
            align_read_pointer_r <= '0;
            final_write_pointer_r <= '0;
            final_read_pointer_r <= '0;
            reserved_count_r <= '0;
            final_fifo_count_r <= '0;
            input_key_count <= 32'd0;
            conversion_key_count <= 32'd0;
            core_input_key_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            meta_write_pointer_r <= '0;
            meta_read_pointer_r <= '0;
            narrow_write_pointer_r <= '0;
            narrow_read_pointer_r <= '0;
            align_write_pointer_r <= '0;
            align_read_pointer_r <= '0;
            final_write_pointer_r <= '0;
            final_read_pointer_r <= '0;
            reserved_count_r <= '0;
            final_fifo_count_r <= '0;
            input_key_count <= 32'd0;
            conversion_key_count <= 32'd0;
            core_input_key_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (in_fire) begin
                meta_fifo[meta_write_pointer_r] <= {
                    in_first_key,in_last_key,input_scale_fp32
                };
                meta_write_pointer_r <= meta_write_pointer_r + 1'b1;
                input_key_count <= input_key_count + 1'b1;
            end
            if (fixed_event) begin
                meta_read_pointer_r <= meta_read_pointer_r + 1'b1;
                if (FP_W == 16) begin
                    narrow_side_fifo[narrow_write_pointer_r] <=
                        selected_meta_side;
                    narrow_write_pointer_r <=
                        narrow_write_pointer_r + 1'b1;
                end
            end
            if (prepared_valid) begin
                align_fifo[align_write_pointer_r] <= {
                    prepared_side,prepared_probability
                };
                align_write_pointer_r <= align_write_pointer_r + 1'b1;
                if (FP_W == 16)
                    narrow_read_pointer_r <=
                        narrow_read_pointer_r + 1'b1;
            end
            if (conversion_event) begin
                final_fifo[final_write_pointer_r] <= {
                    converted_side,converted_probability,value_scaled
                };
                align_read_pointer_r <= align_read_pointer_r + 1'b1;
                final_write_pointer_r <= final_write_pointer_r + 1'b1;
                conversion_key_count <= conversion_key_count + 1'b1;
            end
            if (core_in_fire) begin
                final_read_pointer_r <= final_read_pointer_r + 1'b1;
                core_input_key_count <= core_input_key_count + 1'b1;
            end

            case ({in_fire,core_in_fire})
                2'b10: reserved_count_r <= reserved_count_r + 1'b1;
                2'b01: reserved_count_r <= reserved_count_r - 1'b1;
                default: reserved_count_r <= reserved_count_r;
            endcase
            case ({conversion_event,core_in_fire})
                2'b10: final_fifo_count_r <= final_fifo_count_r + 1'b1;
                2'b01: final_fifo_count_r <= final_fifo_count_r - 1'b1;
                default: final_fifo_count_r <= final_fifo_count_r;
            endcase

            if (core_error || fixed_valid_mismatch ||
                    narrow_valid_mismatch || scale_valid_mismatch ||
                    (fixed_event && reserved_count_r == 0) ||
                    (conversion_event && reserved_count_r == 0) ||
                    (conversion_event &&
                        final_fifo_count_r == FIFO_DEPTH && !core_in_fire) ||
                    (core_in_fire && final_fifo_count_r == 0) ||
                    reserved_count_r > FIFO_DEPTH ||
                    final_fifo_count_r > FIFO_DEPTH ||
                    (in_fire && (scale_reserved_error ||
                        (!zero_scale &&
                            (scale_shift < 8 || scale_shift > 32)) ||
                        (zero_scale && scale_shift != 0))))
                error <= 1'b1;
            if (in_fire) begin
                for (input_lane = 0; input_lane < 16;
                        input_lane = input_lane + 1)
                    if ($signed(in_v16_s12[input_lane*12 +: 12]) ==
                            -12'sd2048 ||
                        (zero_scale &&
                         $signed(in_v16_s12[input_lane*12 +: 12]) != 0))
                        error <= 1'b1;
            end
        end
    end

    initial begin
        if (FP_W != 16 && FP_W != 32)
            $error("M07 boundary FP_W must be 16 or 32");
        if ((CASE_ID == 1) != (FP_W == 16))
            $error("M07 boundary CASE_ID/FP_W mismatch");
        if (FIFO_DEPTH < 32 || (FIFO_DEPTH & (FIFO_DEPTH-1)) != 0)
            $error("M07 boundary FIFO_DEPTH must be a power of two >=32");
    end
endmodule


module m07_fp16_pv_boundary (
    input wire clk, rst_n, clear, in_valid,
    output wire in_ready,
    input wire in_first_key, in_last_key,
    input wire [15:0] in_prob_u16,
    input wire [191:0] in_v16_s12,
    input wire [15:0] in_v_meta16,
    output wire out_valid,
    input wire out_ready,
    output wire [383:0] out_context16_s24,
    output wire [31:0] input_key_count, conversion_key_count,
    core_input_key_count, output_row_count, saturation_count,
    output wire error
);
    m07_fp_pv_boundary #(.FP_W(16), .CASE_ID(1)) u_core (.*);
endmodule


module m07_fp32_pv_boundary (
    input wire clk, rst_n, clear, in_valid,
    output wire in_ready,
    input wire in_first_key, in_last_key,
    input wire [15:0] in_prob_u16,
    input wire [191:0] in_v16_s12,
    input wire [15:0] in_v_meta16,
    output wire out_valid,
    input wire out_ready,
    output wire [383:0] out_context16_s24,
    output wire [31:0] input_key_count, conversion_key_count,
    core_input_key_count, output_row_count, saturation_count,
    output wire error
);
    m07_fp_pv_boundary #(.FP_W(32), .CASE_ID(2)) u_core (.*);
endmodule


module m07_sc_pv_boundary (
    input wire clk, rst_n, clear, in_valid,
    output wire in_ready,
    input wire in_first_key, in_last_key,
    input wire [15:0] in_prob_u16,
    input wire [191:0] in_v16_s12,
    input wire [15:0] in_v_meta16,
    output wire out_valid,
    input wire out_ready,
    output wire [383:0] out_context16_s24,
    output wire [31:0] input_key_count, conversion_key_count,
    core_input_key_count, output_row_count, saturation_count,
    output wire error
);
    hap_pv_tile16_s43 u_core (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_first_key(in_first_key), .in_last_key(in_last_key),
        .in_prob_u16(in_prob_u16), .in_v16_s12(in_v16_s12),
        .in_v_meta16(in_v_meta16),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_context16_s24(out_context16_s24),
        .input_key_count(input_key_count),
        .output_row_count(output_row_count),
        .saturation_count(saturation_count), .error(error));
    assign conversion_key_count = input_key_count;
    assign core_input_key_count = input_key_count;
endmodule
