`timescale 1ns / 1ps

module hap_a8w4_group32_pack2_s17_queue_tb;
    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg send_enable = 1'b0;
    integer send_limit = 0;
    integer send_index = 0;
    wire in_valid = send_enable && send_index < send_limit;
    wire in_ready;
    reg out_ready = 1'b1;

    wire signed [32*9-1:0] activation_s9x32;
    wire signed [32*4-1:0] weight0_s4x32;
    wire signed [32*4-1:0] weight1_s4x32;
    wire out_valid;
    wire signed [16:0] dot0_s17;
    wire signed [16:0] dot1_s17;

    reg signed [16:0] expected0 [0:63];
    reg signed [16:0] expected1 [0:63];
    integer accepted_count = 0;
    integer output_count = 0;
    integer phase_cycle = 0;
    integer wall_cycle = 0;
    integer first_accept_cycle = -1;
    integer first_output_cycle = -1;
    integer last_accept_cycle = -1;
    integer max_accept_interval = 0;
    reg stalled_last_cycle = 1'b0;
    reg signed [33:0] stalled_data_r;

    function automatic signed [3:0] drive_weight0(input integer index);
        integer weight;
        begin
            weight = (index % 15) - 7;
            drive_weight0 = weight;
        end
    endfunction

    function automatic signed [3:0] drive_weight1(input integer index);
        integer weight;
        begin
            weight = 7 - (index % 15);
            drive_weight1 = weight;
        end
    endfunction

    function automatic signed [16:0] expected_dot0(input integer index);
        integer weight;
        begin
            weight = (index % 15) - 7;
            expected_dot0 = weight * 32;
        end
    endfunction

    function automatic signed [16:0] expected_dot1(input integer index);
        integer weight;
        begin
            weight = 7 - (index % 15);
            expected_dot1 = weight * 32;
        end
    endfunction

    assign activation_s9x32 = {32{9'sd1}};
    assign weight0_s4x32 = {32{drive_weight0(send_index)}};
    assign weight1_s4x32 = {32{drive_weight1(send_index)}};

    hap_a8w4_group32_pack2_s17 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .activation_s9x32(activation_s9x32),
        .weight0_s4x32(weight0_s4x32),
        .weight1_s4x32(weight1_s4x32),
        .out_valid(out_valid), .out_ready(out_ready),
        .dot0_s17(dot0_s17), .dot1_s17(dot1_s17)
    );

    always @(posedge clk) begin
        wall_cycle <= wall_cycle + 1;
        if (wall_cycle > 2000)
            $fatal(1, "pack2 queue test timeout");

        if (!rst_n || clear) begin
            send_index <= 0;
            accepted_count <= 0;
            output_count <= 0;
            phase_cycle <= 0;
            first_accept_cycle <= -1;
            first_output_cycle <= -1;
            last_accept_cycle <= -1;
            max_accept_interval <= 0;
            stalled_last_cycle <= 1'b0;
        end else begin
            phase_cycle <= phase_cycle + 1;
            if (in_valid && in_ready) begin
                if ($isunknown({activation_s9x32, weight0_s4x32,
                                weight1_s4x32}))
                    $fatal(1, "pack2 queue accepted unknown input");
                expected0[accepted_count] <= expected_dot0(send_index);
                expected1[accepted_count] <= expected_dot1(send_index);
                accepted_count <= accepted_count + 1;
                send_index <= send_index + 1;
                if (first_accept_cycle < 0)
                    first_accept_cycle <= phase_cycle;
                if (last_accept_cycle >= 0 &&
                    phase_cycle - last_accept_cycle > max_accept_interval)
                    max_accept_interval <= phase_cycle - last_accept_cycle;
                last_accept_cycle <= phase_cycle;
            end

            if (out_valid && out_ready) begin
                if (dot0_s17 !== expected0[output_count] ||
                    dot1_s17 !== expected1[output_count])
                    $fatal(1,
                        "pack2 queue exact mismatch index=%0d got=%0d,%0d expected=%0d,%0d qcount=%0d rd=%0d q0=%h,%h q1=%h,%h",
                        output_count, dot0_s17, dot1_s17,
                        expected0[output_count], expected1[output_count],
                        dut.dot_q_count_r, dut.dot_q_rd_ptr_r,
                        dut.dot0_q[0], dut.dot1_q[0],
                        dut.dot0_q[1], dut.dot1_q[1]);
                if (first_output_cycle < 0)
                    first_output_cycle <= phase_cycle;
                output_count <= output_count + 1;
            end

            if (dut.dot_q_push &&
                $isunknown({dut.s4_sum0_s17_r, dut.s4_sum1_s17_r}))
                $fatal(1, "pack2 queue pushed unknown s4 payload");

            if (out_valid && !out_ready) begin
                if (stalled_last_cycle &&
                    {dot1_s17, dot0_s17} !== stalled_data_r)
                    $fatal(1, "pack2 stalled head changed");
                stalled_data_r <= {dot1_s17, dot0_s17};
                stalled_last_cycle <= 1'b1;
            end else begin
                stalled_last_cycle <= 1'b0;
            end
        end
    end

    task automatic pulse_clear;
        begin
            @(negedge clk);
            clear = 1'b1;
            @(posedge clk);
            #1;
            if (out_valid || dut.dot_q_count_r != 0 || dut.s4_valid_r)
                $fatal(1, "clear did not empty pack2 queue and final stage");
            @(negedge clk);
            clear = 1'b0;
        end
    endtask

    task automatic pulse_reset;
        begin
            @(negedge clk);
            rst_n = 1'b0;
            @(posedge clk);
            #1;
            if (out_valid || dut.dot_q_count_r != 0 || dut.s4_valid_r ||
                dot0_s17 !== 17'sd0 || dot1_s17 !== 17'sd0)
                $fatal(1, "reset contract failed for pack2 queue");
            @(negedge clk);
            rst_n = 1'b1;
        end
    endtask

    integer accepted_before_release;
    initial begin
        repeat (4) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        // Continuous-ready traffic must keep the historical first-valid
        // latency and accept one group on every cycle.
        send_limit = 32;
        send_enable = 1'b1;
        out_ready = 1'b1;
        wait (output_count == 32);
        @(negedge clk);
        send_enable = 1'b0;
        if (accepted_count != 32 || max_accept_interval != 1)
            $fatal(1, "continuous II1 failed accepted=%0d max_ii=%0d",
                accepted_count, max_accept_interval);
        if (first_output_cycle - first_accept_cycle != 9)
            $fatal(1, "first-valid latency changed got=%0d expected=9",
                first_output_cycle - first_accept_cycle);

        // Fill the queue and final reduction slot.  A full queue may pop but
        // must not push on that same edge; credit returns on the next cycle.
        pulse_clear();
        send_limit = 24;
        send_enable = 1'b1;
        out_ready = 1'b0;
        wait (dut.dot_q_count_r == 2 && dut.s4_valid_r && !in_ready);
        repeat (5) @(posedge clk);
        accepted_before_release = accepted_count;
        @(negedge clk);
        out_ready = 1'b1;
        @(posedge clk);
        #1;
        if (dut.dot_q_count_r != 1)
            $fatal(1, "full queue accepted same-edge push during first pop");
        if (accepted_count != accepted_before_release)
            $fatal(1, "input advanced on full-queue release edge");
        @(posedge clk);
        #1;
        if (accepted_count != accepted_before_release + 1)
            $fatal(1, "registered credit recovery bubble was not one cycle");
        wait (output_count == 24);
        @(negedge clk);
        send_enable = 1'b0;

        // Clear and reset each discard a full stalled queue.  Fresh traffic
        // restarts at transaction zero, proving no stale pre-event output.
        pulse_clear();
        send_limit = 16;
        send_enable = 1'b1;
        out_ready = 1'b0;
        wait (dut.dot_q_count_r == 2 && dut.s4_valid_r);
        pulse_clear();
        out_ready = 1'b1;
        wait (output_count == 16);
        @(negedge clk);
        send_enable = 1'b0;

        pulse_clear();
        send_limit = 12;
        send_enable = 1'b1;
        out_ready = 1'b0;
        wait (dut.dot_q_count_r == 2 && dut.s4_valid_r);
        pulse_reset();
        out_ready = 1'b1;
        wait (output_count == 12);
        @(negedge clk);
        send_enable = 1'b0;

        $display("PACK2_QUEUE latency=9 unstalled_ii=1 full_recovery_bubble=1 reset_clear_stale=0");
        $display("HARDWARE_AGENT_SIM_PASS");
        $finish;
    end
endmodule
