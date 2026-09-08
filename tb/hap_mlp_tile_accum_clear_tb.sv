`timescale 1ns / 1ps

// Directed maintenance test for the resetless accumulator payload contract.
// The wide accumulator and projection payload registers intentionally retain
// their contents across clear.  Telemetry must nevertheless be invalidated so
// stale overflow flags cannot reassert the sticky error after clear.
module hap_mlp_tile_accum_clear_case #(
    parameter integer ACC_W = 43,
    parameter integer GROUPS = 128
) ();
    localparam integer LANES = 128;
    localparam signed [ACC_W-1:0] ACC_MAX =
        {1'b0, {(ACC_W-1){1'b1}}};

    reg clk = 1'b0;
    always #3.333 clk = ~clk;

    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    wire in_ready;
    reg in_first_group = 1'b0;
    reg in_last_group = 1'b0;
    reg signed [LANES*36-1:0] in_guard_s36 = '0;
    wire out_valid;
    reg out_ready = 1'b1;
    wire signed [LANES*24-1:0] out_projection_s24;
    wire [31:0] input_group_count;
    wire [31:0] output_tile_count;
    wire [31:0] saturation_count;
    wire error;

    integer group_index;
    integer wait_cycles;

    hap_mlp_tile_accum_s36 #(
        .LANES(LANES),
        .ACC_W(ACC_W),
        .GROUPS(GROUPS)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .clear(clear),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_first_group(in_first_group),
        .in_last_group(in_last_group),
        .in_guard_s36(in_guard_s36),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_projection_s24(out_projection_s24),
        .input_group_count(input_group_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count),
        .error(error)
    );

    task automatic pulse_clear;
        begin
            @(negedge clk);
            in_valid = 1'b0;
            clear = 1'b1;
            @(negedge clk);
            clear = 1'b0;
        end
    endtask

    task automatic send_group;
        input first_group;
        input last_group;
        input signed [35:0] lane0_guard;
        begin : send_wait
            @(negedge clk);
            in_guard_s36 = '0;
            in_guard_s36[35:0] = lane0_guard;
            in_first_group = first_group;
            in_last_group = last_group;
            in_valid = 1'b1;
            forever begin
                @(posedge clk);
                if (in_ready) begin
                    @(negedge clk);
                    in_valid = 1'b0;
                    disable send_wait;
                end
            end
        end
    endtask

    task automatic require_idle_after_clear;
        input integer cycles;
        begin
            repeat (cycles) begin
                @(posedge clk);
                #1;
                if (error)
                    $fatal(1,
                        "FAIL ACC_W=%0d: stale error reasserted after clear",
                        ACC_W);
                if (out_valid)
                    $fatal(1,
                        "FAIL ACC_W=%0d: stale output survived clear",
                        ACC_W);
            end
            if (!in_ready)
                $fatal(1,
                    "FAIL ACC_W=%0d: input did not reopen after clear",
                    ACC_W);
            if (input_group_count != 0 || output_tile_count != 0 ||
                saturation_count != 0)
                $fatal(1,
                    "FAIL ACC_W=%0d: counters not cleared in/out/sat=%0d/%0d/%0d",
                    ACC_W, input_group_count, output_tile_count,
                    saturation_count);
        end
    endtask

    initial begin
        repeat (5) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        // Clear followed by no traffic must remain quiescent indefinitely.
        pulse_clear();
        require_idle_after_clear(8);

        // Complete a zero tile, block its output, then clear while the output
        // channel is stalled.  The pending output and all telemetry must be
        // cancelled without requiring the sink to become ready.
        out_ready = 1'b0;
        for (group_index = 0; group_index < GROUPS;
             group_index = group_index + 1)
            send_group(group_index == 0, group_index == GROUPS-1, 36'sd0);
        wait_cycles = 0;
        while (!out_valid && wait_cycles < 8) begin
            @(posedge clk);
            #1;
            wait_cycles = wait_cycles + 1;
        end
        if (!out_valid)
            $fatal(1,
                "FAIL ACC_W=%0d: output did not enter the directed stall",
                ACC_W);
        pulse_clear();
        require_idle_after_clear(8);

        // Produce a real signed accumulator overflow without a protocol
        // violation: accept group zero, temporarily force lane zero to the
        // positive ACC_W limit, then add one in group one.
        out_ready = 1'b1;
        send_group(1'b1, 1'b0, 36'sd0);
        @(negedge clk);
        dut.accum_r[0] = ACC_MAX;
        send_group(1'b0, 1'b0, 36'sd1);
        wait_cycles = 0;
        while (!error && wait_cycles < 12) begin
            @(posedge clk);
            #1;
            wait_cycles = wait_cycles + 1;
        end
        if (!error)
            $fatal(1,
                "FAIL ACC_W=%0d: directed overflow was not reported",
                ACC_W);

        // This is the historical failure: clear drops error, but an invalid
        // stale overflow flag must not flow back through the reduction tree.
        pulse_clear();
        require_idle_after_clear(12);

        $display("PASS: hap_mlp_tile_accum clear/stall/overflow contract ACC_W=%0d GROUPS=%0d",
            ACC_W, GROUPS);
        $finish;
    end
endmodule

module hap_mlp_tile_accum_s43_clear_tb;
    hap_mlp_tile_accum_clear_case #(
        .ACC_W(43), .GROUPS(128)
    ) test ();
endmodule

module hap_mlp_tile_accum_s45_clear_tb;
    hap_mlp_tile_accum_clear_case #(
        .ACC_W(45), .GROUPS(448)
    ) test ();
endmodule
