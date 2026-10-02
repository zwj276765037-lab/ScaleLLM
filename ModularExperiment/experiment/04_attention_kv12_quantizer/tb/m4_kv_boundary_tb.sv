`timescale 1ns/1ps

module m4_kv_boundary_tb;
    parameter integer CASE_ID = 0;
    parameter integer BACKPRESSURE = 0;
    parameter DATA_DIR = "data";

    localparam integer BATCHES = 16;
    localparam integer RECORDS_PER_BANK = 32;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    reg [3071:0] in_s24 = 3072'd0;
    reg in_is_v = 1'b0;
    reg [11:0] in_base_addr = 12'd0;
    wire in_ready;
    reg k_rd_valid = 1'b0;
    wire k_rd_ready;
    reg [11:0] k_rd_addr = 12'd0;
    wire k_rsp_valid;
    reg k_rsp_ready = 1'b0;
    reg v_rd_valid = 1'b0;
    wire v_rd_ready;
    reg [11:0] v_rd_addr = 12'd0;
    wire v_rsp_valid;
    reg v_rsp_ready = 1'b0;

    wire [383:0] k_rsp_s12;
    wire [15:0] k_rsp_meta;
    wire [383:0] v_rsp_s12;
    wire [15:0] v_rsp_meta;
    wire [511:0] k_rsp_fp16;
    wire [511:0] v_rsp_fp16;
    wire [1023:0] k_rsp_fp32;
    wire [1023:0] v_rsp_fp32;
    wire [31:0] input_batch_count;
    wire [31:0] output_group_count;
    wire [31:0] converted_lane_count;
    wire [31:0] k_write_count;
    wire [31:0] v_write_count;
    wire [31:0] k_read_count;
    wire [31:0] v_read_count;
    wire [31:0] format_error_count;
    wire error;

    reg [3071:0] input_mem [0:BATCHES-1];
    reg [383:0] expected_s12_mem [0:BATCHES*4-1];
    reg [15:0] expected_meta_mem [0:BATCHES*4-1];
    reg [511:0] expected_fp16_mem [0:BATCHES*4-1];
    reg [1023:0] expected_fp32_mem [0:BATCHES*4-1];

    integer cycle = 0;
    integer batch_sent = 0;
    integer k_request_count = 0;
    integer v_request_count = 0;
    integer k_response_count = 0;
    integer v_response_count = 0;
    integer mismatch_count = 0;
    integer input_stall_cycles = 0;
    integer k_output_stall_cycles = 0;
    integer v_output_stall_cycles = 0;
    integer first_input_cycle = -1;
    integer last_input_cycle = -1;
    integer last_write_cycle = -1;
    integer last_batch_fire_cycle = -1;
    integer batch_ii_min = 1000000;
    integer batch_ii_max = 0;
    integer delta;
    integer read_phase = 0;
    integer done_pending = 0;
    reg [11:0] k_pending_addr = 12'd0;
    reg [11:0] v_pending_addr = 12'd0;
    reg k_was_stalled = 1'b0;
    reg v_was_stalled = 1'b0;
    reg [1023:0] k_hold = 1024'd0;
    reg [1023:0] v_hold = 1024'd0;

    function automatic [11:0] k_address;
        input integer index;
        begin
            k_address = ((index >> 2) * 8) + (index & 3);
        end
    endfunction

    function automatic [11:0] v_address;
        input integer index;
        begin
            v_address = ((index >> 2) * 8) + 4 + (index & 3);
        end
    endfunction

    generate
        if (CASE_ID == 0) begin : g_sc
            assign converted_lane_count = 32'd0;
            m4_sc_kv_boundary_top dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready), .in_s24(in_s24),
                .in_is_v(in_is_v), .in_base_addr(in_base_addr),
                .k_rd_valid(k_rd_valid), .k_rd_ready(k_rd_ready),
                .k_rd_addr(k_rd_addr), .k_rsp_valid(k_rsp_valid),
                .k_rsp_ready(k_rsp_ready), .k_rsp_s12(k_rsp_s12),
                .k_rsp_meta(k_rsp_meta), .v_rd_valid(v_rd_valid),
                .v_rd_ready(v_rd_ready), .v_rd_addr(v_rd_addr),
                .v_rsp_valid(v_rsp_valid), .v_rsp_ready(v_rsp_ready),
                .v_rsp_s12(v_rsp_s12), .v_rsp_meta(v_rsp_meta),
                .input_batch_count(input_batch_count),
                .output_group_count(output_group_count),
                .k_write_count(k_write_count), .v_write_count(v_write_count),
                .k_read_count(k_read_count), .v_read_count(v_read_count),
                .format_error_count(format_error_count), .error(error)
            );
        end else if (CASE_ID == 1) begin : g_fp16
            m4_fp16_kv_boundary_top dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_s24(in_s24), .in_is_v(in_is_v),
                .in_base_addr(in_base_addr), .in_ready(in_ready),
                .k_rd_valid(k_rd_valid), .k_rd_addr(k_rd_addr),
                .k_rd_ready(k_rd_ready), .k_rsp_valid(k_rsp_valid),
                .k_rsp_ready(k_rsp_ready), .k_rsp_fp(k_rsp_fp16),
                .v_rd_valid(v_rd_valid), .v_rd_addr(v_rd_addr),
                .v_rd_ready(v_rd_ready), .v_rsp_valid(v_rsp_valid),
                .v_rsp_ready(v_rsp_ready), .v_rsp_fp(v_rsp_fp16),
                .input_batch_count(input_batch_count),
                .output_group_count(output_group_count),
                .converted_lane_count(converted_lane_count),
                .k_write_count(k_write_count), .v_write_count(v_write_count),
                .k_read_count(k_read_count), .v_read_count(v_read_count),
                .format_error_count(format_error_count), .error(error)
            );
        end else begin : g_fp32
            m4_fp32_kv_boundary_top dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_s24(in_s24), .in_is_v(in_is_v),
                .in_base_addr(in_base_addr), .in_ready(in_ready),
                .k_rd_valid(k_rd_valid), .k_rd_addr(k_rd_addr),
                .k_rd_ready(k_rd_ready), .k_rsp_valid(k_rsp_valid),
                .k_rsp_ready(k_rsp_ready), .k_rsp_fp(k_rsp_fp32),
                .v_rd_valid(v_rd_valid), .v_rd_addr(v_rd_addr),
                .v_rd_ready(v_rd_ready), .v_rsp_valid(v_rsp_valid),
                .v_rsp_ready(v_rsp_ready), .v_rsp_fp(v_rsp_fp32),
                .input_batch_count(input_batch_count),
                .output_group_count(output_group_count),
                .converted_lane_count(converted_lane_count),
                .k_write_count(k_write_count), .v_write_count(v_write_count),
                .k_read_count(k_read_count), .v_read_count(v_read_count),
                .format_error_count(format_error_count), .error(error)
            );
        end
    endgenerate

    always #5 clk = ~clk;

    initial begin
        $readmemh({DATA_DIR, "/input_s24.mem"}, input_mem);
        $readmemh({DATA_DIR, "/expected_s12.mem"}, expected_s12_mem);
        $readmemh({DATA_DIR, "/expected_meta.mem"}, expected_meta_mem);
        $readmemh({DATA_DIR, "/expected_fp16.mem"}, expected_fp16_mem);
        $readmemh({DATA_DIR, "/expected_fp32.mem"}, expected_fp32_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n) begin
            in_valid <= 1'b0;
            k_rd_valid <= 1'b0;
            v_rd_valid <= 1'b0;
            k_rsp_ready <= 1'b0;
            v_rsp_ready <= 1'b0;
        end else begin
            in_valid <= batch_sent < BATCHES;
            if (batch_sent < BATCHES) begin
                in_s24 <= input_mem[batch_sent];
                in_is_v <= batch_sent[0];
                in_base_addr <= batch_sent * 4;
            end
            k_rsp_ready <= (BACKPRESSURE == 0) ||
                !((cycle % 29 >= 19) && (cycle % 29 <= 23));
            v_rsp_ready <= (BACKPRESSURE == 0) ||
                !((cycle % 41 >= 27) && (cycle % 41 <= 34));
            if (read_phase != 0 && k_request_count < RECORDS_PER_BANK) begin
                k_rd_valid <= 1'b1;
                k_rd_addr <= k_address(k_request_count);
            end else begin
                k_rd_valid <= 1'b0;
            end
            if (read_phase != 0 && v_request_count < RECORDS_PER_BANK) begin
                v_rd_valid <= 1'b1;
                v_rd_addr <= v_address(v_request_count);
            end else begin
                v_rd_valid <= 1'b0;
            end
        end
    end

    always @(posedge clk) begin
        if (rst_n) begin
            cycle = cycle + 1;
            if (in_valid && !in_ready)
                input_stall_cycles = input_stall_cycles + 1;
            if (in_valid && in_ready) begin
                if (first_input_cycle < 0) begin
                    first_input_cycle = cycle;
                end else begin
                    delta = cycle - last_batch_fire_cycle;
                    if (delta < batch_ii_min)
                        batch_ii_min = delta;
                    if (delta > batch_ii_max)
                        batch_ii_max = delta;
                end
                last_batch_fire_cycle = cycle;
                last_input_cycle = cycle;
                batch_sent = batch_sent + 1;
            end

            if ((read_phase == 0) && (batch_sent == BATCHES) &&
                    (k_write_count == RECORDS_PER_BANK) &&
                    (v_write_count == RECORDS_PER_BANK)) begin
                read_phase = 1;
                last_write_cycle = cycle;
            end

            if (k_rsp_valid && !k_rsp_ready)
                k_output_stall_cycles = k_output_stall_cycles + 1;
            if (v_rsp_valid && !v_rsp_ready)
                v_output_stall_cycles = v_output_stall_cycles + 1;
            if (k_was_stalled && (!k_rsp_valid ||
                    (CASE_ID == 0 && {k_rsp_meta, k_rsp_s12} !== k_hold[399:0]) ||
                    (CASE_ID == 1 && k_rsp_fp16 !== k_hold[511:0]) ||
                    (CASE_ID == 2 && k_rsp_fp32 !== k_hold))) begin
                $display("FAIL: M4 K response changed under stall");
                $finish;
            end
            if (v_was_stalled && (!v_rsp_valid ||
                    (CASE_ID == 0 && {v_rsp_meta, v_rsp_s12} !== v_hold[399:0]) ||
                    (CASE_ID == 1 && v_rsp_fp16 !== v_hold[511:0]) ||
                    (CASE_ID == 2 && v_rsp_fp32 !== v_hold))) begin
                $display("FAIL: M4 V response changed under stall");
                $finish;
            end
            k_was_stalled = k_rsp_valid && !k_rsp_ready;
            v_was_stalled = v_rsp_valid && !v_rsp_ready;
            if (k_rsp_valid && !k_rsp_ready)
                k_hold = CASE_ID == 0 ? {624'd0, k_rsp_meta, k_rsp_s12} :
                    (CASE_ID == 1 ? {512'd0, k_rsp_fp16} : k_rsp_fp32);
            if (v_rsp_valid && !v_rsp_ready)
                v_hold = CASE_ID == 0 ? {624'd0, v_rsp_meta, v_rsp_s12} :
                    (CASE_ID == 1 ? {512'd0, v_rsp_fp16} : v_rsp_fp32);

            // Validate the old pending address before accepting its successor.
            if (k_rsp_valid && k_rsp_ready) begin
                if ((CASE_ID == 0 &&
                        ({k_rsp_meta, k_rsp_s12} !==
                         {expected_meta_mem[k_pending_addr],
                          expected_s12_mem[k_pending_addr]})) ||
                        (CASE_ID == 1 &&
                         (k_rsp_fp16 !== expected_fp16_mem[k_pending_addr])) ||
                        (CASE_ID == 2 &&
                         (k_rsp_fp32 !== expected_fp32_mem[k_pending_addr]))) begin
                    if (mismatch_count < 12)
                        $display("M4_KV_MISMATCH K case=%0d addr=%0d",
                            CASE_ID, k_pending_addr);
                    mismatch_count = mismatch_count + 1;
                end
                k_response_count = k_response_count + 1;
            end
            if (v_rsp_valid && v_rsp_ready) begin
                if ((CASE_ID == 0 &&
                        ({v_rsp_meta, v_rsp_s12} !==
                         {expected_meta_mem[v_pending_addr],
                          expected_s12_mem[v_pending_addr]})) ||
                        (CASE_ID == 1 &&
                         (v_rsp_fp16 !== expected_fp16_mem[v_pending_addr])) ||
                        (CASE_ID == 2 &&
                         (v_rsp_fp32 !== expected_fp32_mem[v_pending_addr]))) begin
                    if (mismatch_count < 12)
                        $display("M4_KV_MISMATCH V case=%0d addr=%0d",
                            CASE_ID, v_pending_addr);
                    mismatch_count = mismatch_count + 1;
                end
                v_response_count = v_response_count + 1;
            end
            if (k_rd_valid && k_rd_ready) begin
                k_pending_addr = k_rd_addr;
                k_request_count = k_request_count + 1;
            end
            if (v_rd_valid && v_rd_ready) begin
                v_pending_addr = v_rd_addr;
                v_request_count = v_request_count + 1;
            end

            if (error) begin
                $display("FAIL: M4 boundary error case=%0d bp=%0d batches=%0d writes=%0d/%0d reads=%0d/%0d format=%0d",
                    CASE_ID, BACKPRESSURE, batch_sent, k_write_count,
                    v_write_count, k_read_count, v_read_count,
                    format_error_count);
                $finish;
            end
            if ((k_response_count == RECORDS_PER_BANK) &&
                    (v_response_count == RECORDS_PER_BANK) &&
                    (done_pending == 0))
                done_pending = 1;
            if (done_pending == 1) begin
                done_pending = 2;
            end else if (done_pending == 2) begin
                if ((mismatch_count == 0) &&
                        (input_batch_count == BATCHES) &&
                        (output_group_count == BATCHES*4) &&
                        (k_write_count == RECORDS_PER_BANK) &&
                        (v_write_count == RECORDS_PER_BANK) &&
                        (k_read_count == RECORDS_PER_BANK) &&
                        (v_read_count == RECORDS_PER_BANK) &&
                        (format_error_count == 0) &&
                        ((CASE_ID == 0) ||
                         (converted_lane_count == BATCHES*4*32))) begin
                    $display("M4_KV_METRIC_JSON: {\"case_id\":%0d,\"backpressure\":%0d,\"batches\":%0d,\"groups\":%0d,\"mismatches\":%0d,\"batch_ii_min\":%0d,\"batch_ii_max\":%0d,\"first_input_to_last_write_cycles\":%0d,\"last_input_to_last_write_cycles\":%0d,\"input_stall_cycles\":%0d,\"k_output_stall_cycles\":%0d,\"v_output_stall_cycles\":%0d,\"cycles\":%0d}",
                        CASE_ID, BACKPRESSURE, input_batch_count,
                        output_group_count, mismatch_count,
                        batch_ii_min, batch_ii_max,
                        last_write_cycle-first_input_cycle+1,
                        last_write_cycle-last_input_cycle,
                        input_stall_cycles, k_output_stall_cycles,
                        v_output_stall_cycles, cycle-first_input_cycle+1);
                    $display("PASS: M4 KV boundary");
                end else begin
                    $display("FAIL: M4 final case=%0d bp=%0d mis=%0d batches=%0d groups=%0d lanes=%0d kw=%0d vw=%0d kr=%0d vr=%0d format=%0d",
                        CASE_ID, BACKPRESSURE, mismatch_count,
                        input_batch_count, output_group_count,
                        converted_lane_count, k_write_count, v_write_count,
                        k_read_count, v_read_count, format_error_count);
                end
                $finish;
            end
            if (cycle > 20000) begin
                $display("FAIL: M4 timeout case=%0d bp=%0d batches=%0d writes=%0d/%0d req=%0d/%0d rsp=%0d/%0d",
                    CASE_ID, BACKPRESSURE, batch_sent, k_write_count,
                    v_write_count, k_request_count, v_request_count,
                    k_response_count, v_response_count);
                $finish;
            end
        end
    end

    initial begin
        if ((CASE_ID < 0) || (CASE_ID > 2))
            $error("CASE_ID must be 0, 1, or 2");
    end
endmodule
