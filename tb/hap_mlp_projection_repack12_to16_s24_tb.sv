`timescale 1ns / 1ps

module projection_repack_tester #(
    parameter integer MATRICES = 2,
    parameter integer TEST_ID = 0,
    parameter integer ROWS = 16,
    parameter integer MATRIX_W = (MATRICES <= 1) ? 1 : $clog2(MATRICES)
) (
    input  wire clk,
    input  wire rst_n,
    output reg  done,
    output reg  failed
);
    localparam integer IN_W = ROWS*12*24;
    localparam integer OUT_W = ROWS*16*24;

    reg clear;
    reg in_valid;
    wire in_ready;
    reg signed [IN_W-1:0] in_payload;
    reg [8:0] in_tag;
    reg [1:0] in_pass;
    reg [MATRIX_W-1:0] in_matrix;
    reg [11:0] in_mask;
    reg in_last;
    wire out_valid;
    reg out_ready;
    wire signed [OUT_W-1:0] out_payload;
    wire [8:0] out_tag;
    wire [1:0] out_record;
    wire [MATRIX_W-1:0] out_matrix;
    wire [15:0] out_mask;
    wire out_last;
    wire [31:0] input_count;
    wire [31:0] output_count;
    wire error;

    reg signed [OUT_W-1:0] expected_payload [0:63];
    reg [8:0] expected_tag [0:63];
    reg [1:0] expected_record [0:63];
    reg [MATRIX_W-1:0] expected_matrix [0:63];
    reg expected_last [0:63];
    integer expected_write;
    integer expected_read;
    integer input_stalls;
    integer output_stalls;
    integer stable_checks;
    integer clear_count;

    reg stalled_previous;
    reg signed [OUT_W-1:0] stalled_payload;
    reg [8:0] stalled_tag;
    reg [1:0] stalled_record;
    reg [MATRIX_W-1:0] stalled_matrix;
    reg stalled_last;
    reg [31:0] random_state;

    hap_mlp_projection_repack12_to16_s24 #(
        .ROWS(ROWS), .MATRICES(MATRICES), .TAG_W(9)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_projection_s24xrowsx12(in_payload),
        .in_block_tag(in_tag), .in_pass_index(in_pass),
        .in_matrix(in_matrix), .in_col_valid_u12(in_mask),
        .in_last_pass(in_last),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_projection_s24xrowsx16(out_payload),
        .out_block_tag(out_tag), .out_record_index(out_record),
        .out_matrix(out_matrix), .out_col_valid_u16(out_mask),
        .out_last_record(out_last), .input_pass_count(input_count),
        .output_record_count(output_count), .error(error)
    );

    function automatic [23:0] sample_value;
        input integer tag_value;
        input integer matrix_value;
        input integer column_value;
        input integer row_value;
        reg [31:0] mixed;
        begin
            mixed = (tag_value * 32'h0012d687) ^
                    (matrix_value * 32'h00034567) ^
                    (column_value * 32'h00001021) ^
                    (row_value * 32'h00000113) ^ 32'h0055aa31;
            sample_value = mixed[23:0];
        end
    endfunction

    function automatic [11:0] low_mask12;
        input integer count;
        begin
            if (count >= 12) low_mask12 = 12'hfff;
            else low_mask12 = (12'h001 << count) - 1'b1;
        end
    endfunction

    task automatic build_input;
        input integer tag_value;
        input integer pass_value;
        input integer matrix_value;
        input integer valid_columns;
        integer row_index;
        integer lane_index;
        begin
            in_payload = '0;
            for (row_index = 0; row_index < ROWS; row_index = row_index + 1)
                for (lane_index = 0; lane_index < valid_columns;
                     lane_index = lane_index + 1)
                    in_payload[(row_index*12+lane_index)*24 +: 24] =
                        sample_value(tag_value, matrix_value,
                                     pass_value*12+lane_index, row_index);
            in_tag = tag_value[8:0];
            in_pass = pass_value[1:0];
            in_matrix = matrix_value[MATRIX_W-1:0];
            in_mask = low_mask12(valid_columns);
        end
    endtask

    task automatic enqueue_block;
        input integer tag_value;
        input integer valid_columns;
        integer records;
        integer record_index;
        integer matrix_index;
        integer row_index;
        integer lane_index;
        integer slot;
        begin
            records = (valid_columns + 15) / 16;
            for (record_index = 0; record_index < records;
                 record_index = record_index + 1) begin
                for (matrix_index = 0; matrix_index < MATRICES;
                     matrix_index = matrix_index + 1) begin
                    slot = expected_write;
                    expected_payload[slot] = '0;
                    for (row_index = 0; row_index < ROWS;
                         row_index = row_index + 1)
                        for (lane_index = 0; lane_index < 16;
                             lane_index = lane_index + 1)
                            expected_payload[slot][
                                (row_index*16+lane_index)*24 +: 24] =
                                sample_value(tag_value, matrix_index,
                                    record_index*16+lane_index, row_index);
                    expected_tag[slot] = tag_value[8:0];
                    expected_record[slot] = record_index[1:0];
                    expected_matrix[slot] =
                        matrix_index[MATRIX_W-1:0];
                    expected_last[slot] = (record_index == records-1);
                    expected_write = expected_write + 1;
                end
            end
        end
    endtask

    task automatic send_pass;
        input integer tag_value;
        input integer pass_value;
        input integer matrix_value;
        input integer valid_columns;
        input integer last_value;
        integer wait_cycles;
        begin
            // Randomized source bubbles.  Once valid is asserted all fields
            // remain stable until the ready/valid handshake.
            repeat ((tag_value + pass_value + matrix_value + TEST_ID) % 3)
                @(negedge clk);
            @(negedge clk);
            build_input(tag_value, pass_value, matrix_value, valid_columns);
            in_last = last_value;
            in_valid = 1'b1;
            wait_cycles = 0;
            begin : wait_for_fire
            forever begin
                @(posedge clk);
                if (in_ready)
                    disable wait_for_fire;
                else begin
                    input_stalls = input_stalls + 1;
                    wait_cycles = wait_cycles + 1;
                end
                if (wait_cycles == 2000) begin
                    $display("FAIL tester%0d: source deadlock tag=%0d pass=%0d matrix=%0d mask=%h last=%0d error=%0d active=%0d expected=%0d/%0d/%0d order=%0d capacity=%0d",
                        TEST_ID, in_tag, in_pass, in_matrix, in_mask, in_last,
                        error, dut.sequence_active_r, dut.expected_block_r,
                        dut.expected_pass_r, dut.expected_matrix_r,
                        dut.order_legal_c, dut.output_capacity);
                    failed = 1'b1;
                    $fatal(1, "projection repacker source deadlock");
                end
            end
            end
            @(negedge clk);
            in_valid = 1'b0;
        end
    endtask

    task automatic send_block;
        input integer tag_value;
        input integer valid_columns;
        integer passes;
        integer pass_index;
        integer matrix_index;
        integer valid_this_pass;
        begin
            enqueue_block(tag_value, valid_columns);
            passes = (valid_columns + 11) / 12;
            for (pass_index = 0; pass_index < passes;
                 pass_index = pass_index + 1) begin
                valid_this_pass = valid_columns - pass_index*12;
                if (valid_this_pass > 12) valid_this_pass = 12;
                for (matrix_index = 0; matrix_index < MATRICES;
                     matrix_index = matrix_index + 1)
                    send_pass(tag_value, pass_index, matrix_index,
                              valid_this_pass, pass_index == passes-1);
            end
        end
    endtask

    task automatic pulse_clear;
        begin
            @(negedge clk);
            in_valid = 1'b0;
            clear = 1'b1;
            @(posedge clk);
            @(negedge clk);
            clear = 1'b0;
            clear_count = clear_count + 1;
        end
    endtask

    // Independent deterministic backpressure, including multi-cycle stalls.
    always @(negedge clk) begin
        if (!rst_n || clear) begin
            out_ready <= 1'b0;
            random_state <= 32'h1aceb00c ^ TEST_ID;
        end else begin
            random_state <= {random_state[30:0],
                random_state[31] ^ random_state[21] ^
                random_state[1] ^ random_state[0]};
            out_ready <= random_state[0] | random_state[3];
        end
    end

    always @(posedge clk) begin
        if (rst_n && !clear) begin
            if (stalled_previous) begin
                stable_checks = stable_checks + 1;
                if (!out_valid || out_payload !== stalled_payload ||
                    out_tag !== stalled_tag || out_record !== stalled_record ||
                    out_matrix !== stalled_matrix || out_last !== stalled_last) begin
                    $display("FAIL tester%0d: output changed while stalled", TEST_ID);
                    failed = 1'b1;
                end
            end
            stalled_previous = out_valid && !out_ready;
            if (stalled_previous) begin
                output_stalls = output_stalls + 1;
                stalled_payload = out_payload;
                stalled_tag = out_tag;
                stalled_record = out_record;
                stalled_matrix = out_matrix;
                stalled_last = out_last;
            end
            if (out_valid && out_ready) begin
                if (expected_read >= expected_write) begin
                    $display("FAIL tester%0d: unexpected output", TEST_ID);
                    failed = 1'b1;
                end else if (out_payload !== expected_payload[expected_read] ||
                    out_tag !== expected_tag[expected_read] ||
                    out_record !== expected_record[expected_read] ||
                    out_matrix !== expected_matrix[expected_read] ||
                    out_last !== expected_last[expected_read] ||
                    out_mask !== 16'hffff) begin
                    $display("FAIL tester%0d: mismatch output=%0d tag=%0d rec=%0d matrix=%0d last=%0d",
                        TEST_ID, expected_read, out_tag, out_record,
                        out_matrix, out_last);
                    failed = 1'b1;
                end
                expected_read = expected_read + 1;
            end
        end else begin
            stalled_previous = 1'b0;
        end
    end

    integer partial_matrix;
    integer timeout;
    integer tail_columns;
    initial begin
        done = 1'b0;
        failed = 1'b0;
        clear = 1'b0;
        in_valid = 1'b0;
        in_payload = '0;
        in_tag = '0;
        in_pass = '0;
        in_matrix = '0;
        in_mask = '0;
        in_last = 1'b0;
        out_ready = 1'b0;
        random_state = 32'h1aceb00c ^ TEST_ID;
        expected_write = 0;
        expected_read = 0;
        input_stalls = 0;
        output_stalls = 0;
        stable_checks = 0;
        clear_count = 0;
        stalled_previous = 1'b0;

        wait (rst_n);
        repeat (3 + TEST_ID) @(posedge clk);

        // A partial first pass creates tails but no output; clear must discard
        // that hidden state without resetting the payload flops themselves.
        for (partial_matrix = 0; partial_matrix < MATRICES;
             partial_matrix = partial_matrix + 1)
            send_pass(9'h011 + TEST_ID, 0, partial_matrix, 12, 0);
        pulse_clear();

        send_block(9'h040 + TEST_ID, 48);
        tail_columns = (MATRICES == 1) ? 16 : 32;
        send_block(9'h080 + TEST_ID, tail_columns);

        timeout = 0;
        while (expected_read != expected_write && timeout < 10000) begin
            @(posedge clk);
            timeout = timeout + 1;
        end
        if (timeout == 10000 || expected_read != expected_write) begin
            $display("FAIL tester%0d: output timeout %0d/%0d",
                TEST_ID, expected_read, expected_write);
            failed = 1'b1;
        end
        if (error) begin
            $display("FAIL tester%0d: legal stream latched error", TEST_ID);
            failed = 1'b1;
        end

        // Fail-closed order check: a new sequence cannot start at pass1.
        @(negedge clk);
        build_input(9'h155 + TEST_ID, 1, 0, 12);
        in_last = 1'b0;
        in_valid = 1'b1;
        @(posedge clk);
        @(negedge clk);
        in_valid = 1'b0;
        @(posedge clk);
        if (!error || in_ready) begin
            $display("FAIL tester%0d: illegal order was not rejected", TEST_ID);
            failed = 1'b1;
        end
        pulse_clear();
        if (error) begin
            $display("FAIL tester%0d: clear did not recover error", TEST_ID);
            failed = 1'b1;
        end

        // One final legal tail proves post-error recovery.
        send_block(9'h180 + TEST_ID, tail_columns);
        timeout = 0;
        while (expected_read != expected_write && timeout < 10000) begin
            @(posedge clk);
            timeout = timeout + 1;
        end
        if (timeout == 10000 || expected_read != expected_write || error)
            failed = 1'b1;
        if (output_stalls == 0 || stable_checks == 0 || clear_count != 2) begin
            $display("FAIL tester%0d: coverage stalls=%0d/%0d stable=%0d clear=%0d",
                TEST_ID, input_stalls, output_stalls, stable_checks, clear_count);
            failed = 1'b1;
        end

        $display("%s: projection_repack matrices=%0d inputs=%0d outputs=%0d source_stalls=%0d sink_stalls=%0d stable=%0d",
            failed ? "FAIL" : "PASS", MATRICES, input_count, output_count,
            input_stalls, output_stalls, stable_checks);
        done = 1'b1;
    end
endmodule

module hap_mlp_projection_repack12_to16_s24_tb;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    wire done_gate_up;
    wire fail_gate_up;
    wire done_down;
    wire fail_down;

    always #3.333 clk = ~clk;

    projection_repack_tester #(.MATRICES(2), .TEST_ID(0)) gate_up (
        .clk(clk), .rst_n(rst_n), .done(done_gate_up), .failed(fail_gate_up)
    );
    projection_repack_tester #(.MATRICES(1), .TEST_ID(1)) down (
        .clk(clk), .rst_n(rst_n), .done(done_down), .failed(fail_down)
    );

    initial begin
        repeat (8) @(posedge clk);
        rst_n = 1'b1;
        wait (done_gate_up && done_down);
        repeat (3) @(posedge clk);
        if (fail_gate_up || fail_down) begin
            $display("FAIL: hap_mlp_projection_repack12_to16_s24_tb");
            $fatal(1);
        end
        $display("PASS: hap_mlp_projection_repack12_to16_s24_tb gate/up and down bit-exact, backpressure, clear, tail and fail-closed order");
        $finish;
    end

    initial begin
        #2000000;
        $fatal(1, "projection repacker global timeout");
    end
endmodule
