`timescale 1ns / 1ps

module hap_a8w4_group32_lane2_s36_tb;
    localparam integer VECTOR_COUNT = 2048;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire signed [287:0] activation_s9x32;
    wire signed [127:0] weight0_s4x32;
    wire signed [127:0] weight1_s4x32;
    wire [7:0] activation_code_u8;
    wire [5:0] activation_shift_u6;
    wire [7:0] weight0_code_u8;
    wire [5:0] weight0_shift_u6;
    wire [7:0] weight1_code_u8;
    wire [5:0] weight1_shift_u6;
    wire out_valid;
    reg out_ready = 1'b1;
    wire signed [35:0] guard0_s36;
    wire signed [35:0] guard1_s36;
    wire [31:0] input_group_count;
    wire [31:0] output_group_count;
    wire error;

    reg [287:0] activation_mem [0:VECTOR_COUNT-1];
    reg [255:0] weights_mem [0:VECTOR_COUNT-1];
    reg [41:0] metadata_mem [0:VECTOR_COUNT-1];
    reg [71:0] expected_mem [0:VECTOR_COUNT-1];
    integer send_index = 0;
    integer receive_index = 0;
    integer cycle_count = 0;
    integer mismatch_count = 0;
    integer last_accept_cycle = -1;
    integer unstalled_accept_interval_max = 0;
    wire [10:0] source_index = send_index < VECTOR_COUNT ? send_index :
        VECTOR_COUNT-1;

    assign in_valid = send_index < VECTOR_COUNT;
    assign activation_s9x32 = activation_mem[source_index];
    assign weight0_s4x32 = weights_mem[source_index][127:0];
    assign weight1_s4x32 = weights_mem[source_index][255:128];
    assign activation_code_u8 = metadata_mem[source_index][7:0];
    assign activation_shift_u6 = metadata_mem[source_index][13:8];
    assign weight0_code_u8 = metadata_mem[source_index][21:14];
    assign weight0_shift_u6 = metadata_mem[source_index][27:22];
    assign weight1_code_u8 = metadata_mem[source_index][35:28];
    assign weight1_shift_u6 = metadata_mem[source_index][41:36];

    hap_a8w4_group32_lane2_s36 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .activation_s9x32(activation_s9x32),
        .weight0_s4x32(weight0_s4x32),
        .weight1_s4x32(weight1_s4x32),
        .activation_code_u8(activation_code_u8),
        .activation_shift_u6(activation_shift_u6),
        .weight0_code_u8(weight0_code_u8),
        .weight0_shift_u6(weight0_shift_u6),
        .weight1_code_u8(weight1_code_u8),
        .weight1_shift_u6(weight1_shift_u6),
        .out_valid(out_valid), .out_ready(out_ready),
        .guard0_s36(guard0_s36), .guard1_s36(guard1_s36),
        .input_group_count(input_group_count),
        .output_group_count(output_group_count), .error(error)
    );

    initial begin
        $readmemh("data/a8w4_group32_lane2/activation_s9x32.mem",
            activation_mem);
        $readmemh("data/a8w4_group32_lane2/weights_s4x64.mem",
            weights_mem);
        $readmemh("data/a8w4_group32_lane2/metadata_u42.mem",
            metadata_mem);
        $readmemh("data/a8w4_group32_lane2/expected_s36x2.mem",
            expected_mem);
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            out_ready <= 1'b1;
            send_index <= 0;
            receive_index <= 0;
            cycle_count <= 0;
            mismatch_count <= 0;
            last_accept_cycle <= -1;
            unstalled_accept_interval_max <= 0;
        end else begin
            cycle_count <= cycle_count + 1;
            out_ready <= (receive_index < 1024) ? 1'b1 :
                ((cycle_count % 13) != 4 && (cycle_count % 19) != 8);
            if (in_valid && in_ready) begin
                send_index <= send_index + 1;
                if (send_index < 1024 && last_accept_cycle >= 0 &&
                    cycle_count-last_accept_cycle >
                    unstalled_accept_interval_max)
                    unstalled_accept_interval_max <=
                        cycle_count-last_accept_cycle;
                last_accept_cycle <= cycle_count;
            end
            if (out_valid && out_ready) begin
                if ({guard1_s36, guard0_s36} !==
                    expected_mem[receive_index]) begin
                    $display("MISMATCH index=%0d got=%h_%h expected=%h",
                        receive_index, guard1_s36, guard0_s36,
                        expected_mem[receive_index]);
                    mismatch_count <= mismatch_count + 1;
                end
                receive_index <= receive_index + 1;
                if (receive_index + 1 == VECTOR_COUNT) begin
                    if (mismatch_count == 0 && !error &&
                        unstalled_accept_interval_max <= 1 &&
                        input_group_count == VECTOR_COUNT &&
                        output_group_count + 1 == VECTOR_COUNT) begin
                        $display("PASS: hap_a8w4_group32_lane2_s36 vectors=%0d cycles=%0d mismatches=0 unstalled_ii=%0d",
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
            if (cycle_count > 10000)
                $fatal(1, "FAIL: timeout send=%0d receive=%0d error=%0d",
                    send_index, receive_index, error);
        end
    end
endmodule
