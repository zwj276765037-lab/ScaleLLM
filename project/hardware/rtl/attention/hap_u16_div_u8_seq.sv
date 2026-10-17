`timescale 1ns / 1ps

module hap_u16_div_u8_seq (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         clear,
    input  wire         start,
    input  wire [15:0]  numerator,
    input  wire [7:0]   denominator,
    output reg          busy,
    output reg          done,
    output reg          error,
    output reg  [15:0]  quotient
);

    reg [15:0] dividend_r;
    reg [7:0] divisor_r;
    reg [8:0] remainder_r;
    reg [4:0] bit_index_r;
    wire [8:0] shifted_remainder =
        {remainder_r[7:0], dividend_r[bit_index_r]};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0;
            done <= 1'b0;
            error <= 1'b0;
            quotient <= 16'd0;
            dividend_r <= 16'd0;
            divisor_r <= 8'd0;
            remainder_r <= 9'd0;
            bit_index_r <= 5'd0;
        end else if (clear) begin
            busy <= 1'b0;
            done <= 1'b0;
            error <= 1'b0;
            quotient <= 16'd0;
            remainder_r <= 9'd0;
            bit_index_r <= 5'd0;
        end else begin
            done <= 1'b0;
            if (start && !busy) begin
                if (denominator == 0) begin
                    error <= 1'b1;
                    done <= 1'b1;
                    quotient <= 16'hffff;
                end else begin
                    busy <= 1'b1;
                    error <= 1'b0;
                    quotient <= 16'd0;
                    dividend_r <= numerator;
                    divisor_r <= denominator;
                    remainder_r <= 9'd0;
                    bit_index_r <= 5'd15;
                end
            end else if (busy) begin
                if (shifted_remainder >= {1'b0, divisor_r}) begin
                    remainder_r <= shifted_remainder - {1'b0, divisor_r};
                    quotient[bit_index_r] <= 1'b1;
                end else begin
                    remainder_r <= shifted_remainder;
                    quotient[bit_index_r] <= 1'b0;
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
