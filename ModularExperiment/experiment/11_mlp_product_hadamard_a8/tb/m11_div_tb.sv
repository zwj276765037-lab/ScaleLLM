`timescale 1ns/1ps

module m11_div_tb;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg start = 1'b0;
    reg round_parity_offset = 1'b0;
    reg [43:0] numerator = 44'd0;
    reg [35:0] denominator = 36'd1;
    wire busy;
    wire done;
    wire error;
    wire [43:0] quotient;
    integer test_count = 0;
    integer mismatch_count = 0;
    reg [63:0] state = 64'h6a09e667f3bcc909;
    reg [43:0] expected;

    function automatic [43:0] round_div_even;
        input [43:0] n;
        input [35:0] d;
        reg [43:0] floor_q;
        reg [35:0] remainder;
        reg [36:0] doubled;
        begin
            floor_q = n / d;
            remainder = n % d;
            doubled = {1'b0, remainder} << 1;
            round_div_even = floor_q;
            if ((doubled > {1'b0, d}) ||
                ((doubled == {1'b0, d}) && floor_q[0]))
                round_div_even = floor_q + 1'b1;
        end
    endfunction

    always #5 clk = ~clk;

    m11_u44_div_u36_radix16 dut (.*);

    task automatic run_case;
        input [43:0] test_numerator;
        input [35:0] test_denominator;
        begin
            while (busy) @(posedge clk);
            @(negedge clk);
            numerator = test_numerator;
            denominator = test_denominator;
            expected = round_div_even(test_numerator, test_denominator);
            start = 1'b1;
            @(negedge clk);
            start = 1'b0;
            while (!done) @(posedge clk);
            #1;
            test_count = test_count + 1;
            if (error || quotient !== expected) begin
                mismatch_count = mismatch_count + 1;
                $display("M11_DIV_MISMATCH n=%h d=%h got=%h expected=%h error=%b",
                    test_numerator, test_denominator, quotient, expected,
                    error);
            end
        end
    endtask

    integer index;
    initial begin
        repeat (5) @(posedge clk);
        rst_n = 1'b1;
        run_case(44'd0, 36'd1);
        run_case(44'd1, 36'd2);
        run_case(44'd3, 36'd2);
        run_case(44'd5, 36'd2);
        run_case(44'd7, 36'd2);
        run_case({44{1'b1}}, 36'd1);
        run_case({44{1'b1}}, {36{1'b1}});
        run_case((44'd255 << 35) + ((36'd1 << 35)-1), 36'd1 << 35);
        run_case(44'h80000000000, 36'h800000000);
        for (index = 0; index < 256; index = index + 1) begin
            state = state ^ (state << 13);
            state = state ^ (state >> 7);
            state = state ^ (state << 17);
            numerator = state[43:0] ^ (index * 44'h102030405);
            state = state ^ (state << 13);
            state = state ^ (state >> 7);
            state = state ^ (state << 17);
            denominator = state[35:0] | 36'd1;
            run_case(numerator, denominator);
        end
        if (mismatch_count == 0) begin
            $display("PASS: M11 radix16 divider cases=%0d mismatches=0",
                test_count);
            $finish;
        end
        $fatal(1, "FAIL: M11 divider mismatches=%0d/%0d",
            mismatch_count, test_count);
    end
endmodule
