`timescale 1ns / 1ps

module hap_attention_cohort16_local_stores_tb;
    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg rst_n = 1'b0;
    reg clear = 1'b0;
    integer checks = 0;
    integer index;
    integer lane;

    reg query_pair_valid = 1'b0;
    reg [8:0] query_pair_index = 9'd0;
    reg [9:0] query_tile = 10'd0;
    reg signed [23:0] query_y0 = 24'sd0;
    reg signed [23:0] query_y1 = 24'sd0;
    reg query_read_addr_valid = 1'b0;
    reg query_read_data_valid = 1'b0;
    reg [3:0] query_read_row = 4'd0;
    reg [4:0] query_read_head = 5'd0;
    reg [1:0] query_read_group = 2'd0;
    wire [767:0] query_read_data;

    reg post_capture_valid = 1'b0;
    reg [9:0] post_tile = 10'd0;
    reg post_wave = 1'b0;
    reg [8*16*24-1:0] post_projection = '0;
    reg post_shift_valid = 1'b0;
    reg [3:0] post_input_row = 4'd0;
    reg post_store_valid = 1'b0;
    reg [8:0] post_output_index = 9'd0;
    reg signed [23:0] post_y0 = 24'sd0;
    reg signed [23:0] post_y1 = 24'sd0;
    reg [3:0] post_quant_row = 4'd0;
    wire [47:0] post_pair;
    wire [4*768-1:0] post_quant;
    reg [8*16*24-1:0] even_projection;
    reg [8*16*24-1:0] odd_projection;

    reg context_write_valid = 1'b0;
    reg [3:0] context_write_row = 4'd0;
    reg [4:0] context_write_head = 5'd0;
    reg [2:0] context_write_tile = 3'd0;
    reg [383:0] context_write_data = '0;
    reg context_read_issue = 1'b0;
    reg context_read_wave = 1'b0;
    reg [3:0] context_read_slot = 4'd0;
    reg [6:0] context_read_group = 7'd0;
    wire [8*32*24-1:0] context_activation;

    hap_attention_cohort16_query_store u_query (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .pair_valid(query_pair_valid), .pair_index(query_pair_index),
        .projection_tile(query_tile), .pair_y0_s24(query_y0),
        .pair_y1_s24(query_y1), .read_addr_valid(query_read_addr_valid),
        .read_data_valid(query_read_data_valid), .read_row(query_read_row),
        .read_head(query_read_head), .read_group(query_read_group),
        .read_data_s24(query_read_data)
    );

    hap_attention_cohort16_postprocess_store u_post (
        .clk(clk), .projection_capture_valid(post_capture_valid),
        .projection_tile(post_tile), .projection_wave(post_wave),
        .projection_s24(post_projection),
        .rope_shift_valid(post_shift_valid), .rope_input_row(post_input_row),
        .rope_store_valid(post_store_valid),
        .rope_output_index(post_output_index), .rope_y0_s24(post_y0),
        .rope_y1_s24(post_y1), .quant_row(post_quant_row),
        .rope_input_pair_s24(post_pair), .quant_s24(post_quant)
    );

    hap_attention_cohort16_context_store u_context (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .row_write_valid(context_write_valid),
        .row_write_row(context_write_row),
        .row_write_head(context_write_head),
        .row_write_tile(context_write_tile),
        .row_write_s24(context_write_data),
        .read_issue(context_read_issue), .read_wave(context_read_wave),
        .read_slot(context_read_slot), .read_group(context_read_group),
        .activation_s24(context_activation)
    );

    function automatic [383:0] context_word(input integer slot);
        integer word_index;
        begin
            for (word_index = 0; word_index < 12;
                    word_index = word_index + 1)
                context_word[word_index*32 +: 32] =
                    32'hc000_0000 + slot*16 + word_index;
        end
    endfunction

    function automatic [47:0] query_pair_word(input integer pair);
        reg [23:0] low_word;
        reg [23:0] high_word;
        begin
            low_word = 24'h100000 + pair;
            high_word = 24'h200000 + pair;
            query_pair_word = {high_word, low_word};
        end
    endfunction

    task automatic tick;
        begin
            @(posedge clk);
            #1;
        end
    endtask

    task automatic check(input bit condition, input string reason);
        begin
            checks = checks + 1;
            if (condition !== 1'b1) begin
                $display("FAIL: %0s", reason);
                $fatal(1);
            end
        end
    endtask

    initial begin
        repeat (3) tick();
        rst_n = 1'b1;
        tick();

        // Query row 3, head 1, group 0: one complete 16-pair word.
        query_tile = 10'd8;
        query_pair_valid = 1'b1;
        for (index = 0; index < 16; index = index + 1) begin
            query_pair_index = 9'd48 + index;
            query_y0 = 24'h100000 + index;
            query_y1 = 24'h200000 + index;
            tick();
        end
        query_pair_valid = 1'b0;
        tick();
        query_read_row = 4'd3;
        query_read_head = 5'd1;
        query_read_group = 2'd0;
        query_read_addr_valid = 1'b1;
        tick();
        query_read_addr_valid = 1'b0;
        query_read_data_valid = 1'b1;
        tick();
        query_read_data_valid = 1'b0;
        for (index = 0; index < 16; index = index + 1)
            check(query_read_data[index*48 +: 48] ===
                query_pair_word(index),
                "query pair packing/address mismatch");

        // Context group 5 uses addresses 10/11 within each row.
        context_write_valid = 1'b1;
        for (index = 0; index < 16; index = index + 1) begin
            context_write_row = index >> 1;
            context_write_head = 5'd1;
            context_write_tile = 3'd2 + index[0];
            context_write_data = context_word(index);
            tick();
        end
        context_write_valid = 1'b0;
        tick();
        context_read_wave = 1'b0;
        context_read_group = 7'd5;
        context_read_issue = 1'b1;
        for (index = 0; index < 16; index = index + 1) begin
            context_read_slot = index;
            tick();
        end
        context_read_issue = 1'b0;
        tick();
        for (index = 0; index < 16; index = index + 1)
            check(context_activation[
                (index >> 1)*768 + index[0]*384 +: 384] ===
                context_word(index), "context BRAM bank/address mismatch");

        // Projection tile 320/321 must assemble each 768-bit V row exactly.
        for (lane = 0; lane < 96; lane = lane + 1) begin
            even_projection[lane*32 +: 32] = 32'he000_0000 + lane;
            odd_projection[lane*32 +: 32] = 32'hd000_0000 + lane;
        end
        post_projection = even_projection;
        post_tile = 10'd320;
        post_capture_valid = 1'b1;
        tick();
        post_projection = odd_projection;
        post_tile = 10'd321;
        tick();
        post_capture_valid = 1'b0;
        post_quant_row = 4'd0;
        #1;
        for (index = 0; index < 4; index = index + 1) begin
            check(post_quant[index*768 +: 384] ===
                even_projection[index*384 +: 384],
                "postprocess even tile mismatch");
            check(post_quant[index*768 + 384 +: 384] ===
                odd_projection[index*384 +: 384],
                "postprocess odd tile mismatch");
        end

        post_input_row = 4'd0;
        check(post_pair === even_projection[47:0],
            "postprocess initial RoPE pair mismatch");
        post_shift_valid = 1'b1;
        tick();
        post_shift_valid = 1'b0;
        check(post_pair === even_projection[95:48],
            "postprocess RoPE shift mismatch");
        post_store_valid = 1'b1;
        post_output_index = 9'd0;
        post_y0 = 24'h345678;
        post_y1 = 24'habcdef;
        tick();
        post_store_valid = 1'b0;
        check(post_quant[47:0] === {24'habcdef, 24'h345678},
            "postprocess RoPE result store mismatch");

        // Wave 1 selects rows 8-15 while preserving the local projection-row
        // order. An odd capture also resets the non-destructive RoPE cursor.
        for (lane = 0; lane < 96; lane = lane + 1) begin
            even_projection[lane*32 +: 32] = 32'ha000_0000 + lane;
            odd_projection[lane*32 +: 32] = 32'hb000_0000 + lane;
        end
        post_wave = 1'b1;
        post_projection = even_projection;
        post_tile = 10'd320;
        post_capture_valid = 1'b1;
        tick();
        post_projection = odd_projection;
        post_tile = 10'd321;
        tick();
        post_capture_valid = 1'b0;
        post_quant_row = 4'd8;
        #1;
        for (index = 0; index < 4; index = index + 1) begin
            check(post_quant[index*768 +: 384] ===
                even_projection[index*384 +: 384],
                "postprocess wave1 even tile mismatch");
            check(post_quant[index*768 + 384 +: 384] ===
                odd_projection[index*384 +: 384],
                "postprocess wave1 odd tile mismatch");
        end

        post_input_row = 4'd9;
        #1;
        check(post_pair === even_projection[384 +: 48],
            "postprocess wave1 row cursor reset mismatch");
        post_shift_valid = 1'b1;
        repeat (16) tick();
        post_shift_valid = 1'b0;
        check(post_pair === even_projection[384 +: 48],
            "postprocess RoPE cursor wrap mismatch");

        $display("PASS: hap_attention_cohort16_local_stores checks=%0d",
            checks);
        $finish;
    end
endmodule
