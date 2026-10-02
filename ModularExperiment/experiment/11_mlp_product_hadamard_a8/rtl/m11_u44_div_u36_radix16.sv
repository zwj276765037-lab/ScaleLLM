`timescale 1ns/1ps

// Unsigned 44/36 divider with round-to-nearest, ties-to-even.  Four quotient
// bits are retired per cycle, so a request completes in eleven cycles without
// inferring a combinational '/' operator.  Before final rounding the remainder
// invariant is remainder < denominator.
module m11_u44_div_u36_radix16 (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         clear,
    input  wire         start,
    input  wire         round_parity_offset,
    input  wire [43:0]  numerator,
    input  wire [35:0]  denominator,
    output reg          busy,
    output reg          done,
    output reg          error,
    output reg  [43:0]  quotient
);
    reg [43:0] numerator_shift_r;
    reg [35:0] denominator_r;
    reg [35:0] remainder_r;
    reg [43:0] quotient_work_r;
    reg [3:0] step_r;

    always @(posedge clk or negedge rst_n) begin : p_divide
        reg [39:0] trial_remainder;
        reg [39:0] denominator_ext;
        reg [3:0] quotient_digit;
        reg [43:0] quotient_next;
        reg [40:0] doubled_remainder;
        if (!rst_n) begin
            numerator_shift_r <= 44'd0;
            denominator_r <= 36'd0;
            remainder_r <= 36'd0;
            quotient_work_r <= 44'd0;
            step_r <= 4'd0;
            busy <= 1'b0;
            done <= 1'b0;
            error <= 1'b0;
            quotient <= 44'd0;
        end else if (clear) begin
            numerator_shift_r <= 44'd0;
            denominator_r <= 36'd0;
            remainder_r <= 36'd0;
            quotient_work_r <= 44'd0;
            step_r <= 4'd0;
            busy <= 1'b0;
            done <= 1'b0;
            error <= 1'b0;
            quotient <= 44'd0;
        end else begin
            done <= 1'b0;
            error <= 1'b0;
            if (start && !busy) begin
                if (denominator == 0) begin
                    quotient <= {44{1'b1}};
                    done <= 1'b1;
                    error <= 1'b1;
                end else begin
                    numerator_shift_r <= numerator;
                    denominator_r <= denominator;
                    remainder_r <= 36'd0;
                    quotient_work_r <= 44'd0;
                    step_r <= 4'd0;
                    busy <= 1'b1;
                end
            end else if (busy) begin
                if (start)
                    error <= 1'b1;
                trial_remainder = {remainder_r,
                    numerator_shift_r[43:40]};
                denominator_ext = {4'd0, denominator_r};
                quotient_digit = 4'd0;
                if (trial_remainder >= (denominator_ext << 3)) begin
                    trial_remainder = trial_remainder -
                        (denominator_ext << 3);
                    quotient_digit = quotient_digit + 4'd8;
                end
                if (trial_remainder >= (denominator_ext << 2)) begin
                    trial_remainder = trial_remainder -
                        (denominator_ext << 2);
                    quotient_digit = quotient_digit + 4'd4;
                end
                if (trial_remainder >= (denominator_ext << 1)) begin
                    trial_remainder = trial_remainder -
                        (denominator_ext << 1);
                    quotient_digit = quotient_digit + 4'd2;
                end
                if (trial_remainder >= denominator_ext) begin
                    trial_remainder = trial_remainder - denominator_ext;
                    quotient_digit = quotient_digit + 4'd1;
                end
                quotient_next = {quotient_work_r[39:0], quotient_digit};
                remainder_r <= trial_remainder[35:0];
                numerator_shift_r <= {numerator_shift_r[39:0], 4'd0};
                quotient_work_r <= quotient_next;
                if (step_r == 4'd10) begin
                    doubled_remainder = {1'b0, trial_remainder} << 1;
                    if ((doubled_remainder > {5'd0, denominator_r}) ||
                        ((doubled_remainder == {5'd0, denominator_r}) &&
                         (quotient_next[0] ^ round_parity_offset)))
                        quotient_next = quotient_next + 1'b1;
                    quotient <= quotient_next;
                    busy <= 1'b0;
                    done <= 1'b1;
                    step_r <= 4'd0;
                end else begin
                    step_r <= step_r + 1'b1;
                end
            end
        end
    end
endmodule
