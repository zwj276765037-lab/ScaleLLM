`timescale 1ns / 1ps

module hap_mlp_down_group_major_accum_s45_tb;
    localparam integer GROUPS = 5;
    localparam integer TILES = 8;
`ifdef HAP_V5_96_LANES
    localparam integer LANES = 96;
    localparam DATA_DIR = "data/mlp_down_group_major_accum_s45_v5_96";
`else
    localparam integer LANES = 128;
    localparam DATA_DIR = "data/mlp_down_group_major_accum_s45";
`endif
    localparam integer TOTAL = GROUPS*TILES;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire in_first_group;
    wire in_last_group;
    wire [2:0] in_tile_index;
    wire signed [LANES*36-1:0] in_guard_s36;
    wire out_valid;
    reg out_ready = 1'b1;
    wire [2:0] out_tile_index;
    wire signed [LANES*24-1:0] out_projection_s24;
    wire [31:0] input_tile_count;
    wire [31:0] input_group_count;
    wire [31:0] output_tile_count;
    wire [31:0] saturation_count;
    wire error;

    reg [LANES*36-1:0] guard_mem [0:TOTAL-1];
    reg [LANES*24-1:0] expected_mem [0:TILES-1];
    reg [31:0] expected_saturation_mem [0:0];
    integer send_index = 0;
    integer receive_index = 0;
    integer cycle_count = 0;
    integer mismatch_count = 0;
    integer last_accept_cycle = -1;
    integer max_interval = 0;
    wire [5:0] source_index = send_index < TOTAL ? send_index : TOTAL-1;
    wire [2:0] source_tile = source_index % TILES;
    wire [2:0] source_group = source_index / TILES;

    assign in_valid = send_index < TOTAL;
    assign in_first_group = source_group == 0;
    assign in_last_group = source_group == GROUPS-1;
    assign in_tile_index = source_tile;
    assign in_guard_s36 = guard_mem[source_index];

    hap_mlp_down_group_major_accum_s45 #(
        .LANES(LANES), .TILES(TILES), .GROUPS(GROUPS)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_first_group(in_first_group),
        .in_last_group(in_last_group),
        .in_tile_index(in_tile_index), .in_guard_s36(in_guard_s36),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_tile_index(out_tile_index),
        .out_projection_s24(out_projection_s24),
        .input_tile_count(input_tile_count),
        .input_group_count(input_group_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count), .error(error)
    );

    initial begin
        $readmemh({DATA_DIR, "/guard_s36x8.mem"},
            guard_mem);
        $readmemh({DATA_DIR, "/expected_s24x8.mem"},
            expected_mem);
        $readmemh({DATA_DIR, "/expected_saturation.mem"},
            expected_saturation_mem);
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
            max_interval <= 0;
        end else begin
            cycle_count <= cycle_count + 1;
            out_ready <= (cycle_count % 7) != 3 &&
                (cycle_count % 11) != 5;
            if (in_valid && in_ready) begin
                if (last_accept_cycle >= 0 && source_group != GROUPS-1 &&
                    cycle_count-last_accept_cycle > max_interval)
                    max_interval <= cycle_count-last_accept_cycle;
                last_accept_cycle <= cycle_count;
                send_index <= send_index + 1;
            end
            if (out_valid && out_ready) begin
                if (out_tile_index !== receive_index ||
                    out_projection_s24 !== expected_mem[receive_index]) begin
                    $display("MISMATCH output tile=%0d expected=%0d",
                        out_tile_index, receive_index);
                    mismatch_count <= mismatch_count + 1;
                end
                receive_index <= receive_index + 1;
                if (receive_index + 1 == TILES) begin
                    if (mismatch_count == 0 && !error &&
                        input_tile_count == TOTAL &&
                        input_group_count == GROUPS &&
                        output_tile_count + 1 == TILES &&
                        saturation_count == expected_saturation_mem[0] &&
                        max_interval <= 1) begin
                        $display("PASS: hap_mlp_down_group_major_accum_s45 groups=%0d tiles=%0d lanes=%0d cycles=%0d saturation=%0d II=%0d mismatches=0",
                            GROUPS, TILES, LANES, cycle_count,
                            saturation_count, max_interval);
                        $finish;
                    end else begin
                        $fatal(1,
                            "FAIL mismatch=%0d error=%0d in_tiles=%0d groups=%0d out=%0d sat=%0d II=%0d",
                            mismatch_count, error, input_tile_count,
                            input_group_count, output_tile_count + 1,
                            saturation_count, max_interval);
                    end
                end
            end
            if (cycle_count > 500)
                $fatal(1, "FAIL timeout sent=%0d received=%0d error=%0d",
                    send_index, receive_index, error);
        end
    end
endmodule
