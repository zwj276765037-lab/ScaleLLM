`timescale 1ns / 1ps

module hap_attention_cohort16_context_store_post_synth_tb;
    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg row_write_valid = 1'b0;
    reg [3:0] row_write_row = 4'd0;
    reg [4:0] row_write_head = 5'd0;
    reg [2:0] row_write_tile = 3'd0;
    reg [383:0] row_write_s24 = '0;
    reg read_issue = 1'b0;
    reg read_wave = 1'b0;
    reg [3:0] read_slot = 4'd0;
    reg [6:0] read_group = 7'd0;
    wire [8*32*24-1:0] activation_s24;
    integer index;
    integer checks = 0;

    hap_attention_cohort16_context_store_ooc_wrapper dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .row_write_valid(row_write_valid),
        .row_write_row(row_write_row),
        .row_write_head(row_write_head),
        .row_write_tile(row_write_tile),
        .row_write_s24(row_write_s24),
        .read_issue(read_issue), .read_wave(read_wave),
        .read_slot(read_slot), .read_group(read_group),
        .activation_s24(activation_s24)
    );

    function automatic [383:0] context_word(input integer slot);
        integer word_index;
        begin
            for (word_index = 0; word_index < 12;
                    word_index = word_index + 1)
                context_word[word_index*32 +: 32] =
                    32'h5a00_0000 + slot*16 + word_index;
        end
    endfunction

    task automatic tick;
        begin
            @(posedge clk);
            #1;
        end
    endtask

    initial begin
        repeat (12) tick();
        rst_n = 1'b1;
        tick();

        row_write_valid = 1'b1;
        for (index = 0; index < 16; index = index + 1) begin
            row_write_row = index >> 1;
            row_write_head = 5'd1;
            row_write_tile = 3'd2 + index[0];
            row_write_s24 = context_word(index);
            tick();
        end
        row_write_valid = 1'b0;
        tick();

        read_wave = 1'b0;
        read_group = 7'd5;
        read_issue = 1'b1;
        for (index = 0; index < 16; index = index + 1) begin
            read_slot = index;
            tick();
        end
        read_issue = 1'b0;
        tick();

        for (index = 0; index < 16; index = index + 1) begin
            checks = checks + 1;
            if (activation_s24[
                    (index >> 1)*768 + index[0]*384 +: 384] !==
                    context_word(index)) begin
                $display("FAIL: post-opt context slot %0d mismatch", index);
                $fatal(1);
            end
        end
        $display("PASS: context_store_post_opt_funcsim checks=%0d", checks);
        $finish;
    end
endmodule
