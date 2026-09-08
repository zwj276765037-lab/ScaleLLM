`timescale 1ns / 1ps

module hap_mlp_gate_up_dual_local_accum16x12_s43_tb;
    localparam integer GROUPS = 128;

    reg clk = 1'b0;
    always #3.333 clk = ~clk;

    reg rst_n = 1'b0;
    reg clear = 1'b0;
    integer cycle_count = 0;

    reg [4607:0] activation_mem [0:GROUPS-1];
    reg [1535:0] weight_mem [0:GROUPS-1];
    reg [223:0] activation_meta_mem [0:GROUPS-1];
    reg [167:0] weight_meta_mem [0:GROUPS-1];
    reg [11:0] mask_mem [0:GROUPS-1];
    reg [6911:0] guard_expected_mem [0:GROUPS-1];
    reg [4607:0] projection_expected_mem [0:0];

    integer new_send = 0;
    integer ref_send = 0;
    integer new_receive = 0;
    integer ref_receive = 0;
    integer new_guard0_index = 0;
    integer new_guard1_index = 0;
    integer new_last_accept = -1;
    integer ref_last_accept = -1;
    integer new_max_accept_interval = 0;
    integer ref_max_accept_interval = 0;

    wire [6:0] new_source = new_send < GROUPS ?
        new_send[6:0] : 7'd127;
    wire new_in_valid = new_send < GROUPS;
    wire new_in_ready;
    wire new_out_valid;
    reg new_out_ready = 1'b0;
    wire signed [4607:0] new_projection;
    wire [31:0] new_input_count;
    wire [31:0] new_output_count;
    wire [31:0] new_saturation_count;
    wire new_error;

    hap_mlp_gate_up_dual_local_accum16x12_s43 new_dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(new_in_valid), .in_ready(new_in_ready),
        .in_first_group(new_send == 0),
        .in_last_group(new_send == GROUPS-1),
        .activation_s9x16x32(activation_mem[new_source]),
        .weights_s4x12x32(weight_mem[new_source]),
        .activation_code_u8x16(
            activation_meta_mem[new_source][127:0]),
        .activation_shift_u6x16(
            activation_meta_mem[new_source][223:128]),
        .weight_code_u8x12(weight_meta_mem[new_source][95:0]),
        .weight_shift_u6x12(weight_meta_mem[new_source][167:96]),
        .column_valid_u12(mask_mem[new_source]),
        .out_valid(new_out_valid), .out_ready(new_out_ready),
        .projection_s24x16x12(new_projection),
        .input_group_count(new_input_count),
        .output_pass_count(new_output_count),
        .saturation_count(new_saturation_count),
        .error(new_error)
    );

    // Numerical/order reference: Run 0122 central 192-lane accumulator.
    // It receives the same 128 transactions through an independent source;
    // its known temporary II=2 must not throttle the candidate under test.
    wire [6:0] ref_source = ref_send < GROUPS ?
        ref_send[6:0] : 7'd127;
    wire ref_in_valid = ref_send < GROUPS;
    wire ref_in_ready;
    wire ref_out_valid;
    reg ref_out_ready = 1'b0;
    wire signed [4607:0] ref_projection;
    wire [31:0] ref_input_count;
    wire [31:0] ref_output_count;
    wire [31:0] ref_saturation_count;
    wire ref_error;

    hap_mlp_gate_up_dual_slice16x12_s43 ref_dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(ref_in_valid), .in_ready(ref_in_ready),
        .in_first_group(ref_send == 0),
        .in_last_group(ref_send == GROUPS-1),
        .activation_s9x16x32(activation_mem[ref_source]),
        .weights_s4x12x32(weight_mem[ref_source]),
        .activation_code_u8x16(
            activation_meta_mem[ref_source][127:0]),
        .activation_shift_u6x16(
            activation_meta_mem[ref_source][223:128]),
        .weight_code_u8x12(weight_meta_mem[ref_source][95:0]),
        .weight_shift_u6x12(weight_meta_mem[ref_source][167:96]),
        .column_valid_u12(mask_mem[ref_source]),
        .out_valid(ref_out_valid), .out_ready(ref_out_ready),
        .projection_s24x16x12(ref_projection),
        .input_group_count(ref_input_count),
        .output_pass_count(ref_output_count),
        .saturation_count(ref_saturation_count),
        .error(ref_error)
    );

    reg [15:0] ready_lfsr = 16'h1ace;
    integer new_forced_stalls_remaining = 6;
    integer ref_forced_stalls_remaining = 4;
    integer new_stall_cycles = 0;
    integer ref_stall_cycles = 0;
    integer new_stability_checks = 0;
    integer ref_stability_checks = 0;
    reg new_was_stalled = 1'b0;
    reg ref_was_stalled = 1'b0;
    reg [4607:0] new_hold;
    reg [4607:0] ref_hold;
    reg [4607:0] new_result;
    reg [4607:0] ref_result;

    initial begin
        $readmemh(
            "data/mlp_v5_dual_slice16x12/gate_activation_s9x16x32.mem",
            activation_mem);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/gate_weights_s4x12x32.mem",
            weight_mem);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/gate_activation_meta_u224.mem",
            activation_meta_mem);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/gate_weight_meta_u168.mem",
            weight_meta_mem);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/gate_column_valid_u12.mem",
            mask_mem);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/gate_expected_s36x16x12.mem",
            guard_expected_mem);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/gate_expected_s24x16x12.mem",
            projection_expected_mem);

        repeat (6) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (rst_n) begin
            cycle_count <= cycle_count + 1;
            ready_lfsr <= {ready_lfsr[14:0],
                ready_lfsr[15] ^ ready_lfsr[13] ^
                ready_lfsr[12] ^ ready_lfsr[10]};

            // Force observable stalls first, then use two deterministic
            // pseudo-random ready functions.  Both have bounded long-term
            // progress but are independent of DUT valid timing.
            if (new_forced_stalls_remaining > 0) begin
                new_out_ready <= 1'b0;
                if (new_out_valid)
                    new_forced_stalls_remaining =
                        new_forced_stalls_remaining - 1;
            end else begin
                new_out_ready <= |ready_lfsr[2:0];
            end
            if (ref_forced_stalls_remaining > 0) begin
                ref_out_ready <= 1'b0;
                if (ref_out_valid)
                    ref_forced_stalls_remaining =
                        ref_forced_stalls_remaining - 1;
            end else begin
                ref_out_ready <= |ready_lfsr[6:4];
            end

            if (new_in_valid && new_in_ready) begin
                if (new_last_accept >= 0) begin
                    if (cycle_count-new_last_accept >
                        new_max_accept_interval)
                        new_max_accept_interval <=
                            cycle_count-new_last_accept;
                    if (cycle_count-new_last_accept != 1)
                        $fatal(1,
                            "FAIL new gate candidate lost II=1 at input %0d interval=%0d",
                            new_send, cycle_count-new_last_accept);
                end
                new_last_accept <= cycle_count;
                new_send <= new_send + 1;
            end

            if (ref_in_valid && ref_in_ready) begin
                if (ref_last_accept >= 0 &&
                    cycle_count-ref_last_accept > ref_max_accept_interval)
                    ref_max_accept_interval <= cycle_count-ref_last_accept;
                ref_last_accept <= cycle_count;
                ref_send <= ref_send + 1;
            end

            // Each physical branch is checked independently at its actual
            // kernel-to-local-accumulator handshake.  This catches stale
            // fork replay, tag skew and row-half ordering defects before S43.
            if (new_dut.u_branch0.kernel_out_fire) begin
                if (new_dut.u_branch0.guard_s36x8x12 !==
                    guard_expected_mem[new_guard0_index][0 +: 8*12*36])
                    $fatal(1,
                        "FAIL branch0 S36 mismatch group=%0d lane0=%h expected=%h",
                        new_guard0_index,
                        new_dut.u_branch0.guard_s36x8x12[35:0],
                        guard_expected_mem[new_guard0_index][35:0]);
                new_guard0_index <= new_guard0_index + 1;
            end
            if (new_dut.u_branch1.kernel_out_fire) begin
                if (new_dut.u_branch1.guard_s36x8x12 !==
                    guard_expected_mem[new_guard1_index][8*12*36 +:
                        8*12*36])
                    $fatal(1,
                        "FAIL branch1 S36 mismatch group=%0d lane0=%h expected=%h",
                        new_guard1_index,
                        new_dut.u_branch1.guard_s36x8x12[35:0],
                        guard_expected_mem[new_guard1_index]
                            [8*12*36 +: 36]);
                new_guard1_index <= new_guard1_index + 1;
            end

            if (new_was_stalled) begin
                new_stability_checks = new_stability_checks + 1;
                if (!new_out_valid || new_projection !== new_hold)
                    $fatal(1,
                        "FAIL new S24 output changed under backpressure");
            end
            if (ref_was_stalled) begin
                ref_stability_checks = ref_stability_checks + 1;
                if (!ref_out_valid || ref_projection !== ref_hold)
                    $fatal(1,
                        "FAIL reference S24 output changed under backpressure");
            end

            new_was_stalled <= new_out_valid && !new_out_ready;
            ref_was_stalled <= ref_out_valid && !ref_out_ready;
            if (new_out_valid && !new_out_ready) begin
                new_hold <= new_projection;
                new_stall_cycles = new_stall_cycles + 1;
            end
            if (ref_out_valid && !ref_out_ready) begin
                ref_hold <= ref_projection;
                ref_stall_cycles = ref_stall_cycles + 1;
            end

            if (new_out_valid && new_out_ready) begin
                if (new_projection !== projection_expected_mem[0])
                    $fatal(1, "FAIL new S24 projection mismatch");
                new_result <= new_projection;
                new_receive <= new_receive + 1;
            end
            if (ref_out_valid && ref_out_ready) begin
                if (ref_projection !== projection_expected_mem[0])
                    $fatal(1, "FAIL reference S24 projection mismatch");
                ref_result <= ref_projection;
                ref_receive <= ref_receive + 1;
            end

            if (new_receive == 1 && ref_receive == 1) begin
                if (new_result !== ref_result)
                    $fatal(1,
                        "FAIL new/reference completed S24 payload differs");
                if (new_send != GROUPS || ref_send != GROUPS ||
                    new_guard0_index != GROUPS ||
                    new_guard1_index != GROUPS ||
                    new_input_count != GROUPS ||
                    new_output_count != 1 || ref_input_count != GROUPS ||
                    ref_output_count != 1)
                    $fatal(1,
                        "FAIL counts send=%0d/%0d guard=%0d/%0d top=%0d/%0d ref=%0d/%0d",
                        new_send, ref_send, new_guard0_index,
                        new_guard1_index, new_input_count,
                        new_output_count, ref_input_count, ref_output_count);
                if (new_error || ref_error ||
                    new_saturation_count != ref_saturation_count)
                    $fatal(1,
                        "FAIL sticky status new/ref error=%0d/%0d sat=%0d/%0d",
                        new_error, ref_error, new_saturation_count,
                        ref_saturation_count);
                if (new_max_accept_interval != 1 ||
                    new_stall_cycles == 0 || new_stability_checks == 0 ||
                    ref_stall_cycles == 0 || ref_stability_checks == 0)
                    $fatal(1,
                        "FAIL coverage new_ii=%0d stalls=%0d/%0d stable=%0d/%0d",
                        new_max_accept_interval, new_stall_cycles,
                        ref_stall_cycles, new_stability_checks,
                        ref_stability_checks);

                $display(
                    "PASS: V5 gate dual-local S43 bit-exact groups=%0d new_ii=%0d ref_ii=%0d cycles=%0d stalls=%0d/%0d stable=%0d/%0d",
                    new_input_count, new_max_accept_interval,
                    ref_max_accept_interval, cycle_count,
                    new_stall_cycles, ref_stall_cycles,
                    new_stability_checks, ref_stability_checks);
                $finish;
            end

            if (new_receive > 1 || ref_receive > 1)
                $fatal(1, "FAIL duplicate completed pass new/ref=%0d/%0d",
                    new_receive, ref_receive);
            if (cycle_count > 1200)
                $fatal(1,
                    "FAIL timeout send=%0d/%0d receive=%0d/%0d guard=%0d/%0d error=%0d/%0d",
                    new_send, ref_send, new_receive, ref_receive,
                    new_guard0_index, new_guard1_index,
                    new_error, ref_error);
        end
    end

endmodule
