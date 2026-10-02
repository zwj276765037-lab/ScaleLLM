`timescale 1ns / 1ps

module m03_projection_rope_boundary_tb #(
    parameter integer CASE_ID = 0,
    parameter integer BACKPRESSURE = 1,
    parameter string DATA_DIR = "data_boundary"
);
    localparam integer GROUPS = 128;
    localparam integer PAIRS = 12;
    localparam integer TRANSACTIONS = GROUPS*PAIRS;

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg out_ready = 1'b0;
    wire in_valid;
    wire in_ready;
    wire out_valid;
    wire signed [23:0] out_y0_s24;
    wire signed [23:0] out_y1_s24;
    wire [31:0] input_group_count;
    wire [31:0] input_pair_count;
    wire [31:0] output_pair_count;
    wire [31:0] saturation_count;
    wire error;

    reg [41:0] correlation_mem [0:TRANSACTIONS-1];
    reg [41:0] sc_meta_mem [0:TRANSACTIONS-1];
    reg [47:0] fp16_scale_mem [0:TRANSACTIONS-1];
    reg [95:0] fp32_scale_mem [0:TRANSACTIONS-1];
    reg [35:0] coefficient_mem [0:PAIRS-1];
    reg [47:0] expected_sc_mem [0:PAIRS-1];
    reg [47:0] expected_fp16_mem [0:PAIRS-1];
    reg [47:0] expected_fp32_mem [0:PAIRS-1];

    integer cycle = 0;
    integer sent = 0;
    integer received = 0;
    integer mismatches = 0;
    integer first_input_cycle = -1;
    integer first_output_cycle = -1;
    integer final_cycle = -1;
    integer previous_accept_cycle = -1;
    integer ii_min = 999999;
    integer ii_max = 0;
    integer interval;
    integer input_wait_cycles = 0;
    integer output_stall_cycles = 0;
    integer stability_checks = 0;
    reg stalled_last_cycle = 1'b0;
    reg [47:0] stalled_output;

    wire [31:0] bounded_index = sent < TRANSACTIONS ?
        sent : TRANSACTIONS-1;
    wire [31:0] source_pair = bounded_index / GROUPS;
    wire [6:0] source_group = bounded_index % GROUPS;
    wire signed [20:0] in_corr0_s21 =
        correlation_mem[bounded_index][20:0];
    wire signed [20:0] in_corr1_s21 =
        correlation_mem[bounded_index][41:21];
    wire in_first_group = source_group == 0;
    wire in_last_group = source_group == GROUPS-1;
    wire signed [17:0] in_cos_s18 =
        coefficient_mem[source_pair][17:0];
    wire signed [17:0] in_sin_s18 =
        coefficient_mem[source_pair][35:18];
    wire [7:0] in_act_scale_code = sc_meta_mem[bounded_index][7:0];
    wire [5:0] in_act_scale_shift = sc_meta_mem[bounded_index][13:8];
    wire [7:0] in_weight0_scale_code = sc_meta_mem[bounded_index][21:14];
    wire [5:0] in_weight0_scale_shift = sc_meta_mem[bounded_index][27:22];
    wire [7:0] in_weight1_scale_code = sc_meta_mem[bounded_index][35:28];
    wire [5:0] in_weight1_scale_shift = sc_meta_mem[bounded_index][41:36];
    wire [15:0] in_act_scale_fp16 = fp16_scale_mem[bounded_index][15:0];
    wire [15:0] in_weight0_scale_fp16 =
        fp16_scale_mem[bounded_index][31:16];
    wire [15:0] in_weight1_scale_fp16 =
        fp16_scale_mem[bounded_index][47:32];
    wire [31:0] in_act_scale_fp32 = fp32_scale_mem[bounded_index][31:0];
    wire [31:0] in_weight0_scale_fp32 =
        fp32_scale_mem[bounded_index][63:32];
    wire [31:0] in_weight1_scale_fp32 =
        fp32_scale_mem[bounded_index][95:64];
    assign in_valid = rst_n && sent < TRANSACTIONS;

    function automatic [47:0] expected_output;
        input integer index;
        begin
            case (CASE_ID)
                0: expected_output = expected_sc_mem[index];
                1: expected_output = expected_fp16_mem[index];
                default: expected_output = expected_fp32_mem[index];
            endcase
        end
    endfunction

    generate
        if (CASE_ID == 0) begin : g_sc
            m03_sc_projection_rope_pair dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_group(in_first_group),
                .in_last_group(in_last_group),
                .in_corr0_s21(in_corr0_s21), .in_corr1_s21(in_corr1_s21),
                .in_act_scale_code(in_act_scale_code),
                .in_act_scale_shift(in_act_scale_shift),
                .in_weight0_scale_code(in_weight0_scale_code),
                .in_weight0_scale_shift(in_weight0_scale_shift),
                .in_weight1_scale_code(in_weight1_scale_code),
                .in_weight1_scale_shift(in_weight1_scale_shift),
                .in_cos_s18(in_cos_s18), .in_sin_s18(in_sin_s18),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_y0_s24(out_y0_s24), .out_y1_s24(out_y1_s24),
                .input_group_count(input_group_count),
                .input_pair_count(input_pair_count),
                .output_pair_count(output_pair_count),
                .saturation_count(saturation_count), .error(error));
        end else if (CASE_ID == 1) begin : g_fp16
            m03_fp16_projection_rope_pair dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_group(in_first_group),
                .in_last_group(in_last_group),
                .in_corr0_s21(in_corr0_s21), .in_corr1_s21(in_corr1_s21),
                .in_act_scale_fp(in_act_scale_fp16),
                .in_weight0_scale_fp(in_weight0_scale_fp16),
                .in_weight1_scale_fp(in_weight1_scale_fp16),
                .in_cos_s18(in_cos_s18), .in_sin_s18(in_sin_s18),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_y0_s24(out_y0_s24), .out_y1_s24(out_y1_s24),
                .input_group_count(input_group_count),
                .input_pair_count(input_pair_count),
                .output_pair_count(output_pair_count),
                .saturation_count(saturation_count), .error(error));
        end else begin : g_fp32
            m03_fp32_projection_rope_pair dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_group(in_first_group),
                .in_last_group(in_last_group),
                .in_corr0_s21(in_corr0_s21), .in_corr1_s21(in_corr1_s21),
                .in_act_scale_fp(in_act_scale_fp32),
                .in_weight0_scale_fp(in_weight0_scale_fp32),
                .in_weight1_scale_fp(in_weight1_scale_fp32),
                .in_cos_s18(in_cos_s18), .in_sin_s18(in_sin_s18),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_y0_s24(out_y0_s24), .out_y1_s24(out_y1_s24),
                .input_group_count(input_group_count),
                .input_pair_count(input_pair_count),
                .output_pair_count(output_pair_count),
                .saturation_count(saturation_count), .error(error));
        end
    endgenerate

    initial begin
        $readmemh({DATA_DIR,"/correlation_s21_pair.mem"}, correlation_mem);
        $readmemh({DATA_DIR,"/scale_meta_sc_u42.mem"}, sc_meta_mem);
        $readmemh({DATA_DIR,"/scale_fp16x3.mem"}, fp16_scale_mem);
        $readmemh({DATA_DIR,"/scale_fp32x3.mem"}, fp32_scale_mem);
        $readmemh({DATA_DIR,"/coeff_s18_pair.mem"}, coefficient_mem);
        $readmemh({DATA_DIR,"/expected_sc_s24_pair.mem"}, expected_sc_mem);
        $readmemh({DATA_DIR,"/expected_fp16_s24_pair.mem"},
            expected_fp16_mem);
        $readmemh({DATA_DIR,"/expected_fp32_s24_pair.mem"},
            expected_fp32_mem);
        repeat (10) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n)
            out_ready <= 1'b0;
        else if (BACKPRESSURE == 0)
            out_ready <= 1'b1;
        else if (BACKPRESSURE == 1)
            out_ready <= !((cycle % 23) >= 15 && (cycle % 23) <= 19);
        else
            out_ready <= !((cycle * 17 + 5) % 29 < 8);
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            sent <= 0;
            received <= 0;
            mismatches <= 0;
            first_input_cycle <= -1;
            first_output_cycle <= -1;
            final_cycle <= -1;
            previous_accept_cycle <= -1;
            ii_min <= 999999;
            ii_max <= 0;
            input_wait_cycles <= 0;
            output_stall_cycles <= 0;
            stability_checks <= 0;
            stalled_last_cycle <= 1'b0;
        end else begin
            cycle <= cycle + 1;
            if (error) begin
                $display("FAIL: M03 boundary sticky error case=%0d cycle=%0d sent=%0d received=%0d",
                    CASE_ID, cycle, sent, received);
                $finish;
            end
            if (in_valid && in_ready) begin
                if (first_input_cycle < 0)
                    first_input_cycle <= cycle;
                if (source_group != 0 && previous_accept_cycle >= 0) begin
                    interval = cycle-previous_accept_cycle;
                    if (interval < ii_min)
                        ii_min <= interval;
                    if (interval > ii_max)
                        ii_max <= interval;
                end
                previous_accept_cycle <= cycle;
                sent <= sent + 1;
            end else if (in_valid) begin
                input_wait_cycles <= input_wait_cycles + 1;
            end

            if (stalled_last_cycle) begin
                stability_checks <= stability_checks + 1;
                if (!out_valid || {out_y1_s24,out_y0_s24} !==
                    stalled_output) begin
                    $display("FAIL: M03 boundary output changed under backpressure case=%0d cycle=%0d",
                        CASE_ID, cycle);
                    $finish;
                end
            end
            stalled_last_cycle <= out_valid && !out_ready;
            if (out_valid && !out_ready) begin
                stalled_output <= {out_y1_s24,out_y0_s24};
                output_stall_cycles <= output_stall_cycles + 1;
            end

            if (out_valid && out_ready) begin
                if (first_output_cycle < 0)
                    first_output_cycle <= cycle;
                if ({out_y1_s24,out_y0_s24} !== expected_output(received)) begin
                    mismatches <= mismatches + 1;
                    $display("M03_BOUNDARY_MISMATCH case=%0d pair=%0d actual=%012x expected=%012x",
                        CASE_ID, received, {out_y1_s24,out_y0_s24},
                        expected_output(received));
                end
                received <= received + 1;
                if (received + 1 == PAIRS) begin
                    final_cycle <= cycle;
                    if (mismatches == 0 &&
                        {out_y1_s24,out_y0_s24} === expected_output(received) &&
                        input_group_count == TRANSACTIONS &&
                        input_pair_count == PAIRS &&
                        output_pair_count + 1 == PAIRS &&
                        ii_min == 2 && ii_max == 2) begin
                        $display("M03_BOUNDARY_METRIC_JSON: {\"case_id\":%0d,\"pairs\":12,\"groups_per_pair\":128,\"transactions\":1536,\"mismatches\":0,\"ii_min\":%0d,\"ii_max\":%0d,\"first_output_latency\":%0d,\"total_cycles\":%0d,\"input_wait_cycles\":%0d,\"output_stall_cycles\":%0d,\"stability_checks\":%0d,\"saturation_count\":%0d}",
                            CASE_ID, ii_min, ii_max,
                            first_output_cycle-first_input_cycle,
                            cycle-first_input_cycle+1, input_wait_cycles,
                            output_stall_cycles, stability_checks,
                            saturation_count);
                        $display("PASS: M03 projection-tail RoPE boundary case=%0d backpressure=%0d",
                            CASE_ID, BACKPRESSURE);
                    end else begin
                        $display("FAIL: M03 boundary final gate case=%0d mismatches=%0d groups=%0d in_pairs=%0d out_pairs=%0d ii=%0d/%0d",
                            CASE_ID, mismatches, input_group_count,
                            input_pair_count, output_pair_count+1,
                            ii_min, ii_max);
                    end
                    $finish;
                end
            end
            if (cycle > 50000) begin
                $display("FAIL: M03 boundary timeout case=%0d sent=%0d received=%0d",
                    CASE_ID, sent, received);
                $finish;
            end
        end
    end

    initial begin
        if (CASE_ID < 0 || CASE_ID > 2)
            $error("M03 boundary CASE_ID must be 0, 1, or 2");
        if (BACKPRESSURE < 0 || BACKPRESSURE > 2)
            $error("M03 boundary BACKPRESSURE must be 0, 1, or 2");
    end
endmodule
