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
            if (error) begin
                if (format_error_count == 1 && out_valid &&
                    out_u8 == 256'd0 && out_meta == 24'd0)
                    $display("PASS: MLP Robust A8 S35 rejected unencodable ScaleCode range format_errors=1 cycles=%0d",
                        cycle);
                else
                    $display("FAIL: malformed format error state count=%0d out_valid=%0d q=%h meta=%h",
                        format_error_count, out_valid, out_u8, out_meta);
                $finish;
            end
            if (cycle>500) begin
                $display("FAIL: format error timeout state=%0d diff=%0d",
                    dut.state_r, dut.diff_r); $finish;
            end
        end
    end
endmodule
