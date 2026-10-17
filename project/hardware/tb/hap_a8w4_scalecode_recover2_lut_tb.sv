`timescale 1ns / 1ps

module hap_a8w4_scalecode_recover2_lut_tb;
    localparam integer VECTOR_COUNT = 4096;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    wire in_ready;
    reg signed [16:0] dot0_s17;
    reg signed [16:0] dot1_s17;
    reg [7:0] activation_code_u8;
    reg [7:0] weight0_code_u8;
    reg [7:0] weight1_code_u8;
    wire out_valid;
    reg out_ready = 1'b1;
    wire signed [32:0] raw0_s33;
    wire signed [32:0] raw1_s33;

    reg signed [16:0] expected_dot0 [0:VECTOR_COUNT-1];
    reg signed [16:0] expected_dot1 [0:VECTOR_COUNT-1];
    reg [7:0] expected_act_code [0:VECTOR_COUNT-1];
    reg [7:0] expected_w0_code [0:VECTOR_COUNT-1];
    reg [7:0] expected_w1_code [0:VECTOR_COUNT-1];
    integer send_count = 0;
    integer receive_count = 0;
    integer cycle_count = 0;
    integer mismatch_count = 0;
    integer seed = 32'h5ca1e004;
    integer i;
    reg signed [32:0] expected_raw0;
    reg signed [32:0] expected_raw1;

    // Keep the golden arithmetic wider than the DUT result.  A chained
    // S17*U8*U8 expression is only self-determined to the operand width in
    // SystemVerilog and can silently lose the sign/high bits.
    function automatic signed [32:0] golden_raw_s33;
        input signed [16:0] dot_s17;
        input [7:0] act_code_u8;
        input [7:0] weight_code_u8;
        reg signed [63:0] dot_s64;
        reg signed [63:0] act_code_s64;
        reg signed [63:0] weight_code_s64;
        reg signed [63:0] product_s64;
        begin
            dot_s64 = dot_s17;
            act_code_s64 = $signed({1'b0, act_code_u8});
            weight_code_s64 = $signed({1'b0, weight_code_u8});
            product_s64 = dot_s64 * act_code_s64 * weight_code_s64;
            golden_raw_s33 = product_s64[32:0];
        end
    endfunction

    hap_a8w4_scalecode_recover2_lut dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .dot0_s17(dot0_s17), .dot1_s17(dot1_s17),
        .activation_code_u8(activation_code_u8),
        .weight0_code_u8(weight0_code_u8),
        .weight1_code_u8(weight1_code_u8),
        .out_valid(out_valid), .out_ready(out_ready),
        .raw0_s33(raw0_s33), .raw1_s33(raw1_s33)
    );

    initial begin
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            in_valid <= 1'b0;
            out_ready <= 1'b1;
            send_count <= 0;
            receive_count <= 0;
            cycle_count <= 0;
            mismatch_count <= 0;
        end else begin
            cycle_count <= cycle_count + 1;
            out_ready <= (receive_count < 2048) ? 1'b1 :
                ((cycle_count % 11) != 3);
            if (!in_valid || in_ready) begin
                if (send_count < VECTOR_COUNT) begin
                    if (send_count == 0) begin
                        dot0_s17 <= 17'sd65280;
                        dot1_s17 <= -17'sd65280;
                        activation_code_u8 <= 8'd255;
                        weight0_code_u8 <= 8'd255;
                        weight1_code_u8 <= 8'd255;
                    end else begin
                        dot0_s17 <= ($random(seed) % 65281);
                        dot1_s17 <= ($random(seed) % 65281);
                        activation_code_u8 <= $random(seed);
                        weight0_code_u8 <= $random(seed);
                        weight1_code_u8 <= $random(seed);
                    end
                    in_valid <= 1'b1;
                end else begin
                    in_valid <= 1'b0;
                end
            end
            if (in_valid && in_ready) begin
                expected_dot0[send_count] <= dot0_s17;
                expected_dot1[send_count] <= dot1_s17;
                expected_act_code[send_count] <= activation_code_u8;
                expected_w0_code[send_count] <= weight0_code_u8;
                expected_w1_code[send_count] <= weight1_code_u8;
                send_count <= send_count + 1;
            end
            if (out_valid && out_ready) begin
                expected_raw0 = golden_raw_s33(
                    expected_dot0[receive_count],
                    expected_act_code[receive_count],
                    expected_w0_code[receive_count]);
                expected_raw1 = golden_raw_s33(
                    expected_dot1[receive_count],
                    expected_act_code[receive_count],
                    expected_w1_code[receive_count]);
                if (raw0_s33 !== expected_raw0 ||
                    raw1_s33 !== expected_raw1) begin
                    $display("MISMATCH index=%0d got=%h_%h expected=%h_%h",
                        receive_count, raw1_s33, raw0_s33,
                        expected_raw1, expected_raw0);
                    mismatch_count <= mismatch_count + 1;
                end
                receive_count <= receive_count + 1;
                if (receive_count + 1 == VECTOR_COUNT) begin
                    if (mismatch_count == 0 &&
                        raw0_s33 === expected_raw0 &&
                        raw1_s33 === expected_raw1) begin
                        $display("PASS: hap_a8w4_scalecode_recover2_lut vectors=%0d cycles=%0d mismatches=0",
                            VECTOR_COUNT, cycle_count);
                        $finish;
                    end else begin
                        $fatal(1, "FAIL: mismatches=%0d",
                            mismatch_count + 1);
                    end
                end
            end
            if (cycle_count > 10000) begin
                $fatal(1, "FAIL: timeout send=%0d receive=%0d",
                    send_count, receive_count);
            end
        end
    end
endmodule
