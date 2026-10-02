`timescale 1ns / 1ps

module m1_hadamard_benchmark_tb;
    localparam integer VECTOR_COUNT = 96;
    localparam integer INPUT_W = 32*24;
    localparam integer OUTPUT_W = 32*27;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    wire in_valid;
    wire in_ready;
    wire [INPUT_W-1:0] in_s24;
    wire out_valid;
    wire [OUTPUT_W-1:0] out_s27;
    wire [31:0] input_group_count;
    wire [31:0] output_group_count;
    wire [31:0] saturation_count;
    wire error;
    reg [INPUT_W-1:0] input_mem [0:VECTOR_COUNT-1];
    reg [OUTPUT_W-1:0] expected_mem [0:VECTOR_COUNT-1];
    integer accept_cycle [0:VECTOR_COUNT-1];
    integer cycle = 0;
    integer sent = 0;
    integer received = 0;
    integer mismatch = 0;
    integer first_accept = -1;
    integer previous_accept = -1;
    integer interval_min = 32'h7fff_ffff;
    integer interval_max = 0;
    integer latency_min = 32'h7fff_ffff;
    integer latency_max = 0;
    integer latency_sum = 0;
    integer value;

    always #3.3335 clk = ~clk;
    assign in_valid = rst_n && (sent < VECTOR_COUNT);
    assign in_s24 = input_mem[sent];
    hap_hadamard32_norm_stream #(.FIFO_DEPTH(8)) dut (
        .clk(clk), .rst_n(rst_n), .clear(1'b0),
        .in_valid(in_valid), .in_ready(in_ready), .in_s24(in_s24),
        .out_valid(out_valid), .out_ready(1'b1), .out_s27(out_s27),
        .input_group_count(input_group_count),
        .output_group_count(output_group_count),
        .saturation_count(saturation_count), .error(error)
    );
    initial begin
        $readmemh("hap_data/hadamard32/input.mem", input_mem);
        $readmemh("hap_data/hadamard32/expected.mem", expected_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end
    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0; sent <= 0; received <= 0; mismatch <= 0;
        end else begin
            cycle <= cycle + 1;
            if (in_valid && in_ready) begin
                accept_cycle[sent] = cycle;
                if (first_accept < 0) first_accept = cycle;
                if (previous_accept >= 0) begin
                    value = cycle - previous_accept;
                    if (value < interval_min) interval_min = value;
                    if (value > interval_max) interval_max = value;
                end
                previous_accept = cycle;
                sent <= sent + 1;
            end
            if (out_valid) begin
                value = cycle - accept_cycle[received];
                latency_sum = latency_sum + value;
                if (value < latency_min) latency_min = value;
                if (value > latency_max) latency_max = value;
                if (out_s27 !== expected_mem[received]) mismatch <= mismatch + 1;
                received <= received + 1;
                if (received == VECTOR_COUNT-1) begin
                    if (mismatch != 0 || out_s27 !== expected_mem[received] ||
                        error || saturation_count != 0) begin
                        $display("FAIL: M1 Hadamard intrinsic mismatch=%0d", mismatch);
                    end else begin
                        $display("M1_SINGLE_METRIC_JSON: {\"case\":\"hadamard_only\",\"vectors\":96,\"mismatches\":0,\"latency_min\":%0d,\"latency_mean\":%0f,\"latency_max\":%0d,\"ii_min\":%0d,\"ii_max\":%0d,\"total_cycles\":%0d}",
                            latency_min, latency_sum*1.0/VECTOR_COUNT,
                            (value > latency_max) ? value : latency_max,
                            interval_min, interval_max, cycle-first_accept+1);
                        $display("PASS: M1 Hadamard intrinsic benchmark.");
                    end
                    $finish;
                end
            end
            if (error || cycle > 1000) begin
                $display("FAIL: M1 Hadamard intrinsic error/timeout");
                $finish;
            end
        end
    end
endmodule

module m1_robust_a8_benchmark_tb;
    localparam integer VECTOR_COUNT = 48;
    localparam integer INPUT_W = 32*27;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    wire in_valid;
    wire in_ready;
    wire [INPUT_W-1:0] in_s27;
    wire out_valid;
    wire [255:0] out_u8;
    wire [23:0] out_meta;
    wire [31:0] input_group_count;
    wire [31:0] output_group_count;
    wire [31:0] cycle_count;
    wire error;
    reg [INPUT_W-1:0] input_mem [0:VECTOR_COUNT-1];
    reg [255:0] expected_q_mem [0:VECTOR_COUNT-1];
    reg [23:0] expected_meta_mem [0:VECTOR_COUNT-1];
    integer accept_cycle [0:VECTOR_COUNT-1];
    integer cycle = 0;
    integer sent = 0;
    integer received = 0;
    integer mismatch = 0;
    integer first_accept = -1;
    integer previous_accept = -1;
    integer interval_min = 32'h7fff_ffff;
    integer interval_max = 0;
    integer latency_min = 32'h7fff_ffff;
    integer latency_max = 0;
    integer latency_sum = 0;
    integer value;

    always #3.3335 clk = ~clk;
    assign in_valid = rst_n && (sent < VECTOR_COUNT);
    assign in_s27 = input_mem[sent];
    hap_robust_a8_quantizer dut (
        .clk(clk), .rst_n(rst_n), .clear(1'b0),
        .in_valid(in_valid), .in_ready(in_ready), .in_s27(in_s27),
        .out_valid(out_valid), .out_ready(1'b1), .out_u8(out_u8),
        .out_meta(out_meta), .input_group_count(input_group_count),
        .output_group_count(output_group_count), .cycle_count(cycle_count),
        .error(error)
    );
    initial begin
        $readmemh("hap_data/robust_a8/input.mem", input_mem);
        $readmemh("hap_data/robust_a8/expected_q.mem", expected_q_mem);
        $readmemh("hap_data/robust_a8/expected_meta.mem", expected_meta_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end
    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0; sent <= 0; received <= 0; mismatch <= 0;
        end else begin
            cycle <= cycle + 1;
            if (in_valid && in_ready) begin
                accept_cycle[sent] = cycle;
                if (first_accept < 0) first_accept = cycle;
                if (previous_accept >= 0) begin
                    value = cycle - previous_accept;
                    if (value < interval_min) interval_min = value;
                    if (value > interval_max) interval_max = value;
                end
                previous_accept = cycle;
                sent <= sent + 1;
            end
            if (out_valid) begin
                value = cycle - accept_cycle[received];
                latency_sum = latency_sum + value;
                if (value < latency_min) latency_min = value;
                if (value > latency_max) latency_max = value;
                if ((out_u8 !== expected_q_mem[received]) ||
                    (out_meta !== expected_meta_mem[received])) mismatch <= mismatch + 1;
                received <= received + 1;
                if (received == VECTOR_COUNT-1) begin
                    if (mismatch != 0 || out_u8 !== expected_q_mem[received] ||
                        out_meta !== expected_meta_mem[received] || error) begin
                        $display("FAIL: M1 Robust A8 intrinsic mismatch=%0d", mismatch);
                    end else begin
                        $display("M1_SINGLE_METRIC_JSON: {\"case\":\"direct_robust_a8_group\",\"vectors\":48,\"mismatches\":0,\"latency_min\":%0d,\"latency_mean\":%0f,\"latency_max\":%0d,\"accept_interval_min\":%0d,\"accept_interval_max\":%0d,\"total_cycles\":%0d,\"dut_active_cycles\":%0d}",
                            latency_min, latency_sum*1.0/VECTOR_COUNT,
                            (value > latency_max) ? value : latency_max,
                            interval_min, interval_max, cycle-first_accept+1,
                            cycle_count);
                        $display("PASS: M1 Robust A8 intrinsic benchmark.");
                    end
                    $finish;
                end
            end
            if (error || cycle > 20000) begin
                $display("FAIL: M1 Robust A8 intrinsic error/timeout");
                $finish;
            end
        end
    end
endmodule
