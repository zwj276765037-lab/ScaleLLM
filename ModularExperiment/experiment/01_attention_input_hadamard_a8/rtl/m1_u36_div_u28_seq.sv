`timescale 1ns/1ps

// Saturating unsigned divider with round-to-nearest, ties-to-even.  Only the
// low eight quotient bits are needed by the A8 quantizers.
module m1_u36_div_u28_seq (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         clear,
    input  wire         start,
    input  wire         round_parity_offset,
    input  wire [35:0]  numerator,
    input  wire [27:0]  denominator,
    output reg          busy,
    output reg          done,
    output reg          error,
    output reg  [35:0]  quotient
);
    reg [27:0] divisor_r;
    reg [35:0] remainder_r;
    reg [2:0] bit_index_r;
    reg saturate_r;
    wire [35:0] shifted_divisor = {8'd0, divisor_r} << bit_index_r;
    wire [35:0] input_saturation_threshold =
        ({8'd0, denominator} << 8) - {8'd0, denominator};

    always @(posedge clk or negedge rst_n) begin : p_divide
        reg [35:0] remainder_next;
        reg [35:0] quotient_next;
        reg [36:0] doubled_remainder;
        if (!rst_n) begin
            busy <= 1'b0;
            done <= 1'b0;
            error <= 1'b0;
            quotient <= 36'd0;
            divisor_r <= 28'd0;
            remainder_r <= 36'd0;
            bit_index_r <= 3'd0;
            saturate_r <= 1'b0;
        end else if (clear) begin
            busy <= 1'b0;
            done <= 1'b0;
            error <= 1'b0;
            quotient <= 36'd0;
            remainder_r <= 36'd0;
            bit_index_r <= 3'd0;
            saturate_r <= 1'b0;
        end else begin
            done <= 1'b0;
            if (start && !busy) begin
                if (denominator == 0) begin
                    error <= 1'b1;
                    done <= 1'b1;
                    quotient <= {36{1'b1}};
                end else begin
                    busy <= 1'b1;
                    error <= 1'b0;
                    quotient <= 36'd0;
                    divisor_r <= denominator;
                    remainder_r <= numerator;
                    bit_index_r <= 3'd7;
                    saturate_r <= numerator >= input_saturation_threshold;
                end
            end else if (busy) begin
                if (saturate_r) begin
                    if (bit_index_r == 0)
                        quotient <= {28'd0, 8'hff};
                end else begin
                    remainder_next = remainder_r;
                    quotient_next = quotient;
                    if (remainder_r >= shifted_divisor) begin
                        remainder_next = remainder_r - shifted_divisor;
                        quotient_next[bit_index_r] = 1'b1;
                    end else begin
                        quotient_next[bit_index_r] = 1'b0;
                    end
                    remainder_r <= remainder_next;
                    if (bit_index_r == 0) begin
                        doubled_remainder = {1'b0, remainder_next} << 1;
                        if ((doubled_remainder > {9'd0, divisor_r}) ||
                            ((doubled_remainder == {9'd0, divisor_r}) &&
                             (quotient_next[0] ^ round_parity_offset)))
                            quotient_next = quotient_next + 1'b1;
                    end
                    quotient <= quotient_next;
                end
                if (bit_index_r == 0) begin
                    busy <= 1'b0;
                    done <= 1'b1;
                end else begin
                    bit_index_r <= bit_index_r - 1'b1;
                end
            end
        end
    end
endmodule
