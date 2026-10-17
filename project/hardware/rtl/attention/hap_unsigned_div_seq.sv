`timescale 1ns / 1ps

module hap_unsigned_div_seq #(
    parameter integer NUM_W = 35,
    parameter integer DEN_W = 24,
    parameter integer QUOT_W = 12
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 start,
    input  wire [NUM_W-1:0]     numerator,
    input  wire [DEN_W-1:0]     denominator,
    output reg                  busy,
    output reg                  done,
    output reg                  error,
    output reg  [QUOT_W-1:0]    quotient
);

    localparam integer INDEX_W = $clog2(NUM_W);
    reg [NUM_W-1:0] dividend_r;
    reg [DEN_W-1:0] divisor_r;
    reg [DEN_W:0] remainder_r;
    reg [INDEX_W-1:0] bit_index_r;
    wire [DEN_W:0] shifted_remainder =
        {remainder_r[DEN_W-1:0], dividend_r[bit_index_r]};
    wire quotient_bit = shifted_remainder >= {1'b0, divisor_r};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0;
            done <= 1'b0;
            error <= 1'b0;
            quotient <= '0;
            dividend_r <= '0;
            divisor_r <= '0;
            remainder_r <= '0;
            bit_index_r <= '0;
        end else if (clear) begin
            busy <= 1'b0;
            done <= 1'b0;
            error <= 1'b0;
            quotient <= '0;
            remainder_r <= '0;
            bit_index_r <= '0;
        end else begin
            done <= 1'b0;
            if (start && !busy) begin
                quotient <= '0;
                remainder_r <= '0;
                if (denominator == 0) begin
                    busy <= 1'b0;
                    done <= 1'b1;
                    error <= 1'b1;
                end else begin
                    busy <= 1'b1;
                    error <= 1'b0;
                    dividend_r <= numerator;
                    divisor_r <= denominator;
                    bit_index_r <= NUM_W - 1;
                end
            end else if (busy) begin
                if (quotient_bit) begin
                    remainder_r <= shifted_remainder - {1'b0, divisor_r};
                    if (bit_index_r < QUOT_W)
                        quotient[bit_index_r] <= 1'b1;
                    else
                        error <= 1'b1;
                end else begin
                    remainder_r <= shifted_remainder;
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
