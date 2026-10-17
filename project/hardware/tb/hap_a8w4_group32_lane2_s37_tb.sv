`timescale 1ns / 1ps

module hap_a8w4_group32_lane2_s37_tb;
    localparam integer VECTOR_COUNT = 2048;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg traffic_enable = 1'b0;
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
    wire signed [36:0] guard0_s37;
    wire signed [36:0] guard1_s37;
    wire signed [44:0] guard0_s45;
    wire signed [44:0] guard1_s45;
    wire out_down;
    wire guard_overflow;
    wire [31:0] total_shift_format_count;
    wire format_error;
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
    integer last_accept_cycle = -1;
    integer unstalled_accept_interval_max = 0;
    integer meta_full_recovery_checks = 0;
    integer stalled_head_checks = 0;
    reg stalled_last_cycle = 1'b0;
    reg signed [73:0] stalled_guard_r;
    wire [10:0] source_index = send_index < VECTOR_COUNT ? send_index :
        VECTOR_COUNT-1;

    assign in_valid = traffic_enable && send_index < VECTOR_COUNT;
    assign activation_s9x32 = activation_mem[source_index];
    assign weight0_s4x32 = weights_mem[source_index][127:0];
    assign weight1_s4x32 = weights_mem[source_index][255:128];
    assign activation_code_u8 = metadata_mem[source_index][7:0];
    assign activation_shift_u6 = metadata_mem[source_index][13:8];
    assign weight0_code_u8 = metadata_mem[source_index][21:14];
    assign weight0_shift_u6 = metadata_mem[source_index][27:22];
    assign weight1_code_u8 = metadata_mem[source_index][35:28];
    assign weight1_shift_u6 = metadata_mem[source_index][41:36];

    hap_a8w4_group32_lane2_s37 #(.META_DEPTH(16)) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear), .down_mode(1'b0),
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
        .guard0_s37(guard0_s37), .guard1_s37(guard1_s37),
        .guard0_s45(guard0_s45), .guard1_s45(guard1_s45),
        .out_down(out_down), .guard_overflow(guard_overflow),
        .total_shift_format_count(total_shift_format_count),
        .format_error(format_error),
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
        repeat (20) @(posedge clk);
        rst_n <= 1'b1;
        @(negedge clk);
        // The legal depth16 queue is larger than natural dot-pipeline
        // occupancy.  Inject the registered full state between edges solely
        // to exercise the same-edge credit expression, then release every
        // force before normal exact traffic starts.
        force dut.meta_count_r = 16;
        force dut.dot_fire = 1'b1;
        force dut.ingress_valid_r = 1'b1;
        #1;
        if (dut.core_meta_ready || dut.ingress_to_core_fire || in_ready)
            $fatal(1, "dot_fire leaked through full metadata credit");
        meta_full_recovery_checks = meta_full_recovery_checks + 1;
        release dut.ingress_valid_r;
        release dut.dot_fire;
        release dut.meta_count_r;
        clear = 1'b1;
        @(posedge clk);
        @(negedge clk);
        clear = 1'b0;
        traffic_enable = 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            out_ready <= 1'b1;
            send_index <= 0;
            receive_index <= 0;
            cycle_count <= 0;
            last_accept_cycle <= -1;
            unstalled_accept_interval_max <= 0;
            meta_full_recovery_checks <= 0;
            stalled_head_checks <= 0;
            stalled_last_cycle <= 1'b0;
        end else begin
            cycle_count <= cycle_count + 1;
            if (cycle_count >= 1200 && cycle_count < 1320)
                out_ready <= 1'b0;
            else if (receive_index < 1024)
                out_ready <= 1'b1;
            else
                out_ready <= (cycle_count % 13) != 4 &&
                    (cycle_count % 19) != 8;

            if (in_valid && in_ready) begin
                send_index <= send_index + 1;
                if (send_index < 1024 && last_accept_cycle >= 0 &&
                    cycle_count-last_accept_cycle >
                    unstalled_accept_interval_max)
                    unstalled_accept_interval_max <=
                        cycle_count-last_accept_cycle;
                last_accept_cycle <= cycle_count;
            end

            if (dut.meta_full && dut.dot_fire) begin
                if (dut.core_meta_ready || dut.ingress_to_core_fire)
                    $fatal(1,
                        "full metadata FIFO reused same-edge dot credit");
                meta_full_recovery_checks <= meta_full_recovery_checks + 1;
            end

            if (out_valid && out_ready) begin
                if ({guard1_s37, guard0_s37} !==
                    {{1{expected_mem[receive_index][71]}},
                     expected_mem[receive_index][71:36],
                     {1{expected_mem[receive_index][35]}},
                     expected_mem[receive_index][35:0]})
                    $fatal(1,
                        "S37 lane exact mismatch index=%0d got=%h_%h expected=%h",
                        receive_index, guard1_s37, guard0_s37,
                        expected_mem[receive_index]);
                if (out_down || guard_overflow || format_error || error ||
                    total_shift_format_count != 0)
                    $fatal(1, "S37 lane status/mode mismatch index=%0d",
                        receive_index);
                if (guard0_s45 !== {{8{guard0_s37[36]}},guard0_s37} ||
                    guard1_s45 !== {{8{guard1_s37[36]}},guard1_s37})
                    $fatal(1, "S37/S45 lane view mismatch index=%0d",
                        receive_index);
                receive_index <= receive_index + 1;
                if (receive_index + 1 == VECTOR_COUNT) begin
                    if (unstalled_accept_interval_max != 1 ||
                        input_group_count != VECTOR_COUNT ||
                        output_group_count + 1 != VECTOR_COUNT ||
                        meta_full_recovery_checks == 0 ||
                        stalled_head_checks == 0)
                        $fatal(1,
                            "S37 lane coverage/count failure ii=%0d in=%0d out=%0d meta=%0d stable=%0d",
                            unstalled_accept_interval_max, input_group_count,
                            output_group_count + 1,
                            meta_full_recovery_checks, stalled_head_checks);
                    $display("S37_LANE vectors=%0d ii=%0d meta_full_credit_checks=%0d stalled_stable=%0d",
                        VECTOR_COUNT, unstalled_accept_interval_max,
                        meta_full_recovery_checks,
                        stalled_head_checks);
                    $display("HARDWARE_AGENT_SIM_PASS");
                    $finish;
                end
            end

            if (out_valid && !out_ready) begin
                if (stalled_last_cycle &&
                    {guard1_s37, guard0_s37} !== stalled_guard_r)
                    $fatal(1, "S37 lane stalled head changed");
                stalled_guard_r <= {guard1_s37, guard0_s37};
                stalled_last_cycle <= 1'b1;
                stalled_head_checks <= stalled_head_checks + 1;
            end else begin
                stalled_last_cycle <= 1'b0;
            end

            if (cycle_count > 12000)
                $fatal(1,
                    "S37 lane timeout send=%0d receive=%0d meta=%0d",
                    send_index, receive_index, dut.meta_count_r);
        end
    end
endmodule
