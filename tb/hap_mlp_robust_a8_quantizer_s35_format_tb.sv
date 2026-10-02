`timescale 1ns / 1ps

module hap_mlp_robust_a8_quantizer_s35_format_tb;
    reg clk=1'b0, rst_n=1'b0, clear=1'b0, in_valid=1'b0;
    reg [32*35-1:0] in_s35='0;
    wire in_ready, out_valid, error;
    wire [255:0] out_u8;
    wire [23:0] out_meta;
    wire [31:0] input_group_count, output_group_count, cycle_count;
    wire [31:0] format_error_count;
    integer lane, cycle=0;
    always #3.3335 clk=~clk;

    hap_mlp_robust_a8_quantizer_s35 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready), .in_s35(in_s35),
        .out_valid(out_valid), .out_ready(1'b1),
        .out_u8(out_u8), .out_meta(out_meta),
        .input_group_count(input_group_count),
        .output_group_count(output_group_count), .cycle_count(cycle_count),
        .format_error_count(format_error_count), .error(error)
    );

    initial begin
        for (lane=0; lane<32; lane=lane+1)
            in_s35[lane*35 +: 35] = lane[0] ?
                -35'sd17179869184 : 35'sd17179869183;
        repeat (6) @(posedge clk);
        rst_n <= 1'b1;
        @(posedge clk);
        in_valid <= 1'b1;
        do @(posedge clk); while (!in_ready);
        in_valid <= 1'b0;
    end

    always @(posedge clk) begin
        if (rst_n) begin
            cycle <= cycle+1;
            if (out_valid) begin
                if (!error && format_error_count == 1 &&
                        out_meta == 24'h00ff80) begin
                    for (lane=0; lane<32; lane=lane+1)
                        if (out_u8[lane*8 +: 8] !==
                                (lane[0] ? 8'd0 : 8'd255))
                            $fatal(1, "FAIL: S35 full-range U8 lane=%0d got=%0d",
                                lane, out_u8[lane*8 +: 8]);
                    $display("PASS: MLP MinMax A8 S35 saturated ScaleCode metadata while preserving ideal U8 format_events=1 cycles=%0d",
                        cycle);
                    $finish;
                end else begin
                    $fatal(1, "FAIL: malformed format saturation state count=%0d error=%0d q=%h meta=%h",
                        format_error_count, error, out_u8, out_meta);
                end
            end
            if (cycle>500) begin
                $fatal(1, "FAIL: format saturation timeout state=%0d diff=%0d",
                    dut.state_r, dut.diff_r);
            end
        end
    end
endmodule
