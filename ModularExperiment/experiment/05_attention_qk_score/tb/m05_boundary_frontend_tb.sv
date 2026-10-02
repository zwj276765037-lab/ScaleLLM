`timescale 1ns / 1ps

module m05_boundary_frontend_tb #(
    parameter integer CASE_ID = 1,
    parameter string DATA_DIR = "data_boundary"
);
    localparam integer FP_W = CASE_ID == 1 ? 16 : 32;
    localparam integer QUERY_RECORDS = 288;
    localparam integer KEY_RECORDS = 16944;
    localparam integer QUERY_TEST = 4;
    localparam integer KEY_TEST = 32;

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg [1:0] phase = 0;
    integer cycle = 0;
    integer query_sent = 0;
    integer key_sent = 0;
    integer query_received = 0;
    integer key_received = 0;
    integer previous_accept_cycle = -1;
    integer ii_min = 999999;
    integer ii_max = 0;
    integer interval;

    reg [767:0] query_s24_mem [0:QUERY_RECORDS-1];
    reg [511:0] query_cache16_mem [0:QUERY_RECORDS-1];
    reg [1023:0] query_cache32_mem [0:QUERY_RECORDS-1];
    reg [383:0] key_s12_mem [0:KEY_RECORDS-1];
    reg [15:0] key_scale16_mem [0:KEY_RECORDS-1];
    reg [31:0] key_scale32_mem [0:KEY_RECORDS-1];
    reg [511:0] key_cache16_mem [0:KEY_RECORDS-1];
    reg [1023:0] key_cache32_mem [0:KEY_RECORDS-1];

    wire in_valid = rst_n &&
        ((phase == 0 && query_sent < QUERY_TEST) ||
         (phase == 2 && key_sent < KEY_TEST));
    wire in_is_key = phase == 2;
    wire [8:0] in_address = in_is_key ? key_sent[8:0] : query_sent[8:0];
    wire signed [767:0] in_query_s24x32 =
        query_s24_mem[query_sent < QUERY_TEST ? query_sent : QUERY_TEST-1];
    wire signed [383:0] in_key_s12x32 =
        key_s12_mem[key_sent < KEY_TEST ? key_sent : KEY_TEST-1];
    wire [FP_W-1:0] in_key_scale_fp;
    generate
        if (FP_W == 16) begin : g_scale16
            assign in_key_scale_fp = key_scale16_mem[
                key_sent < KEY_TEST ? key_sent : KEY_TEST-1];
        end else begin : g_scale32
            assign in_key_scale_fp = key_scale32_mem[
                key_sent < KEY_TEST ? key_sent : KEY_TEST-1];
        end
    endgenerate

    wire in_ready;
    wire out_valid;
    wire out_is_key;
    wire [8:0] out_address;
    wire [32*FP_W-1:0] out_group_fp;
    wire [31:0] input_group_count;
    wire [31:0] output_group_count;
    wire idle;
    wire error;
    wire [1023:0] out_group_extended;

    generate
        if (FP_W == 16) begin : g_out_extend16
            assign out_group_extended = {512'd0,out_group_fp};
        end else begin : g_out_extend32
            assign out_group_extended = out_group_fp;
        end
    endgenerate

    m05_fp_group32_dequant16 #(.FP_W(FP_W)) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_is_key(in_is_key), .in_address(in_address),
        .in_query_s24x32(in_query_s24x32),
        .in_key_s12x32(in_key_s12x32),
        .in_key_scale_fp(in_key_scale_fp),
        .out_valid(out_valid), .out_is_key(out_is_key),
        .out_address(out_address), .out_group_fp(out_group_fp),
        .input_group_count(input_group_count),
        .output_group_count(output_group_count), .idle(idle), .error(error));

    function automatic [1023:0] expected_query;
        input integer index;
        begin
            if (FP_W == 16)
                expected_query = {512'd0,query_cache16_mem[index]};
            else
                expected_query = query_cache32_mem[index];
        end
    endfunction

    function automatic [1023:0] expected_key;
        input integer index;
        begin
            if (FP_W == 16)
                expected_key = {512'd0,key_cache16_mem[index]};
            else
                expected_key = key_cache32_mem[index];
        end
    endfunction

    initial begin
        $readmemh({DATA_DIR,"/query_group_s24.mem"}, query_s24_mem);
        $readmemh({DATA_DIR,"/query_cache_fp16.mem"}, query_cache16_mem);
        $readmemh({DATA_DIR,"/query_cache_fp32.mem"}, query_cache32_mem);
        $readmemh({DATA_DIR,"/key_group_s12.mem"}, key_s12_mem);
        $readmemh({DATA_DIR,"/key_scale_fp16.mem"}, key_scale16_mem);
        $readmemh({DATA_DIR,"/key_scale_fp32.mem"}, key_scale32_mem);
        $readmemh({DATA_DIR,"/key_cache_fp16.mem"}, key_cache16_mem);
        $readmemh({DATA_DIR,"/key_cache_fp32.mem"}, key_cache32_mem);
        repeat (10) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            phase <= 0;
            cycle <= 0;
            query_sent <= 0;
            key_sent <= 0;
            query_received <= 0;
            key_received <= 0;
            previous_accept_cycle <= -1;
            ii_min <= 999999;
            ii_max <= 0;
        end else begin
            cycle <= cycle + 1;
            if (error) begin
                $display("FAIL: M05 boundary frontend sticky error case=%0d cycle=%0d",
                    CASE_ID, cycle);
                $finish;
            end
            if (in_valid && in_ready) begin
                if (previous_accept_cycle >= 0) begin
                    interval = cycle-previous_accept_cycle;
                    if (interval < ii_min)
                        ii_min <= interval;
                    if (interval > ii_max)
                        ii_max <= interval;
                end
                previous_accept_cycle <= cycle;
                if (phase == 0) begin
                    query_sent <= query_sent + 1;
                    if (query_sent + 1 == QUERY_TEST) begin
                        phase <= 1;
                        previous_accept_cycle <= -1;
                    end
                end else begin
                    key_sent <= key_sent + 1;
                    if (key_sent + 1 == KEY_TEST)
                        phase <= 3;
                end
            end
            if (phase == 1 && idle) begin
                phase <= 2;
                previous_accept_cycle <= -1;
            end

            if (out_valid) begin
                if (!out_is_key) begin
                    if (out_address !== query_received[8:0] ||
                        out_group_extended !== expected_query(query_received)) begin
                        $display("FAIL: M05 boundary query mismatch case=%0d index=%0d address=%0d",
                            CASE_ID, query_received, out_address);
                        $finish;
                    end
                    query_received <= query_received + 1;
                end else begin
                    if (out_address !== key_received[8:0] ||
                        out_group_extended !== expected_key(key_received)) begin
                        $display("FAIL: M05 boundary key mismatch case=%0d index=%0d address=%0d",
                            CASE_ID, key_received, out_address);
                        $finish;
                    end
                    key_received <= key_received + 1;
                end
            end

            if (phase == 3 && idle && key_received == KEY_TEST) begin
                if (query_sent != QUERY_TEST || key_sent != KEY_TEST ||
                    query_received != QUERY_TEST ||
                    input_group_count != QUERY_TEST+KEY_TEST ||
                    output_group_count != QUERY_TEST+KEY_TEST ||
                    ii_min != 2 || ii_max != 2) begin
                    $display("FAIL: M05 boundary frontend final gate case=%0d q=%0d/%0d k=%0d/%0d counts=%0d/%0d ii=%0d/%0d",
                        CASE_ID, query_sent, query_received,
                        key_sent, key_received, input_group_count,
                        output_group_count, ii_min, ii_max);
                    $finish;
                end
                $display("M05_BOUNDARY_FRONTEND_METRIC_JSON: {\"case_id\":%0d,\"query_groups\":4,\"key_groups\":32,\"input_ii_min\":%0d,\"input_ii_max\":%0d,\"mismatches\":0,\"total_cycles\":%0d}",
                    CASE_ID, ii_min, ii_max, cycle);
                $display("PASS: M05 boundary FP group32 frontend case=%0d",
                    CASE_ID);
                $finish;
            end
            if (cycle > 5000) begin
                $display("FAIL: M05 boundary frontend timeout case=%0d q=%0d/%0d k=%0d/%0d",
                    CASE_ID, query_sent, query_received,
                    key_sent, key_received);
                $finish;
            end
        end
    end

    initial begin
        if (CASE_ID != 1 && CASE_ID != 2)
            $error("M05 boundary frontend CASE_ID must be 1 or 2");
    end
endmodule
