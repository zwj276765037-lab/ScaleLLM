`timescale 1ns / 1ps

module m09_gate_up_tile_tb #(
    parameter integer CASE_ID = 0,
    parameter integer BACKPRESSURE = 0,
    parameter integer START_TILE = 0,
    parameter integer RUN_TILES = 12,
    parameter string DATA_DIR = "data"
);
    localparam integer GROUPS = 128;
    localparam integer TILES = 12;
    localparam integer TRANSACTIONS = GROUPS*TILES;
    localparam integer RUN_TRANSACTIONS = GROUPS*RUN_TILES;
    localparam integer END_TRANSACTION = (START_TILE+RUN_TILES)*GROUPS;

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg out_ready = 1'b0;

    reg [4607:0] activation_mem [0:TRANSACTIONS-1];
    reg [1535:0] weight_mem [0:TRANSACTIONS-1];
    reg [223:0] activation_sc_mem [0:TRANSACTIONS-1];
    reg [167:0] weight_sc_mem [0:TRANSACTIONS-1];
    reg [255:0] activation_fp16_mem [0:TRANSACTIONS-1];
    reg [191:0] weight_fp16_mem [0:TRANSACTIONS-1];
    reg [511:0] activation_fp32_mem [0:TRANSACTIONS-1];
    reg [383:0] weight_fp32_mem [0:TRANSACTIONS-1];
    reg [11:0] mask_mem [0:TRANSACTIONS-1];
    reg [4607:0] expected_sc [0:TILES-1];
    reg [4607:0] expected_fp16 [0:TILES-1];
    reg [4607:0] expected_fp32 [0:TILES-1];

    integer cycle = 0;
    integer sent = START_TILE*GROUPS;
    integer received = START_TILE;
    wire [31:0] source_index = sent < TRANSACTIONS ?
        sent : TRANSACTIONS-1;
    integer first_accept = -1;
    integer first_output = -1;
    integer previous_accept = -1;
    integer previous_output = -1;
    integer input_ii_min = 999999;
    integer input_ii_max = 0;
    integer output_ii_min = 999999;
    integer output_ii_max = 0;
    integer input_wait_cycles = 0;
    integer output_stall_cycles = 0;
    integer stability_checks = 0;
    integer interval;
    integer lane;
    reg stalled_last_cycle = 1'b0;
    reg [4607:0] stalled_payload;
    reg [4607:0] expected_payload;
    wire in_valid = rst_n && sent < END_TRANSACTION;
    wire in_ready;
    wire in_first = (source_index % GROUPS) == 0;
    wire in_last = (source_index % GROUPS) == GROUPS-1;
    wire out_valid;
    wire signed [4607:0] projection_s24;
    wire [31:0] input_group_count;
    wire [31:0] output_tile_count;
    wire [31:0] saturation_count;
    wire error;

    generate
        if (CASE_ID == 0) begin : g_sc
            m09_sc_gate_up_tile dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_group(in_first), .in_last_group(in_last),
                .activation_s9x16x32(activation_mem[source_index]),
                .weights_s4x12x32(weight_mem[source_index]),
                .activation_code_u8x16(
                    activation_sc_mem[source_index][127:0]),
                .activation_shift_u6x16(
                    activation_sc_mem[source_index][223:128]),
                .weight_code_u8x12(weight_sc_mem[source_index][95:0]),
                .weight_shift_u6x12(weight_sc_mem[source_index][167:96]),
                .column_valid_u12(mask_mem[source_index]),
                .out_valid(out_valid), .out_ready(out_ready),
                .projection_s24x16x12(projection_s24),
                .input_group_count(input_group_count),
                .output_tile_count(output_tile_count),
                .saturation_count(saturation_count), .error(error)
            );
        end else if (CASE_ID == 1) begin : g_fp16
            assign saturation_count = 32'd0;
            m09_fp16_gate_up_tile dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_group(in_first), .in_last_group(in_last),
                .activation_s9x16x32(activation_mem[source_index]),
                .weights_s4x12x32(weight_mem[source_index]),
                .activation_scale_fpx16(activation_fp16_mem[source_index]),
                .weight_scale_fpx12(weight_fp16_mem[source_index]),
                .column_valid_u12(mask_mem[source_index]),
                .out_valid(out_valid), .out_ready(out_ready),
                .projection_s24x16x12(projection_s24),
                .input_group_count(input_group_count),
                .output_tile_count(output_tile_count), .error(error)
            );
        end else begin : g_fp32
            assign saturation_count = 32'd0;
            m09_fp32_gate_up_tile dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_group(in_first), .in_last_group(in_last),
                .activation_s9x16x32(activation_mem[source_index]),
                .weights_s4x12x32(weight_mem[source_index]),
                .activation_scale_fpx16(activation_fp32_mem[source_index]),
                .weight_scale_fpx12(weight_fp32_mem[source_index]),
                .column_valid_u12(mask_mem[source_index]),
                .out_valid(out_valid), .out_ready(out_ready),
                .projection_s24x16x12(projection_s24),
                .input_group_count(input_group_count),
                .output_tile_count(output_tile_count), .error(error)
            );
        end
    endgenerate

    function automatic [4607:0] expected_for_case;
        input integer tile;
        begin
            case (CASE_ID)
                0: expected_for_case = expected_sc[tile];
                1: expected_for_case = expected_fp16[tile];
                default: expected_for_case = expected_fp32[tile];
            endcase
        end
    endfunction

    initial begin
        $readmemh({DATA_DIR,"/activation_s9x16x32.mem"}, activation_mem);
        $readmemh({DATA_DIR,"/weights_s4x12x32.mem"}, weight_mem);
        $readmemh({DATA_DIR,"/activation_meta_sc_u224.mem"},
            activation_sc_mem);
        $readmemh({DATA_DIR,"/weight_meta_sc_u168.mem"}, weight_sc_mem);
        $readmemh({DATA_DIR,"/activation_scale_fp16x16.mem"},
            activation_fp16_mem);
        $readmemh({DATA_DIR,"/weight_scale_fp16x12.mem"}, weight_fp16_mem);
        $readmemh({DATA_DIR,"/activation_scale_fp32x16.mem"},
            activation_fp32_mem);
        $readmemh({DATA_DIR,"/weight_scale_fp32x12.mem"}, weight_fp32_mem);
        $readmemh({DATA_DIR,"/column_mask_u12.mem"}, mask_mem);
        $readmemh({DATA_DIR,"/expected_sc_s24x16x12.mem"}, expected_sc);
        $readmemh({DATA_DIR,"/expected_fp16_s24x16x12.mem"}, expected_fp16);
        $readmemh({DATA_DIR,"/expected_fp32_s24x16x12.mem"}, expected_fp32);
        repeat (10) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n)
            out_ready <= 1'b0;
        else if (BACKPRESSURE == 0)
            out_ready <= 1'b1;
        else
            out_ready <= !((cycle % 37) >= 25 && (cycle % 37) <= 31);
    end

    always @(posedge clk) begin
        if (rst_n) begin
            cycle <= cycle + 1;
            if (in_valid && in_ready) begin
                if (first_accept < 0)
                    first_accept = cycle;
                if (previous_accept >= 0) begin
                    interval = cycle-previous_accept;
                    if (interval < input_ii_min) input_ii_min = interval;
                    if (interval > input_ii_max) input_ii_max = interval;
                end
                previous_accept = cycle;
                sent <= sent + 1;
            end else if (in_valid) begin
                input_wait_cycles = input_wait_cycles + 1;
            end

            if (stalled_last_cycle) begin
                stability_checks = stability_checks + 1;
                if (!out_valid || projection_s24 !== stalled_payload) begin
                    $display("FAIL: M09 output changed under backpressure case=%0d cycle=%0d", CASE_ID, cycle);
                    $finish;
                end
            end
            stalled_last_cycle <= out_valid && !out_ready;
            if (out_valid && !out_ready) begin
                stalled_payload <= projection_s24;
                output_stall_cycles = output_stall_cycles + 1;
            end

            if (error) begin
                $display("FAIL: M09 sticky error case=%0d cycle=%0d sent=%0d received=%0d", CASE_ID, cycle, sent, received);
                $finish;
            end
            if (out_valid && out_ready) begin
                expected_payload = expected_for_case(received);
                if (first_output < 0)
                    first_output = cycle;
                if (previous_output >= 0) begin
                    interval = cycle-previous_output;
                    if (interval < output_ii_min) output_ii_min = interval;
                    if (interval > output_ii_max) output_ii_max = interval;
                end
                previous_output = cycle;
                if (projection_s24 !== expected_payload) begin
                    $display("FAIL: M09 mismatch case=%0d tile=%0d", CASE_ID, received);
                    for (lane = 0; lane < 192; lane = lane + 1)
                        if (projection_s24[lane*24 +: 24] !==
                            expected_payload[lane*24 +: 24])
                            $display("M09_MISMATCH tile=%0d lane=%0d expected=%h got=%h",
                                received, lane,
                                expected_payload[lane*24 +: 24],
                                projection_s24[lane*24 +: 24]);
                    $finish;
                end
                received <= received + 1;
                if (received == START_TILE+RUN_TILES-1) begin
                    if (sent != END_TRANSACTION ||
                        input_group_count != RUN_TRANSACTIONS ||
                        output_tile_count != RUN_TILES-1 ||
                        saturation_count != 0) begin
                        $display("FAIL: M09 counters case=%0d sent=%0d input=%0d received=%0d output=%0d saturation=%0d",
                            CASE_ID, sent, input_group_count, received,
                            output_tile_count, saturation_count);
                        $finish;
                    end
                    $display("M09_METRIC_JSON: {\"case_id\":%0d,\"backpressure\":%0d,\"groups\":%0d,\"tiles\":%0d,\"mismatches\":0,\"input_ii_min\":%0d,\"input_ii_max\":%0d,\"output_ii_min\":%0d,\"output_ii_max\":%0d,\"first_output_latency\":%0d,\"total_cycles\":%0d,\"input_wait_cycles\":%0d,\"output_stall_cycles\":%0d,\"stability_checks\":%0d}",
                        CASE_ID, BACKPRESSURE, RUN_TRANSACTIONS, RUN_TILES,
                        input_ii_min, input_ii_max, output_ii_min,
                        output_ii_max, first_output-first_accept,
                        cycle-first_accept+1, input_wait_cycles,
                        output_stall_cycles, stability_checks);
                    $display("PASS: M09 Gate/Up A8W4 native-scale matched tile case=%0d backpressure=%0d", CASE_ID, BACKPRESSURE);
                    $finish;
                end
            end
            if (cycle > 30000) begin
                $display("FAIL: M09 timeout case=%0d sent=%0d received=%0d input_count=%0d output_count=%0d",
                    CASE_ID, sent, received, input_group_count,
                    output_tile_count);
                $finish;
            end
        end
    end
endmodule
