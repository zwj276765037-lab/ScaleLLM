`timescale 1ns / 1ps

// Dedicated no-backpressure throughput gate.  Keeping this separate from the
// random-stall bit-exact test prevents intentional sink backpressure from
// being misreported as an intrinsic kernel/ingress initiation interval.
module hap_mlp_shared_dual_slice16x12_s43_s45_ii_tb;
    localparam integer GATE_GROUPS = 128;
    localparam integer DOWN_GROUPS = 5;
    localparam integer DOWN_TILES = 4;
    localparam integer DOWN_TOTAL = DOWN_GROUPS*DOWN_TILES;
    localparam integer TOTAL = GATE_GROUPS+DOWN_TOTAL+GATE_GROUPS;

    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    integer cycle_count = 0;

    reg [4607:0] gate_activation [0:GATE_GROUPS-1];
    reg [1535:0] gate_weight [0:GATE_GROUPS-1];
    reg [223:0] gate_ameta [0:GATE_GROUPS-1];
    reg [167:0] gate_wmeta [0:GATE_GROUPS-1];
    reg [4607:0] gate_expected [0:0];
    reg [4607:0] down_activation [0:DOWN_TOTAL-1];
    reg [1535:0] down_weight [0:DOWN_TOTAL-1];
    reg [223:0] down_ameta [0:DOWN_TOTAL-1];
    reg [167:0] down_wmeta [0:DOWN_TOTAL-1];
    reg [4607:0] down_expected [0:DOWN_TILES-1];

    function automatic [11:0] phase_mask;
        input integer down_tile_index;
        begin
            case (down_tile_index)
                1: phase_mask = 12'h0ff;
                3: phase_mask = 12'h00f;
                default: phase_mask = 12'hfff;
            endcase
        end
    endfunction

    function automatic [4607:0] mask_s24;
        input [4607:0] original;
        input [11:0] mask;
        integer row;
        integer column;
        begin
            mask_s24 = '0;
            for (row = 0; row < 16; row = row + 1)
                for (column = 0; column < 12; column = column + 1)
                    if (mask[column])
                        mask_s24[(row*12+column)*24 +: 24] =
                            original[(row*12+column)*24 +: 24];
        end
    endfunction

    integer send_count = 0;
    wire in_valid = send_count < TOTAL;
    wire in_ready;
    reg in_down;
    reg in_first;
    reg in_last;
    reg [1:0] in_tile;
    reg signed [4607:0] in_activation;
    reg signed [1535:0] in_weight;
    reg [127:0] in_activation_code;
    reg [95:0] in_activation_shift;
    reg [95:0] in_weight_code;
    reg [71:0] in_weight_shift;
    reg [11:0] in_mask;
    integer source_index;
    integer down_index;

    always @* begin
        in_down = 1'b0;
        in_first = 1'b0;
        in_last = 1'b0;
        in_tile = 2'd0;
        in_activation = '0;
        in_weight = '0;
        in_activation_code = '0;
        in_activation_shift = '0;
        in_weight_code = '0;
        in_weight_shift = '0;
        in_mask = 12'hfff;
        source_index = 0;
        down_index = 0;
        if (send_count < GATE_GROUPS) begin
            source_index = send_count;
            in_first = send_count == 0;
            in_last = send_count == GATE_GROUPS-1;
            in_activation = gate_activation[source_index];
            in_weight = gate_weight[source_index];
            in_activation_code = gate_ameta[source_index][127:0];
            in_activation_shift = gate_ameta[source_index][223:128];
            in_weight_code = gate_wmeta[source_index][95:0];
            in_weight_shift = gate_wmeta[source_index][167:96];
        end else if (send_count < GATE_GROUPS+DOWN_TOTAL) begin
            in_down = 1'b1;
            down_index = send_count-GATE_GROUPS;
            source_index = down_index;
            in_first = down_index/DOWN_TILES == 0;
            in_last = down_index/DOWN_TILES == DOWN_GROUPS-1;
            in_tile = down_index % DOWN_TILES;
            in_activation = down_activation[source_index];
            in_weight = down_weight[source_index];
            in_activation_code = down_ameta[source_index][127:0];
            in_activation_shift = down_ameta[source_index][223:128];
            in_weight_code = down_wmeta[source_index][95:0];
            in_weight_shift = down_wmeta[source_index][167:96];
            in_mask = phase_mask(in_tile);
        end else begin
            source_index = send_count-GATE_GROUPS-DOWN_TOTAL;
            in_first = source_index == 0;
            in_last = source_index == GATE_GROUPS-1;
            in_activation = gate_activation[source_index];
            in_weight = gate_weight[source_index];
            in_activation_code = gate_ameta[source_index][127:0];
            in_activation_shift = gate_ameta[source_index][223:128];
            in_weight_code = gate_wmeta[source_index][95:0];
            in_weight_shift = gate_wmeta[source_index][167:96];
            in_mask = 12'h0ff;
        end
    end

    wire gate_valid;
    wire signed [4607:0] gate_projection;
    wire down_valid;
    wire [1:0] down_tile;
    wire signed [4607:0] down_projection;
    wire [31:0] gate_saturation;
    wire [31:0] down_saturation;
    wire [31:0] input_count;
    wire [31:0] gate_output_count;
    wire [31:0] down_output_count;
    wire error;

    hap_mlp_shared_dual_slice16x12_s43_s45 #(
        .DOWN_TILES(DOWN_TILES), .DOWN_GROUPS(DOWN_GROUPS)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_down(in_down), .in_first(in_first), .in_last(in_last),
        .in_tile(in_tile), .activation_s9x16x32(in_activation),
        .weights_s4x12x32(in_weight),
        .activation_code_u8x16(in_activation_code),
        .activation_shift_u6x16(in_activation_shift),
        .weight_code_u8x12(in_weight_code),
        .weight_shift_u6x12(in_weight_shift),
        .column_valid_u12(in_mask),
        .gate_valid(gate_valid), .gate_ready(1'b1),
        .gate_s24x16x12(gate_projection),
        .down_valid(down_valid), .down_ready(1'b1),
        .down_tile(down_tile), .down_s24x16x12(down_projection),
        .gate_saturation(gate_saturation),
        .down_saturation(down_saturation),
        .input_transaction_count(input_count),
        .gate_output_pass_count(gate_output_count),
        .down_output_pass_count(down_output_count), .error(error)
    );

    integer last_accept = -1;
    integer max_accept_interval = 0;
    integer accept_samples = 0;
    reg previous_mode = 1'b0;
    integer switch_count = 0;
    integer branch0_last_dispatch = -1;
    integer branch1_last_dispatch = -1;
    integer branch0_max_dispatch_interval = 0;
    integer branch1_max_dispatch_interval = 0;
    integer branch0_dispatches = 0;
    integer branch1_dispatches = 0;
    integer branch0_refills = 0;
    integer branch1_refills = 0;
    integer gate_outputs = 0;
    integer down_outputs = 0;

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
            "data/mlp_v5_dual_slice16x12/down_expected_s24x16x12.mem",
            down_expected);
        repeat (7) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (rst_n) begin
            cycle_count <= cycle_count+1;
            if (in_valid && in_ready) begin
                if (last_accept >= 0) begin
                    if (cycle_count-last_accept > max_accept_interval)
                        max_accept_interval <= cycle_count-last_accept;
                    if (cycle_count-last_accept != 1)
                        $fatal(1,
                            "FAIL no-stall top II input=%0d interval=%0d",
                            send_count, cycle_count-last_accept);
                    accept_samples <= accept_samples+1;
                    if (previous_mode != in_down)
                        switch_count <= switch_count+1;
                end
                previous_mode <= in_down;
                last_accept <= cycle_count;
                send_count <= send_count+1;
            end

            if (dut.u_branch0.dispatch_fire) begin
                if (branch0_last_dispatch >= 0) begin
                    if (cycle_count-branch0_last_dispatch >
                        branch0_max_dispatch_interval)
                        branch0_max_dispatch_interval <=
                            cycle_count-branch0_last_dispatch;
                    if (cycle_count-branch0_last_dispatch != 1)
                        $fatal(1,
                            "FAIL no-stall branch0 dispatch II=%0d at %0d",
                            cycle_count-branch0_last_dispatch,
                            branch0_dispatches);
                end
                branch0_last_dispatch <= cycle_count;
                branch0_dispatches <= branch0_dispatches+1;
            end
            if (dut.u_branch1.dispatch_fire) begin
                if (branch1_last_dispatch >= 0) begin
                    if (cycle_count-branch1_last_dispatch >
                        branch1_max_dispatch_interval)
                        branch1_max_dispatch_interval <=
                            cycle_count-branch1_last_dispatch;
                    if (cycle_count-branch1_last_dispatch != 1)
                        $fatal(1,
                            "FAIL no-stall branch1 dispatch II=%0d at %0d",
                            cycle_count-branch1_last_dispatch,
                            branch1_dispatches);
                end
                branch1_last_dispatch <= cycle_count;
                branch1_dispatches <= branch1_dispatches+1;
            end
            if (dut.u_branch0.input_fire && dut.u_branch0.dispatch_fire)
                branch0_refills <= branch0_refills+1;
            if (dut.u_branch1.input_fire && dut.u_branch1.dispatch_fire)
                branch1_refills <= branch1_refills+1;

            if (gate_valid) begin
                if (gate_projection !== mask_s24(gate_expected[0],
                    gate_outputs == 0 ? 12'hfff : 12'h0ff))
                    $fatal(1,
                        "FAIL no-stall gate bit-exact output=%0d",
                        gate_outputs);
                gate_outputs <= gate_outputs+1;
            end
            if (down_valid) begin
                if (down_tile !== down_outputs[1:0] ||
                    down_projection !== mask_s24(
                        down_expected[down_outputs],
                        phase_mask(down_outputs)))
                    $fatal(1,
                        "FAIL no-stall down bit-exact output=%0d tile=%0d",
                        down_outputs, down_tile);
                down_outputs <= down_outputs+1;
            end
            if (error)
                $fatal(1, "FAIL no-stall shared sticky error");

            if (gate_outputs == 2 && down_outputs == DOWN_TILES) begin
                if (send_count != TOTAL || input_count != TOTAL ||
                    gate_output_count != 2 ||
                    down_output_count != DOWN_TILES ||
                    gate_saturation != 0 || down_saturation != 0 ||
                    max_accept_interval != 1 ||
                    accept_samples != TOTAL-1 || switch_count != 2 ||
                    branch0_dispatches != TOTAL ||
                    branch1_dispatches != TOTAL ||
                    branch0_max_dispatch_interval != 1 ||
                    branch1_max_dispatch_interval != 1 ||
                    branch0_refills != TOTAL-1 ||
                    branch1_refills != TOTAL-1)
                    $fatal(1,
                        "FAIL no-stall final counts=%0d/%0d/%0d II=%0d dispatch=%0d/%0d max=%0d/%0d refill=%0d/%0d switches=%0d",
                        send_count, gate_outputs, down_outputs,
                        max_accept_interval, branch0_dispatches,
                        branch1_dispatches,
                        branch0_max_dispatch_interval,
                        branch1_max_dispatch_interval,
                        branch0_refills, branch1_refills,
                        switch_count);
                $display(
                    "PASS: V5 shared dual 16x12 no-stall II=1 inputs=%0d dispatch=%0d/%0d refills=%0d/%0d switches=%0d gate=%0d down=%0d cycles=%0d",
                    input_count, branch0_dispatches,
                    branch1_dispatches, branch0_refills,
                    branch1_refills, switch_count,
                    gate_output_count, down_output_count, cycle_count);
                $finish;
            end
            if (cycle_count > 1000)
                $fatal(1,
                    "FAIL no-stall timeout send=%0d dispatch=%0d/%0d output=%0d/%0d",
                    send_count, branch0_dispatches,
                    branch1_dispatches, gate_outputs, down_outputs);
        end
    end

endmodule
