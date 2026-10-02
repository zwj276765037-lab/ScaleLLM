`timescale 1ns / 1ps

// Native-FP Softmax farm beginning at the common S20 Q6.14 score boundary.
// conversion_inflight_r reserves space for values accepted by the nonblocking
// converter but not yet written into score_fifo.  The sideband FIFO aligns
// first/last/mask by transaction order rather than assuming a simulator-only
// fixed delay.
module m06_fp_softmax_boundary #(
    parameter integer FP_W = 16,
    parameter integer CASE_ID = 1,
    parameter integer FIFO_DEPTH = 256,
    parameter integer PTR_W = $clog2(FIFO_DEPTH)
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    output wire                 in_ready,
    input  wire                 in_first_key,
    input  wire                 in_last_key,
    input  wire                 in_mask,
    input  wire signed [19:0]   in_score_s20,
    output wire                 out_valid,
    input  wire                 out_ready,
    output wire [15:0]          out_prob_u16,
    output wire [6:0]           out_key_index,
    output wire                 out_last_key,
    output reg  [31:0]          input_score_count,
    output reg  [31:0]          conversion_score_count,
    output reg  [31:0]          core_input_score_count,
    output wire [31:0]          output_prob_count,
    output wire [31:0]          row_count,
    output reg                  error
);
    localparam integer SCORE_ENTRY_W = FP_W + 3;
    reg [2:0] side_fifo [0:FIFO_DEPTH-1];
    reg [SCORE_ENTRY_W-1:0] score_fifo [0:FIFO_DEPTH-1];
    reg [PTR_W-1:0] side_write_pointer_r;
    reg [PTR_W-1:0] side_read_pointer_r;
    reg [PTR_W-1:0] score_write_pointer_r;
    reg [PTR_W-1:0] score_read_pointer_r;
    reg [PTR_W:0] conversion_inflight_r;
    reg [PTR_W:0] score_fifo_count_r;
    wire [PTR_W+1:0] reserved_count =
        conversion_inflight_r + score_fifo_count_r;
    wire in_fire = in_valid && in_ready;

    wire score32_valid;
    wire [31:0] score_fp32;
    m06_boundary_s20q14_to_fp32 u_fixed_to_fp32 (
        .aclk(clk),
        .s_axis_a_tvalid(in_fire),
        .s_axis_a_tdata(in_score_s20),
        .m_axis_result_tvalid(score32_valid),
        .m_axis_result_tdata(score_fp32));

    wire converted_valid;
    wire [FP_W-1:0] converted_score;
    generate
        if (FP_W == 16) begin : g_narrow
            m06_boundary_fp32_to_fp16 u_narrow (
                .aclk(clk),
                .s_axis_a_tvalid(score32_valid),
                .s_axis_a_tdata(score_fp32),
                .m_axis_result_tvalid(converted_valid),
                .m_axis_result_tdata(converted_score));
        end else begin : g_fp32
            assign converted_valid = score32_valid;
            assign converted_score = score_fp32;
        end
    endgenerate

    wire core_in_ready;
    wire core_error;
    wire core_in_valid = score_fifo_count_r != 0;
    wire core_in_fire = core_in_valid && core_in_ready;
    wire [SCORE_ENTRY_W-1:0] selected_score =
        score_fifo[score_read_pointer_r];
    wire selected_mask = selected_score[FP_W];
    wire selected_last = selected_score[FP_W+1];
    wire selected_first = selected_score[FP_W+2];

    generate
        if (FP_W == 16) begin : g_fp16_farm
            m8_fp16_softmax_x22 u_core (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(core_in_valid), .in_ready(core_in_ready),
                .in_first_key(selected_first),
                .in_last_key(selected_last),
                .in_mask(selected_mask),
                .in_score(selected_score[15:0]),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_prob_u16(out_prob_u16),
                .out_key_index(out_key_index),
                .out_last_key(out_last_key),
                .input_score_count(),
                .output_prob_count(output_prob_count),
                .row_count(row_count), .error(core_error));
        end else begin : g_fp32_farm
            m8_fp32_softmax_x26 u_core (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(core_in_valid), .in_ready(core_in_ready),
                .in_first_key(selected_first),
                .in_last_key(selected_last),
                .in_mask(selected_mask),
                .in_score(selected_score[31:0]),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_prob_u16(out_prob_u16),
                .out_key_index(out_key_index),
                .out_last_key(out_last_key),
                .input_score_count(),
                .output_prob_count(output_prob_count),
                .row_count(row_count), .error(core_error));
        end
    endgenerate

    assign in_ready = rst_n && !clear &&
        reserved_count < FIFO_DEPTH-2;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            side_write_pointer_r <= '0;
            side_read_pointer_r <= '0;
            score_write_pointer_r <= '0;
            score_read_pointer_r <= '0;
            conversion_inflight_r <= '0;
            score_fifo_count_r <= '0;
            input_score_count <= 32'd0;
            conversion_score_count <= 32'd0;
            core_input_score_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            side_write_pointer_r <= '0;
            side_read_pointer_r <= '0;
            score_write_pointer_r <= '0;
            score_read_pointer_r <= '0;
            conversion_inflight_r <= '0;
            score_fifo_count_r <= '0;
            input_score_count <= 32'd0;
            conversion_score_count <= 32'd0;
            core_input_score_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (in_fire) begin
                side_fifo[side_write_pointer_r] <=
                    {in_first_key,in_last_key,in_mask};
                side_write_pointer_r <= side_write_pointer_r + 1'b1;
                input_score_count <= input_score_count + 1'b1;
            end
            if (converted_valid) begin
                score_fifo[score_write_pointer_r] <= {
                    side_fifo[side_read_pointer_r],
                    converted_score
                };
                side_read_pointer_r <= side_read_pointer_r + 1'b1;
                score_write_pointer_r <= score_write_pointer_r + 1'b1;
                conversion_score_count <= conversion_score_count + 1'b1;
            end
            if (core_in_fire) begin
                score_read_pointer_r <= score_read_pointer_r + 1'b1;
                core_input_score_count <= core_input_score_count + 1'b1;
            end

            case ({in_fire,converted_valid})
                2'b10:
                    conversion_inflight_r <= conversion_inflight_r + 1'b1;
                2'b01:
                    conversion_inflight_r <= conversion_inflight_r - 1'b1;
                default:
                    conversion_inflight_r <= conversion_inflight_r;
            endcase
            case ({converted_valid,core_in_fire})
                2'b10: score_fifo_count_r <= score_fifo_count_r + 1'b1;
                2'b01: score_fifo_count_r <= score_fifo_count_r - 1'b1;
                default: score_fifo_count_r <= score_fifo_count_r;
            endcase

            if (core_error ||
                (converted_valid && conversion_inflight_r == 0) ||
                (converted_valid && score_fifo_count_r == FIFO_DEPTH &&
                    !core_in_fire) ||
                (core_in_fire && score_fifo_count_r == 0) ||
                conversion_inflight_r > FIFO_DEPTH ||
                score_fifo_count_r > FIFO_DEPTH)
                error <= 1'b1;
        end
    end

    initial begin
        if (FP_W != 16 && FP_W != 32)
            $error("M06 boundary FP_W must be 16 or 32");
        if ((CASE_ID == 1) != (FP_W == 16))
            $error("M06 boundary CASE_ID/FP_W mismatch");
        if (FIFO_DEPTH < 16 || (FIFO_DEPTH & (FIFO_DEPTH-1)) != 0)
            $error("M06 boundary FIFO_DEPTH must be a power of two >=16");
    end
endmodule


module m06_fp16_softmax_boundary (
    input wire clk, rst_n, clear, in_valid,
    output wire in_ready,
    input wire in_first_key, in_last_key, in_mask,
    input wire signed [19:0] in_score_s20,
    output wire out_valid,
    input wire out_ready,
    output wire [15:0] out_prob_u16,
    output wire [6:0] out_key_index,
    output wire out_last_key,
    output wire [31:0] input_score_count, conversion_score_count,
    core_input_score_count, output_prob_count, row_count,
    output wire error
);
    m06_fp_softmax_boundary #(.FP_W(16), .CASE_ID(1)) u_core (.*);
endmodule


module m06_fp32_softmax_boundary (
    input wire clk, rst_n, clear, in_valid,
    output wire in_ready,
    input wire in_first_key, in_last_key, in_mask,
    input wire signed [19:0] in_score_s20,
    output wire out_valid,
    input wire out_ready,
    output wire [15:0] out_prob_u16,
    output wire [6:0] out_key_index,
    output wire out_last_key,
    output wire [31:0] input_score_count, conversion_score_count,
    core_input_score_count, output_prob_count, row_count,
    output wire error
);
    m06_fp_softmax_boundary #(.FP_W(32), .CASE_ID(2)) u_core (.*);
endmodule


module m06_sc_softmax_boundary (
    input wire clk, rst_n, clear, in_valid,
    output wire in_ready,
    input wire in_first_key, in_last_key, in_mask,
    input wire signed [19:0] in_score_s20,
    output wire out_valid,
    input wire out_ready,
    output wire [15:0] out_prob_u16,
    output wire [6:0] out_key_index,
    output wire out_last_key,
    output wire [31:0] input_score_count, conversion_score_count,
    core_input_score_count, output_prob_count, row_count,
    output wire error
);
    wire busy;
    hap_softmax_row_128 u_core (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_first_key(in_first_key), .in_last_key(in_last_key),
        .in_mask(in_mask), .in_score_q14_s20(in_score_s20),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_prob_u16(out_prob_u16), .out_key_index(out_key_index),
        .out_last_key(out_last_key), .busy(busy),
        .input_score_count(input_score_count),
        .output_prob_count(output_prob_count),
        .row_count(row_count), .error(error));
    assign conversion_score_count = input_score_count;
    assign core_input_score_count = input_score_count;
endmodule
