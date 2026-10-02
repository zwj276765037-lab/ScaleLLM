`timescale 1ns / 1ps

module hap_mlp_v5_shift20_recovery_tb;
    localparam integer ROWS = 8;
    localparam integer COLS = 12;
    localparam integer LANES = ROWS*COLS;
    localparam integer TILES = 2;
    localparam integer GROUPS = 2;
    localparam signed [36:0] EXPECTED_GUARD = 37'sd7219200;
    localparam signed [23:0] EXPECTED_S24 = 24'sd56400;
    localparam [7:0] ACTIVATION_ZERO_POINT = 8'd0;

    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    wire in_ready;
    reg in_first = 1'b0;
    reg in_last = 1'b0;
    reg in_down = 1'b1;
    reg in_tile = 1'b0;
    reg signed [ROWS*32*9-1:0] activation_s9x8x32;
    reg signed [COLS*32*4-1:0] weights_s4x12x32;
    reg [ROWS*8-1:0] activation_code_u8x8;
    reg [ROWS*6-1:0] activation_shift_u6x8;
    reg [COLS*8-1:0] weight_code_u8x12;
    reg [COLS*6-1:0] weight_shift_u6x12;
    reg [11:0] column_valid_u12 = 12'hfff;

    wire gate_valid;
    reg gate_ready = 1'b1;
    wire signed [LANES*24-1:0] gate_s24x8x12;
    wire down_valid;
    reg down_ready = 1'b1;
    wire down_tile;
    wire signed [LANES*24-1:0] down_s24x8x12;
    wire [31:0] gate_saturation;
    wire [31:0] down_saturation;
    wire guard_overflow;
    wire accumulator_overflow;
    wire error;

    integer lane;
    integer received = 0;
    integer guard_events = 0;
    integer cycles = 0;

    hap_mlp_shared_local_slice8x12_s44_s46 #(
        .DOWN_TILES(TILES),
        .DOWN_GROUPS(GROUPS),
        .TILE_W(1)
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
        .down_tile(down_tile), .down_s24x8x12(down_s24x8x12),
        .gate_saturation(gate_saturation),
        .down_saturation(down_saturation),
        .guard_overflow(guard_overflow),
        .accumulator_overflow(accumulator_overflow),
        .error(error)
    );

    task automatic send_down;
        input first_group;
        input last_group;
        input tile_index;
        begin
            @(negedge clk);
            in_first = first_group;
            in_last = last_group;
            in_tile = tile_index;
            in_valid = 1'b1;
            do @(posedge clk); while (!in_ready);
            @(negedge clk);
            in_valid = 1'b0;
        end
    endtask

    initial begin
        activation_s9x8x32 = '0;
        weights_s4x12x32 = '0;
        activation_code_u8x8 = '0;
        activation_shift_u6x8 = '0;
        weight_code_u8x12 = '0;
        weight_shift_u6x12 = '0;
        for (lane = 0; lane < ROWS*32; lane = lane + 1)
            activation_s9x8x32[lane*9 +: 9] = 9'sd1;
        for (lane = 0; lane < COLS*32; lane = lane + 1)
            weights_s4x12x32[lane*4 +: 4] = 4'sd1;
        for (lane = 0; lane < ROWS; lane = lane + 1) begin
            activation_code_u8x8[lane*8 +: 8] = 8'd100;
            activation_shift_u6x8[lane*6 +: 6] = 6'd6;
        end
        for (lane = 0; lane < COLS; lane = lane + 1) begin
            weight_code_u8x12[lane*8 +: 8] = 8'd141;
            weight_shift_u6x12[lane*6 +: 6] = 6'd14;
        end

        repeat (5) @(posedge clk);
        rst_n = 1'b1;
        repeat (3) @(posedge clk);
        if (ACTIVATION_ZERO_POINT != 0)
            $fatal(1, "test contract requires zp=0");

        // Two tiles avoid a same-address read/write hazard in the group-major
        // BRAM while still accumulating exactly two nonzero Group32 terms.
        send_down(1'b1, 1'b0, 1'b0);
        send_down(1'b1, 1'b0, 1'b1);
        send_down(1'b0, 1'b1, 1'b0);
        send_down(1'b0, 1'b1, 1'b1);

        while (received != TILES && cycles < 2000)
            @(posedge clk);
        repeat (8) @(posedge clk);

        if (received != TILES)
            $fatal(1, "FAIL shift20 timeout received=%0d", received);
        if (guard_events != TILES*GROUPS)
            $fatal(1, "FAIL shift20 guard events=%0d expected=%0d",
                guard_events, TILES*GROUPS);
        if (guard_overflow || accumulator_overflow ||
            dut.kernel_guard_overflow ||
            dut.gate_accumulator_overflow ||
            dut.down_accumulator_overflow)
            $fatal(1, "FAIL shift20 overflow guard=%0d accum=%0d",
                guard_overflow, accumulator_overflow);
        if (error || gate_valid || gate_saturation != 0 ||
            down_saturation != 0)
            $fatal(1,
                "FAIL shift20 status error=%0d gate_valid=%0d sat=%0d/%0d",
                error, gate_valid, gate_saturation, down_saturation);

        $display("PASS: MLP_V5_SHIFT20 raw_s24=56400 guard_s37=7219200 groups=2 zp=0 guard_overflow=0 accumulator_overflow=0");
        $finish;
    end

    always @(posedge clk) begin
        if (rst_n)
            cycles <= cycles + 1;

        if (rst_n && dut.kernel_valid && !dut.tag_empty &&
            dut.selected_accum_ready) begin
            for (lane = 0; lane < LANES; lane = lane + 1)
                if ($signed(dut.guard_s37[lane*37 +: 37]) !==
                    EXPECTED_GUARD)
                    $fatal(1,
                        "FAIL shift20 guard lane=%0d got=%0d expected=%0d",
                        lane, $signed(dut.guard_s37[lane*37 +: 37]),
                        EXPECTED_GUARD);
            guard_events <= guard_events + 1;
        end

        if (down_valid && down_ready) begin
            if (down_tile !== received[0])
                $fatal(1, "FAIL shift20 tile order got=%0d expected=%0d",
                    down_tile, received[0]);
            for (lane = 0; lane < LANES; lane = lane + 1)
                if ($signed(down_s24x8x12[lane*24 +: 24]) !==
                    EXPECTED_S24)
                    $fatal(1,
                        "FAIL shift20 output tile=%0d lane=%0d got=%0d expected=56400",
                        down_tile, lane,
                        $signed(down_s24x8x12[lane*24 +: 24]));
            received <= received + 1;
        end

        if (cycles > 2200)
            $fatal(1, "FAIL shift20 global timeout");
    end
endmodule
