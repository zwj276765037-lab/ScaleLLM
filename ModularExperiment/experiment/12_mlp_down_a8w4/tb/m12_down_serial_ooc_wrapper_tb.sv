`timescale 1ns / 1ps

module m12_down_serial_ooc_wrapper_tb #(
    parameter integer CASE_ID = 0,
    parameter integer BACKPRESSURE = 1,
    parameter string DATA_DIR = "data_mini"
);
    localparam integer GROUPS = 5;
    localparam integer TILES = 16;
    localparam integer TILE_W = 4;
    localparam integer TRANSACTIONS = GROUPS*TILES;
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
    wire [TILE_W-1:0] result_tile_index;
    wire [31:0] input_transaction_count;
    wire [31:0] input_group_count;
    wire [31:0] output_tile_count;
    wire error;
    reg [7167:0] payload;
    reg [7167:0] payload_mem [0:TRANSACTIONS-1];
    reg [4607:0] expected_mem [0:TILES-1];

    integer cycle = 0;
    integer group;
    integer tile;
    integer word_index;
    integer receive_tile = 0;
    integer receive_word = 0;
    integer first_load_cycle = -1;
    integer final_cycle = -1;
    integer output_stall_cycles = 0;
    integer stability_checks = 0;
    integer load_word_count = 0;
    integer output_word_count = 0;
    integer nonzero_result_words = 0;
    integer accepted_transaction_count = 0;
    integer last_transaction_cycle = -1;
    integer input_interval_min = 32'h7fffffff;
    integer input_interval_max = 0;
    reg [31:0] previous_input_transaction_count = 0;
    reg stalled_last_cycle = 1'b0;
    reg [255:0] stalled_data;
    reg stalled_last;
    reg [TILE_W-1:0] stalled_tile;

    m12_down_serial_ooc_wrapper #(
        .VARIANT(CASE_ID), .TILES(TILES), .GROUPS(GROUPS),
        .TILE_W(TILE_W)
    ) dut (.*);

    always @(negedge clk) begin
        if (!rst_n)
            result_ready <= 1'b0;
        else if (BACKPRESSURE == 0)
            result_ready <= 1'b1;
        else
            result_ready <= !((cycle % 17) >= 9 && (cycle % 17) <= 12);
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            receive_tile <= 0;
            receive_word <= 0;
            stalled_last_cycle <= 1'b0;
            previous_input_transaction_count <= 0;
        end else begin
            cycle <= cycle + 1;
            if (error) begin
                $display("FAIL: M12 serial sticky error case=%0d cycle=%0d",
                    CASE_ID, cycle);
                $finish;
            end
            if (stalled_last_cycle) begin
                stability_checks = stability_checks + 1;
                if (!result_valid || result_data !== stalled_data ||
                    result_last !== stalled_last ||
                    result_tile_index !== stalled_tile) begin
                    $display("FAIL: M12 serial output changed under backpressure case=%0d cycle=%0d",
                        CASE_ID, cycle);
                    $finish;
                end
            end
            stalled_last_cycle <= result_valid && !result_ready;
            if (result_valid && !result_ready) begin
                stalled_data <= result_data;
                stalled_last <= result_last;
                stalled_tile <= result_tile_index;
                output_stall_cycles = output_stall_cycles + 1;
            end
            if (result_valid && result_ready) begin
                if (result_data !==
                        expected_mem[receive_tile][receive_word*256 +: 256] ||
                    result_tile_index !== receive_tile[TILE_W-1:0] ||
                    result_last !== (receive_word == RESULT_WORDS-1)) begin
                    $display("FAIL: M12 serial result mismatch case=%0d tile=%0d word=%0d got_tile=%0d last=%0d expected=%h data=%h",
                        CASE_ID, receive_tile, receive_word,
                        result_tile_index, result_last,
                        expected_mem[receive_tile][receive_word*256 +: 256],
                        result_data);
                    $finish;
                end
                $display("M12_SERIAL_WORD_HEX: case=%0d cycle=%0d tile=%0d word=%0d data=%064h",
                    CASE_ID, cycle, receive_tile, receive_word, result_data);
                output_word_count = output_word_count + 1;
                if (result_data != 256'd0)
                    nonzero_result_words = nonzero_result_words + 1;
                if (receive_word == RESULT_WORDS-1) begin
                    receive_word <= 0;
                    receive_tile <= receive_tile + 1;
                    if (receive_tile + 1 == TILES)
                        final_cycle <= cycle;
                end else
                    receive_word <= receive_word + 1;
            end
            if (load_valid && load_ready)
                load_word_count = load_word_count + 1;
            if (input_transaction_count != previous_input_transaction_count) begin
                if (input_transaction_count !=
                    previous_input_transaction_count + 1) begin
                    $display("FAIL: M12 serial input counter jump case=%0d previous=%0d current=%0d",
                        CASE_ID, previous_input_transaction_count,
                        input_transaction_count);
                    $finish;
                end
                if (last_transaction_cycle >= 0) begin
                    if (cycle-last_transaction_cycle < input_interval_min)
                        input_interval_min = cycle-last_transaction_cycle;
                    if (cycle-last_transaction_cycle > input_interval_max)
                        input_interval_max = cycle-last_transaction_cycle;
                end
                last_transaction_cycle = cycle;
                accepted_transaction_count = accepted_transaction_count + 1;
                $display("M12_SERIAL_INPUT_ACCEPT: case=%0d cycle=%0d transaction_count=%0d",
                    CASE_ID, cycle, input_transaction_count);
                previous_input_transaction_count <= input_transaction_count;
            end
            if (cycle > 200000) begin
                $display("FAIL: M12 serial timeout case=%0d tx=%0d out=%0d",
                    CASE_ID, input_transaction_count, output_tile_count);
                $finish;
            end
        end
    end

    initial begin
        case (CASE_ID)
            0: begin
                $readmemh({DATA_DIR,"/payload_sc_u6656.mem"}, payload_mem);
                $readmemh({DATA_DIR,"/expected_sc_s24x16x12.mem"},
                    expected_mem);
            end
            1: begin
                $readmemh({DATA_DIR,"/payload_fp16_u6656.mem"}, payload_mem);
                $readmemh({DATA_DIR,"/expected_fp16_s24x16x12.mem"},
                    expected_mem);
            end
            default: begin
                $readmemh({DATA_DIR,"/payload_fp32_u7168.mem"}, payload_mem);
                $readmemh({DATA_DIR,"/expected_fp32_s24x16x12.mem"},
                    expected_mem);
            end
        endcase
        repeat (10) @(posedge clk);
        rst_n <= 1'b1;
        for (group = 0; group < GROUPS; group = group + 1) begin
            for (tile = 0; tile < TILES; tile = tile + 1) begin
                payload = payload_mem[group*TILES+tile];
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
        end
        @(negedge clk);
        load_valid = 1'b0;
        load_data = '0;
        while (receive_tile < TILES)
            @(posedge clk);
        repeat (2) @(posedge clk);
        if (input_transaction_count != TRANSACTIONS ||
            input_group_count != GROUPS || output_tile_count != TILES ||
            receive_word != 0 || load_word_count != TRANSACTIONS*LOAD_WORDS ||
            output_word_count != TILES*RESULT_WORDS ||
            accepted_transaction_count != TRANSACTIONS ||
            nonzero_result_words == 0) begin
            $display("FAIL: M12 serial counters case=%0d tx=%0d groups=%0d out=%0d recv_tile=%0d recv_word=%0d load_words=%0d output_words=%0d accepted=%0d nonzero_words=%0d",
                CASE_ID, input_transaction_count, input_group_count,
                output_tile_count, receive_tile, receive_word,
                load_word_count, output_word_count,
                accepted_transaction_count, nonzero_result_words);
            $finish;
        end
        $display("M12_SERIAL_METRIC_JSON: {\"case_id\":%0d,\"backpressure\":%0d,\"load_words_per_transaction\":%0d,\"groups\":5,\"tiles\":16,\"transactions\":80,\"result_words_per_tile\":18,\"mismatches\":0,\"total_cycles\":%0d,\"input_interval_min\":%0d,\"input_interval_max\":%0d,\"load_words\":%0d,\"output_words\":%0d,\"nonzero_result_words\":%0d,\"output_stall_cycles\":%0d,\"stability_checks\":%0d}",
            CASE_ID, BACKPRESSURE, LOAD_WORDS,
            final_cycle-first_load_cycle+1, input_interval_min,
            input_interval_max, load_word_count, output_word_count,
            nonzero_result_words, output_stall_cycles, stability_checks);
        $display("PASS: M12 Down serial physical wrapper case=%0d backpressure=%0d",
            CASE_ID, BACKPRESSURE);
        $finish;
    end
endmodule
