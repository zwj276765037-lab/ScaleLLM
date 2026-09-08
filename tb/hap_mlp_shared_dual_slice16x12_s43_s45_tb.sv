`timescale 1ns / 1ps

module hap_mlp_shared_dual_slice16x12_s43_s45_tb;
    localparam integer GATE_GROUPS = 128;
    localparam integer GATE_PASSES = 2;
    localparam integer DOWN_GROUPS = 5;
    localparam integer DOWN_TILES = 4;
    localparam integer DOWN_TOTAL = DOWN_GROUPS*DOWN_TILES;
    localparam integer SHARED_TOTAL =
        GATE_GROUPS + DOWN_TOTAL + GATE_GROUPS;

    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    integer cycle_count = 0;

    reg [4607:0] gate_activation [0:GATE_GROUPS-1];
    reg [1535:0] gate_weight [0:GATE_GROUPS-1];
    reg [223:0] gate_ameta [0:GATE_GROUPS-1];
    reg [167:0] gate_wmeta [0:GATE_GROUPS-1];
    reg [11:0] gate_mask [0:GATE_GROUPS-1];
    reg [4607:0] gate_expected [0:0];
    reg [4607:0] down_activation [0:DOWN_TOTAL-1];
    reg [1535:0] down_weight [0:DOWN_TOTAL-1];
    reg [223:0] down_ameta [0:DOWN_TOTAL-1];
    reg [167:0] down_wmeta [0:DOWN_TOTAL-1];
    reg [11:0] down_mask [0:DOWN_TOTAL-1];
    reg [4607:0] down_expected [0:DOWN_TILES-1];

    function automatic [4607:0] mask_projection_s24;
        input [4607:0] original;
        input [11:0] mask;
        integer row;
        integer column;
        begin
            mask_projection_s24 = '0;
            for (row = 0; row < 16; row = row + 1)
                for (column = 0; column < 12; column = column + 1)
                    if (mask[column])
                        mask_projection_s24[
                            (row*12+column)*24 +: 24] =
                            original[(row*12+column)*24 +: 24];
        end
    endfunction

    function automatic [11:0] test_down_mask;
        input integer tile;
        begin
            case (tile)
                1: test_down_mask = 12'h0ff;
                3: test_down_mask = 12'h00f;
                default: test_down_mask = 12'hfff;
            endcase
        end
    endfunction

    // ------------------------------------------------------------------
    // Shared DUT source: gate(full) -> down(full/8/4 tails) -> gate(8-tail).
    // The source remains continuously valid so every accepted-input interval
    // and both mode transitions directly exercise same-cycle refill.
    // ------------------------------------------------------------------
    integer shared_send = 0;
    wire shared_in_valid = shared_send < SHARED_TOTAL;
    wire shared_in_ready;
    reg shared_in_down;
    reg shared_in_first;
    reg shared_in_last;
    reg [1:0] shared_in_tile;
    reg signed [4607:0] shared_activation;
    reg signed [1535:0] shared_weight;
    reg [127:0] shared_activation_code;
    reg [95:0] shared_activation_shift;
    reg [95:0] shared_weight_code;
    reg [71:0] shared_weight_shift;
    reg [11:0] shared_column_mask;
    integer shared_source_index;
    integer shared_down_index;

    always @* begin
        shared_in_down = 1'b0;
        shared_in_first = 1'b0;
        shared_in_last = 1'b0;
        shared_in_tile = 2'd0;
        shared_activation = '0;
        shared_weight = '0;
        shared_activation_code = '0;
        shared_activation_shift = '0;
        shared_weight_code = '0;
        shared_weight_shift = '0;
        shared_column_mask = 12'hfff;
        shared_source_index = 0;
        shared_down_index = 0;
        if (shared_send < GATE_GROUPS) begin
            shared_source_index = shared_send;
            shared_in_first = shared_send == 0;
            shared_in_last = shared_send == GATE_GROUPS-1;
            shared_activation = gate_activation[shared_source_index];
            shared_weight = gate_weight[shared_source_index];
            shared_activation_code =
                gate_ameta[shared_source_index][127:0];
            shared_activation_shift =
                gate_ameta[shared_source_index][223:128];
            shared_weight_code = gate_wmeta[shared_source_index][95:0];
            shared_weight_shift = gate_wmeta[shared_source_index][167:96];
            shared_column_mask = 12'hfff;
        end else if (shared_send < GATE_GROUPS+DOWN_TOTAL) begin
            shared_in_down = 1'b1;
            shared_down_index = shared_send-GATE_GROUPS;
            shared_source_index = shared_down_index;
            shared_in_first = shared_down_index/DOWN_TILES == 0;
            shared_in_last =
                shared_down_index/DOWN_TILES == DOWN_GROUPS-1;
            shared_in_tile = shared_down_index % DOWN_TILES;
            shared_activation = down_activation[shared_source_index];
            shared_weight = down_weight[shared_source_index];
            shared_activation_code =
                down_ameta[shared_source_index][127:0];
            shared_activation_shift =
                down_ameta[shared_source_index][223:128];
            shared_weight_code = down_wmeta[shared_source_index][95:0];
            shared_weight_shift = down_wmeta[shared_source_index][167:96];
            shared_column_mask = test_down_mask(shared_in_tile);
        end else begin
            shared_source_index = shared_send-GATE_GROUPS-DOWN_TOTAL;
            shared_in_first = shared_source_index == 0;
            shared_in_last = shared_source_index == GATE_GROUPS-1;
            shared_activation = gate_activation[shared_source_index];
            shared_weight = gate_weight[shared_source_index];
            shared_activation_code =
                gate_ameta[shared_source_index][127:0];
            shared_activation_shift =
                gate_ameta[shared_source_index][223:128];
            shared_weight_code = gate_wmeta[shared_source_index][95:0];
            shared_weight_shift = gate_wmeta[shared_source_index][167:96];
            shared_column_mask = 12'h0ff;
        end
    end

    wire shared_gate_valid;
    wire shared_gate_ready;
    wire signed [4607:0] shared_gate_projection;
    wire shared_down_valid;
    wire shared_down_ready;
    wire [1:0] shared_down_tile;
    wire signed [4607:0] shared_down_projection;
    wire [31:0] shared_gate_saturation;
    wire [31:0] shared_down_saturation;
    wire [31:0] shared_input_count;
    wire [31:0] shared_gate_output_count;
    wire [31:0] shared_down_output_count;
    wire shared_error;

    hap_mlp_shared_dual_slice16x12_s43_s45 #(
        .DOWN_TILES(DOWN_TILES), .DOWN_GROUPS(DOWN_GROUPS)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(shared_in_valid), .in_ready(shared_in_ready),
        .in_down(shared_in_down), .in_first(shared_in_first),
        .in_last(shared_in_last), .in_tile(shared_in_tile),
        .activation_s9x16x32(shared_activation),
        .weights_s4x12x32(shared_weight),
        .activation_code_u8x16(shared_activation_code),
        .activation_shift_u6x16(shared_activation_shift),
        .weight_code_u8x12(shared_weight_code),
        .weight_shift_u6x12(shared_weight_shift),
        .column_valid_u12(shared_column_mask),
        .gate_valid(shared_gate_valid), .gate_ready(shared_gate_ready),
        .gate_s24x16x12(shared_gate_projection),
        .down_valid(shared_down_valid), .down_ready(shared_down_ready),
        .down_tile(shared_down_tile),
        .down_s24x16x12(shared_down_projection),
        .gate_saturation(shared_gate_saturation),
        .down_saturation(shared_down_saturation),
        .input_transaction_count(shared_input_count),
        .gate_output_pass_count(shared_gate_output_count),
        .down_output_pass_count(shared_down_output_count),
        .error(shared_error)
    );

    // ------------------------------------------------------------------
    // Gate numerical reference: the Run 0123 bit-exact dual-local candidate.
    // It receives the same two gate passes through an independent source.
    // ------------------------------------------------------------------
    integer gate_ref_send = 0;
    wire gate_ref_in_valid = gate_ref_send < GATE_GROUPS*GATE_PASSES;
    wire gate_ref_in_ready;
    wire [6:0] gate_ref_source = gate_ref_send < GATE_GROUPS ?
        gate_ref_send[6:0] : (gate_ref_send-GATE_GROUPS);
    wire gate_ref_second_pass = gate_ref_send >= GATE_GROUPS;
    wire gate_ref_out_valid;
    wire gate_ref_out_ready;
    wire signed [4607:0] gate_ref_projection;
    wire [31:0] gate_ref_input_count;
    wire [31:0] gate_ref_output_count;
    wire [31:0] gate_ref_saturation;
    wire gate_ref_error;

    hap_mlp_gate_up_dual_local_accum16x12_s43 gate_ref (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(gate_ref_in_valid), .in_ready(gate_ref_in_ready),
        .in_first_group(gate_ref_source == 0),
        .in_last_group(gate_ref_source == GATE_GROUPS-1),
        .activation_s9x16x32(gate_activation[gate_ref_source]),
        .weights_s4x12x32(gate_weight[gate_ref_source]),
        .activation_code_u8x16(gate_ameta[gate_ref_source][127:0]),
        .activation_shift_u6x16(gate_ameta[gate_ref_source][223:128]),
        .weight_code_u8x12(gate_wmeta[gate_ref_source][95:0]),
        .weight_shift_u6x12(gate_wmeta[gate_ref_source][167:96]),
        .column_valid_u12(gate_ref_second_pass ? 12'h0ff : 12'hfff),
        .out_valid(gate_ref_out_valid), .out_ready(gate_ref_out_ready),
        .projection_s24x16x12(gate_ref_projection),
        .input_group_count(gate_ref_input_count),
        .output_pass_count(gate_ref_output_count),
        .saturation_count(gate_ref_saturation), .error(gate_ref_error)
    );

    // ------------------------------------------------------------------
    // Down numerical reference: the existing V5 dual-slice16x12 wrapper.
    // Tile 1 is changed from full to 8 columns; tile 3 retains the 4-column
    // formal tail.  Both DUT and reference see the identical override.
    // ------------------------------------------------------------------
    integer down_ref_send = 0;
    wire down_ref_in_valid = down_ref_send < DOWN_TOTAL;
    wire down_ref_in_ready;
    wire [4:0] down_ref_source = down_ref_send < DOWN_TOTAL ?
        down_ref_send[4:0] : DOWN_TOTAL-1;
    wire [1:0] down_ref_tile_in = down_ref_send % DOWN_TILES;
    wire down_ref_out_valid;
    wire down_ref_out_ready;
    wire [1:0] down_ref_tile;
    wire signed [4607:0] down_ref_projection;
    wire [31:0] down_ref_input_count;
    wire [31:0] down_ref_output_count;
    wire [31:0] down_ref_saturation;
    wire down_ref_error;

    hap_mlp_down_group_major_dual_slice16x12_s45 #(
        .TILES(DOWN_TILES), .GROUPS(DOWN_GROUPS)
    ) down_ref (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(down_ref_in_valid), .in_ready(down_ref_in_ready),
        .in_first_group(down_ref_send/DOWN_TILES == 0),
        .in_last_group(
            down_ref_send/DOWN_TILES == DOWN_GROUPS-1),
        .in_tile_index(down_ref_tile_in),
        .activation_s9x16x32(down_activation[down_ref_source]),
        .weights_s4x12x32(down_weight[down_ref_source]),
        .activation_code_u8x16(down_ameta[down_ref_source][127:0]),
        .activation_shift_u6x16(down_ameta[down_ref_source][223:128]),
        .weight_code_u8x12(down_wmeta[down_ref_source][95:0]),
        .weight_shift_u6x12(down_wmeta[down_ref_source][167:96]),
        .column_valid_u12(test_down_mask(down_ref_tile_in)),
        .out_valid(down_ref_out_valid), .out_ready(down_ref_out_ready),
        .out_tile_index(down_ref_tile),
        .projection_s24x16x12(down_ref_projection),
        .input_tile_count(down_ref_input_count),
        .output_pass_count(down_ref_output_count),
        .saturation_count(down_ref_saturation), .error(down_ref_error)
    );

    // Atomic reference comparison plus pseudo-random sink backpressure.
    reg [15:0] ready_lfsr = 16'h4d35;
    reg gate_sink_ready = 1'b0;
    reg down_sink_ready = 1'b0;
    integer gate_forced_stalls = 5;
    integer down_forced_stalls = 6;
    wire gate_pair_valid = shared_gate_valid && gate_ref_out_valid;
    wire down_pair_valid = shared_down_valid && down_ref_out_valid;
    assign shared_gate_ready = gate_sink_ready && gate_ref_out_valid;
    assign gate_ref_out_ready = gate_sink_ready && shared_gate_valid;
    assign shared_down_ready = down_sink_ready && down_ref_out_valid;
    assign down_ref_out_ready = down_sink_ready && shared_down_valid;

    integer gate_pair_count = 0;
    integer down_pair_count = 0;
    integer gate_stall_cycles = 0;
    integer down_stall_cycles = 0;
    integer gate_stability_checks = 0;
    integer down_stability_checks = 0;
    reg gate_was_stalled = 1'b0;
    reg down_was_stalled = 1'b0;
    reg [4607:0] gate_hold;
    reg [4607:0] down_hold;
    reg [1:0] down_tile_hold;

    // II and phase-transition coverage at both the top boundary and each
    // branch's actual ingress-to-kernel dispatch boundary.
    integer shared_last_accept = -1;
    integer shared_max_accept_interval = 0;
    integer shared_ii_samples = 0;
    reg previous_mode = 1'b0;
    integer mode_switch_count = 0;
    integer mask12_accepts = 0;
    integer mask8_accepts = 0;
    integer mask4_accepts = 0;
    integer branch0_last_dispatch = -1;
    integer branch1_last_dispatch = -1;
    integer branch0_max_dispatch_interval = 0;
    integer branch1_max_dispatch_interval = 0;
    integer branch0_dispatch_count = 0;
    integer branch1_dispatch_count = 0;
    integer branch0_refill_count = 0;
    integer branch1_refill_count = 0;
    integer parent_full_cycles = 0;
    integer parent_backpressure_cycles = 0;

    initial begin
        $readmemh(
            "data/mlp_v5_dual_slice16x12/gate_activation_s9x16x32.mem",
            gate_activation);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/gate_weights_s4x12x32.mem",
            gate_weight);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/gate_activation_meta_u224.mem",
            gate_ameta);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/gate_weight_meta_u168.mem",
            gate_wmeta);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/gate_column_valid_u12.mem",
            gate_mask);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/gate_expected_s24x16x12.mem",
            gate_expected);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/down_activation_s9x16x32.mem",
            down_activation);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/down_weights_s4x12x32.mem",
            down_weight);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/down_activation_meta_u224.mem",
            down_ameta);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/down_weight_meta_u168.mem",
            down_wmeta);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/down_column_valid_u12.mem",
            down_mask);
        $readmemh(
            "data/mlp_v5_dual_slice16x12/down_expected_s24x16x12.mem",
            down_expected);
        repeat (7) @(posedge clk);
        rst_n <= 1'b1;
    end

    // Exercise the P8 parent boundary itself.  Holding one local branch in
    // maintenance clear fills both central slots without allowing a partial
    // branch delivery; after release the original continuous stream must
    // recover without loss, duplication or reordering.
    initial begin
        wait (rst_n);
        @(negedge clk);
        force dut.u_branch0.clear_local_r = 1'b1;
        repeat (5) @(posedge clk);
        @(negedge clk);
        release dut.u_branch0.clear_local_r;
    end

    always @(posedge clk) begin
        if (rst_n) begin
            cycle_count <= cycle_count + 1;
            ready_lfsr <= {ready_lfsr[14:0],
                ready_lfsr[15] ^ ready_lfsr[13] ^
                ready_lfsr[12] ^ ready_lfsr[10]};

            if (gate_forced_stalls > 0) begin
                gate_sink_ready <= 1'b0;
                if (gate_pair_valid)
                    gate_forced_stalls = gate_forced_stalls-1;
            end else begin
                gate_sink_ready <= |ready_lfsr[2:0];
            end
            if (down_forced_stalls > 0) begin
                down_sink_ready <= 1'b0;
                if (down_pair_valid)
                    down_forced_stalls = down_forced_stalls-1;
            end else begin
                down_sink_ready <= |ready_lfsr[7:5];
            end

            if (shared_in_valid && shared_in_ready) begin
                if (shared_last_accept >= 0) begin
                    if (cycle_count-shared_last_accept >
                        shared_max_accept_interval)
                        shared_max_accept_interval <=
                            cycle_count-shared_last_accept;
                    shared_ii_samples <= shared_ii_samples + 1;
                    if (previous_mode != shared_in_down) begin
                        mode_switch_count <= mode_switch_count + 1;
                    end
                end
                previous_mode <= shared_in_down;
                shared_last_accept <= cycle_count;
                shared_send <= shared_send + 1;
                case (shared_column_mask)
                    12'hfff: mask12_accepts <= mask12_accepts + 1;
                    12'h0ff: mask8_accepts <= mask8_accepts + 1;
                    12'h00f: mask4_accepts <= mask4_accepts + 1;
                    default: $fatal(1, "FAIL unexpected test mask %h",
                        shared_column_mask);
                endcase
            end
            if (dut.parent_full)
                parent_full_cycles <= parent_full_cycles + 1;
            if (shared_in_valid && !shared_in_ready && dut.parent_full)
                parent_backpressure_cycles <=
                    parent_backpressure_cycles + 1;

            if (gate_ref_in_valid && gate_ref_in_ready)
                gate_ref_send <= gate_ref_send + 1;
            if (down_ref_in_valid && down_ref_in_ready)
                down_ref_send <= down_ref_send + 1;

            if (dut.u_branch0.dispatch_fire) begin
                if (branch0_last_dispatch >= 0) begin
                    if (cycle_count-branch0_last_dispatch >
                        branch0_max_dispatch_interval)
                        branch0_max_dispatch_interval <=
                            cycle_count-branch0_last_dispatch;
                end
                branch0_last_dispatch <= cycle_count;
                branch0_dispatch_count <= branch0_dispatch_count + 1;
            end
            if (dut.u_branch1.dispatch_fire) begin
                if (branch1_last_dispatch >= 0) begin
                    if (cycle_count-branch1_last_dispatch >
                        branch1_max_dispatch_interval)
                        branch1_max_dispatch_interval <=
                            cycle_count-branch1_last_dispatch;
                end
                branch1_last_dispatch <= cycle_count;
                branch1_dispatch_count <= branch1_dispatch_count + 1;
            end
            if (dut.u_branch0.input_fire && dut.u_branch0.dispatch_fire)
                branch0_refill_count <= branch0_refill_count + 1;
            if (dut.u_branch1.input_fire && dut.u_branch1.dispatch_fire)
                branch1_refill_count <= branch1_refill_count + 1;

            if (gate_was_stalled) begin
                gate_stability_checks = gate_stability_checks + 1;
                if (!shared_gate_valid ||
                    shared_gate_projection !== gate_hold)
                    $fatal(1,
                        "FAIL shared gate output changed under backpressure");
            end
            if (down_was_stalled) begin
                down_stability_checks = down_stability_checks + 1;
                if (!shared_down_valid ||
                    shared_down_projection !== down_hold ||
                    shared_down_tile !== down_tile_hold)
                    $fatal(1,
                        "FAIL shared down output changed under backpressure");
            end
            gate_was_stalled <=
                shared_gate_valid && !shared_gate_ready;
            down_was_stalled <=
                shared_down_valid && !shared_down_ready;
            if (shared_gate_valid && !shared_gate_ready) begin
                gate_hold <= shared_gate_projection;
                gate_stall_cycles = gate_stall_cycles + 1;
            end
            if (shared_down_valid && !shared_down_ready) begin
                down_hold <= shared_down_projection;
                down_tile_hold <= shared_down_tile;
                down_stall_cycles = down_stall_cycles + 1;
            end

            if (shared_gate_valid && shared_gate_ready) begin
                if (shared_gate_projection !== gate_ref_projection)
                    $fatal(1,
                        "FAIL shared/reference gate mismatch pass=%0d",
                        gate_pair_count);
                if (shared_gate_projection !==
                    mask_projection_s24(gate_expected[0],
                        gate_pair_count == 0 ? 12'hfff : 12'h0ff))
                    $fatal(1,
                        "FAIL independent gate expected mismatch pass=%0d",
                        gate_pair_count);
                if (shared_gate_saturation != gate_ref_saturation)
                    $fatal(1,
                        "FAIL gate saturation mismatch shared/ref=%0d/%0d",
                        shared_gate_saturation, gate_ref_saturation);
                gate_pair_count <= gate_pair_count + 1;
            end

            if (shared_down_valid && shared_down_ready) begin
                if (shared_down_tile !== down_ref_tile ||
                    shared_down_projection !== down_ref_projection)
                    $fatal(1,
                        "FAIL shared/reference down mismatch output=%0d tile=%0d/%0d",
                        down_pair_count, shared_down_tile, down_ref_tile);
                if (shared_down_tile !== down_pair_count[1:0])
                    $fatal(1,
                        "FAIL down tile order output=%0d tile=%0d",
                        down_pair_count, shared_down_tile);
                if (shared_down_projection !== mask_projection_s24(
                    down_expected[down_pair_count],
                    test_down_mask(down_pair_count)))
                    $fatal(1,
                        "FAIL independent down expected mismatch tile=%0d",
                        down_pair_count);
                if (shared_down_saturation != down_ref_saturation)
                    $fatal(1,
                        "FAIL down saturation mismatch shared/ref=%0d/%0d",
                        shared_down_saturation, down_ref_saturation);
                down_pair_count <= down_pair_count + 1;
            end

            if (shared_error || gate_ref_error || down_ref_error)
                $fatal(1,
                    "FAIL sticky error shared/gate/down=%0d/%0d/%0d",
                    shared_error, gate_ref_error, down_ref_error);

            if (gate_pair_count == GATE_PASSES &&
                down_pair_count == DOWN_TILES) begin
                if (shared_send != SHARED_TOTAL ||
                    gate_ref_send != GATE_GROUPS*GATE_PASSES ||
                    down_ref_send != DOWN_TOTAL ||
                    shared_input_count != SHARED_TOTAL ||
                    shared_gate_output_count != GATE_PASSES ||
                    shared_down_output_count != DOWN_TILES ||
                    gate_ref_input_count != GATE_GROUPS*GATE_PASSES ||
                    gate_ref_output_count != GATE_PASSES ||
                    down_ref_input_count != DOWN_TOTAL ||
                    down_ref_output_count != DOWN_TILES)
                    $fatal(1,
                        "FAIL final counts shared=%0d/%0d/%0d ref=%0d/%0d/%0d/%0d",
                        shared_input_count, shared_gate_output_count,
                        shared_down_output_count, gate_ref_input_count,
                        gate_ref_output_count, down_ref_input_count,
                        down_ref_output_count);
                if (shared_ii_samples != SHARED_TOTAL-1 ||
                    mode_switch_count != 2 ||
                    branch0_dispatch_count != SHARED_TOTAL ||
                    branch1_dispatch_count != SHARED_TOTAL ||
                    branch0_refill_count == 0 ||
                    branch1_refill_count == 0 ||
                    parent_full_cycles == 0 ||
                    parent_backpressure_cycles == 0)
                    $fatal(1,
                        "FAIL II/refill top=%0d samples=%0d switches=%0d dispatch=%0d/%0d max=%0d/%0d refill=%0d/%0d parent_full/backpressure=%0d/%0d",
                        shared_max_accept_interval, shared_ii_samples,
                        mode_switch_count, branch0_dispatch_count,
                        branch1_dispatch_count,
                        branch0_max_dispatch_interval,
                        branch1_max_dispatch_interval,
                        branch0_refill_count, branch1_refill_count,
                        parent_full_cycles, parent_backpressure_cycles);
                if (mask12_accepts != GATE_GROUPS+DOWN_GROUPS*2 ||
                    mask8_accepts != GATE_GROUPS+DOWN_GROUPS ||
                    mask4_accepts != DOWN_GROUPS ||
                    gate_stall_cycles == 0 || down_stall_cycles == 0 ||
                    gate_stability_checks == 0 ||
                    down_stability_checks == 0)
                    $fatal(1,
                        "FAIL coverage masks=%0d/%0d/%0d stalls=%0d/%0d stable=%0d/%0d",
                        mask12_accepts, mask8_accepts, mask4_accepts,
                        gate_stall_cycles, down_stall_cycles,
                        gate_stability_checks, down_stability_checks);

                $display(
                    "PASS: V5 shared dual 16x12 gate/down bit-exact inputs=%0d gate=%0d down=%0d top_ii=%0d dispatch_ii=%0d/%0d switches=%0d masks=%0d/%0d/%0d refills=%0d/%0d stalls=%0d/%0d stable=%0d/%0d parent_full/backpressure=%0d/%0d cycles=%0d",
                    shared_input_count, shared_gate_output_count,
                    shared_down_output_count, shared_max_accept_interval,
                    branch0_max_dispatch_interval,
                    branch1_max_dispatch_interval, mode_switch_count,
                    mask12_accepts, mask8_accepts, mask4_accepts,
                    branch0_refill_count, branch1_refill_count,
                    gate_stall_cycles, down_stall_cycles,
                    gate_stability_checks, down_stability_checks,
                    parent_full_cycles, parent_backpressure_cycles,
                    cycle_count);
                $finish;
            end

            if (gate_pair_count > GATE_PASSES ||
                down_pair_count > DOWN_TILES)
                $fatal(1, "FAIL duplicate output gate/down=%0d/%0d",
                    gate_pair_count, down_pair_count);
            if (cycle_count > 2500)
                $fatal(1,
                    "FAIL timeout send=%0d gate/down=%0d/%0d dispatch=%0d/%0d errors=%0d/%0d/%0d",
                    shared_send, gate_pair_count, down_pair_count,
                    branch0_dispatch_count, branch1_dispatch_count,
                    shared_error, gate_ref_error, down_ref_error);
        end
    end

endmodule
