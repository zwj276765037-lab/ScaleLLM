`timescale 1ns / 1ps

module hap_pv_tile16_s43_tb #(
    parameter string DATA_DIR = "data/sc_source"
);
    localparam integer SOURCE_ROW_COUNT = 32;
    localparam integer TEST_ROW_COUNT = 96;
    localparam integer KEY_COUNT = 128;
    localparam integer SOURCE_INPUT_COUNT = SOURCE_ROW_COUNT * KEY_COUNT;
    localparam integer TEST_INPUT_COUNT = TEST_ROW_COUNT * KEY_COUNT;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    wire in_ready;
    reg in_first_key = 1'b0;
    reg in_last_key = 1'b0;
    reg [15:0] in_prob = '0;
    reg [191:0] in_v16 = '0;
    reg [15:0] in_meta = '0;
    wire out_valid;
    reg out_ready = 1'b0;
    wire [383:0] out_context16;
    wire [31:0] input_key_count;
    wire [31:0] output_row_count;
    wire [31:0] saturation_count;
    wire error;
    reg [15:0] prob_mem [0:SOURCE_INPUT_COUNT-1];
    reg [191:0] value_mem [0:SOURCE_INPUT_COUNT-1];
    reg [15:0] meta_mem [0:SOURCE_INPUT_COUNT-1];
    reg [383:0] expected_mem [0:SOURCE_ROW_COUNT-1];
    reg [7:0] expected_sat_mem [0:SOURCE_ROW_COUNT-1];
    integer cycle = 0;
    integer send_index = 0;
    integer receive_index = 0;
    integer mismatch_count = 0;
    integer expected_saturation_total = 0;
    integer previous_accept_cycle = -1;
    integer min_accept_interval = 999;
    integer max_accept_interval = 0;
    integer first_input_cycle = -1;
    integer first_output_cycle = -1;
    integer previous_output_cycle = -1;
    integer min_output_interval = 999999;
    integer max_output_interval = 0;
    integer output_interval;
    reg [383:0] held_output = '0;
    reg was_stalled = 1'b0;

    always #5 clk = ~clk;
    hap_pv_tile16_s43 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_first_key(in_first_key), .in_last_key(in_last_key),
        .in_prob_u16(in_prob), .in_v16_s12(in_v16),
        .in_v_meta16(in_meta), .out_valid(out_valid),
        .out_ready(out_ready), .out_context16_s24(out_context16),
        .input_key_count(input_key_count),
        .output_row_count(output_row_count),
        .saturation_count(saturation_count), .error(error)
    );

    initial begin
        $readmemh({DATA_DIR,"/input_prob.mem"}, prob_mem);
        $readmemh({DATA_DIR,"/input_v16_s12.mem"}, value_mem);
        $readmemh({DATA_DIR,"/input_meta16.mem"}, meta_mem);
        $readmemh({DATA_DIR,"/expected_context16_s24.mem"}, expected_mem);
        $readmemh({DATA_DIR,"/expected_saturation.mem"}, expected_sat_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n) begin
            in_valid <= 1'b0;
            out_ready <= 1'b0;
        end else begin
            out_ready <= !(((cycle % 31) >= 21) && ((cycle % 31) <= 25));
            if (send_index < TEST_INPUT_COUNT) begin
                in_prob <= prob_mem[send_index % SOURCE_INPUT_COUNT];
                in_v16 <= value_mem[send_index % SOURCE_INPUT_COUNT];
                in_meta <= meta_mem[send_index % SOURCE_INPUT_COUNT];
                in_first_key <= ((send_index % KEY_COUNT) == 0);
                in_last_key <= ((send_index % KEY_COUNT) == KEY_COUNT-1);
                in_valid <= 1'b1;
            end else begin
                in_valid <= 1'b0;
            end
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            send_index <= 0;
            receive_index <= 0;
            mismatch_count <= 0;
            expected_saturation_total <= 0;
            previous_accept_cycle <= -1;
            min_accept_interval <= 999;
            max_accept_interval <= 0;
            first_input_cycle <= -1;
            first_output_cycle <= -1;
            previous_output_cycle <= -1;
            min_output_interval <= 999999;
            max_output_interval <= 0;
            was_stalled <= 1'b0;
        end else begin
            cycle <= cycle + 1;
            if (was_stalled && (!out_valid || out_context16 !== held_output)) begin
                $display("FAIL: PV output changed under backpressure cycle=%0d", cycle);
                $finish;
            end
            was_stalled <= out_valid && !out_ready;
            if (out_valid && !out_ready)
                held_output <= out_context16;
            if (in_valid && in_ready) begin
                if (first_input_cycle < 0)
                    first_input_cycle <= cycle;
                if ((previous_accept_cycle >= 0) &&
                    ((send_index % KEY_COUNT) != 0)) begin
                    if ((cycle - previous_accept_cycle) < min_accept_interval)
                        min_accept_interval <= cycle - previous_accept_cycle;
                    if ((cycle - previous_accept_cycle) > max_accept_interval)
                        max_accept_interval <= cycle - previous_accept_cycle;
                end
                previous_accept_cycle <= cycle;
                send_index <= send_index + 1;
            end
            if (out_valid && out_ready) begin
                if (out_context16 !==
                        expected_mem[receive_index % SOURCE_ROW_COUNT]) begin
                    mismatch_count <= mismatch_count + 1;
                    $display("MISMATCH row=%0d expected=%h got=%h",
                        receive_index,
                        expected_mem[receive_index % SOURCE_ROW_COUNT],
                        out_context16);
                end
                expected_saturation_total <= expected_saturation_total +
                    expected_sat_mem[receive_index % SOURCE_ROW_COUNT];
                if (first_output_cycle < 0)
                    first_output_cycle <= cycle;
                if (previous_output_cycle >= 0) begin
                    output_interval = cycle - previous_output_cycle;
                    if (output_interval < min_output_interval)
                        min_output_interval <= output_interval;
                    if (output_interval > max_output_interval)
                        max_output_interval <= output_interval;
                end
                previous_output_cycle <= cycle;
                receive_index <= receive_index + 1;
            end
            if (error) begin
                $display("FAIL: PV sticky error cycle=%0d send=%0d recv=%0d",
                    cycle, send_index, receive_index);
                $finish;
            end
            if ((receive_index == TEST_ROW_COUNT-1) &&
                    out_valid && out_ready) begin
                if ((mismatch_count != 0) ||
                    (out_context16 !==
                        expected_mem[receive_index % SOURCE_ROW_COUNT]) ||
                    (input_key_count != TEST_INPUT_COUNT) ||
                    (output_row_count != TEST_ROW_COUNT-1) ||
                    (saturation_count != expected_saturation_total +
                        expected_sat_mem[receive_index % SOURCE_ROW_COUNT]) ||
                    (min_accept_interval != 1) ||
                    (max_accept_interval != 1)) begin
                    $display("FAIL: PV final mismatch=%0d in=%0d out_before=%0d sat=%0d expected_sat=%0d interval=%0d/%0d",
                        mismatch_count, input_key_count, output_row_count,
                        saturation_count, expected_saturation_total,
                        min_accept_interval, max_accept_interval);
                end else begin
                    $display("PV_TILE16_METRIC_JSON: {\"rows\":96,\"keys\":12288,\"lanes\":16,\"mismatches\":0,\"input_ii\":1,\"first_output_latency\":%0d,\"row_interval_min\":%0d,\"row_interval_max\":%0d,\"saturation_count\":%0d,\"cycles\":%0d}",
                        first_output_cycle-first_input_cycle,
                        min_output_interval,
                        output_interval > max_output_interval ?
                            output_interval : max_output_interval,
                        saturation_count,
                        cycle-first_input_cycle+1);
                    $display("PASS: PV tile16 S43 accumulation matched FixBit v2 golden.");
                end
                $finish;
            end
            if (cycle > 20000) begin
                $display("FAIL: PV timeout send=%0d recv=%0d", send_index, receive_index);
                $finish;
            end
        end
    end
endmodule
