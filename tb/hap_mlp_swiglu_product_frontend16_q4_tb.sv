`timescale 1ns / 1ps

module hap_mlp_swiglu_product_frontend16_q4_tb;
    localparam integer GROUPS = 3;
    localparam integer TILES = GROUPS*4;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire in_is_up;
    wire in_second_half;
    wire signed [6143:0] projection_s24x16x16;
    wire out_valid;
    reg out_ready = 1'b1;
    wire [4095:0] activation_u8x16x32;
    wire [383:0] activation_meta_u24x16;
    wire [31:0] input_tile_count;
    wire [31:0] product_group_count;
    wire [31:0] activation_group_count;
    wire [31:0] frontend_busy_cycle_count;
    wire error;

    reg [6143:0] tile_mem [0:TILES-1];
    reg [4095:0] expected_u8_mem [0:GROUPS-1];
    reg [383:0] expected_meta_mem [0:GROUPS-1];
    integer send_index = 0;
    integer receive_index = 0;
    integer cycle_count = 0;
    integer mismatch_count = 0;
    integer last_receive_cycle = 0;
    integer max_group_interval = 0;
    integer clear_count = 0;
    wire [3:0] tile_phase = send_index[3:0] % 4;
    wire [3:0] source_index = send_index < TILES ? send_index : TILES-1;

    assign in_valid = send_index < TILES &&
        ((cycle_count % 13) != 4);
    assign in_is_up = tile_phase == 1 || tile_phase == 3;
    assign in_second_half = tile_phase >= 2;
    assign projection_s24x16x16 = tile_mem[source_index];

    hap_mlp_swiglu_product_frontend16_q4 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_is_up(in_is_up), .in_second_half(in_second_half),
        .projection_s24x16x16(projection_s24x16x16),
        .out_valid(out_valid), .out_ready(out_ready),
        .activation_u8x16x32(activation_u8x16x32),
        .activation_meta_u24x16(activation_meta_u24x16),
        .input_tile_count(input_tile_count),
        .product_group_count(product_group_count),
        .activation_group_count(activation_group_count),
        .frontend_busy_cycle_count(frontend_busy_cycle_count),
        .error(error)
    );

    initial begin
        $readmemh("data/mlp_swiglu_product_frontend16_q4/projection_tiles_s24x16x16.mem",
            tile_mem);
        $readmemh("data/mlp_swiglu_product_frontend16_q4/expected_u8x16x32.mem",
            expected_u8_mem);
        $readmemh("data/mlp_swiglu_product_frontend16_q4/expected_meta_u24x16.mem",
            expected_meta_mem);
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
        wait (send_index == 2);
        @(negedge clk);
        clear = 1'b1;
        @(negedge clk);
        clear = 1'b0;
        clear_count = clear_count + 1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            out_ready <= 1'b1;
            send_index <= 0;
            receive_index <= 0;
            cycle_count <= 0;
            mismatch_count <= 0;
            last_receive_cycle <= 0;
            max_group_interval <= 0;
        end else if (clear) begin
            out_ready <= 1'b1;
            send_index <= 0;
            receive_index <= 0;
            cycle_count <= 0;
            mismatch_count <= 0;
            last_receive_cycle <= 0;
            max_group_interval <= 0;
        end else begin
            cycle_count <= cycle_count + 1;
            out_ready <= (cycle_count % 7) != 3 &&
                (cycle_count % 11) != 5;
            if (in_valid && in_ready)
                send_index <= send_index + 1;
            if (out_valid && out_ready) begin
                if (activation_u8x16x32 !==
                    expected_u8_mem[receive_index] ||
                    activation_meta_u24x16 !==
                    expected_meta_mem[receive_index]) begin
                    $display("MISMATCH group=%0d", receive_index);
                    mismatch_count <= mismatch_count + 1;
                end
                if (receive_index != 0 &&
                    cycle_count-last_receive_cycle > max_group_interval)
                    max_group_interval <= cycle_count-last_receive_cycle;
                last_receive_cycle <= cycle_count;
                receive_index <= receive_index + 1;
                if (receive_index + 1 == GROUPS) begin
                    if (mismatch_count == 0 && !error && clear_count == 1 &&
                        input_tile_count == TILES &&
                        product_group_count == GROUPS &&
                        activation_group_count + 1 == GROUPS) begin
                        $display("PASS: hap_mlp_swiglu_product_frontend16_q4 groups=%0d tiles=%0d cycles=%0d max_group_interval=%0d mismatches=0",
                            GROUPS, TILES, cycle_count,
                            cycle_count-last_receive_cycle >
                            max_group_interval ?
                            cycle_count-last_receive_cycle :
                            max_group_interval);
                        $finish;
                    end else begin
                        $display("DIAG sticky=%0d branch=%b hadamard=%0d quant=%b phase=%0d bank_valid=%b bank_complete=%b bank_seq=%0d/%0d score=%h/%h beats=%0d/%0d/%0d/%0d consume=%0d bank=%0d seq=%0d src=%0d dispatch=%0d completed=%0d",
                            dut.sticky_error_r, dut.branch_error,
                            dut.hadamard_error, dut.quant_error,
                            dut.expected_input_phase_r,
                            dut.bank_valid_r, dut.bank_complete_r,
                            dut.bank_group_seq_r[0],
                            dut.bank_group_seq_r[1],
                            dut.row_complete_scoreboard_r[0],
                            dut.row_complete_scoreboard_r[1],
                            dut.bank_branch_beat_count_r[0][0],
                            dut.bank_branch_beat_count_r[0][1],
                            dut.bank_branch_beat_count_r[1][0],
                            dut.bank_branch_beat_count_r[1][1],
                            dut.consume_active_r, dut.consume_bank_r,
                            dut.consume_group_seq_r, dut.source_row_r,
                            dut.dispatch_row_r,
                            dut.completed_row_count_r);
                        $fatal(1,
                            "FAIL mismatch=%0d error=%0d clear=%0d tiles=%0d product=%0d activation=%0d busy=%0d",
                            mismatch_count, error, clear_count,
                            input_tile_count,
                            product_group_count,
                            activation_group_count + 1,
                            frontend_busy_cycle_count);
                    end
                end
            end
            if (cycle_count > 6000)
                $fatal(1,
                    "FAIL timeout sent=%0d received=%0d error=%0d",
                    send_index, receive_index, error);
        end
    end
endmodule
