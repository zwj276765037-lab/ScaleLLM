`timescale 1ns/1ps

module m11_ooc_wrapper_tb #(
    parameter integer CASE_ID = 0,
    parameter DATA_DIR = "/tmp"
);
    localparam integer GROUPS = 448;
    localparam integer RESULT_WORDS = CASE_ID == 2 ? 148 : 140;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire load_valid;
    wire load_ready;
    wire [31:0] load_product_s32;
    wire result_valid;
    wire result_ready;
    wire [31:0] result_data;
    wire result_last;
    wire [31:0] busy_cycle_count;
    wire error;

    reg [16383:0] input_mem [0:GROUPS-1];
    reg [4095:0] expected_sc_u8_mem [0:GROUPS-1];
    reg [383:0] expected_sc_meta_mem [0:GROUPS-1];
    reg [4095:0] expected_fp_u8_mem [0:GROUPS-1];
    reg [383:0] expected_fp16_meta_mem [0:GROUPS-1];
    reg [639:0] expected_fp32_meta_mem [0:GROUPS-1];
    wire [4735:0] expected_payload = CASE_ID == 0 ?
        {{256{1'b0}}, expected_sc_meta_mem[0], expected_sc_u8_mem[0]} :
        CASE_ID == 1 ?
        {{256{1'b0}}, expected_fp16_meta_mem[0], expected_fp_u8_mem[0]} :
        {expected_fp32_meta_mem[0], expected_fp_u8_mem[0]};

    integer cycle = 0;
    integer load_word = 0;
    integer result_word = 0;
    integer output_stall_cycles = 0;
    reg result_was_stalled = 1'b0;
    reg [31:0] stalled_data;
    reg stalled_last;

    always #5 clk = ~clk;
    assign load_valid = rst_n && load_word < 512;
    assign load_product_s32 = input_mem[0][
        (load_word < 512 ? load_word : 511)*32 +: 32];
    assign result_ready = rst_n && ((cycle % 11) != 3);

    initial begin
        $readmemh({DATA_DIR, "/input_s32.mem"}, input_mem);
        $readmemh({DATA_DIR, "/expected_sc_u8.mem"},
            expected_sc_u8_mem);
        $readmemh({DATA_DIR, "/expected_sc_meta.mem"},
            expected_sc_meta_mem);
        $readmemh({DATA_DIR, "/expected_fp_u8.mem"},
            expected_fp_u8_mem);
        $readmemh({DATA_DIR, "/expected_fp16_meta.mem"},
            expected_fp16_meta_mem);
        $readmemh({DATA_DIR, "/expected_fp32_meta.mem"},
            expected_fp32_meta_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    generate
        if (CASE_ID == 0) begin : g_sc
            hap_mlp_product_frontend16_q4_ooc_wrapper dut (.*);
        end else if (CASE_ID == 1) begin : g_fp16
            m11_fp16_mlp_product_frontend16_q4_ooc_wrapper dut (.*);
        end else begin : g_fp32
            m11_fp32_mlp_product_frontend16_q4_ooc_wrapper dut (.*);
        end
    endgenerate

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            load_word <= 0;
            result_word <= 0;
            output_stall_cycles <= 0;
            result_was_stalled <= 1'b0;
        end else begin
            cycle <= cycle + 1;
            if (load_valid && load_ready)
                load_word <= load_word + 1;
            if (result_valid && !result_ready)
                output_stall_cycles <= output_stall_cycles + 1;

            if (result_was_stalled &&
                    (!result_valid || result_data !== stalled_data ||
                     result_last !== stalled_last)) begin
                $display("FAIL: M11 wrapper payload changed while stalled");
                $finish;
            end
            result_was_stalled <= result_valid && !result_ready;
            if (result_valid && !result_ready) begin
                stalled_data <= result_data;
                stalled_last <= result_last;
            end

            if (result_valid && result_ready) begin
                if (result_data !==
                        expected_payload[result_word*32 +: 32]) begin
                    $display("FAIL: M11 wrapper data case=%0d word=%0d",
                        CASE_ID, result_word);
                    $finish;
                end
                if (result_last !== (result_word == RESULT_WORDS-1)) begin
                    $display("FAIL: M11 wrapper last case=%0d word=%0d",
                        CASE_ID, result_word);
                    $finish;
                end
                if (result_last) begin
                    $display("M11_WRAPPER_METRIC_JSON: {\"case_id\":%0d,\"load_words\":512,\"result_words\":%0d,\"output_stall_cycles\":%0d,\"busy_cycles\":%0d,\"cycles\":%0d}",
                        CASE_ID, RESULT_WORDS, output_stall_cycles,
                        busy_cycle_count, cycle+1);
                    $display("PASS: M11 serial OOC wrapper");
                    $finish;
                end
                result_word <= result_word + 1;
            end
            if (error) begin
                $display("FAIL: M11 wrapper DUT error case=%0d cycle=%0d",
                    CASE_ID, cycle);
                $finish;
            end
            if (cycle > 3000) begin
                $display("FAIL: M11 wrapper timeout case=%0d load=%0d result=%0d",
                    CASE_ID, load_word, result_word);
                $finish;
            end
        end
    end

    initial begin
        if (CASE_ID < 0 || CASE_ID > 2)
            $error("M11 wrapper CASE_ID must be 0, 1, or 2");
    end
endmodule
