`timescale 1ns / 1ps

module hap_mlp_tile_accum_s45_tb;
    localparam integer TILES = 2;
    localparam integer GROUPS = 448;
    localparam integer TOTAL_GROUPS = TILES*GROUPS;
    localparam integer EXPECTED_SATURATION = 191;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire in_first_group;
    wire in_last_group;
    wire signed [4607:0] in_guard_s36;
    wire out_valid;
    reg out_ready = 1'b1;
    wire signed [3071:0] out_projection_s24;
    wire [31:0] input_group_count;
    wire [31:0] output_tile_count;
    wire [31:0] saturation_count;
    wire error;

    reg [4607:0] guard_mem [0:TOTAL_GROUPS-1];
    reg [3071:0] expected_mem [0:TILES-1];
    integer send_index = 0;
    integer receive_index = 0;
    integer cycle_count = 0;
    integer mismatch_count = 0;
    integer last_accept_cycle = -1;
    integer within_tile_interval_max = 0;
    integer finish_countdown = -1;
    wire [9:0] source_index = send_index < TOTAL_GROUPS ? send_index :
        TOTAL_GROUPS-1;

    assign in_valid = send_index < TOTAL_GROUPS;
    assign in_guard_s36 = guard_mem[source_index];
    assign in_first_group = (send_index % GROUPS) == 0;
    assign in_last_group = (send_index % GROUPS) == GROUPS-1;

    hap_mlp_tile_accum_s36 #(
        .LANES(128), .ACC_W(45), .GROUPS(448)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_first_group(in_first_group), .in_last_group(in_last_group),
        .in_guard_s36(in_guard_s36),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_projection_s24(out_projection_s24),
        .input_group_count(input_group_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count), .error(error)
    );

    initial begin
        $readmemh("data/mlp_tile_accum_s45/guard_s36x128.mem",
            guard_mem);
        $readmemh("data/mlp_tile_accum_s45/expected_s24x128.mem",
            expected_mem);
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            out_ready <= 1'b1;
            send_index <= 0;
            receive_index <= 0;
            cycle_count <= 0;
            mismatch_count <= 0;
            last_accept_cycle <= -1;
            within_tile_interval_max <= 0;
            finish_countdown <= -1;
        end else begin
            cycle_count <= cycle_count + 1;
            out_ready <= ((cycle_count % 7) != 3 &&
                          (cycle_count % 13) != 8);
            if (in_valid && in_ready) begin
                send_index <= send_index + 1;
                if ((send_index % GROUPS) != 0 &&
                    last_accept_cycle >= 0 &&
                    cycle_count-last_accept_cycle >
                    within_tile_interval_max)
                    within_tile_interval_max <=
                        cycle_count-last_accept_cycle;
                last_accept_cycle <= cycle_count;
            end
            if (out_valid && out_ready) begin
                if (out_projection_s24 !== expected_mem[receive_index]) begin
                    $display("MISMATCH tile=%0d", receive_index);
                    mismatch_count <= mismatch_count + 1;
                end
                receive_index <= receive_index + 1;
                if (receive_index + 1 == TILES)
                    finish_countdown <= 8;
            end
            if (finish_countdown >= 0) begin
                finish_countdown <= finish_countdown - 1;
                if (finish_countdown == 0) begin
                    if (mismatch_count == 0 && !error &&
                        within_tile_interval_max <= 1 &&
                        input_group_count == TOTAL_GROUPS &&
                        output_tile_count == TILES &&
                        saturation_count == EXPECTED_SATURATION) begin
                        $display("PASS: hap_mlp_tile_accum_s45 tiles=%0d groups=%0d cycles=%0d mismatches=0 within_tile_ii=%0d saturation_count=%0d",
                            TILES, GROUPS, cycle_count,
                            within_tile_interval_max, saturation_count);
                        $finish;
                    end else begin
                        $fatal(1,
                            "FAIL: mismatch=%0d error=%0d ii=%0d in=%0d out=%0d sat=%0d",
                            mismatch_count, error,
                            within_tile_interval_max,
                            input_group_count, output_tile_count,
                            saturation_count);
                    end
                end
            end
            if (cycle_count > 3000)
                $fatal(1, "FAIL: timeout send=%0d receive=%0d error=%0d",
                    send_index, receive_index, error);
        end
    end
endmodule
