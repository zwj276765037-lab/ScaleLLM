`timescale 1ns / 1ps

module m09_gate_up_serial_ooc_wrapper_tb #(
    parameter integer CASE_ID = 0,
    parameter integer BACKPRESSURE = 1,
    parameter string DATA_DIR = "data"
);
    localparam integer GROUPS = 128;
    localparam integer TRANSACTIONS = 1536;
    localparam integer LOAD_WORDS = CASE_ID == 2 ? 28 : 26;
    localparam integer RESULT_WORDS = 18;

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg load_valid = 1'b0;
    reg [255:0] load_data = '0;
    reg result_ready = 1'b0;
    wire load_ready;
    wire result_valid;
    wire [255:0] result_data;
    wire result_last;
    wire [31:0] input_group_count;
    wire [31:0] output_tile_count;
    wire error;

    reg [4607:0] activation_mem [0:TRANSACTIONS-1];
    reg [1535:0] weight_mem [0:TRANSACTIONS-1];
    reg [223:0] activation_sc_mem [0:TRANSACTIONS-1];
    reg [167:0] weight_sc_mem [0:TRANSACTIONS-1];
    reg [255:0] activation_fp16_mem [0:TRANSACTIONS-1];
    reg [191:0] weight_fp16_mem [0:TRANSACTIONS-1];
    reg [511:0] activation_fp32_mem [0:TRANSACTIONS-1];
    reg [383:0] weight_fp32_mem [0:TRANSACTIONS-1];
    reg [11:0] mask_mem [0:TRANSACTIONS-1];
    reg [4607:0] expected_sc [0:11];
    reg [4607:0] expected_fp16 [0:11];
    reg [4607:0] expected_fp32 [0:11];
    reg [7167:0] payload;
    reg [4607:0] expected_payload;

    integer cycle = 0;
    integer group;
    integer word_index;
    integer first_load_cycle = -1;
    integer final_cycle = -1;
    integer output_stall_cycles = 0;
    integer stability_checks = 0;
    reg stalled_last_cycle = 1'b0;
    reg [255:0] stalled_data;
    reg stalled_last;

    generate
        if (CASE_ID == 0) begin : g_sc
            m09_sc_gate_up_serial_ooc_wrapper dut (.*);
        end else if (CASE_ID == 1) begin : g_fp16
            m09_fp16_gate_up_serial_ooc_wrapper dut (.*);
        end else begin : g_fp32
            m09_fp32_gate_up_serial_ooc_wrapper dut (.*);
        end
    endgenerate

    always @(posedge clk) begin
        if (rst_n) begin
            cycle <= cycle + 1;
            if (error) begin
                $display("FAIL: M09 serial wrapper sticky error case=%0d cycle=%0d",
                    CASE_ID, cycle);
                $finish;
            end
            if (stalled_last_cycle) begin
                stability_checks = stability_checks + 1;
                if (!result_valid || result_data !== stalled_data ||
                    result_last !== stalled_last) begin
                    $display("FAIL: M09 serial wrapper output changed under backpressure case=%0d cycle=%0d",
                        CASE_ID, cycle);
                    $finish;
                end
            end
            stalled_last_cycle <= result_valid && !result_ready;
            if (result_valid && !result_ready) begin
                stalled_data <= result_data;
                stalled_last <= result_last;
                output_stall_cycles = output_stall_cycles + 1;
            end
            if (cycle > 100000) begin
                $display("FAIL: M09 serial wrapper timeout case=%0d input=%0d output=%0d",
                    CASE_ID, input_group_count, output_tile_count);
                $finish;
            end
        end
    end

    always @(negedge clk) begin
        if (!rst_n)
            result_ready <= 1'b0;
        else if (BACKPRESSURE == 0)
            result_ready <= 1'b1;
        else
            result_ready <= !((cycle % 17) >= 9 && (cycle % 17) <= 12);
    end

    task automatic build_payload;
        input integer group_index;
        begin
            payload = '0;
            payload[0 +: 4608] = activation_mem[group_index];
            payload[4608 +: 1536] = weight_mem[group_index];
            if (CASE_ID == 0) begin
                payload[6144 +: 128] =
                    activation_sc_mem[group_index][127:0];
                payload[6272 +: 96] =
                    activation_sc_mem[group_index][223:128];
                payload[6368 +: 96] = weight_sc_mem[group_index][95:0];
                payload[6464 +: 72] = weight_sc_mem[group_index][167:96];
                payload[6536 +: 12] = mask_mem[group_index];
                payload[6548] = group_index == 0;
                payload[6549] = group_index == GROUPS-1;
            end else if (CASE_ID == 1) begin
                payload[6144 +: 256] = activation_fp16_mem[group_index];
                payload[6400 +: 192] = weight_fp16_mem[group_index];
                payload[6592 +: 12] = mask_mem[group_index];
                payload[6604] = group_index == 0;
                payload[6605] = group_index == GROUPS-1;
            end else begin
                payload[6144 +: 512] = activation_fp32_mem[group_index];
                payload[6656 +: 384] = weight_fp32_mem[group_index];
                payload[7040 +: 12] = mask_mem[group_index];
                payload[7052] = group_index == 0;
                payload[7053] = group_index == GROUPS-1;
            end
        end
    endtask

    initial begin
        $readmemh({DATA_DIR,"/activation_s9x16x32.mem"}, activation_mem);
        $readmemh({DATA_DIR,"/weights_s4x12x32.mem"}, weight_mem);
        $readmemh({DATA_DIR,"/activation_meta_sc_u224.mem"},
            activation_sc_mem);
        $readmemh({DATA_DIR,"/weight_meta_sc_u168.mem"}, weight_sc_mem);
        $readmemh({DATA_DIR,"/activation_scale_fp16x16.mem"},
            activation_fp16_mem);
        $readmemh({DATA_DIR,"/weight_scale_fp16x12.mem"},
            weight_fp16_mem);
        $readmemh({DATA_DIR,"/activation_scale_fp32x16.mem"},
            activation_fp32_mem);
        $readmemh({DATA_DIR,"/weight_scale_fp32x12.mem"},
            weight_fp32_mem);
        $readmemh({DATA_DIR,"/column_mask_u12.mem"}, mask_mem);
        $readmemh({DATA_DIR,"/expected_sc_s24x16x12.mem"}, expected_sc);
        $readmemh({DATA_DIR,"/expected_fp16_s24x16x12.mem"}, expected_fp16);
        $readmemh({DATA_DIR,"/expected_fp32_s24x16x12.mem"}, expected_fp32);
        case (CASE_ID)
            0: expected_payload = expected_sc[0];
            1: expected_payload = expected_fp16[0];
            default: expected_payload = expected_fp32[0];
        endcase

        repeat (10) @(posedge clk);
        rst_n <= 1'b1;
        for (group = 0; group < GROUPS; group = group + 1) begin
            build_payload(group);
            for (word_index = 0; word_index < LOAD_WORDS;
                    word_index = word_index + 1) begin
                @(negedge clk);
                load_valid = 1'b1;
                load_data = payload[word_index*256 +: 256];
                while (!load_ready)
                    @(negedge clk);
                @(posedge clk);
                if (first_load_cycle < 0)
                    first_load_cycle = cycle;
            end
        end
        @(negedge clk);
        load_valid = 1'b0;
        load_data = '0;

        word_index = 0;
        while (word_index < RESULT_WORDS) begin
            @(posedge clk);
            if (result_valid && result_ready) begin
                if (result_data !==
                        expected_payload[word_index*256 +: 256]) begin
                    $display("FAIL: M09 serial wrapper mismatch case=%0d word=%0d expected=%h got=%h",
                        CASE_ID, word_index,
                        expected_payload[word_index*256 +: 256],
                        result_data);
                    $finish;
                end
                if (result_last !== (word_index == RESULT_WORDS-1)) begin
                    $display("FAIL: M09 serial wrapper last mismatch case=%0d word=%0d last=%0d",
                        CASE_ID, word_index, result_last);
                    $finish;
                end
                if (word_index == RESULT_WORDS-1)
                    final_cycle = cycle;
                word_index = word_index + 1;
            end
        end
        @(posedge clk);
        if (input_group_count != GROUPS || output_tile_count != 1) begin
            $display("FAIL: M09 serial wrapper counters case=%0d input=%0d output=%0d",
                CASE_ID, input_group_count, output_tile_count);
            $finish;
        end
        $display("M09_SERIAL_METRIC_JSON: {\"case_id\":%0d,\"backpressure\":%0d,\"load_words_per_group\":%0d,\"groups\":128,\"result_words\":18,\"mismatches\":0,\"total_cycles\":%0d,\"output_stall_cycles\":%0d,\"stability_checks\":%0d}",
            CASE_ID, BACKPRESSURE, LOAD_WORDS,
            final_cycle-first_load_cycle+1, output_stall_cycles,
            stability_checks);
        $display("PASS: M09 Gate/Up serial physical wrapper case=%0d backpressure=%0d",
            CASE_ID, BACKPRESSURE);
        $finish;
    end
endmodule
