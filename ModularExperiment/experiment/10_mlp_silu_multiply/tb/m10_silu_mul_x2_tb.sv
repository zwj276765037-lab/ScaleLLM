`timescale 1ns / 1ps

// Power workload for the exact two-lane operator-only tops used by the
// routed OOC checkpoints.  Each lane consumes one half of the interleaved
// 6144-vector boundary data set, so both physical lanes remain active.
module m10_silu_mul_x2_tb #(
    parameter integer CASE_ID = 0,
    parameter integer BACKPRESSURE = 1,
    parameter string DATA_DIR = "data_boundary"
);
    localparam integer VECTOR_COUNT = 6144;
    localparam integer FP16_TOLERANCE = 4096;
    localparam integer FP32_TOLERANCE = 8;

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire [1:0] in_valid;
    wire [1:0] in_ready;
    wire [47:0] gate_s24;
    wire [47:0] up_s24;
    wire [31:0] gate_fp16;
    wire [31:0] up_fp16;
    wire [63:0] gate_fp32;
    wire [63:0] up_fp32;
    wire [1:0] out_valid;
    reg [1:0] out_ready = 2'b00;
    wire [63:0] out_product_s32;
    wire [1:0] error;

    reg [23:0] gate_s24_mem [0:VECTOR_COUNT-1];
    reg [23:0] up_s24_mem [0:VECTOR_COUNT-1];
    reg [15:0] gate_fp16_mem [0:VECTOR_COUNT-1];
    reg [15:0] up_fp16_mem [0:VECTOR_COUNT-1];
    reg [31:0] gate_fp32_mem [0:VECTOR_COUNT-1];
    reg [31:0] up_fp32_mem [0:VECTOR_COUNT-1];
    reg [31:0] expected_sc_mem [0:VECTOR_COUNT-1];
    reg [31:0] expected_fp16_mem [0:VECTOR_COUNT-1];
    reg [31:0] expected_fp32_mem [0:VECTOR_COUNT-1];

    integer sent [0:1];
    integer received [0:1];
    integer first_input_cycle [0:1];
    integer first_output_cycle [0:1];
    integer previous_accept_cycle [0:1];
    integer input_ii_max [0:1];
    integer mismatch_count [0:1];
    integer output_stall_cycles [0:1];
    integer stability_checks [0:1];
    longint signed numeric_error_sum [0:1];
    longint signed numeric_error_max [0:1];
    longint signed difference [0:1];
    reg was_stalled [0:1];
    reg [31:0] held_output [0:1];
    integer cycle = 0;
    integer lane;

    wire [12:0] source0 = sent[0] < VECTOR_COUNT ?
        sent[0] : VECTOR_COUNT-2;
    wire [12:0] source1 = sent[1] < VECTOR_COUNT ?
        sent[1] : VECTOR_COUNT-1;
    wire [12:0] expected_index0 = received[0] < VECTOR_COUNT ?
        received[0] : VECTOR_COUNT-2;
    wire [12:0] expected_index1 = received[1] < VECTOR_COUNT ?
        received[1] : VECTOR_COUNT-1;

    assign in_valid[0] = rst_n && sent[0] < VECTOR_COUNT;
    assign in_valid[1] = rst_n && sent[1] < VECTOR_COUNT;
    assign gate_s24[0 +: 24] = gate_s24_mem[source0];
    assign gate_s24[24 +: 24] = gate_s24_mem[source1];
    assign up_s24[0 +: 24] = up_s24_mem[source0];
    assign up_s24[24 +: 24] = up_s24_mem[source1];
    assign gate_fp16[0 +: 16] = gate_fp16_mem[source0];
    assign gate_fp16[16 +: 16] = gate_fp16_mem[source1];
    assign up_fp16[0 +: 16] = up_fp16_mem[source0];
    assign up_fp16[16 +: 16] = up_fp16_mem[source1];
    assign gate_fp32[0 +: 32] = gate_fp32_mem[source0];
    assign gate_fp32[32 +: 32] = gate_fp32_mem[source1];
    assign up_fp32[0 +: 32] = up_fp32_mem[source0];
    assign up_fp32[32 +: 32] = up_fp32_mem[source1];

    function automatic [31:0] expected_for_case;
        input integer index;
        begin
            case (CASE_ID)
                0: expected_for_case = expected_sc_mem[index];
                1: expected_for_case = expected_fp16_mem[index];
                default: expected_for_case = expected_fp32_mem[index];
            endcase
        end
    endfunction

    generate
        if (CASE_ID == 0) begin : g_sc
            m10_sc_silu_mul_x2 dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .gate_s24(gate_s24), .up_s24(up_s24),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_product_s32(out_product_s32));
            assign error = 2'b00;
        end else if (CASE_ID == 1) begin : g_fp16
            m10_fp16_silu_mul_x2 dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .gate_fp(gate_fp16), .up_fp(up_fp16),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_product_s32(out_product_s32), .error(error));
        end else begin : g_fp32
            m10_fp32_silu_mul_x2 dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .gate_fp(gate_fp32), .up_fp(up_fp32),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_product_s32(out_product_s32), .error(error));
        end
    endgenerate

    initial begin
        $readmemh({DATA_DIR,"/gate_s24.mem"}, gate_s24_mem);
        $readmemh({DATA_DIR,"/up_s24.mem"}, up_s24_mem);
        $readmemh({DATA_DIR,"/gate_fp16.mem"}, gate_fp16_mem);
        $readmemh({DATA_DIR,"/up_fp16.mem"}, up_fp16_mem);
        $readmemh({DATA_DIR,"/gate_fp32.mem"}, gate_fp32_mem);
        $readmemh({DATA_DIR,"/up_fp32.mem"}, up_fp32_mem);
        $readmemh({DATA_DIR,"/expected_sc_s32.mem"}, expected_sc_mem);
        $readmemh({DATA_DIR,"/expected_fp16_s32.mem"}, expected_fp16_mem);
        $readmemh({DATA_DIR,"/expected_fp32_s32.mem"}, expected_fp32_mem);
        repeat (10) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n)
            out_ready <= 2'b00;
        else if (BACKPRESSURE == 0)
            out_ready <= 2'b11;
        else begin
            out_ready[0] <= received[0] < 512 ? 1'b1 :
                !((cycle % 17) >= 9 && (cycle % 17) <= 11);
            out_ready[1] <= received[1] < 513 ? 1'b1 :
                !((cycle % 19) >= 12 && (cycle % 19) <= 15);
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            sent[0] <= 0;
            sent[1] <= 1;
            received[0] <= 0;
            received[1] <= 1;
            for (lane = 0; lane < 2; lane = lane + 1) begin
                first_input_cycle[lane] <= -1;
                first_output_cycle[lane] <= -1;
                previous_accept_cycle[lane] <= -1;
                input_ii_max[lane] <= 0;
                mismatch_count[lane] <= 0;
                output_stall_cycles[lane] <= 0;
                stability_checks[lane] <= 0;
                numeric_error_sum[lane] <= 0;
                numeric_error_max[lane] <= 0;
                was_stalled[lane] <= 1'b0;
            end
        end else begin
            cycle <= cycle + 1;
            if (|error) begin
                $display("FAIL: M10 x2 sticky error case=%0d cycle=%0d error=%b",
                    CASE_ID, cycle, error);
                $finish;
            end
            for (lane = 0; lane < 2; lane = lane + 1) begin
                if (was_stalled[lane]) begin
                    stability_checks[lane] <= stability_checks[lane] + 1;
                    if (!out_valid[lane] ||
                        out_product_s32[lane*32 +: 32] !== held_output[lane]) begin
                        $display("FAIL: M10 x2 output changed under backpressure case=%0d lane=%0d cycle=%0d",
                            CASE_ID, lane, cycle);
                        $finish;
                    end
                end
                was_stalled[lane] <= out_valid[lane] && !out_ready[lane];
                if (out_valid[lane] && !out_ready[lane]) begin
                    held_output[lane] <= out_product_s32[lane*32 +: 32];
                    output_stall_cycles[lane] <=
                        output_stall_cycles[lane] + 1;
                end
                if (in_valid[lane] && in_ready[lane]) begin
                    if (first_input_cycle[lane] < 0)
                        first_input_cycle[lane] <= cycle;
                    if (previous_accept_cycle[lane] >= 0 &&
                        sent[lane] < 512 &&
                        cycle-previous_accept_cycle[lane] > input_ii_max[lane])
                        input_ii_max[lane] <=
                            cycle-previous_accept_cycle[lane];
                    previous_accept_cycle[lane] <= cycle;
                    sent[lane] <= sent[lane] + 2;
                end
                if (out_valid[lane] && out_ready[lane]) begin
                    if (first_output_cycle[lane] < 0)
                        first_output_cycle[lane] <= cycle;
                    difference[lane] = $signed(
                        out_product_s32[lane*32 +: 32]);
                    difference[lane] = difference[lane] - $signed(
                        expected_for_case(lane == 0 ?
                            expected_index0 : expected_index1));
                    if (difference[lane] < 0)
                        difference[lane] = -difference[lane];
                    numeric_error_sum[lane] <=
                        numeric_error_sum[lane] + difference[lane];
                    if (difference[lane] > numeric_error_max[lane])
                        numeric_error_max[lane] <= difference[lane];
                    if (difference[lane] >
                            (CASE_ID == 0 ? 0 :
                             (CASE_ID == 1 ? FP16_TOLERANCE :
                              FP32_TOLERANCE))) begin
                        mismatch_count[lane] <= mismatch_count[lane] + 1;
                        if (mismatch_count[lane] < 8)
                            $display("MISMATCH: M10 x2 case=%0d lane=%0d index=%0d got=%h expected=%h diff=%0d",
                                CASE_ID, lane, received[lane],
                                out_product_s32[lane*32 +: 32],
                                expected_for_case(lane == 0 ?
                                    expected_index0 : expected_index1),
                                difference[lane]);
                    end
                    received[lane] <= received[lane] + 2;
                end
            end
            if (cycle > 50000) begin
                $display("FAIL: M10 x2 timeout case=%0d sent=%0d/%0d received=%0d/%0d",
                    CASE_ID, sent[0], sent[1], received[0], received[1]);
                $finish;
            end
        end
    end

    initial begin
        wait (rst_n);
        wait (received[0] >= VECTOR_COUNT &&
            received[1] >= VECTOR_COUNT+1);
        repeat (3) @(posedge clk);
        if (mismatch_count[0] != 0 || mismatch_count[1] != 0 ||
            input_ii_max[0] > 1 || input_ii_max[1] > 1) begin
            $display("FAIL: M10 x2 final case=%0d mismatch=%0d/%0d ii=%0d/%0d",
                CASE_ID, mismatch_count[0], mismatch_count[1],
                input_ii_max[0], input_ii_max[1]);
            $finish;
        end
        $display("M10_X2_METRIC_JSON: {\"case_id\":%0d,\"backpressure\":%0d,\"vectors\":6144,\"lanes\":2,\"mismatches\":0,\"input_ii_max\":%0d,\"first_output_latency_max\":%0d,\"total_cycles\":%0d,\"numeric_error_sum\":%0d,\"numeric_error_max\":%0d,\"output_stall_cycles\":%0d,\"stability_checks\":%0d}",
            CASE_ID, BACKPRESSURE,
            input_ii_max[0] > input_ii_max[1] ?
                input_ii_max[0] : input_ii_max[1],
            first_output_cycle[0]-first_input_cycle[0] >
                    first_output_cycle[1]-first_input_cycle[1] ?
                first_output_cycle[0]-first_input_cycle[0] :
                first_output_cycle[1]-first_input_cycle[1], cycle+1,
            numeric_error_sum[0]+numeric_error_sum[1],
            numeric_error_max[0] > numeric_error_max[1] ?
                numeric_error_max[0] : numeric_error_max[1],
            output_stall_cycles[0]+output_stall_cycles[1],
            stability_checks[0]+stability_checks[1]);
        $display("PASS: M10 x2 SiLU multiply case=%0d backpressure=%0d",
            CASE_ID, BACKPRESSURE);
        $finish;
    end

    initial begin
        if (CASE_ID < 0 || CASE_ID > 2)
            $error("M10 x2 CASE_ID must be 0, 1, or 2");
        if (BACKPRESSURE < 0 || BACKPRESSURE > 1)
            $error("M10 x2 BACKPRESSURE must be 0 or 1");
    end
endmodule
