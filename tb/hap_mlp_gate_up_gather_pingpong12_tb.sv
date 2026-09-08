`timescale 1ns / 1ps

module hap_mlp_gate_up_gather_pingpong12_tb #(
    parameter integer GROUPS = 8,
    parameter integer GROUP_W = (GROUPS <= 2) ? 1 : $clog2(GROUPS)
);
    localparam integer BLOCK_W = 4;
    localparam integer BLOCKS = 7;

    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;

    reg in_valid = 1'b0;
    wire in_ready;
    reg [BLOCK_W-1:0] source_block_r = '0;
    reg [1:0] source_record_r = 2'd0;
    reg source_matrix_r = 1'b0;
    reg [GROUP_W-1:0] source_group_r = '0;
    wire [5:0] source_columns;
    reg signed [2047:0] source_weights;
    reg [223:0] source_meta;
    reg [15:0] source_mask;

    wire out_valid;
    reg out_ready = 1'b0;
    wire [BLOCK_W-1:0] out_block;
    wire out_matrix;
    wire [1:0] out_pass;
    wire [GROUP_W-1:0] out_group;
    wire out_first_group;
    wire out_last_group;
    wire out_last_pass;
    wire out_last_block_transaction;
    wire signed [1535:0] out_weights;
    wire [167:0] out_meta;
    wire [11:0] out_mask;
    wire [31:0] input_transaction_count;
    wire [31:0] input_block_count;
    wire [31:0] output_transaction_count;
    wire [31:0] output_block_count;
    wire error;

    reg legal_mode = 1'b0;
    reg checker_enable = 1'b0;
    reg source_done = 1'b0;
    reg checker_done = 1'b0;
    reg [BLOCK_W-1:0] expected_block_r = '0;
    reg [1:0] expected_pass_r = 2'd0;
    reg expected_matrix_r = 1'b0;
    reg [GROUP_W-1:0] expected_group_r = '0;
    reg [31:0] lfsr = 32'h17a5_c3e1;
    integer cycle_count = 0;
    integer overlap_input_output = 0;
    integer input_stall_cycles = 0;
    integer output_stall_cycles = 0;
    integer input_stability_checks = 0;
    integer output_stability_checks = 0;
    reg input_stalled_r = 1'b0;
    reg output_stalled_r = 1'b0;
    reg [BLOCK_W+6+1+2+GROUP_W+2048+224+16-1:0]
        held_input_payload_r;
    reg [BLOCK_W+1+2+GROUP_W+1+1+1+1+1536+168+12-1:0]
        held_output_payload_r;

    function automatic integer columns_for_block;
        input integer block_index;
        begin
            case (block_index)
                0: columns_for_block = 48;
                1: columns_for_block = 48;
                2: columns_for_block = 32;
                3: columns_for_block = 16;
                4: columns_for_block = 37;
                5: columns_for_block = 1;
                default: columns_for_block = 48;
            endcase
        end
    endfunction

    function automatic integer record_count;
        input integer columns;
        begin
            record_count = (columns + 15) / 16;
        end
    endfunction

    function automatic integer pass_count;
        input integer columns;
        begin
            pass_count = (columns + 11) / 12;
        end
    endfunction

    function automatic [15:0] low_mask16;
        input integer valid;
        begin
            if (valid >= 16)
                low_mask16 = 16'hffff;
            else if (valid > 0)
                low_mask16 = (16'h0001 << valid) - 1'b1;
            else
                low_mask16 = 16'h0000;
        end
    endfunction

    function automatic [11:0] low_mask12;
        input integer valid;
        begin
            if (valid >= 12)
                low_mask12 = 12'hfff;
            else if (valid > 0)
                low_mask12 = (12'h001 << valid) - 1'b1;
            else
                low_mask12 = 12'h000;
        end
    endfunction

    function automatic [3:0] weight_value;
        input integer block_index;
        input integer matrix;
        input integer column;
        input integer group_index;
        input integer lane;
        begin
            weight_value = block_index*3 + matrix*5 + column*7 +
                group_index*11 + lane*13 + 4'h1;
        end
    endfunction

    function automatic [7:0] code_value;
        input integer block_index;
        input integer matrix;
        input integer column;
        input integer group_index;
        begin
            code_value = 8'h31 ^ (block_index*8'h1d) ^
                (matrix*8'ha7) ^ (column*8'h13) ^ (group_index*8'h25);
        end
    endfunction

    function automatic [5:0] shift_value;
        input integer block_index;
        input integer matrix;
        input integer column;
        input integer group_index;
        begin
            shift_value = block_index*5 + matrix*9 + column*3 +
                group_index*7 + 6'h2b;
        end
    endfunction

    assign source_columns = columns_for_block(source_block_r);

    integer source_column;
    integer source_lane;
    integer source_valid;
    reg [127:0] source_code;
    reg [95:0] source_shift;
    always @* begin
        source_weights = '0;
        source_code = '0;
        source_shift = '0;
        source_valid = columns_for_block(source_block_r) -
            source_record_r*16;
        if (source_valid > 16)
            source_valid = 16;
        source_mask = low_mask16(source_valid);
        for (source_column = 0; source_column < 16;
             source_column = source_column + 1) begin
            // Invalid input lanes are deliberately nonzero.  They must not be
            // written, and masked output lanes must be all-zero.
            source_code[source_column*8 +: 8] = code_value(
                source_block_r, source_matrix_r,
                source_record_r*16 + source_column, source_group_r);
            source_shift[source_column*6 +: 6] = shift_value(
                source_block_r, source_matrix_r,
                source_record_r*16 + source_column, source_group_r);
            for (source_lane = 0; source_lane < 32;
                 source_lane = source_lane + 1)
                source_weights[(source_column*32+source_lane)*4 +: 4] =
                    weight_value(source_block_r, source_matrix_r,
                        source_record_r*16 + source_column,
                        source_group_r, source_lane);
        end
        source_meta = {source_shift, source_code};
    end

    hap_mlp_gate_up_gather_pingpong12 #(
        .GROUPS(GROUPS), .BLOCK_W(BLOCK_W), .GROUP_W(GROUP_W),
        .BANK_DEPTH(8*GROUPS)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_block_index(source_block_r),
        .in_block_valid_columns(source_columns),
        .in_matrix(source_matrix_r), .in_record_index(source_record_r),
        .in_k_group(source_group_r),
        .in_weights_s4x16x32(source_weights),
        .in_weight_meta_u224(source_meta),
        .in_col_valid_u16(source_mask),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_block_index(out_block), .out_matrix(out_matrix),
        .out_pass_index(out_pass), .out_k_group(out_group),
        .out_first_group(out_first_group),
        .out_last_group(out_last_group), .out_last_pass(out_last_pass),
        .out_last_block_transaction(out_last_block_transaction),
        .out_weights_s4x12x32(out_weights),
        .out_weight_meta_u168(out_meta),
        .out_col_valid_u12(out_mask),
        .input_transaction_count(input_transaction_count),
        .input_block_count(input_block_count),
        .output_transaction_count(output_transaction_count),
        .output_block_count(output_block_count), .error(error)
    );

    task automatic advance_source;
        integer columns;
        integer records;
        begin
            columns = columns_for_block(source_block_r);
            records = record_count(columns);
            if (source_group_r == GROUPS-1) begin
                source_group_r <= '0;
                if (!source_matrix_r) begin
                    source_matrix_r <= 1'b1;
                end else begin
                    source_matrix_r <= 1'b0;
                    if (source_record_r + 1 == records) begin
                        source_record_r <= 2'd0;
                        if (source_block_r + 1 == BLOCKS) begin
                            source_done <= 1'b1;
                            in_valid <= 1'b0;
                        end else begin
                            source_block_r <= source_block_r + 1'b1;
                        end
                    end else begin
                        source_record_r <= source_record_r + 1'b1;
                    end
                end
            end else begin
                source_group_r <= source_group_r + 1'b1;
            end
        end
    endtask

    integer expected_columns;
    integer expected_passes;
    integer expected_valid;
    integer expected_column;
    integer expected_lane;
    reg [11:0] expected_mask;
    reg [127:0] expected_column_weights;
    reg [7:0] expected_code;
    reg [5:0] expected_shift;

    task automatic check_output;
        begin
            expected_columns = columns_for_block(expected_block_r);
            expected_passes = pass_count(expected_columns);
            expected_valid = expected_columns - expected_pass_r*12;
            if (expected_valid > 12)
                expected_valid = 12;
            expected_mask = low_mask12(expected_valid);
            if (out_block !== expected_block_r ||
                out_pass !== expected_pass_r ||
                out_matrix !== expected_matrix_r ||
                out_group !== expected_group_r ||
                out_first_group !== (expected_group_r == 0) ||
                out_last_group !== (expected_group_r == GROUPS-1) ||
                out_last_pass !==
                    (expected_pass_r + 1 == expected_passes) ||
                out_last_block_transaction !==
                    (expected_pass_r + 1 == expected_passes &&
                     expected_matrix_r && expected_group_r == GROUPS-1) ||
                out_mask !== expected_mask)
                $fatal(1,
                    "tag/mask mismatch exp block=%0d pass=%0d matrix=%0d group=%0d mask=%03x got block=%0d pass=%0d matrix=%0d group=%0d mask=%03x first=%0d last=%0d lastpass=%0d lastblock=%0d",
                    expected_block_r, expected_pass_r,
                    expected_matrix_r, expected_group_r, expected_mask,
                    out_block, out_pass, out_matrix, out_group, out_mask,
                    out_first_group, out_last_group, out_last_pass,
                    out_last_block_transaction);

            for (expected_column = 0; expected_column < 12;
                 expected_column = expected_column + 1) begin
                expected_column_weights = '0;
                expected_code = '0;
                expected_shift = '0;
                if (expected_column < expected_valid) begin
                    for (expected_lane = 0; expected_lane < 32;
                         expected_lane = expected_lane + 1)
                        expected_column_weights[expected_lane*4 +: 4] =
                            weight_value(expected_block_r,
                                expected_matrix_r,
                                expected_pass_r*12 + expected_column,
                                expected_group_r, expected_lane);
                    expected_code = code_value(expected_block_r,
                        expected_matrix_r,
                        expected_pass_r*12 + expected_column,
                        expected_group_r);
                    expected_shift = shift_value(expected_block_r,
                        expected_matrix_r,
                        expected_pass_r*12 + expected_column,
                        expected_group_r);
                end
                if (out_weights[expected_column*128 +: 128] !==
                        expected_column_weights ||
                    out_meta[expected_column*8 +: 8] !== expected_code ||
                    out_meta[96+expected_column*6 +: 6] !== expected_shift)
                    $fatal(1,
                        "payload mismatch block=%0d pass=%0d matrix=%0d group=%0d column=%0d",
                        expected_block_r, expected_pass_r,
                        expected_matrix_r, expected_group_r,
                        expected_column);
            end
        end
    endtask

    task automatic advance_expected;
        integer columns;
        integer passes;
        begin
            columns = columns_for_block(expected_block_r);
            passes = pass_count(columns);
            if (expected_group_r == GROUPS-1) begin
                expected_group_r <= '0;
                if (!expected_matrix_r) begin
                    expected_matrix_r <= 1'b1;
                end else begin
                    expected_matrix_r <= 1'b0;
                    if (expected_pass_r + 1 == passes) begin
                        expected_pass_r <= 2'd0;
                        if (expected_block_r + 1 == BLOCKS) begin
                            checker_done <= 1'b1;
                        end else begin
                            expected_block_r <= expected_block_r + 1'b1;
                        end
                    end else begin
                        expected_pass_r <= expected_pass_r + 1'b1;
                    end
                end
            end else begin
                expected_group_r <= expected_group_r + 1'b1;
            end
        end
    endtask

    wire [BLOCK_W+6+1+2+GROUP_W+2048+224+16-1:0]
        input_payload = {source_block_r, source_columns, source_matrix_r,
            source_record_r, source_group_r, source_weights,
            source_meta, source_mask};
    wire [BLOCK_W+1+2+GROUP_W+1+1+1+1+1536+168+12-1:0]
        output_payload = {out_block, out_matrix, out_pass, out_group,
            out_first_group, out_last_group, out_last_pass,
            out_last_block_transaction, out_weights, out_meta, out_mask};

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            cycle_count <= 0;
            lfsr <= 32'h17a5_c3e1;
            out_ready <= 1'b0;
            input_stalled_r <= 1'b0;
            output_stalled_r <= 1'b0;
        end else begin
            cycle_count <= cycle_count + 1;
            lfsr <= {lfsr[30:0],
                lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};

            if (legal_mode) begin
                // Random bubbles plus deterministic long stalls exercise both
                // banks and all elastic stages.
                if (!in_valid && !source_done &&
                    (lfsr[0] || lfsr[5]))
                    in_valid <= 1'b1;
                else if (in_valid && in_ready) begin
                    advance_source();
                    // Deassert after every handshake.  The next symbolic
                    // payload is generated from state updated at this same
                    // edge; keeping valid high would violate stable payload
                    // semantics for the just-accepted transaction.
                    in_valid <= 1'b0;
                end
                out_ready <= !((cycle_count % 37) >= 11 &&
                    (cycle_count % 37) <= 19) &&
                    (lfsr[2] || lfsr[7] || lfsr[13]);
            end

            if (checker_enable && out_valid && out_ready) begin
                check_output();
                advance_expected();
            end

            if (in_valid && in_ready && out_valid && out_ready)
                overlap_input_output <= overlap_input_output + 1;

            if (input_stalled_r) begin
                if (!in_valid || input_payload !== held_input_payload_r)
                    $fatal(1, "TB source changed while stalled");
                input_stability_checks <= input_stability_checks + 1;
            end
            if (output_stalled_r) begin
                if (!out_valid || output_payload !== held_output_payload_r)
                    $fatal(1, "DUT output changed while stalled");
                output_stability_checks <= output_stability_checks + 1;
            end
            input_stalled_r <= in_valid && !in_ready;
            output_stalled_r <= out_valid && !out_ready;
            if (in_valid && !in_ready) begin
                held_input_payload_r <= input_payload;
                input_stall_cycles <= input_stall_cycles + 1;
            end
            if (out_valid && !out_ready) begin
                held_output_payload_r <= output_payload;
                output_stall_cycles <= output_stall_cycles + 1;
            end

            if (cycle_count > 100000)
                $fatal(1,
                    "timeout input=%0d blocks=%0d output=%0d blocks=%0d",
                    input_transaction_count, input_block_count,
                    output_transaction_count, output_block_count);
        end
    end

    task automatic drive_one_manual;
        input integer block_index;
        input integer columns;
        input integer matrix;
        input integer record_index;
        input integer group_index;
        integer guard;
        begin
            @(negedge clk);
            source_block_r = block_index;
            source_record_r = record_index;
            source_matrix_r = matrix;
            source_group_r = group_index;
            in_valid = 1'b1;
            guard = 0;
            while (!in_ready) begin
                // If ready is already low because this transaction was
                // accepted at the immediately preceding posedge, the DUT's
                // expected tag has advanced and the task is complete.
                if (dut.fill_active_r &&
                    (dut.fill_group_r != group_index ||
                     dut.fill_matrix_r != matrix ||
                     dut.fill_record_r != record_index)) begin
                    in_valid = 1'b0;
                    disable drive_one_manual;
                end
                guard = guard + 1;
                if (guard == 20)
                    $fatal(1,
                        "manual source refused block=%0d record=%0d matrix=%0d group=%0d expected block=%0d record=%0d matrix=%0d group=%0d active=%0d first=%0d columns=%0d stored=%0d mask=%04x expectedmask=%04x",
                        block_index, record_index, matrix, group_index,
                        dut.next_fill_block_r, dut.fill_record_r,
                        dut.fill_matrix_r, dut.fill_group_r,
                        dut.fill_active_r, dut.fill_first_r,
                        source_columns, dut.fill_valid_columns_r,
                        source_mask, dut.contract_source_mask);
                @(negedge clk);
            end
            @(negedge clk);
            in_valid = 1'b0;
        end
    endtask

    integer expected_input_transactions;
    integer expected_output_transactions;
    integer block_index;
    initial begin
        expected_input_transactions = 0;
        expected_output_transactions = 0;
        for (block_index = 0; block_index < BLOCKS;
             block_index = block_index + 1) begin
            expected_input_transactions = expected_input_transactions +
                record_count(columns_for_block(block_index))*2*GROUPS;
            expected_output_transactions = expected_output_transactions +
                pass_count(columns_for_block(block_index))*2*GROUPS;
        end

        repeat (6) @(posedge clk);
        rst_n <= 1'b1;
        repeat (3) @(posedge clk);

        // Invalid first tag: matrix must start at gate(0).  The transaction is
        // refused and sticky error rises without changing counters.
        @(negedge clk);
        source_block_r = 0;
        source_record_r = 0;
        source_matrix_r = 1;
        source_group_r = 0;
        in_valid = 1'b1;
        repeat (3) @(posedge clk);
        #1;
        if (in_ready || !error || input_transaction_count != 0)
            $fatal(1,
                "illegal order not fail-closed ready=%0d error=%0d count=%0d",
                in_ready, error, input_transaction_count);
        @(negedge clk);
        in_valid = 1'b0;
        clear = 1'b1;
        @(negedge clk);
        clear = 1'b0;
        repeat (2) @(posedge clk);

        // Write a partial block and clear it before seal.  Resetless payload
        // contents must remain unobservable when the legal stream restarts.
        drive_one_manual(0, 48, 0, 0, 0);
        drive_one_manual(0, 48, 0, 0, 1);
        drive_one_manual(0, 48, 0, 0, 2);
        if (input_transaction_count != 3 || output_transaction_count != 0)
            $fatal(1, "partial fill counters are wrong");
        @(negedge clk);
        clear = 1'b1;
        @(negedge clk);
        clear = 1'b0;
        repeat (2) @(posedge clk);
        if (input_transaction_count != 0 || input_block_count != 0 ||
            output_transaction_count != 0 || output_block_count != 0 ||
            error)
            $fatal(1, "clear did not invalidate partial bank/counters");

        @(negedge clk);
        source_block_r = 0;
        source_record_r = 0;
        source_matrix_r = 0;
        source_group_r = 0;
        expected_block_r = 0;
        expected_pass_r = 0;
        expected_matrix_r = 0;
        expected_group_r = 0;
        source_done = 0;
        checker_done = 0;
        overlap_input_output = 0;
        input_stall_cycles = 0;
        output_stall_cycles = 0;
        input_stability_checks = 0;
        output_stability_checks = 0;
        legal_mode = 1'b1;
        checker_enable = 1'b1;

        wait (source_done && checker_done);
        repeat (5) @(posedge clk);
        if (error || in_valid || out_valid ||
            input_transaction_count != expected_input_transactions ||
            output_transaction_count != expected_output_transactions ||
            input_block_count != BLOCKS || output_block_count != BLOCKS ||
            overlap_input_output == 0 || input_stall_cycles == 0 ||
            output_stall_cycles == 0 || input_stability_checks == 0 ||
            output_stability_checks == 0)
            $fatal(1,
                "final gate failed error=%0d invalid=%0d outvalid=%0d input=%0d/%0d output=%0d/%0d blocks=%0d/%0d overlap=%0d stalls=%0d/%0d stability=%0d/%0d",
                error, in_valid, out_valid,
                input_transaction_count, expected_input_transactions,
                output_transaction_count, expected_output_transactions,
                input_block_count, output_block_count,
                overlap_input_output, input_stall_cycles,
                output_stall_cycles, input_stability_checks,
                output_stability_checks);

        $display("PASS: gate/up gather ping-pong bit-exact groups=%0d blocks=%0d input=%0d output=%0d overlap=%0d stalls=%0d/%0d stability=%0d/%0d cycles=%0d",
            GROUPS, BLOCKS, input_transaction_count, output_transaction_count,
            overlap_input_output, input_stall_cycles, output_stall_cycles,
            input_stability_checks, output_stability_checks, cycle_count);
        $finish;
    end

endmodule

module hap_mlp_gate_up_gather_pingpong12_full_groups_tb;
    hap_mlp_gate_up_gather_pingpong12_tb #(
        .GROUPS(128), .GROUP_W(7)
    ) u_formal_groups_tb ();
endmodule
