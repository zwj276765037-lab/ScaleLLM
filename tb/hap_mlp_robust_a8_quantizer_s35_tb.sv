`timescale 1ns / 1ps

module hap_mlp_robust_a8_quantizer_s35_tb;
    localparam integer VECTOR_COUNT = 64;
    localparam integer INPUT_W = 32*35;
    reg clk=1'b0, rst_n=1'b0, clear=1'b0;
    reg in_valid=1'b0, out_ready=1'b0;
    reg [INPUT_W-1:0] in_s35='0;
    wire in_ready, out_valid, error;
    wire [255:0] out_u8;
    wire [23:0] out_meta;
    wire [31:0] input_group_count, output_group_count, cycle_count;
    wire [31:0] format_error_count;
    reg [INPUT_W-1:0] input_mem [0:VECTOR_COUNT-1];
    reg [255:0] expected_u8_mem [0:VECTOR_COUNT-1];
    reg [23:0] expected_meta_mem [0:VECTOR_COUNT-1];
    integer cycle=0, send_index=0, recv_index=0, mismatch_count=0;
    integer group_start=0, max_group_cycles=0, observed_group_cycles=0;
    always #3.3335 clk = ~clk;

    hap_mlp_robust_a8_quantizer_s35 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready), .in_s35(in_s35),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_u8(out_u8), .out_meta(out_meta),
        .input_group_count(input_group_count),
        .output_group_count(output_group_count), .cycle_count(cycle_count),
        .format_error_count(format_error_count), .error(error)
    );

    initial begin
        $readmemh("data/mlp_robust_a8_s35/input_s35.mem", input_mem);
        $readmemh("data/mlp_robust_a8_s35/expected_u8.mem",
            expected_u8_mem);
        $readmemh("data/mlp_robust_a8_s35/expected_meta.mem",
            expected_meta_mem);
        repeat (6) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n) begin
            in_valid <= 1'b0;
            out_ready <= 1'b0;
        end else begin
            out_ready <= ((cycle % 13) != 4) && ((cycle % 13) != 5);
            if (!in_valid && send_index < VECTOR_COUNT && in_ready) begin
                in_s35 <= input_mem[send_index];
                in_valid <= 1'b1;
            end else if (in_valid && in_ready)
                in_valid <= 1'b0;
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle<=0; send_index<=0; recv_index<=0; mismatch_count<=0;
            group_start<=0; max_group_cycles<=0;
        end else begin
            cycle <= cycle + 1;
            if (in_valid && in_ready) begin
                group_start <= cycle;
                send_index <= send_index + 1;
            end
            if (out_valid && out_ready) begin
                observed_group_cycles = cycle-group_start;
                if (observed_group_cycles > max_group_cycles)
                    max_group_cycles <= observed_group_cycles;
                if (out_u8 !== expected_u8_mem[recv_index] ||
                    out_meta !== expected_meta_mem[recv_index]) begin
                    mismatch_count <= mismatch_count + 1;
                    $display("MISMATCH index=%0d got_q=%h exp_q=%h got_meta=%h exp_meta=%h",
                        recv_index, out_u8, expected_u8_mem[recv_index],
                        out_meta, expected_meta_mem[recv_index]);
                end
                recv_index <= recv_index + 1;
                if (recv_index+1 == VECTOR_COUNT) begin
                    if (mismatch_count == 0 &&
                        out_u8 === expected_u8_mem[recv_index] &&
                        out_meta === expected_meta_mem[recv_index] &&
                        format_error_count == 0 && !error)
                        $display("PASS: MLP Robust A8 S35 vectors=%0d max_group_cycles=%0d active_cycles=%0d",
                            VECTOR_COUNT,
                            observed_group_cycles > max_group_cycles ?
                            observed_group_cycles : max_group_cycles,
                            cycle_count);
                    else
                        $display("FAIL: MLP Robust A8 S35 mismatch=%0d format_errors=%0d error=%0d",
                            mismatch_count + ((out_u8 !==
                            expected_u8_mem[recv_index] || out_meta !==
                            expected_meta_mem[recv_index]) ? 1 : 0),
                            format_error_count, error);
                    $finish;
                end
            end
            if (error) begin
                $display("FAIL: unexpected sticky error format_errors=%0d",
                    format_error_count); $finish;
            end
            if (cycle > 30000) begin
                $display("FAIL: timeout send=%0d recv=%0d state=%0d",
                    send_index, recv_index, dut.state_r); $finish;
            end
        end
    end
endmodule
