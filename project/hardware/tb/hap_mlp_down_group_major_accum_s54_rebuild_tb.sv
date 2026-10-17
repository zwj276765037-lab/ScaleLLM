`timescale 1ns / 1ps

// Directed S45->S54->S32 boundary vectors from source/design.md section 6.
// The shift-12 guard is independently fixed at 1,848,115,200. The legal
// maximum Group32 guard is 17,386,831,872,000; its full 448-group sum fits
// S54 but legitimately saturates the terminal S32 output.
module hap_mlp_down_group_major_accum_s54_rebuild_tb;
    localparam integer LANES = 8;
    localparam integer TILES = 2;
    localparam integer GROUPS = 448;
    localparam signed [44:0] SHIFT12_GUARD = 45'sd1848115200;
    localparam signed [44:0] LEGAL_MAX_GUARD = 45'sd17386831872000;

    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0;
    reg clear = 0;
    reg in_valid = 0;
    wire in_ready;
    reg in_first_group = 0;
    reg in_last_group = 0;
    reg in_tile_index = 0;
    reg signed [LANES*45-1:0] in_guard_s45 = '0;
    wire out_valid;
    reg out_ready = 0;
    wire out_tile_index;
    wire signed [LANES*32-1:0] out_projection_s32;
    wire [31:0] input_tile_count;
    wire [31:0] input_group_count;
    wire [31:0] output_tile_count;
    wire [31:0] saturation_count;
    wire accumulator_overflow;
    wire error;

    integer cycles = 0;
    integer received = 0;
    integer checks = 0;
    integer phase = 0;
    integer group_index;
    integer lane;
    reg held = 0;
    reg held_tile;
    reg signed [LANES*32-1:0] held_payload;
    reg saw_stall = 0;

    hap_mlp_down_group_major_accum_s54 #(
        .LANES(LANES), .TILES(TILES), .GROUPS(GROUPS), .TILE_W(1)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_first_group(in_first_group), .in_last_group(in_last_group),
        .in_tile_index(in_tile_index), .in_guard_s45(in_guard_s45),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_tile_index(out_tile_index), .out_projection_s32(out_projection_s32),
        .input_tile_count(input_tile_count),
        .input_group_count(input_group_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count),
        .accumulator_overflow(accumulator_overflow), .error(error)
    );

    task automatic send_group_tile;
        input first_group;
        input last_group;
        input tile_index;
        input signed [44:0] guard;
        integer index;
        begin
            @(negedge clk);
            in_first_group = first_group;
            in_last_group = last_group;
            in_tile_index = tile_index;
            for (index = 0; index < LANES; index = index + 1)
                in_guard_s45[index*45 +: 45] = guard;
            in_valid = 1;
            do @(posedge clk); while (!in_ready);
            @(negedge clk);
            in_valid = 0;
        end
    endtask

    task automatic wait_outputs;
        input integer expected_saturations;
        begin
            wait (received == TILES);
            repeat (5) @(posedge clk);
            if (input_tile_count !== GROUPS*TILES ||
                input_group_count !== GROUPS ||
                output_tile_count !== TILES ||
                saturation_count !== expected_saturations ||
                accumulator_overflow !== 1'b0 || error !== 1'b0)
                $fatal(1,
                    "S54 status phase=%0d in=%0d groups=%0d out=%0d sat=%0d overflow=%0d error=%0d",
                    phase, input_tile_count, input_group_count,
                    output_tile_count, saturation_count,
                    accumulator_overflow, error);
            checks = checks + 6;
        end
    endtask

    initial begin
        repeat (5) @(negedge clk);
        rst_n = 1;
        repeat (2) @(posedge clk);
        for (group_index = 0; group_index < GROUPS; group_index = group_index + 1) begin
            send_group_tile(group_index == 0, group_index == GROUPS-1,
                            0, group_index < 2 ? SHIFT12_GUARD : 45'sd0);
            send_group_tile(group_index == 0, group_index == GROUPS-1,
                            1, group_index < 2 ? -SHIFT12_GUARD : 45'sd0);
        end
        wait_outputs(0);
        if (saw_stall !== 1'b1)
            $fatal(1, "S54 backpressure was not exercised");

        @(negedge clk);
        clear = 1;
        @(negedge clk);
        clear = 0;
        phase = 1;
        received = 0;
        held = 0;
        for (group_index = 0; group_index < GROUPS; group_index = group_index + 1) begin
            send_group_tile(group_index == 0, group_index == GROUPS-1,
                            0, LEGAL_MAX_GUARD);
            send_group_tile(group_index == 0, group_index == GROUPS-1,
                            1, -LEGAL_MAX_GUARD);
        end
        wait_outputs(LANES*TILES);
        $display("checks=%0d shift12_raw=14438400 down_width=32 legal_extreme_terminal_saturation=16", checks);
        $display("HARDWARE_AGENT_SIM_PASS");
        $finish;
    end

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            cycles <= 0;
            held <= 0;
            out_ready <= 0;
        end else begin
            cycles <= cycles + 1;
            out_ready <= (cycles % 5) >= 2;
            if (held && (out_valid !== 1'b1 ||
                         out_tile_index !== held_tile ||
                         out_projection_s32 !== held_payload))
                $fatal(1, "S54 output changed under stall");
            held <= out_valid && !out_ready;
            if (out_valid && !out_ready) begin
                held_tile <= out_tile_index;
                held_payload <= out_projection_s32;
                saw_stall <= 1;
            end
            if (out_valid && out_ready) begin
                if (out_tile_index !== received[0])
                    $fatal(1, "S54 tile order got=%0d expected=%0d",
                        out_tile_index, received);
                for (lane = 0; lane < LANES; lane = lane + 1) begin
                    if (phase == 0) begin
                        if ($signed(out_projection_s32[lane*32 +: 32]) !==
                            (received == 0 ? 32'sd14438400 : -32'sd14438400))
                            $fatal(1, "S54 shift12 high-bit tile=%0d lane=%0d got=%0d",
                                received, lane,
                                $signed(out_projection_s32[lane*32 +: 32]));
                    end else if ($signed(out_projection_s32[lane*32 +: 32]) !==
                                 (received == 0 ? 32'sh7fffffff : 32'sh80000000))
                        $fatal(1, "S54 terminal saturation tile=%0d lane=%0d got=%0d",
                            received, lane,
                            $signed(out_projection_s32[lane*32 +: 32]));
                    checks = checks + 1;
                end
                received <= received + 1;
            end
            if (cycles > 100000)
                $fatal(1, "S54 timeout phase=%0d received=%0d", phase, received);
        end
    end
endmodule
