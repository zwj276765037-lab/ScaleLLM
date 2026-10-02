`timescale 1ns / 1ps

module m07_pv_boundary_tb #(
    parameter integer CASE_ID = 0,
    parameter integer BACKPRESSURE = 1,
    parameter string DATA_DIR = "data_boundary",
    parameter integer EXPECTED_SATURATIONS = 16
);
    localparam integer ROWS = 72;
    localparam integer KEYS = 4236;
    localparam integer LANES = 16;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    reg out_ready = 1'b0;
    wire in_ready;
    wire out_valid;
    wire [383:0] out_context16_s24;
    wire [31:0] input_key_count;
    wire [31:0] conversion_key_count;
    wire [31:0] core_input_key_count;
    wire [31:0] output_row_count;
    wire [31:0] saturation_count;
    wire error;

    reg [7:0] row_length_mem [0:ROWS-1];
    reg [15:0] probability_mem [0:KEYS-1];
    reg [191:0] value_mem [0:KEYS-1];
    reg [15:0] meta_mem [0:KEYS-1];
    reg [383:0] expected_sc_mem [0:ROWS-1];
    reg [383:0] expected_fp16_mem [0:ROWS-1];
    reg [383:0] expected_fp32_mem [0:ROWS-1];

    integer cycle = 0;
    integer sent = 0;
    integer received = 0;
    integer send_row = 0;
    integer send_key = 0;
    integer numeric_mismatches = 0;
    integer difference = 0;
    integer numeric_error_max = 0;
    longint numeric_error_sum = 0;
    integer first_input_cycle = -1;
    integer first_output_cycle = -1;
    integer last_output_cycle = -1;
    integer previous_row_cycle = -1;
    integer row_interval_min = 32'h7fffffff;
    integer row_interval_max = 0;
    longint row_interval_sum = 0;
    integer interval = 0;
    integer lane = 0;
    reg done_pending = 1'b0;
    reg was_stalled = 1'b0;
    reg [383:0] held_output = '0;

    wire [7:0] current_send_length =
        send_row < ROWS ? row_length_mem[send_row] : 8'd1;
    wire input_first_key = send_key == 0;
    wire input_last_key = send_key == current_send_length-1;
    wire [15:0] input_probability =
        sent < KEYS ? probability_mem[sent] : 16'd0;
    wire [191:0] input_value =
        sent < KEYS ? value_mem[sent] : 192'd0;
    wire [15:0] input_meta =
        sent < KEYS ? meta_mem[sent] : 16'd0;
    wire [383:0] expected_context =
        received >= ROWS ? 384'd0 :
        CASE_ID == 0 ? expected_sc_mem[received] :
        CASE_ID == 1 ? expected_fp16_mem[received] :
                       expected_fp32_mem[received];

    generate
        if (CASE_ID == 0) begin : g_sc
            m07_sc_pv_boundary dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_key(input_first_key),
                .in_last_key(input_last_key),
                .in_prob_u16(input_probability),
                .in_v16_s12(input_value), .in_v_meta16(input_meta),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_context16_s24(out_context16_s24),
                .input_key_count(input_key_count),
                .conversion_key_count(conversion_key_count),
                .core_input_key_count(core_input_key_count),
                .output_row_count(output_row_count),
                .saturation_count(saturation_count), .error(error));
        end else if (CASE_ID == 1) begin : g_fp16
            m07_fp16_pv_boundary dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_key(input_first_key),
                .in_last_key(input_last_key),
                .in_prob_u16(input_probability),
                .in_v16_s12(input_value), .in_v_meta16(input_meta),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_context16_s24(out_context16_s24),
                .input_key_count(input_key_count),
                .conversion_key_count(conversion_key_count),
                .core_input_key_count(core_input_key_count),
                .output_row_count(output_row_count),
                .saturation_count(saturation_count), .error(error));
        end else begin : g_fp32
            m07_fp32_pv_boundary dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_key(input_first_key),
                .in_last_key(input_last_key),
                .in_prob_u16(input_probability),
                .in_v16_s12(input_value), .in_v_meta16(input_meta),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_context16_s24(out_context16_s24),
                .input_key_count(input_key_count),
                .conversion_key_count(conversion_key_count),
                .core_input_key_count(core_input_key_count),
                .output_row_count(output_row_count),
                .saturation_count(saturation_count), .error(error));
        end
    endgenerate

    always #5 clk = ~clk;

    initial begin
        if (CASE_ID < 0 || CASE_ID > 2)
            $error("M07 boundary CASE_ID must be 0, 1, or 2");
        if (BACKPRESSURE != 0 && BACKPRESSURE != 1)
            $error("M07 boundary BACKPRESSURE must be 0 or 1");
        $readmemh({DATA_DIR,"/row_key_count_u8.mem"}, row_length_mem);
        $readmemh({DATA_DIR,"/probability_u16.mem"}, probability_mem);
        $readmemh({DATA_DIR,"/value_s12x16.mem"}, value_mem);
        $readmemh({DATA_DIR,"/value_meta_sc_u16.mem"}, meta_mem);
        $readmemh({DATA_DIR,"/expected_sc_s24x16.mem"}, expected_sc_mem);
        $readmemh({DATA_DIR,"/expected_fp16_s24x16.mem"},
            expected_fp16_mem);
        $readmemh({DATA_DIR,"/expected_fp32_s24x16.mem"},
            expected_fp32_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n) begin
            in_valid <= 1'b0;
            out_ready <= 1'b0;
        end else begin
            in_valid <= sent < KEYS;
            if (BACKPRESSURE == 0)
                out_ready <= 1'b1;
            else
                out_ready <= !(((cycle % 43) >= 31) &&
                    ((cycle % 43) <= 36));
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            sent <= 0;
            received <= 0;
            send_row <= 0;
            send_key <= 0;
            numeric_mismatches = 0;
            numeric_error_max = 0;
            numeric_error_sum = 0;
            first_input_cycle <= -1;
            first_output_cycle <= -1;
            last_output_cycle <= -1;
            previous_row_cycle <= -1;
            row_interval_min = 32'h7fffffff;
            row_interval_max = 0;
            row_interval_sum = 0;
            done_pending <= 1'b0;
            was_stalled <= 1'b0;
        end else begin
            cycle <= cycle + 1;

            if (was_stalled &&
                    (!out_valid || out_context16_s24 !== held_output)) begin
                $display("FAIL: M07 boundary output changed under backpressure cycle=%0d",
                    cycle);
                $finish;
            end
            was_stalled <= out_valid && !out_ready;
            if (out_valid && !out_ready)
                held_output <= out_context16_s24;

            if (error) begin
                $display("FAIL: M07 boundary sticky error case=%0d cycle=%0d sent=%0d received=%0d",
                    CASE_ID, cycle, sent, received);
                $finish;
            end

            if (in_valid && in_ready) begin
                if (first_input_cycle < 0)
                    first_input_cycle <= cycle;
                sent <= sent + 1;
                if (input_last_key) begin
                    send_row <= send_row + 1;
                    send_key <= 0;
                end else begin
                    send_key <= send_key + 1;
                end
            end

            if (out_valid && out_ready) begin
                if (first_output_cycle < 0)
                    first_output_cycle <= cycle;
                for (lane = 0; lane < LANES; lane = lane + 1) begin
                    difference =
                        $signed({out_context16_s24[lane*24+23],
                            out_context16_s24[lane*24 +: 24]}) -
                        $signed({expected_context[lane*24+23],
                            expected_context[lane*24 +: 24]});
                    if (difference < 0)
                        difference = -difference;
                    numeric_error_sum = numeric_error_sum + difference;
                    if (difference > numeric_error_max)
                        numeric_error_max = difference;
                    if (difference != 0) begin
                        if (numeric_mismatches < 8)
                            $display("MISMATCH: M07 boundary row=%0d lane=%0d expected=%h got=%h diff=%0d",
                                received, lane,
                                expected_context[lane*24 +: 24],
                                out_context16_s24[lane*24 +: 24],
                                difference);
                        numeric_mismatches = numeric_mismatches + 1;
                    end
                end
                if (previous_row_cycle >= 0) begin
                    interval = cycle - previous_row_cycle;
                    row_interval_sum = row_interval_sum + interval;
                    if (interval < row_interval_min)
                        row_interval_min = interval;
                    if (interval > row_interval_max)
                        row_interval_max = interval;
                end
                previous_row_cycle <= cycle;
                received <= received + 1;
                if (received == ROWS-1) begin
                    last_output_cycle <= cycle;
                    done_pending <= 1'b1;
                end
            end

            if (done_pending) begin
                if (numeric_mismatches != 0 ||
                        input_key_count != KEYS ||
                        conversion_key_count != KEYS ||
                        core_input_key_count != KEYS ||
                        output_row_count != ROWS ||
                        saturation_count != EXPECTED_SATURATIONS ||
                        send_row != ROWS || received != ROWS) begin
                    $display("FAIL: M07 boundary final case=%0d numeric=%0d input=%0d conversion=%0d core=%0d output_rows=%0d saturation=%0d send_rows=%0d received=%0d",
                        CASE_ID, numeric_mismatches, input_key_count,
                        conversion_key_count, core_input_key_count,
                        output_row_count, saturation_count, send_row,
                        received);
                end else begin
                    $display("M07_BOUNDARY_METRIC_JSON: {\"case_id\":%0d,\"backpressure\":%0d,\"rows\":72,\"keys\":4236,\"lanes\":16,\"numeric_mismatches\":0,\"numeric_mae_s24_lsb\":%0f,\"numeric_max_s24_lsb\":%0d,\"saturations\":%0d,\"first_output_latency\":%0d,\"row_interval_min\":%0d,\"row_interval_mean\":%0f,\"row_interval_max\":%0d,\"cycles\":%0d}",
                        CASE_ID, BACKPRESSURE,
                        numeric_error_sum/real'(ROWS*LANES),
                        numeric_error_max,
                        EXPECTED_SATURATIONS,
                        first_output_cycle-first_input_cycle,
                        row_interval_min,
                        row_interval_sum/real'(ROWS-1),
                        row_interval_max,
                        last_output_cycle-first_input_cycle+1);
                    $display("PASS: M07 boundary-inclusive PV");
                end
                $finish;
            end

            if (cycle > 300000) begin
                $display("FAIL: M07 boundary timeout case=%0d sent=%0d received=%0d rows=%0d",
                    CASE_ID, sent, received, output_row_count);
                $finish;
            end
        end
    end
endmodule
