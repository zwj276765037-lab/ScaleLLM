`timescale 1ns / 1ps

module m1_frontend_benchmark_tb #(
    parameter integer DIRECT = 0
);
    localparam integer ROWS = 8;
    localparam integer GROUP_SIZE = 32;
    localparam integer GROUP_COUNT = 128;
    localparam integer INPUT_W = ROWS * GROUP_SIZE * 24;
    localparam integer DATA_W = ROWS * GROUP_SIZE * 8;
    localparam integer META_W = ROWS * 24;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire [6:0] in_group;
    wire [INPUT_W-1:0] in_s24;
    wire rd_req_valid;
    wire rd_req_ready;
    wire [6:0] rd_req_group;
    wire rd_rsp_valid;
    wire [6:0] rd_rsp_group;
    wire [DATA_W-1:0] rd_rsp_u8;
    wire [META_W-1:0] rd_rsp_meta;
    wire [1:0] bank_ready;
    wire [31:0] input_group_count;
    wire [31:0] cache_write_count;
    wire [31:0] cache_read_count;
    wire [31:0] cache_release_count;
    wire [31:0] hadamard_saturation_count;
    wire error;

    reg [INPUT_W-1:0] input_mem [0:GROUP_COUNT-1];
    reg [DATA_W-1:0] expected_u8_mem [0:GROUP_COUNT-1];
    reg [META_W-1:0] expected_meta_mem [0:GROUP_COUNT-1];
    integer cycle = 0;
    integer send_index = 0;
    integer request_index = 0;
    integer receive_count = 0;
    integer mismatch_count = 0;
    integer input_wait_cycles = 0;
    integer first_accept_cycle = -1;
    integer last_accept_cycle = -1;
    integer first_write_cycle = -1;
    integer last_write_cycle = -1;
    integer previous_accept_cycle = -1;
    integer accept_interval_min = 32'h7fff_ffff;
    integer accept_interval_max = 0;
    integer interval;
    integer previous_write_count = 0;

    always #3.3335 clk = ~clk;
    assign in_valid = rst_n && (send_index < GROUP_COUNT);
    assign in_group = send_index[6:0];
    assign in_s24 = input_mem[send_index];
    assign rd_req_valid = rst_n && bank_ready[0] &&
        (request_index < GROUP_COUNT);
    assign rd_req_group = request_index[6:0];

    generate
        if (DIRECT != 0) begin : g_direct
            initial begin
                $readmemh("data/direct_u8.mem", expected_u8_mem);
                $readmemh("data/direct_meta.mem", expected_meta_mem);
            end
            hap_attention_frontend_direct_a8_8row dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready), .in_bank(1'b0),
                .in_group(in_group), .in_s24(in_s24),
                .rd_req_valid(rd_req_valid), .rd_req_ready(rd_req_ready),
                .rd_req_bank(1'b0), .rd_req_group(rd_req_group),
                .rd_rsp_valid(rd_rsp_valid), .rd_rsp_ready(1'b1),
                .rd_rsp_bank(), .rd_rsp_group(rd_rsp_group),
                .rd_rsp_u8(rd_rsp_u8), .rd_rsp_meta(rd_rsp_meta),
                .release_valid(1'b0), .release_ready(), .release_bank(1'b0),
                .bank_ready(bank_ready), .input_group_count(input_group_count),
                .cache_write_count(cache_write_count),
                .cache_read_count(cache_read_count),
                .cache_release_count(cache_release_count),
                .hadamard_saturation_count(hadamard_saturation_count),
                .error(error)
            );
        end else begin : g_proposed
            initial begin
                $readmemh("data/proposed_u8.mem", expected_u8_mem);
                $readmemh("data/proposed_meta.mem", expected_meta_mem);
            end
            hap_attention_frontend_8row dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready), .in_bank(1'b0),
                .in_group(in_group), .in_s24(in_s24),
                .rd_req_valid(rd_req_valid), .rd_req_ready(rd_req_ready),
                .rd_req_bank(1'b0), .rd_req_group(rd_req_group),
                .rd_rsp_valid(rd_rsp_valid), .rd_rsp_ready(1'b1),
                .rd_rsp_bank(), .rd_rsp_group(rd_rsp_group),
                .rd_rsp_u8(rd_rsp_u8), .rd_rsp_meta(rd_rsp_meta),
                .release_valid(1'b0), .release_ready(), .release_bank(1'b0),
                .bank_ready(bank_ready), .input_group_count(input_group_count),
                .cache_write_count(cache_write_count),
                .cache_read_count(cache_read_count),
                .cache_release_count(cache_release_count),
                .hadamard_saturation_count(hadamard_saturation_count),
                .error(error)
            );
        end
    endgenerate

    initial begin
        $readmemh("data/input_s24.mem", input_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            send_index <= 0;
            request_index <= 0;
            receive_count <= 0;
            mismatch_count <= 0;
            input_wait_cycles <= 0;
            first_accept_cycle <= -1;
            last_accept_cycle <= -1;
            first_write_cycle <= -1;
            last_write_cycle <= -1;
            previous_accept_cycle <= -1;
            accept_interval_min <= 32'h7fff_ffff;
            accept_interval_max <= 0;
            previous_write_count <= 0;
        end else begin
            cycle <= cycle + 1;
            if (in_valid && in_ready) begin
                if (first_accept_cycle < 0)
                    first_accept_cycle <= cycle;
                last_accept_cycle <= cycle;
                if (previous_accept_cycle >= 0) begin
                    interval = cycle - previous_accept_cycle;
                    if (interval < accept_interval_min)
                        accept_interval_min <= interval;
                    if (interval > accept_interval_max)
                        accept_interval_max <= interval;
                end
                previous_accept_cycle <= cycle;
                send_index <= send_index + 1;
            end else if (in_valid) begin
                input_wait_cycles <= input_wait_cycles + 1;
            end

            if (cache_write_count != previous_write_count) begin
                if (first_write_cycle < 0)
                    first_write_cycle <= cycle;
                last_write_cycle <= cycle;
                previous_write_count <= cache_write_count;
            end
            if (rd_req_valid && rd_req_ready)
                request_index <= request_index + 1;
            if (rd_rsp_valid) begin
                if ((rd_rsp_u8 !== expected_u8_mem[rd_rsp_group]) ||
                    (rd_rsp_meta !== expected_meta_mem[rd_rsp_group])) begin
                    mismatch_count <= mismatch_count + 1;
                    $display("MISMATCH: direct=%0d group=%0d", DIRECT,
                        rd_rsp_group);
                end
                receive_count <= receive_count + 1;
            end
            if (error) begin
                $display("FAIL: M1 frontend direct=%0d error cycle=%0d",
                    DIRECT, cycle);
                $finish;
            end
            if (cycle > 80000) begin
                $display("FAIL: M1 frontend direct=%0d timeout", DIRECT);
                $finish;
            end
            if ((receive_count == GROUP_COUNT-1) && rd_rsp_valid) begin
                if ((mismatch_count != 0) ||
                    (rd_rsp_u8 !== expected_u8_mem[rd_rsp_group]) ||
                    (rd_rsp_meta !== expected_meta_mem[rd_rsp_group]) ||
                    (input_group_count != GROUP_COUNT) ||
                    (cache_write_count != GROUP_COUNT)) begin
                    $display("FAIL: M1 frontend direct=%0d mismatch=%0d input=%0d write=%0d",
                        DIRECT, mismatch_count, input_group_count,
                        cache_write_count);
                end else begin
                    $display("M1_FRONTEND_BENCH_METRIC_JSON: {\"case\":\"%s\",\"groups\":128,\"rows\":8,\"mismatches\":0,\"first_group_latency\":%0d,\"first_accept_cycle\":%0d,\"last_accept_cycle\":%0d,\"last_write_cycle\":%0d,\"frontend_cycles\":%0d,\"accept_interval_min\":%0d,\"accept_interval_max\":%0d,\"input_wait_cycles\":%0d,\"hadamard_saturations\":%0d}",
                        DIRECT ? "direct_robust_a8" : "hadamard_robust_a8",
                        first_write_cycle-first_accept_cycle,
                        first_accept_cycle, last_accept_cycle,
                        last_write_cycle,
                        last_write_cycle-first_accept_cycle+1,
                        accept_interval_min, accept_interval_max,
                        input_wait_cycles, hadamard_saturation_count);
                    $display("PASS: M1 frontend intrinsic benchmark direct=%0d", DIRECT);
                end
                $finish;
            end
        end
    end
endmodule

module m1_frontend_proposed_tb;
    m1_frontend_benchmark_tb #(.DIRECT(0)) bench();
endmodule

module m1_frontend_direct_tb;
    m1_frontend_benchmark_tb #(.DIRECT(1)) bench();
endmodule

