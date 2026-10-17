`timescale 1ns / 1ps

// The actual shared 8x12 branch, including kernel mode tags and accumulators.
// Vectors are fixed integers from source/design.md section 6; 126 Gate and
// 446 Down zero-code groups test canonical bypass at full group counts.
module hap_mlp_rebuild_recovery_tb;
    localparam integer ROWS = 8;
    localparam integer COLS = 12;
    localparam integer LANES = ROWS*COLS;
    localparam integer DOWN_GROUPS = 448;

    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0;
    reg clear = 0;
    reg in_valid = 0;
    wire in_ready;
    reg in_down = 0;
    reg in_first = 0;
    reg in_last = 0;
    reg in_tile = 0;
    reg signed [ROWS*32*9-1:0] activation_s9x8x32 = '0;
    reg signed [COLS*32*4-1:0] weights_s4x12x32 = '0;
    reg [ROWS*8-1:0] activation_code_u8x8 = '0;
    reg [ROWS*6-1:0] activation_shift_u6x8 = '0;
    reg [COLS*8-1:0] weight_code_u8x12 = '0;
    reg [COLS*6-1:0] weight_shift_u6x12 = '0;
    reg [11:0] column_valid_u12 = 12'hfff;
    wire gate_valid;
    reg gate_ready = 0;
    wire signed [LANES*24-1:0] gate_s24x8x12;
    wire down_valid;
    reg down_ready = 0;
    wire down_tile;
    wire signed [LANES*32-1:0] down_s32x8x12;
    wire [31:0] gate_saturation;
    wire [31:0] down_saturation;
    wire guard_overflow;
    wire accumulator_overflow;
    wire [31:0] total_shift_format_count;
    wire format_error;
    wire error;

    integer cycles = 0;
    integer kernel_seen = 0;
    integer gate_seen = 0;
    integer down_seen = 0;
    integer checks = 0;
    integer group_index;
    integer lane;
    reg gate_held = 0;
    reg down_held = 0;
    reg signed [LANES*24-1:0] gate_hold_data;
    reg signed [LANES*32-1:0] down_hold_data;
    reg down_hold_tile;
    reg gate_stalled = 0;
    reg down_stalled = 0;
    reg checking_invalid = 0;
    reg release_gate = 0;
    reg mode_overlap_seen = 0;

    hap_mlp_shared_local_slice8x12_s44_s54 #(
        .DOWN_TILES(2), .DOWN_GROUPS(DOWN_GROUPS), .TILE_W(1)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_down(in_down), .in_first(in_first), .in_last(in_last),
        .in_tile(in_tile),
        .activation_s9x8x32(activation_s9x8x32),
        .weights_s4x12x32(weights_s4x12x32),
        .activation_code_u8x8(activation_code_u8x8),
        .activation_shift_u6x8(activation_shift_u6x8),
        .weight_code_u8x12(weight_code_u8x12),
        .weight_shift_u6x12(weight_shift_u6x12),
        .column_valid_u12(column_valid_u12),
        .gate_valid(gate_valid), .gate_ready(gate_ready),
        .gate_s24x8x12(gate_s24x8x12),
        .down_valid(down_valid), .down_ready(down_ready),
        .down_tile(down_tile), .down_s32x8x12(down_s32x8x12),
        .gate_saturation(gate_saturation),
        .down_saturation(down_saturation),
        .guard_overflow(guard_overflow),
        .accumulator_overflow(accumulator_overflow),
        .total_shift_format_count(total_shift_format_count),
        .format_error(format_error), .error(error)
    );

    task automatic send_group;
        input mode_down;
        input first_group;
        input last_group;
        input tile_index;
        input integer act_code;
        input integer act_shift;
        input integer weight_code;
        input integer weight_shift;
        input integer weight_value;
        integer index;
        begin
            @(negedge clk);
            in_down = mode_down;
            in_first = first_group;
            in_last = last_group;
            in_tile = tile_index;
            for (index = 0; index < ROWS; index = index + 1) begin
                activation_code_u8x8[index*8 +: 8] = act_code[7:0];
                activation_shift_u6x8[index*6 +: 6] = act_shift[5:0];
            end
            for (index = 0; index < COLS; index = index + 1) begin
                weight_code_u8x12[index*8 +: 8] = weight_code[7:0];
                weight_shift_u6x12[index*6 +: 6] = weight_shift[5:0];
            end
            for (index = 0; index < COLS*32; index = index + 1)
                weights_s4x12x32[index*4 +: 4] = weight_value[3:0];
            in_valid = 1;
            do @(posedge clk); while (in_ready !== 1'b1);
            @(negedge clk);
            in_valid = 0;
        end
    endtask

    initial begin
        for (lane = 0; lane < ROWS*32; lane = lane + 1)
            activation_s9x8x32[lane*9 +: 9] = 9'sd1;
        repeat (5) @(negedge clk);
        rst_n = 1;
        repeat (3) @(posedge clk);

        for (group_index = 0; group_index < 128; group_index = group_index + 1) begin
            if (group_index < 2)
                send_group(0, group_index == 0, group_index == 127, 0,
                           100, 6, 141, 14, 1);
            else
                send_group(0, 0, group_index == 127, 0,
                           0, 0, 0, 0, 1);
        end
        for (group_index = 0; group_index < DOWN_GROUPS; group_index = group_index + 1) begin
            if (group_index < 2) begin
                send_group(1, group_index == 0, group_index == DOWN_GROUPS-1, 0,
                           100, 6, 141, 6, 1);
                send_group(1, group_index == 0, group_index == DOWN_GROUPS-1, 1,
                           100, 6, 141, 6, -1);
            end else begin
                send_group(1, 0, group_index == DOWN_GROUPS-1, 0,
                           0, 0, 0, 0, 1);
                send_group(1, 0, group_index == DOWN_GROUPS-1, 1,
                           0, 0, 0, 0, -1);
            end
            if (group_index == 0) begin
                wait (kernel_seen >= 129);
                if (gate_seen !== 0 || mode_overlap_seen !== 1'b1)
                    $fatal(1, "Down mode did not execute before stalled Gate retired");
                release_gate = 1;
                wait (gate_seen == 1);
                if (gate_saturation !== 32'd0 ||
                    guard_overflow !== 1'b0 ||
                    accumulator_overflow !== 1'b0 ||
                    format_error !== 1'b0 ||
                    total_shift_format_count !== 32'd0 ||
                    error !== 1'b0)
                    $fatal(1, "Gate shift20 numeric status mismatch");
            end
        end
        wait (down_seen == 2);
        repeat (6) @(posedge clk);
        if (kernel_seen !== 128 + 2*DOWN_GROUPS || gate_seen !== 1 ||
            down_saturation !== 32'd0 ||
            guard_overflow !== 1'b0 ||
            accumulator_overflow !== 1'b0 ||
            format_error !== 1'b0 ||
            total_shift_format_count !== 32'd0 ||
            error !== 1'b0)
            $fatal(1,
                "Down shift12 status kernel=%0d gate=%0d sat=%0d guard=%0d accum=%0d format=%0d count=%0d error=%0d",
                kernel_seen, gate_seen, down_saturation, guard_overflow,
                accumulator_overflow, format_error,
                total_shift_format_count, error);
        if (gate_stalled !== 1'b1 || down_stalled !== 1'b1 ||
            mode_overlap_seen !== 1'b1)
            $fatal(1, "Gate/Down output backpressure not exercised");

        @(negedge clk);
        clear = 1;
        @(negedge clk);
        clear = 0;
        checking_invalid = 1;
        send_group(1, 1, 0, 0, 100, 5, 141, 6, 1);
        wait (format_error && total_shift_format_count != 0);
        @(negedge clk);
        clear = 1;
        @(negedge clk);
        clear = 0;
        repeat (4) @(posedge clk);
        if (format_error !== 1'b0 ||
            total_shift_format_count !== 32'd0 ||
            error !== 1'b0 || guard_overflow !== 1'b0 ||
            accumulator_overflow !== 1'b0 ||
            gate_valid !== 1'b0 || down_valid !== 1'b0)
            $fatal(1, "numeric fault state was not cleared");
        $display("checks=%0d shift20_raw=56400 shift12_raw=14438400 signed_down=1 zero_code_bypass_gate=126 zero_code_bypass_down=446 mode_overlap=1 invalid11_refused=1 clear_after_fault=1", checks);
        $display("HARDWARE_AGENT_SIM_PASS");
        $finish;
    end

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            cycles <= 0;
            gate_held <= 0;
            down_held <= 0;
            gate_ready <= 0;
            down_ready <= 0;
        end else begin
            cycles <= cycles + 1;
            gate_ready <= release_gate && gate_stalled && (cycles % 5) >= 2;
            down_ready <= down_stalled && (cycles % 7) >= 3;
            if (gate_held && (gate_valid !== 1'b1 ||
                              gate_s24x8x12 !== gate_hold_data))
                $fatal(1, "Gate payload changed under stall");
            if (down_held && (down_valid !== 1'b1 ||
                              down_tile !== down_hold_tile ||
                              down_s32x8x12 !== down_hold_data))
                $fatal(1, "Down payload/tag changed under stall");
            gate_held <= gate_valid && !gate_ready;
            down_held <= down_valid && !down_ready;
            if (gate_valid && !gate_ready) begin
                gate_hold_data <= gate_s24x8x12;
                gate_stalled <= 1;
            end
            if (down_valid && !down_ready) begin
                down_hold_data <= down_s32x8x12;
                down_hold_tile <= down_tile;
                down_stalled <= 1;
            end
            if (!checking_invalid && dut.kernel_valid && !dut.tag_empty &&
                dut.selected_accum_ready) begin
                if (kernel_seen >= 128 && gate_seen == 0)
                    mode_overlap_seen <= 1'b1;
                if (dut.kernel_down !== (kernel_seen >= 128))
                    $fatal(1, "kernel mode tag mismatch at %0d", kernel_seen);
                for (lane = 0; lane < LANES; lane = lane + 1) begin
                    if (kernel_seen < 128) begin
                        if ($signed(dut.guard_s37[lane*37 +: 37]) !==
                            (kernel_seen < 2 ? 37'sd7219200 : 37'sd0))
                            $fatal(1, "Gate guard mismatch group=%0d lane=%0d",
                                kernel_seen, lane);
                    end else if ($signed(dut.guard_s45[lane*45 +: 45]) !==
                                 ((kernel_seen - 128) / 2 < 2 ?
                                  ((kernel_seen - 128) % 2 == 0 ?
                                   45'sd1848115200 : -45'sd1848115200) :
                                  45'sd0))
                        $fatal(1, "Down guard mismatch group=%0d lane=%0d got=%0d",
                            kernel_seen, lane,
                            $signed(dut.guard_s45[lane*45 +: 45]));
                    checks = checks + 1;
                end
                kernel_seen <= kernel_seen + 1;
            end
            if (gate_valid && gate_ready) begin
                if (gate_seen != 0)
                    $fatal(1, "unexpected second Gate output");
                for (lane = 0; lane < LANES; lane = lane + 1) begin
                    if ($signed(gate_s24x8x12[lane*24 +: 24]) !== 24'sd56400)
                        $fatal(1, "Gate shift20 output lane=%0d got=%0d",
                            lane, $signed(gate_s24x8x12[lane*24 +: 24]));
                    checks = checks + 1;
                end
                gate_seen <= gate_seen + 1;
            end
            if (down_valid && down_ready) begin
                if (down_tile !== down_seen[0])
                    $fatal(1, "Down tile tag mismatch got=%0d expected=%0d",
                        down_tile, down_seen);
                for (lane = 0; lane < LANES; lane = lane + 1) begin
                    if ($signed(down_s32x8x12[lane*32 +: 32]) !==
                        (down_seen == 0 ? 32'sd14438400 : -32'sd14438400))
                        $fatal(1, "Down shift12 output tile=%0d lane=%0d got=%0d",
                            down_seen, lane,
                            $signed(down_s32x8x12[lane*32 +: 32]));
                    checks = checks + 1;
                end
                down_seen <= down_seen + 1;
            end
            if (cycles > 100000)
                $fatal(1, "recovery timeout kernel=%0d gate=%0d down=%0d",
                    kernel_seen, gate_seen, down_seen);
        end
    end
endmodule
