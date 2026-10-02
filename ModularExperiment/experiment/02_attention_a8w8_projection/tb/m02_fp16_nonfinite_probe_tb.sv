`timescale 1ns / 1ps

// Directed characterization of the exact AMD Floating-Point IP chain used by
// the matched FP16 projection baseline.  This is deliberately a probe, not a
// golden-value test: every intermediate bit pattern is recorded so real
// projection traces that exceed the binary16 finite range can use observed
// hardware semantics instead of an invented software saturation policy.
module m02_fp16_nonfinite_probe_tb;
    localparam integer CASES = 25;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    wire in_ready;
    reg [255:0] in_act_u8 = '0;
    reg [255:0] in_wgt_s8 = '0;
    reg [7:0] in_act_zero_point = 8'd0;
    reg [15:0] in_act_scale_fp16 = 16'h1c00;
    reg [15:0] in_wgt_scale_fp16 = 16'h1c00;
    wire out_valid;
    reg out_ready = 1'b1;
    wire signed [41:0] out_guard_s42;
    wire [31:0] input_group_count;
    wire [31:0] output_group_count;
    wire error;

    integer correlations [0:CASES-1];
    reg [15:0] act_scales [0:CASES-1];
    reg [15:0] weight_scales [0:CASES-1];
    integer current_case = -1;
    integer requested_corr = 0;
    integer observed_corr = 0;
    integer failures = 0;
    integer completed = 0;
    integer corr_events = 0;
    integer c32_events = 0;
    integer c16_events = 0;
    integer mul1_events = 0;
    integer mul2_events = 0;
    integer widen_events = 0;
    integer fixed_events = 0;
    reg output_seen = 1'b0;
    reg [31:0] observed_c32 = '0;
    reg [15:0] observed_c16 = '0;
    reg [15:0] observed_mul1 = '0;
    reg [15:0] observed_mul2 = '0;
    reg [31:0] observed_widen = '0;
    reg [47:0] observed_fixed = '0;

    always #5 clk = ~clk;

    m3_fp16_scale_lane dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_act_u8(in_act_u8), .in_wgt_s8(in_wgt_s8),
        .in_act_zero_point(in_act_zero_point),
        .in_act_scale_fp16(in_act_scale_fp16),
        .in_wgt_scale_fp16(in_wgt_scale_fp16),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_guard_s42(out_guard_s42),
        .input_group_count(input_group_count),
        .output_group_count(output_group_count), .error(error));

    function automatic integer fp16_nonfinite(input reg [15:0] value);
        begin
            fp16_nonfinite = (value[14:10] == 5'h1f);
        end
    endfunction

    function automatic integer fp32_nonfinite(input reg [31:0] value);
        begin
            fp32_nonfinite = (value[30:23] == 8'hff);
        end
    endfunction

    // Construct an exact pre-centered group32 correlation without bypassing
    // the production integer MAC.  Relevant Q/K/V trace extrema are below
    // 300k, so at most eleven lanes are required by this decomposition.
    task automatic encode_correlation(input integer target);
        integer magnitude;
        integer lane;
        integer quotient;
        integer base;
        begin
            in_act_u8 = '0;
            in_wgt_s8 = '0;
            in_act_zero_point = 8'd0;
            magnitude = (target < 0) ? -target : target;
            base = (target < 0) ? 128 : 127;
            lane = 0;
            while (magnitude > 0) begin
                if (lane >= 32) begin
                    $display("FAIL: M02 probe correlation cannot be encoded target=%0d", target);
                    $fatal(1);
                end
                quotient = magnitude / base;
                if (quotient > 255)
                    quotient = 255;
                if (quotient > 0) begin
                    in_act_u8[lane*8 +: 8] = quotient[7:0];
                    if (target < 0)
                        in_wgt_s8[lane*8 +: 8] = 8'h80;
                    else
                        in_wgt_s8[lane*8 +: 8] = 8'h7f;
                    magnitude = magnitude - quotient * base;
                end else begin
                    in_act_u8[lane*8 +: 8] = magnitude[7:0];
                    if (target < 0)
                        in_wgt_s8[lane*8 +: 8] = 8'hff;
                    else
                        in_wgt_s8[lane*8 +: 8] = 8'h01;
                    magnitude = 0;
                end
                lane = lane + 1;
            end
        end
    endtask

    task automatic run_case(input integer index);
        begin
            current_case = index;
            requested_corr = correlations[index];
            corr_events = 0;
            c32_events = 0;
            c16_events = 0;
            mul1_events = 0;
            mul2_events = 0;
            widen_events = 0;
            fixed_events = 0;
            output_seen = 1'b0;
            encode_correlation(requested_corr);
            in_act_scale_fp16 = act_scales[index];
            in_wgt_scale_fp16 = weight_scales[index];

            // Start every request on a falling edge so in_valid necessarily
            // spans the following rising edge.  run_case returns after a
            // rising edge, so omitting this alignment would make cases after
            // the first only half-cycle pulses that the DUT never accepts.
            @(negedge clk);
            while (!in_ready)
                @(negedge clk);
            in_valid = 1'b1;
            @(negedge clk);
            in_valid = 1'b0;

            fork : timeout_block
                begin
                    repeat (400) @(posedge clk);
                    if (!output_seen) begin
                        $display("FAIL: M02 probe timeout case=%0d corr=%0d", index,
                            requested_corr);
                        $fatal(1);
                    end
                end
                begin
                    wait (output_seen);
                end
            join_any
            disable timeout_block;
            repeat (2) @(posedge clk);
        end
    endtask

    always @(posedge clk) begin
        if (rst_n) begin
            if (dut.corr_valid) begin
                corr_events = corr_events + 1;
                observed_corr = $signed(dut.corr);
            end
            if (dut.c32v) begin
                c32_events = c32_events + 1;
                observed_c32 = dut.c32d;
            end
            if (dut.c16v) begin
                c16_events = c16_events + 1;
                observed_c16 = dut.c16d;
            end
            if (dut.actv) begin
                mul1_events = mul1_events + 1;
                observed_mul1 = dut.actd;
            end
            if (dut.finalv) begin
                mul2_events = mul2_events + 1;
                observed_mul2 = dut.finald;
            end
            if (dut.backv) begin
                widen_events = widen_events + 1;
                observed_widen = dut.backd;
            end
            if (dut.fixedv) begin
                fixed_events = fixed_events + 1;
                observed_fixed = dut.fixedd;
            end
            if (out_valid && out_ready) begin
                if (observed_corr != requested_corr || corr_events != 1 ||
                        c32_events != 1 || c16_events != 1 ||
                        mul1_events != 1 || mul2_events != 1 ||
                        widen_events != 1 || fixed_events != 1 || error) begin
                    failures = failures + 1;
                    $display("FAIL: M02 probe protocol case=%0d requested=%0d observed=%0d events=%0d/%0d/%0d/%0d/%0d/%0d/%0d error=%b",
                        current_case, requested_corr, observed_corr, corr_events,
                        c32_events, c16_events, mul1_events, mul2_events,
                        widen_events, fixed_events, error);
                end
                $display("M02_FP16_SEMANTIC_RECORD_JSON: {\"case\":%0d,\"correlation_s21\":%0d,\"act_scale_fp16\":\"0x%04h\",\"weight_scale_fp16\":\"0x%04h\",\"correlation_fp32\":\"0x%08h\",\"correlation_fp16\":\"0x%04h\",\"correlation_fp16_nonfinite\":%0d,\"mul1_fp16\":\"0x%04h\",\"mul1_nonfinite\":%0d,\"mul2_fp16\":\"0x%04h\",\"mul2_nonfinite\":%0d,\"widen_fp32\":\"0x%08h\",\"widen_nonfinite\":%0d,\"float_to_s42_raw48\":\"0x%012h\",\"output_s42\":\"0x%011h\"}",
                    current_case, observed_corr, in_act_scale_fp16,
                    in_wgt_scale_fp16, observed_c32, observed_c16,
                    fp16_nonfinite(observed_c16), observed_mul1,
                    fp16_nonfinite(observed_mul1), observed_mul2,
                    fp16_nonfinite(observed_mul2), observed_widen,
                    fp32_nonfinite(observed_widen), observed_fixed,
                    out_guard_s42);
                completed = completed + 1;
                output_seen = 1'b1;
            end
        end
    end

    integer index;
    initial begin
        correlations[0]  = 0;
        correlations[1]  = 65503;
        correlations[2]  = 65504;
        correlations[3]  = 65519;
        correlations[4]  = 65520;
        correlations[5]  = 65521;
        correlations[6]  = 65535;
        correlations[7]  = 65536;
        correlations[8]  = -65503;
        correlations[9]  = -65504;
        correlations[10] = -65519;
        correlations[11] = -65520;
        correlations[12] = -65521;
        correlations[13] = -65535;
        correlations[14] = -65536;
        correlations[15] = 106787;
        correlations[16] = -121705;
        correlations[17] = 269277;
        correlations[18] = -277754;
        correlations[19] = 298909;
        correlations[20] = -269769;
        correlations[21] = 65520;
        correlations[22] = -65520;
        correlations[23] = 65520;
        correlations[24] = -65520;
        for (index = 0; index < CASES; index = index + 1) begin
            // 2^-8 x 2^-8 is representative of a small, nonzero native-scale
            // product while preserving Infinity through both multipliers.
            act_scales[index] = 16'h1c00;
            weight_scales[index] = 16'h1c00;
        end
        // Explicitly characterize Infinity multiplied by zero, which may
        // produce NaN before the final float-to-fixed conversion.
        act_scales[21] = 16'h0000;
        act_scales[22] = 16'h0000;
        weight_scales[23] = 16'h0000;
        weight_scales[24] = 16'h0000;

        repeat (8) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        for (index = 0; index < CASES; index = index + 1)
            run_case(index);

        if (failures == 0 && completed == CASES &&
                input_group_count == CASES && output_group_count == CASES) begin
            $display("M02_FP16_SEMANTIC_SUMMARY_JSON: {\"cases\":%0d,\"completed\":%0d,\"failures\":0,\"input_groups\":%0d,\"output_groups\":%0d}",
                CASES, completed, input_group_count, output_group_count);
            $display("PASS: M02 FP16 nonfinite semantic probe");
            $finish;
        end
        $display("FAIL: M02 probe final cases=%0d completed=%0d failures=%0d input=%0d output=%0d",
            CASES, completed, failures, input_group_count, output_group_count);
        $fatal(1);
    end
endmodule
