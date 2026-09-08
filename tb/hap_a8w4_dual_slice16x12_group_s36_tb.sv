`timescale 1ns / 1ps

module hap_a8w4_dual_slice16x12_group_s36_tb;
    localparam integer VECTOR_COUNT = 112;
    localparam integer CLEAR_CUT_INDEX = 48;
    localparam integer EXPECTED_AFTER_CLEAR = VECTOR_COUNT-CLEAR_CUT_INDEX;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire signed [4607:0] activation_s9x16x32;
    wire signed [1535:0] weights_s4x12x32;
    wire [127:0] activation_code_u8x16;
    wire [95:0] activation_shift_u6x16;
    wire [95:0] weight_code_u8x12;
    wire [71:0] weight_shift_u6x12;
    wire [11:0] column_valid_u12;
    wire out_valid;
    reg out_ready = 1'b1;
    wire signed [6911:0] guard_s36x16x12;
    wire [31:0] input_group_count;
    wire [31:0] output_group_count;
    wire error;

    reg [4607:0] activation_mem [0:VECTOR_COUNT-1];
    reg [1535:0] weights_mem [0:VECTOR_COUNT-1];
    reg [223:0] activation_meta_mem [0:VECTOR_COUNT-1];
    reg [167:0] weight_meta_mem [0:VECTOR_COUNT-1];
    reg [11:0] mask_mem [0:VECTOR_COUNT-1];
    reg [6911:0] expected_mem [0:VECTOR_COUNT-1];
    integer send_index = 0;
    integer receive_index = 0;
    integer cycle_count = 0;
    integer mismatch_count = 0;
    integer last_accept_cycle = -1;
    integer unstalled_accept_interval_max = 0;
    reg clear_issued = 1'b0;
    reg clear_pending = 1'b0;
    wire [6:0] source_index = send_index < VECTOR_COUNT ? send_index :
        VECTOR_COUNT-1;

    assign in_valid = send_index < VECTOR_COUNT &&
        (clear_issued || send_index < CLEAR_CUT_INDEX);
    assign activation_s9x16x32 = activation_mem[source_index];
    assign weights_s4x12x32 = weights_mem[source_index];
    assign activation_code_u8x16 = activation_meta_mem[source_index][127:0];
    assign activation_shift_u6x16 =
        activation_meta_mem[source_index][223:128];
    assign weight_code_u8x12 = weight_meta_mem[source_index][95:0];
    assign weight_shift_u6x12 = weight_meta_mem[source_index][167:96];
    assign column_valid_u12 = mask_mem[source_index];

    hap_a8w4_dual_slice16x12_group_s36 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .activation_s9x16x32(activation_s9x16x32),
        .weights_s4x12x32(weights_s4x12x32),
        .activation_code_u8x16(activation_code_u8x16),
        .activation_shift_u6x16(activation_shift_u6x16),
        .weight_code_u8x12(weight_code_u8x12),
        .weight_shift_u6x12(weight_shift_u6x12),
        .column_valid_u12(column_valid_u12),
        .out_valid(out_valid), .out_ready(out_ready),
        .guard_s36x16x12(guard_s36x16x12),
        .input_group_count(input_group_count),
        .output_group_count(output_group_count), .error(error)
    );

    initial begin
        $readmemh("data/a8w4_dual_slice16x12_group/activation_s9x16x32.mem",
            activation_mem);
        $readmemh("data/a8w4_dual_slice16x12_group/weights_s4x12x32.mem",
            weights_mem);
        $readmemh("data/a8w4_dual_slice16x12_group/activation_meta_u224.mem",
            activation_meta_mem);
        $readmemh("data/a8w4_dual_slice16x12_group/weight_meta_u168.mem",
            weight_meta_mem);
        $readmemh("data/a8w4_dual_slice16x12_group/column_valid_u12.mem",
            mask_mem);
        $readmemh("data/a8w4_dual_slice16x12_group/expected_s36x16x12.mem",
            expected_mem);
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
    end

    integer row;
    integer column;
    always @(posedge clk) begin
        if (!rst_n) begin
            out_ready <= 1'b1;
            send_index <= 0;
            receive_index <= 0;
            cycle_count <= 0;
            mismatch_count <= 0;
            last_accept_cycle <= -1;
            unstalled_accept_interval_max <= 0;
            clear_issued <= 1'b0;
            clear_pending <= 1'b0;
            clear <= 1'b0;
        end else begin
            cycle_count <= cycle_count + 1;
            // First half proves unstalled II=1.  Second half stresses the
            // atomic dual-slice join under deterministic pseudo-random stalls.
            out_ready <= (receive_index < 24) ? 1'b1 :
                ((cycle_count % 7) != 3 && (cycle_count % 11) != 5);
            clear <= 1'b0;
            if (!clear_issued && send_index >= CLEAR_CUT_INDEX &&
                receive_index >= CLEAR_CUT_INDEX &&
                input_group_count >= CLEAR_CUT_INDEX &&
                output_group_count >= CLEAR_CUT_INDEX) begin
                // Assert clear only after every pre-clear output drained.  The
                // counters must restart and the next accepted vector must be
                // exactly CLEAR_CUT_INDEX; this tests recovery without making
                // the scoreboard guess which accepted in-flight item died.
                clear <= 1'b1;
                clear_issued <= 1'b1;
                clear_pending <= 1'b1;
                last_accept_cycle <= -1;
            end else if (clear_pending) begin
                clear_pending <= 1'b0;
            end
            if (in_valid && in_ready) begin
                send_index <= send_index + 1;
                if (send_index < 24 && last_accept_cycle >= 0 &&
                    cycle_count-last_accept_cycle >
                    unstalled_accept_interval_max)
                    unstalled_accept_interval_max <=
                        cycle_count-last_accept_cycle;
                last_accept_cycle <= cycle_count;
            end
            if (out_valid && out_ready) begin
                if (guard_s36x16x12 !== expected_mem[receive_index]) begin
                    $display("MISMATCH index=%0d mask=%03x",
                        receive_index, mask_mem[receive_index]);
                    mismatch_count <= mismatch_count + 1;
                end
                for (row = 0; row < 16; row = row + 1)
                    for (column = 0; column < 12; column = column + 1)
                        if (!mask_mem[receive_index][column] &&
                            guard_s36x16x12[(row*12+column)*36 +: 36] !==
                            36'd0)
                            $fatal(1,
                                "FAIL: invalid tail column nonzero vector=%0d row=%0d column=%0d",
                                receive_index, row, column);
                receive_index <= receive_index + 1;
                if (receive_index + 1 == VECTOR_COUNT) begin
                    if (mismatch_count == 0 && !error &&
                        unstalled_accept_interval_max <= 1 &&
                        clear_issued &&
                        input_group_count == EXPECTED_AFTER_CLEAR &&
                        output_group_count + 1 == EXPECTED_AFTER_CLEAR) begin
                        $display("PASS: hap_a8w4_dual_slice16x12_group_s36 vectors=%0d cycles=%0d mismatches=0 masks=12/8/4 unstalled_ii=%0d",
                            VECTOR_COUNT, cycle_count,
                            unstalled_accept_interval_max);
                        $finish;
                    end else begin
                        $fatal(1,
                            "FAIL: mismatches=%0d error=%0d ii=%0d input_count=%0d output_count=%0d",
                            mismatch_count, error,
                            unstalled_accept_interval_max,
                            input_group_count, output_group_count + 1);
                    end
                end
            end
            if (cycle_count > 3500)
                $fatal(1, "FAIL: timeout send=%0d receive=%0d error=%0d",
                    send_index, receive_index, error);
        end
    end
endmodule
