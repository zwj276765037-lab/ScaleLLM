`timescale 1ns/1ps

module m7_qk_arch_tb #(
    parameter integer CASE_ID = 0,
    parameter integer QUERY_START = 0,
    parameter integer VALID_KEYS = 8,
    parameter DATA_DIR = "data_arch"
);
    localparam integer MAX_QUERY_RECORDS = 1024;
    localparam integer MAX_KEY_RECORDS = 131072;
    localparam integer MAX_SCORES = 32768;
    localparam integer EXPECTED_ROWS = 256;
    localparam integer EXPECTED_SCORES =
        32 * (8*QUERY_START + 36);
    localparam integer EXPECTED_KEY_GROUPS = 4 * EXPECTED_SCORES;
    localparam integer EXPECTED_VALUE_RECORDS = 8 * EXPECTED_SCORES;
    localparam integer WATCHDOG_CYCLES = 1200000;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg start = 1'b0;
    wire [9:0] query_addr;
    wire [16:0] key_addr;
    wire query_req, key_req;
    wire busy, done, score_fire, score_mask, score_last, error;
    wire signed [19:0] score;
    wire [6:0] score_key;
    wire [2:0] row, kv_head;
    wire [5:0] head;
    wire [31:0] cycles, pre_pv_frontend_cycles, wait_cycles;
    wire [31:0] query_groups, key_groups, value_records;
    wire [31:0] completed_rows, completed_tiles, clips, context_saturations;

    reg [767:0] query_fixed_mem [0:MAX_QUERY_RECORDS-1];
    reg [511:0] query_fp16_mem [0:MAX_QUERY_RECORDS-1];
    reg [1023:0] query_fp32_mem [0:MAX_QUERY_RECORDS-1];
    reg [383:0] key_fixed_mem [0:MAX_KEY_RECORDS-1];
    reg [15:0] key_meta_mem [0:MAX_KEY_RECORDS-1];
    reg [511:0] key_fp16_mem [0:MAX_KEY_RECORDS-1];
    reg [1023:0] key_fp32_mem [0:MAX_KEY_RECORDS-1];
    reg [19:0] expected_fixed_mem [0:MAX_SCORES-1];
    reg [19:0] expected_fp16_mem [0:MAX_SCORES-1];
    reg [19:0] expected_fp32_mem [0:MAX_SCORES-1];

    integer tb_cycles = 0;
    integer score_count = 0;
    integer mismatch_count = 0;
    integer address_mismatch_count = 0;
    integer query_request_count = 0;
    integer key_request_count = 0;
    integer unique_query_address_count = 0;
    integer unique_key_address_count = 0;
    integer first_cycle = -1;
    integer row_score_base = 0;
    integer expected_index;
    reg [19:0] expected_score;
    reg query_address_seen [0:MAX_QUERY_RECORDS-1];
    reg key_address_seen [0:4095];
    integer query_address_access_count [0:MAX_QUERY_RECORDS-1];
    integer key_address_access_count [0:4095];
    integer expected_query_addr;
    integer expected_key_addr;
    integer expected_unique_key_addresses;
    integer expected_address_accesses;
    integer kv_i;
    integer key_i;
    integer group_i;
    integer row_i;

    always #3.3335 clk = ~clk;

    m7_attention_accel_arch #(
        .CASE_ID(CASE_ID), .QUERY_START(QUERY_START),
        .VALID_KEYS(VALID_KEYS)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear), .start(start),
        .query_record_addr(query_addr),
        .query_record_fixed(query_fixed_mem[query_addr]),
        .query_record_fp16(query_fp16_mem[query_addr]),
        .query_record_fp32(query_fp32_mem[query_addr]),
        .key_record_addr(key_addr),
        .key_record_fixed(key_fixed_mem[key_addr]),
        .key_meta_fixed(key_meta_mem[key_addr]),
        .key_record_fp16(key_fp16_mem[key_addr]),
        .key_record_fp32(key_fp32_mem[key_addr]),
        .query_record_req(query_req), .key_record_req(key_req),
        .busy(busy), .done(done), .attention_row(row),
        .attention_head(head), .attention_kv_head(kv_head),
        .launch_cycle_count(cycles),
        .pre_pv_frontend_cycle_count(pre_pv_frontend_cycles),
        .scheduler_wait_cycle_count(wait_cycles),
        .query_group_count(query_groups), .key_group_count(key_groups),
        .value_record_count(value_records),
        .completed_row_count(completed_rows),
        .completed_context_tile_count(completed_tiles),
        .score_fire(score_fire), .score_q14_s20(score),
        .score_mask(score_mask), .score_key_index(score_key),
        .score_last_key(score_last), .score_clip_count(clips),
        .context_saturation_count(context_saturations), .error(error));

    initial begin
        for (kv_i = 0; kv_i < MAX_QUERY_RECORDS; kv_i = kv_i + 1) begin
            query_address_seen[kv_i] = 1'b0;
            query_address_access_count[kv_i] = 0;
        end
        for (kv_i = 0; kv_i < 4096; kv_i = kv_i + 1) begin
            key_address_seen[kv_i] = 1'b0;
            key_address_access_count[kv_i] = 0;
        end
        expected_unique_key_addresses = 0;
        for (kv_i = 0; kv_i < 8; kv_i = kv_i + 1)
            for (key_i = 0; key_i < VALID_KEYS; key_i = key_i + 1)
                if (key_i < QUERY_START + 8)
                    for (group_i = 0; group_i < 4;
                            group_i = group_i + 1)
                        expected_unique_key_addresses =
                            expected_unique_key_addresses + 1;
        $readmemh({DATA_DIR, "/query_group_fixed.mem"}, query_fixed_mem);
        $readmemh({DATA_DIR, "/query_group_fp16.mem"}, query_fp16_mem);
        $readmemh({DATA_DIR, "/query_group_fp32.mem"}, query_fp32_mem);
        $readmemh({DATA_DIR, "/key_group_fixed.mem"}, key_fixed_mem);
        $readmemh({DATA_DIR, "/key_meta_fixed.mem"}, key_meta_mem);
        $readmemh({DATA_DIR, "/key_group_fp16.mem"}, key_fp16_mem);
        $readmemh({DATA_DIR, "/key_group_fp32.mem"}, key_fp32_mem);
        $readmemh({DATA_DIR, "/expected_fixed.mem"}, expected_fixed_mem);
        $readmemh({DATA_DIR, "/expected_fp16.mem"}, expected_fp16_mem);
        $readmemh({DATA_DIR, "/expected_fp32.mem"}, expected_fp32_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
        repeat (3) @(posedge clk);
        start <= 1'b1;
        @(posedge clk);
        start <= 1'b0;
    end

    always @(posedge clk) begin
        if (rst_n) begin
            tb_cycles <= tb_cycles + 1;
            if (busy && first_cycle < 0)
                first_cycle = tb_cycles;
            if (error) begin
                $display("FAIL: M7 ARCH DUT error case=%0d row=%0d head=%0d score_count=%0d", CASE_ID, row, head, score_count);
                $finish;
            end
            if (kv_head !== head[4:2]) begin
                if (address_mismatch_count < 12)
                    $display("ADDRESS_MISMATCH GQA row=%0d head=%0d expected_kv=%0d got_kv=%0d", row, head, head[4:2], kv_head);
                address_mismatch_count = address_mismatch_count + 1;
            end
            if (query_req) begin
                expected_query_addr = (row * 128) + (head * 4) +
                    dut.attention_query_group_r[1:0];
                query_request_count = query_request_count + 1;
                query_address_access_count[query_addr] =
                    query_address_access_count[query_addr] + 1;
                if (query_addr !== expected_query_addr[9:0]) begin
                    if (address_mismatch_count < 12)
                        $display("ADDRESS_MISMATCH Q row=%0d head=%0d group=%0d expected=%0d got=%0d", row, head, dut.attention_query_group_r[1:0], expected_query_addr, query_addr);
                    address_mismatch_count = address_mismatch_count + 1;
                end
                if (!query_address_seen[query_addr]) begin
                    query_address_seen[query_addr] = 1'b1;
                    unique_query_address_count =
                        unique_query_address_count + 1;
                end
            end
            if (key_req) begin
                expected_key_addr = (kv_head * 512) +
                    (dut.attention_key_r * 4) +
                    dut.attention_key_group_r[1:0];
                key_request_count = key_request_count + 1;
                key_address_access_count[key_addr[11:0]] =
                    key_address_access_count[key_addr[11:0]] + 1;
                if ((key_addr[16:12] !== 5'd0) ||
                        (key_addr[11:0] !== expected_key_addr[11:0])) begin
                    if (address_mismatch_count < 12)
                        $display("ADDRESS_MISMATCH K row=%0d head=%0d kv=%0d key=%0d group=%0d expected=%0d got=%0d", row, head, kv_head, dut.attention_key_r, dut.attention_key_group_r[1:0], expected_key_addr, key_addr);
                    address_mismatch_count = address_mismatch_count + 1;
                end
                if (!key_address_seen[key_addr[11:0]]) begin
                    key_address_seen[key_addr[11:0]] = 1'b1;
                    unique_key_address_count = unique_key_address_count + 1;
                end
            end
            if (score_fire) begin
                // Vectors are packed row-major then head-major.  Each head
                // owns QUERY_START+row+1 scores in the supported workloads.
                expected_index = row_score_base + head * (QUERY_START + row + 1) + score_key;
                case (CASE_ID)
                    0: expected_score = expected_fixed_mem[expected_index];
                    1: expected_score = expected_fp16_mem[expected_index];
                    default: expected_score = expected_fp32_mem[expected_index];
                endcase
                if ((score !== expected_score) || score_mask ||
                    (score_last !== (score_key == QUERY_START + row))) begin
                    if (mismatch_count < 12)
                        $display("MISMATCH case=%0d row=%0d head=%0d kv=%0d key=%0d expected=%h got=%h mask=%0d last=%0d", CASE_ID, row, head, kv_head, score_key, expected_score, score, score_mask, score_last);
                    mismatch_count <= mismatch_count + 1;
                end
                score_count <= score_count + 1;
                if (score_last && (head == 31))
                    row_score_base <= row_score_base +
                        32 * (QUERY_START + row + 1);
            end
            if (done) begin
                // Audit the complete address multiset independently of score
                // ordering.  Each Q record is requested once.  A semantic K
                // record is reused by four Q heads for every query row whose
                // causal window includes that token.
                for (expected_query_addr = 0;
                        expected_query_addr < MAX_QUERY_RECORDS;
                        expected_query_addr = expected_query_addr + 1)
                    if (query_address_access_count[expected_query_addr] != 1) begin
                        if (address_mismatch_count < 12)
                            $display("ADDRESS_COUNT_MISMATCH Q addr=%0d expected=1 got=%0d", expected_query_addr, query_address_access_count[expected_query_addr]);
                        address_mismatch_count =
                            address_mismatch_count + 1;
                    end
                for (kv_i = 0; kv_i < 8; kv_i = kv_i + 1)
                    for (key_i = 0; key_i < 128; key_i = key_i + 1)
                        for (group_i = 0; group_i < 4;
                                group_i = group_i + 1) begin
                            expected_address_accesses = 0;
                            for (row_i = 0; row_i < 8;
                                    row_i = row_i + 1)
                                if ((key_i < VALID_KEYS) &&
                                        (key_i < QUERY_START + row_i + 1))
                                    expected_address_accesses =
                                        expected_address_accesses + 4;
                            expected_key_addr = (kv_i * 512) +
                                (key_i * 4) + group_i;
                            if (key_address_access_count[expected_key_addr] !=
                                    expected_address_accesses) begin
                                if (address_mismatch_count < 12)
                                    $display("ADDRESS_COUNT_MISMATCH K addr=%0d kv=%0d key=%0d group=%0d expected=%0d got=%0d", expected_key_addr, kv_i, key_i, group_i, expected_address_accesses, key_address_access_count[expected_key_addr]);
                                address_mismatch_count =
                                    address_mismatch_count + 1;
                            end
                        end
                $display("M7_QK_ARCH_METRIC_JSON: {\"case_id\":%0d,\"query_start\":%0d,\"valid_keys\":%0d,\"logical_rows\":%0d,\"scores\":%0d,\"query_groups\":%0d,\"key_groups\":%0d,\"value_records\":%0d,\"context_tiles\":%0d,\"launch_cycles\":%0d,\"pre_pv_frontend_cycles\":%0d,\"scheduler_wait_cycles\":%0d,\"score_mismatches\":%0d,\"address_mismatches\":%0d,\"query_requests\":%0d,\"key_requests\":%0d,\"unique_query_addresses\":%0d,\"unique_key_addresses\":%0d,\"score_clips\":%0d,\"context_saturations\":%0d}", CASE_ID, QUERY_START, VALID_KEYS, completed_rows, score_count, query_groups, key_groups, value_records, completed_tiles, cycles, pre_pv_frontend_cycles, wait_cycles, mismatch_count, address_mismatch_count, query_request_count, key_request_count, unique_query_address_count, unique_key_address_count, clips, context_saturations);
                if ((mismatch_count == 0) &&
                    (address_mismatch_count == 0) &&
                    (completed_rows == EXPECTED_ROWS) &&
                    (completed_tiles == EXPECTED_ROWS*8) &&
                    (score_count == EXPECTED_SCORES) &&
                    (query_groups == EXPECTED_ROWS*4) &&
                    (key_groups == EXPECTED_KEY_GROUPS) &&
                    (query_request_count == EXPECTED_ROWS*4) &&
                    (key_request_count == EXPECTED_KEY_GROUPS) &&
                    (unique_query_address_count == EXPECTED_ROWS*4) &&
                    (unique_key_address_count ==
                     expected_unique_key_addresses) &&
                    (value_records == EXPECTED_VALUE_RECORDS) &&
                    (context_saturations == 0))
                    $display("PASS: M7 architecture-level attention launch");
                else
                    $display("FAIL: M7 ARCH final rows=%0d tiles=%0d scores=%0d q=%0d k=%0d v=%0d score_mis=%0d addr_mis=%0d q_req=%0d k_req=%0d uq=%0d uk=%0d expected_uk=%0d", completed_rows, completed_tiles, score_count, query_groups, key_groups, value_records, mismatch_count, address_mismatch_count, query_request_count, key_request_count, unique_query_address_count, unique_key_address_count, expected_unique_key_addresses);
                $finish;
            end
            if (tb_cycles > WATCHDOG_CYCLES) begin
                $display("FAIL: M7 ARCH timeout case=%0d busy=%0d row=%0d head=%0d scores=%0d cycles=%0d", CASE_ID, busy, row, head, score_count, cycles);
                $finish;
            end
        end
    end
endmodule
