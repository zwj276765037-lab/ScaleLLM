`timescale 1ns / 1ps

// Two interleaved cohort contexts, 12->16 Down S32 repacking, and a stalled
// consumer. Expected elements use the independent column mapping 12*p+lane
// to 16*record+lane, including values above signed-S24 range. The second
// block models the 16-column tail of 4096 = 85*48 + 16.
module hap_mlp_rebuild_repack_s32_tb;
    localparam integer ROWS = 16;
    localparam integer MATRICES = 2;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0;
    reg clear = 0;
    reg in_valid = 0;
    wire in_ready;
    reg signed [ROWS*12*32-1:0] in_projection_s32xrowsx12 = '0;
    reg [8:0] in_block_tag = 0;
    reg [1:0] in_pass_index = 0;
    reg in_matrix = 0;
    reg [11:0] in_col_valid_u12 = 12'hfff;
    reg in_last_pass = 0;
    wire out_valid;
    reg out_ready = 0;
    wire signed [ROWS*16*32-1:0] out_projection_s32xrowsx16;
    wire [8:0] out_block_tag;
    wire [1:0] out_record_index;
    wire out_matrix;
    wire [15:0] out_col_valid_u16;
    wire out_last_record;
    wire [31:0] input_pass_count;
    wire [31:0] output_record_count;
    wire error;

    integer cycles = 0;
    integer received = 0;
    integer checks = 0;
    integer pass;
    integer matrix;
    integer row;
    integer lane;
    reg saw_stall = 0;
    reg tail_phase = 0;
    reg tail_stalled = 0;
    reg held = 0;
    reg signed [ROWS*16*32-1:0] held_payload;
    reg [8:0] held_tag;
    reg [1:0] held_record;
    reg held_matrix;
    reg [15:0] held_mask;
    reg held_last;

    hap_mlp_projection_repack12_to16_s32_history2 #(
        .ROWS(ROWS), .MATRICES(MATRICES), .TAG_W(9), .MATRIX_W(1)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_projection_s32xrowsx12(in_projection_s32xrowsx12),
        .in_block_tag(in_block_tag), .in_pass_index(in_pass_index),
        .in_matrix(in_matrix), .in_col_valid_u12(in_col_valid_u12),
        .in_last_pass(in_last_pass),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_projection_s32xrowsx16(out_projection_s32xrowsx16),
        .out_block_tag(out_block_tag), .out_record_index(out_record_index),
        .out_matrix(out_matrix), .out_col_valid_u16(out_col_valid_u16),
        .out_last_record(out_last_record),
        .input_pass_count(input_pass_count),
        .output_record_count(output_record_count), .error(error)
    );

    function automatic signed [31:0] expected_word;
        input integer context_index;
        input integer row_index;
        input integer column;
        begin
            if (row_index == 1 && column == 0)
                expected_word = 32'sd14438400 + context_index;
            else if (row_index == 1 && column == 16)
                expected_word = -32'sd14438400 - context_index;
            else if (row_index == 15 && column == 47)
                expected_word = 32'sd9830400 + context_index;
            else
                expected_word = (context_index << 20) + (row_index << 12) + column;
        end
    endfunction

    function automatic signed [31:0] expected_tail_word;
        input integer context_index;
        input integer row_index;
        input integer column;
        begin
            if (row_index == 1 && column == 0)
                expected_tail_word = 32'sd14438400 + context_index;
            else if (row_index == 1 && column == 15)
                expected_tail_word = -32'sd14438400 - context_index;
            else if (row_index == 15 && column == 15)
                expected_tail_word = 32'sd9830400 + context_index;
            else
                expected_tail_word = 32'sh5100_0000 +
                                     (context_index << 20) +
                                     (row_index << 8) + column;
        end
    endfunction

    task automatic send_pass;
        input integer pass_number;
        input integer context_index;
        integer r;
        integer c;
        begin
            @(negedge clk);
            in_block_tag = 9'd37;
            in_pass_index = pass_number[1:0];
            in_matrix = context_index[0];
            in_col_valid_u12 = 12'hfff;
            in_last_pass = pass_number == 3;
            for (r = 0; r < ROWS; r = r + 1)
                for (c = 0; c < 12; c = c + 1)
                    in_projection_s32xrowsx12[(r*12+c)*32 +: 32] =
                        expected_word(context_index, r, pass_number*12+c);
            in_valid = 1;
            do @(posedge clk); while (in_ready !== 1'b1);
            @(negedge clk);
            in_valid = 0;
        end
    endtask

    task automatic send_tail_pass;
        input integer pass_number;
        input integer context_index;
        integer r;
        integer c;
        begin
            @(negedge clk);
            in_block_tag = 9'd85;
            in_pass_index = pass_number[1:0];
            in_matrix = context_index[0];
            in_col_valid_u12 = pass_number == 0 ? 12'hfff : 12'h00f;
            in_last_pass = pass_number == 1;
            for (r = 0; r < ROWS; r = r + 1)
                for (c = 0; c < 12; c = c + 1)
                    in_projection_s32xrowsx12[(r*12+c)*32 +: 32] =
                        (pass_number == 1 && c >= 4) ?
                        (32'hdead_0000 ^ (context_index << 16) ^
                         (r << 8) ^ c) :
                        expected_tail_word(context_index, r,
                                           pass_number*12+c);
            in_valid = 1;
            do @(posedge clk); while (in_ready !== 1'b1);
            @(negedge clk);
            in_valid = 0;
        end
    endtask

    task automatic send_next_block_first_pass;
        input integer context_index;
        begin
            @(negedge clk);
            in_block_tag = 9'd86;
            in_pass_index = 2'd0;
            in_matrix = context_index[0];
            in_col_valid_u12 = 12'hfff;
            in_last_pass = 0;
            in_projection_s32xrowsx12 = context_index == 0 ?
                {ROWS*12{32'h6a00_0000}} :
                {ROWS*12{32'h6b00_0000}};
            in_valid = 1;
            do @(posedge clk); while (in_ready !== 1'b1);
            @(negedge clk);
            in_valid = 0;
        end
    endtask

    initial begin
        repeat (5) @(negedge clk);
        rst_n = 1;
        for (pass = 0; pass < 4; pass = pass + 1)
            for (matrix = 0; matrix < MATRICES; matrix = matrix + 1)
                send_pass(pass, matrix);
        wait (received == 6);
        repeat (3) @(posedge clk);
        if (saw_stall !== 1'b1 || error !== 1'b0 ||
            input_pass_count !== 32'd8 ||
            output_record_count !== 32'd6 ||
            checks !== 6*ROWS*16)
            $fatal(1, "S32 repack status stall=%0d error=%0d in=%0d out=%0d",
                saw_stall, error, input_pass_count, output_record_count);

        tail_phase = 1;
        for (pass = 0; pass < 2; pass = pass + 1)
            for (matrix = 0; matrix < MATRICES; matrix = matrix + 1)
                send_tail_pass(pass, matrix);
        wait (received == 8);
        repeat (9) @(posedge clk);
        if (error !== 1'b0 || input_pass_count !== 32'd12 ||
            output_record_count !== 32'd8 || out_valid !== 1'b0 ||
            checks !== 8*ROWS*16 || tail_stalled !== 1'b1)
            $fatal(1, "S32 tail16 status error=%0d in=%0d out=%0d valid=%0d",
                error, input_pass_count, output_record_count, out_valid);
        tail_phase = 0;

        // The next block's first 12 columns cannot complete a record. This
        // catches a retained tail or an extra empty output after the tail16.
        for (matrix = 0; matrix < MATRICES; matrix = matrix + 1)
            send_next_block_first_pass(matrix);
        repeat (9) @(posedge clk);
        if (error !== 1'b0 || input_pass_count !== 32'd14 ||
            output_record_count !== 32'd8 || out_valid !== 1'b0)
            $fatal(1, "S32 stale carry after tail16 error=%0d in=%0d out=%0d valid=%0d",
                error, input_pass_count, output_record_count, out_valid);

        @(negedge clk);
        clear = 1;
        @(negedge clk);
        clear = 0;
        in_block_tag = 9'd38;
        in_pass_index = 2'd1;
        in_matrix = 0;
        in_col_valid_u12 = 12'hfff;
        in_last_pass = 0;
        in_valid = 1;
        @(posedge clk);
        @(negedge clk);
        in_valid = 0;
        if (error !== 1'b1 || in_ready !== 1'b0 ||
            out_valid !== 1'b0 || input_pass_count !== 32'd0 ||
            output_record_count !== 32'd0)
            $fatal(1, "S32 repack accepted illegal first pass");
        $display("checks=%0d full_records=6 tail16_records=2 contexts=2 high_bits=1 no_stale_carry=1 illegal_order_refused=1", checks);
        $display("HARDWARE_AGENT_SIM_PASS");
        $finish;
    end

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            cycles <= 0;
            out_ready <= 0;
            held <= 0;
            tail_stalled <= 0;
        end else begin
            cycles <= cycles + 1;
            if ((in_ready !== 1'b0 && in_ready !== 1'b1) ||
                (out_valid !== 1'b0 && out_valid !== 1'b1) ||
                (error !== 1'b0 && error !== 1'b1))
                $fatal(1, "S32 repack control contains X/Z");
            if (out_valid === 1'b1 &&
                ((^out_projection_s32xrowsx16) === 1'bx ||
                 (^out_block_tag) === 1'bx ||
                 (^out_record_index) === 1'bx ||
                 (^out_matrix) === 1'bx ||
                 (^out_col_valid_u16) === 1'bx ||
                 (out_last_record !== 1'b0 && out_last_record !== 1'b1)))
                $fatal(1, "S32 repack valid output contains X/Z");
            out_ready <= saw_stall && (cycles % 7) >= 3 &&
                         (!tail_phase || tail_stalled);
            if (held && (out_valid !== 1'b1 ||
                         out_projection_s32xrowsx16 !== held_payload ||
                         out_block_tag !== held_tag ||
                         out_record_index !== held_record ||
                         out_matrix !== held_matrix ||
                         out_col_valid_u16 !== held_mask ||
                         out_last_record !== held_last))
                $fatal(1, "S32 repack output changed under stall");
            held <= out_valid && !out_ready;
            if (out_valid && !out_ready) begin
                saw_stall <= 1;
                if (out_block_tag === 9'd85)
                    tail_stalled <= 1;
                held_payload <= out_projection_s32xrowsx16;
                held_tag <= out_block_tag;
                held_record <= out_record_index;
                held_matrix <= out_matrix;
                held_mask <= out_col_valid_u16;
                held_last <= out_last_record;
            end
            if (out_valid && out_ready) begin
                if (received < 6) begin
                    if (out_block_tag !== 9'd37 ||
                        out_record_index !== received/2 ||
                        out_matrix !== received[0] ||
                        out_col_valid_u16 !== 16'hffff ||
                        out_last_record !== (received/2 == 2))
                        $fatal(1, "S32 repack record identity mismatch record=%0d",
                            received);
                    for (row = 0; row < ROWS; row = row + 1)
                        for (lane = 0; lane < 16; lane = lane + 1) begin
                            if ($signed(out_projection_s32xrowsx16[(row*16+lane)*32 +: 32]) !==
                                expected_word(received % 2, row,
                                              (received/2)*16+lane))
                                $fatal(1, "S32 repack data mismatch record=%0d row=%0d lane=%0d got=%0d",
                                    received, row, lane,
                                    $signed(out_projection_s32xrowsx16[(row*16+lane)*32 +: 32]));
                            checks = checks + 1;
                        end
                end else if (received < 8) begin
                    if (out_block_tag !== 9'd85 ||
                        out_record_index !== 2'd0 ||
                        out_matrix !== (received-6) ||
                        out_col_valid_u16 !== 16'hffff ||
                        out_last_record !== 1'b1)
                        $fatal(1, "S32 tail16 record identity mismatch record=%0d",
                            received);
                    for (row = 0; row < ROWS; row = row + 1)
                        for (lane = 0; lane < 16; lane = lane + 1) begin
                            if ($signed(out_projection_s32xrowsx16[(row*16+lane)*32 +: 32]) !==
                                expected_tail_word(received-6, row, lane))
                                $fatal(1, "S32 tail16 data mismatch record=%0d row=%0d lane=%0d got=%0d",
                                    received, row, lane,
                                    $signed(out_projection_s32xrowsx16[(row*16+lane)*32 +: 32]));
                            checks = checks + 1;
                        end
                end else
                    $fatal(1, "S32 repack emitted extra record=%0d", received);
                received <= received + 1;
            end
            if (cycles > 5000)
                $fatal(1, "S32 repack timeout received=%0d", received);
        end
    end
endmodule
