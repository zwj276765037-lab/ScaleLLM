`timescale 1ns / 1ps

module hap_softmax_recip_u17 (
    input  wire          clk,
    input  wire          rst_n,
    input  wire          clear,
    input  wire          in_valid,
    output wire          in_ready,
    input  wire [23:0]   in_row_sum_u24,
    output wire          out_valid,
    input  wire          out_ready,
    output wire [16:0]   out_recip_u17,
    output reg  [31:0]   input_count,
    output reg  [31:0]   output_count,
    output reg            error
);

    reg divider_start_r;
    reg result_valid_r;
    reg [16:0] result_u17_r;
    reg [32:0] numerator_r;
    reg [23:0] denominator_r;
    wire divider_busy_w;
    wire divider_done_w;
    wire divider_error_w;
    wire [16:0] divider_quotient_w;
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;

    assign in_ready = rst_n && !clear && !divider_busy_w &&
        !divider_start_r && (!result_valid_r || out_ready);
    assign out_valid = rst_n && !clear && result_valid_r;
    assign out_recip_u17 = result_u17_r;

    hap_unsigned_div_seq #(
        .NUM_W(33), .DEN_W(24), .QUOT_W(17)
    ) u_divider (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .start(divider_start_r), .numerator(numerator_r),
        .denominator(denominator_r), .busy(divider_busy_w),
        .done(divider_done_w), .error(divider_error_w),
        .quotient(divider_quotient_w)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            divider_start_r <= 1'b0;
            result_valid_r <= 1'b0;
            result_u17_r <= 17'd0;
            numerator_r <= 33'd0;
            denominator_r <= 24'd0;
            input_count <= 32'd0;
            output_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            divider_start_r <= 1'b0;
            result_valid_r <= 1'b0;
            input_count <= 32'd0;
            output_count <= 32'd0;
            error <= 1'b0;
        end else begin
            divider_start_r <= 1'b0;
            if (out_fire) begin
                result_valid_r <= 1'b0;
                output_count <= output_count + 32'd1;
            end
            if (in_fire) begin
                input_count <= input_count + 32'd1;
                denominator_r <= in_row_sum_u24;
                numerator_r <= 33'h1_0000_0000 +
                    {10'd0, in_row_sum_u24[23:1]};
                divider_start_r <= 1'b1;
                if ((in_row_sum_u24 < 24'd65536) ||
                    (in_row_sum_u24 > 24'd8388608))
                    error <= 1'b1;
            end
            if (divider_done_w) begin
                result_valid_r <= 1'b1;
                result_u17_r <= (divider_quotient_w > 17'd65536) ?
                    17'd65536 : divider_quotient_w;
                if (divider_error_w)
                    error <= 1'b1;
            end
        end
    end

endmodule
