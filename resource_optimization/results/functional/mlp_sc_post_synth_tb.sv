`timescale 1ns / 1ps

module mlp_sc_recover2_tb;
    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    reg out_ready = 1'b1;
    reg signed [16:0] dot0_s17 = '0;
    reg signed [16:0] dot1_s17 = '0;
    reg [7:0] activation_code_u8 = '0;
    reg [7:0] weight0_code_u8 = '0;
    reg [7:0] weight1_code_u8 = '0;
    wire [2:0] in_ready;
    wire [2:0] out_valid;
    wire signed [32:0] raw0_s33 [0:2];
    wire signed [32:0] raw1_s33 [0:2];

    hap_a8w4_scalecode_recover2_lut u_lut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready[0]),
        .dot0_s17(dot0_s17), .dot1_s17(dot1_s17),
        .activation_code_u8(activation_code_u8),
        .weight0_code_u8(weight0_code_u8), .weight1_code_u8(weight1_code_u8),
        .out_valid(out_valid[0]), .out_ready(out_ready),
        .raw0_s33(raw0_s33[0]), .raw1_s33(raw1_s33[0])
    );
    hap_a8w4_scalecode_recover2_lut u_raw_dsp (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready[1]),
        .dot0_s17(dot0_s17), .dot1_s17(dot1_s17),
        .activation_code_u8(activation_code_u8),
        .weight0_code_u8(weight0_code_u8), .weight1_code_u8(weight1_code_u8),
        .out_valid(out_valid[1]), .out_ready(out_ready),
        .raw0_s33(raw0_s33[1]), .raw1_s33(raw1_s33[1])
    );
    hap_a8w4_scalecode_recover2_lut u_all_dsp (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready[2]),
        .dot0_s17(dot0_s17), .dot1_s17(dot1_s17),
        .activation_code_u8(activation_code_u8),
        .weight0_code_u8(weight0_code_u8), .weight1_code_u8(weight1_code_u8),
        .out_valid(out_valid[2]), .out_ready(out_ready),
        .raw0_s33(raw0_s33[2]), .raw1_s33(raw1_s33[2])
    );

    // Integer gold computes all three mathematical operands in 64 bits, without
    // reading the DUT's intermediate code product or a second DUT's result.
    function automatic signed [32:0] integer_gold(
        input signed [16:0] dot,
        input [7:0] activation,
        input [7:0] weight
    );
        reg signed [63:0] value;
        begin
            value = $signed(dot);
            value = value * $signed({1'b0, activation});
            value = value * $signed({1'b0, weight});
            integer_gold = value[32:0];
        end
    endfunction

    function automatic [31:0] next_random(input [31:0] x);
        reg [31:0] y;
        begin
            y = x ^ (x << 13);
            y = y ^ (y >> 17);
            next_random = y ^ (y << 5);
        end
    endfunction

    reg model_valid [0:2];
    reg signed [32:0] model_raw0 [0:2];
    reg signed [32:0] model_raw1 [0:2];
    reg signed [32:0] queue_raw0 [0:2][0:7];
    reg signed [32:0] queue_raw1 [0:2][0:7];
    integer queue_cycle [0:2][0:7];
    integer queue_head [0:2];
    integer queue_tail [0:2];
    integer queue_count [0:2];
    integer accepted [0:2];
    integer emitted [0:2];
    integer canceled [0:2];
    integer cycles = 0;
    integer reset_events = 0;
    integer clear_events = 0;
    integer stalled_input_cycles = 0;
    integer held_output_cycles = 0;
    integer latency_checks = 0;
    integer consecutive_accepts = 0;
    integer max_consecutive_accepts = 0;
    integer directed_transactions = 0;
    integer sweep_transactions = 0;
    integer random_transactions = 0;
    bit latency_mode = 1'b0;
    bit stage_out_ready;
    bit stage1_ready;
    bit stage0_ready;
    bit input_fire;
    bit output_fire;
    reg signed [32:0] incoming_raw0;
    reg signed [32:0] incoming_raw1;
    integer index;

    task automatic check_interface(input [127:0] sample_point);
        reg expected_ready;
        integer variant;
        begin
            expected_ready = rst_n && !clear &&
                (!model_valid[0] || !model_valid[1] ||
                 !model_valid[2] || out_ready);
            for (variant = 0; variant < 3; variant = variant + 1) begin
                if (in_ready[variant] !== expected_ready)
                    $fatal(1, "ready mismatch variant=%0d cycle=%0d point=%0s got=%b want=%b",
                           variant, cycles, sample_point, in_ready[variant], expected_ready);
                if (out_valid[variant] !== model_valid[2])
                    $fatal(1, "valid mismatch variant=%0d cycle=%0d point=%0s got=%b want=%b",
                           variant, cycles, sample_point, out_valid[variant], model_valid[2]);
                if (model_valid[2] &&
                    (raw0_s33[variant] !== model_raw0[2] ||
                     raw1_s33[variant] !== model_raw1[2]))
                    $fatal(1, "data mismatch variant=%0d cycle=%0d point=%0s got=%0d,%0d want=%0d,%0d",
                           variant, cycles, sample_point, raw0_s33[variant], raw1_s33[variant],
                           model_raw0[2], model_raw1[2]);
            end
        end
    endtask

    initial begin
        for (index = 0; index < 3; index = index + 1) begin
            model_valid[index] = 1'b0;
            model_raw0[index] = '0;
            model_raw1[index] = '0;
            queue_head[index] = 0;
            queue_tail[index] = 0;
            queue_count[index] = 0;
            accepted[index] = 0;
            emitted[index] = 0;
            canceled[index] = 0;
        end
    end

    always @(posedge clk) begin : scoreboard
        integer variant;
        cycles = cycles + 1;
        // Before the first synchronous reset edge the DUT registers are X.
        if (cycles > 1) check_interface("pre_edge");
        stage_out_ready = !model_valid[2] || out_ready;
        stage1_ready = !model_valid[1] || stage_out_ready;
        stage0_ready = !model_valid[0] || stage1_ready;
        input_fire = rst_n && !clear && in_valid && stage0_ready;
        output_fire = rst_n && !clear && model_valid[2] && out_ready;
        incoming_raw0 = integer_gold(dot0_s17, activation_code_u8, weight0_code_u8);
        incoming_raw1 = integer_gold(dot1_s17, activation_code_u8, weight1_code_u8);

        if (!rst_n || clear) begin
            if (!rst_n) reset_events = reset_events + 1;
            else clear_events = clear_events + 1;
            for (variant = 0; variant < 3; variant = variant + 1) begin
                canceled[variant] = canceled[variant] + queue_count[variant];
                queue_head[variant] = 0;
                queue_tail[variant] = 0;
                queue_count[variant] = 0;
            end
            model_valid[0] = 0;
            model_valid[1] = 0;
            model_valid[2] = 0;
            if (!rst_n) begin
                for (variant = 0; variant < 3; variant = variant + 1) begin
                    model_raw0[variant] = 0;
                    model_raw1[variant] = 0;
                end
            end
            consecutive_accepts = 0;
        end else begin
            if (model_valid[2] && !out_ready)
                held_output_cycles = held_output_cycles + 1;
            if (in_valid && !stage0_ready)
                stalled_input_cycles = stalled_input_cycles + 1;

            for (variant = 0; variant < 3; variant = variant + 1) begin
                if (output_fire) begin
                    if (queue_count[variant] == 0)
                        $fatal(1, "unexpected output variant=%0d cycle=%0d", variant, cycles);
                    if (raw0_s33[variant] !== queue_raw0[variant][queue_head[variant]] ||
                        raw1_s33[variant] !== queue_raw1[variant][queue_head[variant]])
                        $fatal(1, "queue mismatch variant=%0d cycle=%0d", variant, cycles);
                    if (latency_mode && cycles - queue_cycle[variant][queue_head[variant]] != 3)
                        $fatal(1, "handshake latency variant=%0d cycle=%0d accepted_cycle=%0d",
                               variant, cycles, queue_cycle[variant][queue_head[variant]]);
                    if (latency_mode) latency_checks = latency_checks + 1;
                    queue_head[variant] = (queue_head[variant] + 1) % 8;
                    queue_count[variant] = queue_count[variant] - 1;
                    emitted[variant] = emitted[variant] + 1;
                end
                if (input_fire) begin
                    if (queue_count[variant] >= 8)
                        $fatal(1, "queue overflow variant=%0d cycle=%0d", variant, cycles);
                    queue_raw0[variant][queue_tail[variant]] = incoming_raw0;
                    queue_raw1[variant][queue_tail[variant]] = incoming_raw1;
                    queue_cycle[variant][queue_tail[variant]] = cycles;
                    queue_tail[variant] = (queue_tail[variant] + 1) % 8;
                    queue_count[variant] = queue_count[variant] + 1;
                    accepted[variant] = accepted[variant] + 1;
                end
            end

            if (stage_out_ready) begin
                model_valid[2] = model_valid[1];
                if (model_valid[1]) begin
                    model_raw0[2] = model_raw0[1];
                    model_raw1[2] = model_raw1[1];
                end
            end
            if (stage1_ready) begin
                model_valid[1] = model_valid[0];
                if (model_valid[0]) begin
                    model_raw0[1] = model_raw0[0];
                    model_raw1[1] = model_raw1[0];
                end
            end
            if (stage0_ready) begin
                model_valid[0] = input_fire;
                if (input_fire) begin
                    model_raw0[0] = incoming_raw0;
                    model_raw1[0] = incoming_raw1;
                end
            end
            if (input_fire) begin
                consecutive_accepts = consecutive_accepts + 1;
                if (consecutive_accepts > max_consecutive_accepts)
                    max_consecutive_accepts = consecutive_accepts;
            end else consecutive_accepts = 0;
        end

        for (variant = 0; variant < 3; variant = variant + 1) begin
            if (queue_count[variant] > 3 ||
                accepted[variant] != emitted[variant] + canceled[variant] + queue_count[variant])
                $fatal(1, "conservation/capacity variant=%0d cycle=%0d accepted=%0d emitted=%0d canceled=%0d queued=%0d",
                       variant, cycles, accepted[variant], emitted[variant],
                       canceled[variant], queue_count[variant]);
        end
        #1;
        check_interface("post_edge");
        if (!rst_n) begin
            for (variant = 0; variant < 3; variant = variant + 1)
                if (raw0_s33[variant] !== 0 || raw1_s33[variant] !== 0)
                    $fatal(1, "reset output data variant=%0d cycle=%0d", variant, cycles);
        end
    end

    task automatic drive_cycle(
        input bit new_rst_n,
        input bit new_clear,
        input bit new_in_valid,
        input bit new_out_ready,
        input signed [16:0] new_dot0,
        input signed [16:0] new_dot1,
        input [7:0] new_activation,
        input [7:0] new_weight0,
        input [7:0] new_weight1,
        output bit was_accepted
    );
        begin
            @(negedge clk);
            rst_n = new_rst_n;
            clear = new_clear;
            in_valid = new_in_valid;
            out_ready = new_out_ready;
            dot0_s17 = new_dot0;
            dot1_s17 = new_dot1;
            activation_code_u8 = new_activation;
            weight0_code_u8 = new_weight0;
            weight1_code_u8 = new_weight1;
            #1;
            was_accepted = in_valid && in_ready[0];
            @(posedge clk);
            #2;
        end
    endtask

    task automatic idle_cycle(input bit ready_value);
        bit fired;
        begin
            drive_cycle(1, 0, 0, ready_value, 0, 0, 0, 0, 0, fired);
        end
    endtask

    task automatic send_full_speed(
        input signed [16:0] d0,
        input signed [16:0] d1,
        input [7:0] a,
        input [7:0] w0,
        input [7:0] w1
    );
        bit fired;
        begin
            drive_cycle(1, 0, 1, 1, d0, d1, a, w0, w1, fired);
            if (!fired) $fatal(1, "unexpected full-speed backpressure cycle=%0d", cycles);
        end
    endtask

    task automatic drain;
        integer attempts;
        begin
            attempts = 0;
            while (queue_count[0] != 0 || model_valid[0] ||
                   model_valid[1] || model_valid[2]) begin
                idle_cycle(1);
                attempts = attempts + 1;
                if (attempts > 8) $fatal(1, "pipeline failed to drain");
            end
            for (integer variant = 0; variant < 3; variant = variant + 1)
                if (queue_count[variant] != 0)
                    $fatal(1, "variant %0d failed to drain", variant);
        end
    endtask

    integer dot_values [0:6];
    integer code_values [0:2];
    reg [31:0] rng = 32'h6d2b79f5;
    reg signed [16:0] random_dot0;
    reg signed [16:0] random_dot1;
    reg [7:0] random_a;
    reg [7:0] random_w0;
    reg [7:0] random_w1;
    bit fired;
    integer attempts;
    integer i;
    integer j;
    integer k;
    integer l;
    integer m;

    initial begin : stimulus
        // Allow the UNISIM glbl startup GSR to deassert before valid traffic.
        #200;
        dot_values[0] = -65536;
        dot_values[1] = -65535;
        dot_values[2] = -1;
        dot_values[3] = 0;
        dot_values[4] = 1;
        dot_values[5] = 65534;
        dot_values[6] = 65535;
        code_values[0] = 0;
        code_values[1] = 1;
        code_values[2] = 255;

        drive_cycle(0, 0, 0, 1, 0, 0, 0, 0, 0, fired);
        drive_cycle(0, 0, 0, 1, 0, 0, 0, 0, 0, fired);
        drive_cycle(1, 1, 0, 1, 0, 0, 0, 0, 0, fired);
        idle_cycle(1);

        latency_mode = 1;
        for (i = 0; i < 7; i = i + 1)
            for (m = 0; m < 3; m = m + 1)
                for (j = 0; j < 3; j = j + 1)
                    for (k = 0; k < 3; k = k + 1)
                        for (l = 0; l < 3; l = l + 1) begin
                            case (m)
                                0: send_full_speed(dot_values[i], dot_values[6-i],
                                                   code_values[j], code_values[k], code_values[l]);
                                1: send_full_speed(dot_values[i], dot_values[i],
                                                   code_values[j], code_values[k], code_values[l]);
                                2: send_full_speed(dot_values[i], dot_values[(i+3)%7],
                                                   code_values[j], code_values[k], code_values[l]);
                            endcase
                            directed_transactions = directed_transactions + 1;
                        end
        drain();
        idle_cycle(1);

        // Each S17 encoding appears once in each column, in opposite order.
        for (i = 0; i < 131072; i = i + 1) begin
            send_full_speed(i - 65536, 65535 - i, i[7:0],
                            (i >> 3) & 255, (i * 73 + 19) & 255);
            sweep_transactions = sweep_transactions + 1;
        end
        drain();
        latency_mode = 0;
        idle_cycle(1);

        // All three pipeline slots fill. The fourth input must remain stable
        // while output backpressure blocks the whole pipeline.
        drive_cycle(1, 0, 1, 0, -65536, 65535, 255, 255, 1, fired);
        if (!fired) $fatal(1, "first fill failed");
        drive_cycle(1, 0, 1, 0, 65535, -65536, 1, 255, 255, fired);
        if (!fired) $fatal(1, "second fill failed");
        drive_cycle(1, 0, 1, 0, -1, 1, 255, 1, 255, fired);
        if (!fired) $fatal(1, "third fill failed");
        for (i = 0; i < 12; i = i + 1) begin
            drive_cycle(1, 0, 1, 0, 12345, -23456, 173, 91, 243, fired);
            if (fired) $fatal(1, "full pipeline accepted blocked input");
        end
        drive_cycle(1, 0, 1, 1, 12345, -23456, 173, 91, 243, fired);
        if (!fired) $fatal(1, "blocked input did not resume");
        drain();

        // Both cancellation controls are exercised with output blocked.
        for (i = 0; i < 3; i = i + 1)
            drive_cycle(1, 0, 1, 0, i - 10, i + 20, 255, 7, 9, fired);
        if (queue_count[0] != 3) $fatal(1, "reset test did not fill pipeline");
        drive_cycle(0, 0, 1, 0, 111, -222, 255, 255, 255, fired);
        if (fired || queue_count[0] != 0) $fatal(1, "reset cancellation failed");
        send_full_speed(456, -789, 255, 255, 1);
        drain();
        drive_cycle(0, 0, 0, 1, 0, 0, 0, 0, 0, fired);

        for (i = 0; i < 3; i = i + 1)
            drive_cycle(1, 0, 1, 0, i + 100, -i - 100, 111, 31, 37, fired);
        if (queue_count[0] != 3) $fatal(1, "clear test did not fill pipeline");
        drive_cycle(1, 1, 1, 0, 111, -222, 255, 255, 255, fired);
        if (fired || queue_count[0] != 0) $fatal(1, "clear cancellation failed");
        send_full_speed(-999, 888, 255, 254, 253);
        drain();
        drive_cycle(1, 1, 0, 1, 0, 0, 0, 0, 0, fired);

        // Fixed-seed random tests mix full-speed traffic, input bubbles and
        // ready stalls. A blocked producer holds the exact same transaction.
        for (i = 0; i < 4096; i = i + 1) begin
            rng = next_random(rng);
            random_dot0 = rng[16:0];
            rng = next_random(rng);
            random_dot1 = rng[16:0];
            rng = next_random(rng);
            random_a = rng[7:0];
            random_w0 = rng[15:8];
            random_w1 = rng[23:16];
            if (rng[28:25] == 0) idle_cycle(rng[24]);
            attempts = 0;
            fired = 0;
            while (!fired) begin
                rng = next_random(rng);
                drive_cycle(1, 0, 1, rng[3:2] != 0,
                            random_dot0, random_dot1, random_a,
                            random_w0, random_w1, fired);
                attempts = attempts + 1;
                if (attempts > 100) $fatal(1, "random input stuck");
            end
            random_transactions = random_transactions + 1;
        end
        drain();
        idle_cycle(1);

        if (directed_transactions != 567 || sweep_transactions != 131072 ||
            random_transactions != 4096 || max_consecutive_accepts < 131072 ||
            latency_checks < 3 * 131072 || stalled_input_cycles == 0 ||
            held_output_cycles == 0 || reset_events < 2 || clear_events < 2)
            $fatal(1, "coverage incomplete directed=%0d sweep=%0d random=%0d max_ii1=%0d latency=%0d input_stall=%0d output_hold=%0d reset=%0d clear=%0d",
                   directed_transactions, sweep_transactions, random_transactions,
                   max_consecutive_accepts, latency_checks, stalled_input_cycles,
                   held_output_cycles, reset_events, clear_events);
        for (i = 0; i < 3; i = i + 1) begin
            if (queue_count[i] != 0 || accepted[i] != emitted[i] + canceled[i])
                $fatal(1, "final transaction mismatch variant=%0d", i);
            if (accepted[i] != accepted[0] || emitted[i] != emitted[0] ||
                canceled[i] != canceled[0])
                $fatal(1, "variant transaction counts differ variant=%0d", i);
        end
        $display("SIM_STATS cycles=%0d directed=%0d sweep=%0d random=%0d accepted_each=%0d emitted_each=%0d canceled_each=%0d max_ii1=%0d latency_checks=%0d input_stall_cycles=%0d output_hold_cycles=%0d reset_edges=%0d clear_edges=%0d seed=6d2b79f5",
                 cycles, directed_transactions, sweep_transactions, random_transactions,
                 accepted[0], emitted[0], canceled[0], max_consecutive_accepts,
                 latency_checks, stalled_input_cycles, held_output_cycles,
                 reset_events, clear_events);
        $display("HARDWARE_AGENT_SIM_PASS mlp_sc_post_synth_candidate");
        $finish;
    end
endmodule
