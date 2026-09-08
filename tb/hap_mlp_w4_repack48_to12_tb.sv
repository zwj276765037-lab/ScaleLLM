`timescale 1ns / 1ps

module hap_mlp_w4_repack48_to12_tb;
    localparam integer TAG_W = 32;
    localparam integer MAX_RECORDS = 1200;
    localparam integer MAX_PASSES = 1600;

    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;

    reg in_valid = 1'b0;
    wire in_ready;
    reg signed [2047:0] in_weights;
    reg [223:0] in_meta;
    reg [31:0] in_tag;
    reg [1:0] in_record_index;
    reg [15:0] in_mask;
    reg in_flush;

    wire out_valid;
    reg out_ready = 1'b0;
    wire signed [1535:0] out_weights;
    wire [167:0] out_meta;
    wire [31:0] out_tag;
    wire [1:0] out_pass_index;
    wire [11:0] out_mask;
    wire out_last;
    wire [31:0] input_record_count;
    wire [31:0] input_supertile_count;
    wire [31:0] output_pass_count;
    wire error;

    reg [2047:0] source_weights [0:MAX_RECORDS-1];
    reg [223:0] source_meta [0:MAX_RECORDS-1];
    reg [31:0] source_tag [0:MAX_RECORDS-1];
    reg [1:0] source_record [0:MAX_RECORDS-1];
    reg [15:0] source_mask [0:MAX_RECORDS-1];
    reg source_flush [0:MAX_RECORDS-1];

    reg [1535:0] expected_weights [0:MAX_PASSES-1];
    reg [167:0] expected_meta [0:MAX_PASSES-1];
    reg [31:0] expected_tag [0:MAX_PASSES-1];
    reg [1:0] expected_pass [0:MAX_PASSES-1];
    reg [11:0] expected_mask [0:MAX_PASSES-1];
    reg expected_last [0:MAX_PASSES-1];

    integer source_count = 0;
    integer expected_count = 0;
    integer expected_supertile_count = 0;
    integer source_index = 0;
    integer expected_index = 0;
    integer cycle_count = 0;
    integer i;
    reg automatic_mode = 1'b0;
    reg automatic_check = 1'b0;
    reg legal_done = 1'b0;
    reg [31:0] lfsr = 32'h1ace_b00c;

    function automatic [3:0] weight_value;
        input [31:0] tag;
        input integer column;
        input integer lane;
        begin
            weight_value = tag[3:0] + column*3 + lane*5 +
                tag[15:12];
        end
    endfunction

    function automatic [7:0] code_value;
        input [31:0] tag;
        input integer column;
        begin
            code_value = tag[7:0] ^ (column*8'h17) ^ tag[23:16];
        end
    endfunction

    function automatic [5:0] shift_value;
        input [31:0] tag;
        input integer column;
        begin
            shift_value = tag[13:8] + column*7 + tag[29:24];
        end
    endfunction

    function automatic [15:0] low_mask16;
        input integer count;
        begin
            if (count >= 16)
                low_mask16 = 16'hffff;
            else
                low_mask16 = (16'h0001 << count) - 16'h0001;
        end
    endfunction

    function automatic [11:0] low_mask12;
        input integer count;
        begin
            if (count >= 12)
                low_mask12 = 12'hfff;
            else
                low_mask12 = (12'h001 << count) - 12'h001;
        end
    endfunction

    task automatic append_supertile;
        input [31:0] tag;
        input integer valid_cols;
        integer records;
        integer passes;
        integer record;
        integer pass;
        integer col;
        integer lane;
        integer record_valid;
        integer pass_valid;
        integer absolute_col;
        reg [2047:0] weights16;
        reg [127:0] code16;
        reg [95:0] shift16;
        reg [1535:0] weights12;
        reg [95:0] code12;
        reg [71:0] shift12;
        begin
            if (valid_cols <= 0 || valid_cols > 48)
                $fatal(1, "append_supertile valid_cols=%0d", valid_cols);
            records = (valid_cols + 15) / 16;
            passes = (valid_cols + 11) / 12;
            for (record = 0; record < records; record = record + 1) begin
                record_valid = valid_cols - record*16;
                if (record_valid > 16)
                    record_valid = 16;
                weights16 = '0;
                code16 = '0;
                shift16 = '0;
                // Deliberately fill invalid tail columns with non-zero data;
                // the DUT must mask them at the 12-column output.
                for (col = 0; col < 16; col = col + 1) begin
                    absolute_col = record*16 + col;
                    code16[col*8 +: 8] = code_value(tag, absolute_col);
                    shift16[col*6 +: 6] = shift_value(tag, absolute_col);
                    for (lane = 0; lane < 32; lane = lane + 1)
                        weights16[(col*32+lane)*4 +: 4] =
                            weight_value(tag, absolute_col, lane);
                end
                source_weights[source_count] = weights16;
                source_meta[source_count] = {shift16, code16};
                source_tag[source_count] = tag;
                source_record[source_count] = record[1:0];
                source_mask[source_count] = low_mask16(record_valid);
                source_flush[source_count] = record == records-1;
                source_count = source_count + 1;
            end

            for (pass = 0; pass < passes; pass = pass + 1) begin
                pass_valid = valid_cols - pass*12;
                if (pass_valid > 12)
                    pass_valid = 12;
                weights12 = '0;
                code12 = '0;
                shift12 = '0;
                for (col = 0; col < pass_valid; col = col + 1) begin
                    absolute_col = pass*12 + col;
                    code12[col*8 +: 8] = code_value(tag, absolute_col);
                    shift12[col*6 +: 6] = shift_value(tag, absolute_col);
                    for (lane = 0; lane < 32; lane = lane + 1)
                        weights12[(col*32+lane)*4 +: 4] =
                            weight_value(tag, absolute_col, lane);
                end
                expected_weights[expected_count] = weights12;
                expected_meta[expected_count] = {shift12, code12};
                expected_tag[expected_count] = tag;
                expected_pass[expected_count] = pass[1:0];
                expected_mask[expected_count] = low_mask12(pass_valid);
                expected_last[expected_count] = pass == passes-1;
                expected_count = expected_count + 1;
            end
            expected_supertile_count = expected_supertile_count + 1;
        end
    endtask

    task automatic append_matrix;
        input [31:0] tag_prefix;
        input integer columns;
        integer remaining;
        integer supertile;
        integer valid_cols;
        begin
            remaining = columns;
            supertile = 0;
            while (remaining > 0) begin
                valid_cols = remaining > 48 ? 48 : remaining;
                append_supertile(tag_prefix | supertile, valid_cols);
                remaining = remaining - valid_cols;
                supertile = supertile + 1;
            end
        end
    endtask

    hap_mlp_w4_repack48_to12 #(.TAG_W(TAG_W)) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_weights_s4x16x32(in_weights),
        .in_weight_meta_u224(in_meta), .in_tag(in_tag),
        .in_record_index(in_record_index),
        .in_col_valid_u16(in_mask), .in_flush(in_flush),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_weights_s4x12x32(out_weights),
        .out_weight_meta_u168(out_meta), .out_tag(out_tag),
        .out_pass_index(out_pass_index),
        .out_col_valid_u12(out_mask), .out_last_pass(out_last),
        .input_record_count(input_record_count),
        .input_supertile_count(input_supertile_count),
        .output_pass_count(output_pass_count), .error(error)
    );

    // Array-indexed payload is stable whenever valid is stalled because
    // source_index advances only on an input handshake.
    always @* begin
        if (source_index < source_count) begin
            in_weights = source_weights[source_index];
            in_meta = source_meta[source_index];
            in_tag = source_tag[source_index];
            in_record_index = source_record[source_index];
            in_mask = source_mask[source_index];
            in_flush = source_flush[source_index];
        end else begin
            in_weights = '0;
            in_meta = '0;
            in_tag = '0;
            in_record_index = 2'd0;
            in_mask = 16'hffff;
            in_flush = 1'b0;
        end
    end

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            lfsr <= 32'h1ace_b00c;
            cycle_count <= 0;
            if (automatic_mode) begin
                source_index <= 0;
                expected_index <= 0;
                in_valid <= 1'b0;
            end
            legal_done <= 1'b0;
        end else begin
            cycle_count <= cycle_count + 1;
            lfsr <= {lfsr[30:0],
                lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};

            if (automatic_mode) begin
                if (!in_valid) begin
                    if (source_index < source_count &&
                        (lfsr[0] || lfsr[5]))
                        in_valid <= 1'b1;
                end else if (in_ready) begin
                    source_index <= source_index + 1;
                    if (source_index + 1 >= source_count)
                        in_valid <= 1'b0;
                    else
                        in_valid <= lfsr[1] || lfsr[9];
                end
                // Include deterministic seven-cycle sink stalls, not only
                // single random bubbles.  Source payload remains held by its
                // valid/ready contract throughout each long stall.
                out_ready <= !((cycle_count % 31) >= 9 &&
                    (cycle_count % 31) <= 15) &&
                    (lfsr[2] || lfsr[7] || lfsr[13]);
            end

            if (automatic_check && out_valid && out_ready) begin
                if (expected_index >= expected_count)
                    $fatal(1, "unexpected output pass");
                if (out_weights !== expected_weights[expected_index] ||
                    out_meta !== expected_meta[expected_index] ||
                    out_tag !== expected_tag[expected_index] ||
                    out_pass_index !== expected_pass[expected_index] ||
                    out_mask !== expected_mask[expected_index] ||
                    out_last !== expected_last[expected_index])
                    $fatal(1,
                        "bit-exact mismatch expected_index=%0d tag=%08x pass=%0d mask=%03x last=%0d",
                        expected_index, out_tag, out_pass_index,
                        out_mask, out_last);
                expected_index <= expected_index + 1;
                if (expected_index + 1 == expected_count)
                    legal_done <= 1'b1;
            end

            if (cycle_count > 20000)
                $fatal(1, "timeout source=%0d/%0d output=%0d/%0d",
                    source_index, source_count,
                    expected_index, expected_count);
        end
    end

    initial begin
        // Varied short tails exercise every pass count before formal matrix
        // boundaries.  The two formal shapes prove 896->1195 (14336) and
        // 256->342 (4096) record/pass behavior without padding DDR reads.
        append_supertile(32'h0100_0000, 48);
        append_supertile(32'h0100_0001, 37);
        append_supertile(32'h0100_0002, 20);
        append_supertile(32'h0100_0003, 1);
        append_matrix(32'h1000_0000, 14336);
        append_matrix(32'h2000_0000, 4096);

        if (source_count != 1161 || expected_count != 1548 ||
            expected_supertile_count != 389)
            $fatal(1,
                "vector construction counts records=%0d passes=%0d supertiles=%0d",
                source_count, expected_count, expected_supertile_count);

        repeat (6) @(posedge clk);
        automatic_mode <= 1'b1;
        automatic_check <= 1'b1;
        rst_n <= 1'b1;

        wait (legal_done);
        @(posedge clk);
        if (source_index != source_count || in_valid || error ||
            input_record_count != source_count ||
            input_supertile_count != expected_supertile_count ||
            output_pass_count != expected_count)
            $fatal(1,
                "legal counters/error records=%0d supertiles=%0d passes=%0d source=%0d valid=%0d error=%0d",
                input_record_count, input_supertile_count,
                output_pass_count, source_index, in_valid, error);
        $display("LEGAL_PASS records=%0d DDR_bytes=%0d supertiles=%0d passes=%0d cycles=%0d",
            source_count, source_count*256, expected_supertile_count,
            expected_count, cycle_count);

        // Stop the automatic source/checker and clear the leaf.  Presenting
        // record index 1 as a first record must be refused and flagged.
        automatic_mode <= 1'b0;
        automatic_check <= 1'b0;
        @(negedge clk);
        clear <= 1'b1;
        @(negedge clk);
        clear <= 1'b0;
        in_valid <= 1'b1;
        source_index = source_count;
        force in_tag = 32'hdead_0000;
        force in_record_index = 2'd1;
        force in_mask = 16'hffff;
        force in_flush = 1'b0;
        force in_weights = {512{4'ha}};
        force in_meta = {224{1'b1}};
        @(posedge clk);
        #1;
        if (in_ready || !error || input_record_count != 0)
            $fatal(1,
                "illegal sequence was not refused ready=%0d error=%0d count=%0d",
                in_ready, error, input_record_count);
        @(negedge clk);
        in_valid <= 1'b0;
        release in_tag;
        release in_record_index;
        release in_mask;
        release in_flush;
        release in_weights;
        release in_meta;

        // A legal record0 followed by record1 with a different tag must also
        // be refused.  This catches the real integration hazard: adjacent
        // V4 gate/up records can belong to a different matrix/tile.
        clear <= 1'b1;
        @(negedge clk);
        clear <= 1'b0;
        force in_tag = 32'hc1ea_0000;
        force in_record_index = 2'd0;
        force in_mask = 16'hffff;
        force in_flush = 1'b0;
        force in_weights = {512{4'h5}};
        force in_meta = {224{1'b0}};
        in_valid <= 1'b1;
        @(posedge clk);
        #1;
        if (input_record_count != 1 || error)
            $fatal(1, "partial record was not accepted");
        @(negedge clk);
        force in_tag = 32'hc1ea_0001;
        force in_record_index = 2'd1;
        @(posedge clk);
        #1;
        if (in_ready || !error || input_record_count != 1)
            $fatal(1,
                "mismatched tag was not refused ready=%0d error=%0d count=%0d",
                in_ready, error, input_record_count);

        // Clear must discard the partially filled supertile and clear sticky
        // error.  No output may escape from the abandoned record.
        @(negedge clk);
        in_valid <= 1'b0;
        clear <= 1'b1;
        @(negedge clk);
        clear <= 1'b0;
        release in_tag;
        release in_record_index;
        release in_mask;
        release in_flush;
        release in_weights;
        release in_meta;
        out_ready <= 1'b1;
        repeat (6) begin
            @(posedge clk);
            if (out_valid)
                $fatal(1, "abandoned partial supertile leaked output");
        end
        if (error || input_record_count != 0 ||
            input_supertile_count != 0 || output_pass_count != 0)
            $fatal(1, "clear did not reset state/counters");

        $display("PASS: hap_mlp_w4_repack48_to12 bit-exact, backpressure, formal tails, illegal-tag/index rejection and clear");
        $finish;
    end
endmodule
