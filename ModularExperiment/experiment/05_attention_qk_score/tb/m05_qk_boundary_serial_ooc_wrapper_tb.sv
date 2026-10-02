`timescale 1ns / 1ps

module m05_qk_boundary_serial_ooc_wrapper_tb #(
    parameter integer CASE_ID = 0,
    parameter integer BACKPRESSURE = 1
);
    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg load_valid = 1'b0;
    reg [255:0] load_data = 256'd0;
    reg result_ready = 1'b0;
    wire load_ready;
    wire result_valid;
    wire [255:0] result_data;
    wire result_last;
    wire [31:0] input_group_count;
    wire [31:0] output_score_count;
    wire [31:0] clip_count;
    wire [31:0] query_cache_write_count;
    wire [31:0] key_cache_write_count;
    wire error;
    reg [1023:0] payload;
    integer cycle = 0;
    integer command_index;
    integer word_index;
    integer first_load_cycle = -1;
    integer final_cycle = -1;
    integer received = 0;
    integer output_stall_cycles = 0;
    integer stability_checks = 0;
    reg stalled_last_cycle = 1'b0;
    reg [255:0] stalled_data;
    reg stalled_last;

    m05_qk_boundary_serial_ooc_wrapper #(.VARIANT(CASE_ID)) dut (.*);

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
            received <= 0;
            stalled_last_cycle <= 1'b0;
        end else begin
            cycle <= cycle + 1;
            if (error) begin
                $display("FAIL: M05 serial boundary sticky error case=%0d cycle=%0d",
                    CASE_ID, cycle);
                $finish;
            end
            if (stalled_last_cycle) begin
                stability_checks <= stability_checks + 1;
                if (!result_valid || result_data !== stalled_data ||
                    result_last !== stalled_last) begin
                    $display("FAIL: M05 serial boundary changed under backpressure case=%0d cycle=%0d",
                        CASE_ID, cycle);
                    $finish;
                end
            end
            stalled_last_cycle <= result_valid && !result_ready;
            if (result_valid && !result_ready) begin
                stalled_data <= result_data;
                stalled_last <= result_last;
                output_stall_cycles <= output_stall_cycles + 1;
            end
            if (result_valid && result_ready) begin
                if (result_data !== {227'd0,1'b1,7'd0,1'b1,20'd0} ||
                    result_last !== 1'b1 || received != 0) begin
                    $display("FAIL: M05 serial boundary result mismatch case=%0d data=%h last=%0d received=%0d",
                        CASE_ID, result_data, result_last, received);
                    $finish;
                end
                received <= received + 1;
                final_cycle <= cycle;
            end
            if (cycle > 100000) begin
                $display("FAIL: M05 serial boundary timeout case=%0d groups=%0d scores=%0d",
                    CASE_ID, input_group_count, output_score_count);
                $finish;
            end
        end
    end

    task automatic send_payload;
        input [1023:0] value;
        begin
            for (word_index = 0; word_index < 4;
                 word_index = word_index + 1) begin
                @(negedge clk);
                load_valid = 1'b1;
                load_data = value[word_index*256 +: 256];
                while (!load_ready)
                    @(negedge clk);
                @(posedge clk);
                if (first_load_cycle < 0)
                    first_load_cycle = cycle;
            end
        end
    endtask

    initial begin
        repeat (10) @(posedge clk);
        rst_n <= 1'b1;

        // Four all-zero Q groups.
        for (command_index = 0; command_index < 4;
             command_index = command_index + 1) begin
            payload = 1024'd0;
            payload[808:807] = command_index[1:0];
            payload[812:811] = 2'd0;
            send_payload(payload);
        end

        // One key, four all-zero groups, mask asserted on the score.
        for (command_index = 0; command_index < 4;
             command_index = command_index + 1) begin
            payload = 1024'd0;
            payload[806:800] = 7'd0;
            payload[808:807] = command_index[1:0];
            payload[809] = 1'b1;
            payload[810] = command_index == 3;
            payload[812:811] = 2'd1;
            send_payload(payload);
        end

        payload = 1024'd0;
        payload[812:811] = 2'd2;
        send_payload(payload);
        @(negedge clk);
        load_valid = 1'b0;
        load_data = 256'd0;

        while (received < 1)
            @(posedge clk);
        repeat (3) @(posedge clk);
        if (input_group_count != 4 || output_score_count != 1 ||
            clip_count != 0 || query_cache_write_count != 4 ||
            key_cache_write_count != 4) begin
            $display("FAIL: M05 serial boundary counters case=%0d groups=%0d scores=%0d clip=%0d qcache=%0d kcache=%0d",
                CASE_ID, input_group_count, output_score_count, clip_count,
                query_cache_write_count, key_cache_write_count);
            $finish;
        end
        $display("M05_BOUNDARY_SERIAL_METRIC_JSON: {\"case_id\":%0d,\"commands\":9,\"load_words\":36,\"scores\":1,\"mismatches\":0,\"total_cycles\":%0d,\"output_stall_cycles\":%0d,\"stability_checks\":%0d}",
            CASE_ID, final_cycle-first_load_cycle+1,
            output_stall_cycles, stability_checks);
        $display("PASS: M05 QK boundary serial physical wrapper case=%0d backpressure=%0d",
            CASE_ID, BACKPRESSURE);
        $finish;
    end

    initial begin
        if (CASE_ID < 0 || CASE_ID > 2)
            $error("M05 serial boundary CASE_ID must be 0, 1, or 2");
    end
endmodule
