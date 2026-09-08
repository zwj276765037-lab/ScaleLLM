`timescale 1ns / 1ps

module hap_mlp_down_group_major_engine16_s45_tb;
    localparam integer GROUPS = 4;
    localparam integer TILES = 3;
    localparam integer TOTAL = GROUPS*TILES;
    localparam integer EXPECTED_SATURATION = 0;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire activation_valid;
    wire activation_ready;
    wire [4095:0] activation_u8x16x32;
    wire [383:0] activation_meta_u24x16;
    wire weight_valid;
    wire weight_ready;
    wire signed [2047:0] weights_s4x16x32;
    wire [223:0] weight_meta_u224;
    wire out_valid;
    reg out_ready = 1'b1;
    wire [1:0] out_tile_index;
    wire signed [6143:0] projection_s24x16x16;
    wire [31:0] activation_group_count;
    wire [31:0] weight_tile_count;
    wire [31:0] output_tile_count;
    wire [31:0] saturation_count;
    wire error;

    reg [4095:0] activation_mem [0:GROUPS-1];
    reg [383:0] activation_meta_mem [0:GROUPS-1];
    reg [2047:0] weights_mem [0:TOTAL-1];
    reg [223:0] weight_meta_mem [0:TOTAL-1];
    reg [6143:0] expected_mem [0:TILES-1];
    integer activation_index = 0;
    integer weight_index = 0;
    integer receive_index = 0;
    integer cycle_count = 0;
    integer mismatch_count = 0;
    integer accepted_while_output_stalled = 0;
    wire [1:0] activation_source = activation_index < GROUPS ?
        activation_index : GROUPS-1;
    wire [3:0] weight_source = weight_index < TOTAL ?
        weight_index : TOTAL-1;

    assign activation_valid = activation_index < GROUPS &&
        (cycle_count % 5) != 1;
    assign activation_u8x16x32 = activation_mem[activation_source];
    assign activation_meta_u24x16 = activation_meta_mem[activation_source];
    assign weight_valid = weight_index < TOTAL &&
        (cycle_count % 7) != 2;
    assign weights_s4x16x32 = weights_mem[weight_source];
    assign weight_meta_u224 = weight_meta_mem[weight_source];

    hap_mlp_down_group_major_engine16_s45 #(
        .TILES(TILES), .GROUPS(GROUPS)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .activation_valid(activation_valid),
        .activation_ready(activation_ready),
        .activation_u8x16x32(activation_u8x16x32),
        .activation_meta_u24x16(activation_meta_u24x16),
        .weight_valid(weight_valid), .weight_ready(weight_ready),
        .weights_s4x16x32(weights_s4x16x32),
        .weight_meta_u224(weight_meta_u224),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_tile_index(out_tile_index),
        .projection_s24x16x16(projection_s24x16x16),
        .activation_group_count(activation_group_count),
        .weight_tile_count(weight_tile_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count), .error(error)
    );

    initial begin
        $readmemh("data/mlp_down_group_major_engine16_s45/activation_u8x16x32.mem",
            activation_mem);
        $readmemh("data/mlp_down_group_major_engine16_s45/activation_meta_u24x16.mem",
            activation_meta_mem);
        $readmemh("data/mlp_down_group_major_engine16_s45/weights_s4x16x32.mem",
            weights_mem);
        $readmemh("data/mlp_down_group_major_engine16_s45/weight_meta_u224.mem",
            weight_meta_mem);
        $readmemh("data/mlp_down_group_major_engine16_s45/expected_s24x16x16.mem",
            expected_mem);
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            activation_index <= 0;
            weight_index <= 0;
            receive_index <= 0;
            cycle_count <= 0;
            mismatch_count <= 0;
            accepted_while_output_stalled <= 0;
            out_ready <= 1'b1;
        end else begin
            cycle_count <= cycle_count + 1;
            out_ready <= (cycle_count % 7) != 3 &&
                (cycle_count % 13) != 8;
            if (activation_valid && activation_ready)
                activation_index <= activation_index + 1;
            if (weight_valid && weight_ready) begin
                weight_index <= weight_index + 1;
                if (out_valid && !out_ready)
                    accepted_while_output_stalled <=
                        accepted_while_output_stalled + 1;
            end
            if (out_valid && out_ready) begin
                if (out_tile_index !== receive_index ||
                    projection_s24x16x16 !== expected_mem[receive_index]) begin
                    $display("MISMATCH cohort16 down engine tile=%0d got_tile=%0d",
                        receive_index, out_tile_index);
                    mismatch_count <= mismatch_count + 1;
                end
                receive_index <= receive_index + 1;
                if (receive_index + 1 == TILES) begin
                    if (mismatch_count == 0 && !error &&
                        activation_group_count == GROUPS &&
                        weight_tile_count == TOTAL &&
                        output_tile_count + 1 == TILES &&
                        saturation_count == EXPECTED_SATURATION) begin
                        $display("PASS: hap_mlp_down_group_major_engine16_s45 groups=%0d tiles=%0d transactions=%0d cycles=%0d mismatches=0 saturation=%0d",
                            GROUPS, TILES, TOTAL, cycle_count,
                            saturation_count);
                        $finish;
                    end else begin
                        $fatal(1,
                            "FAIL mismatch=%0d error=%0d activation=%0d weights=%0d output=%0d saturation=%0d",
                            mismatch_count, error, activation_group_count,
                            weight_tile_count, output_tile_count + 1,
                            saturation_count);
                    end
                end
            end
            if (cycle_count > 1000)
                $fatal(1,
                    "FAIL timeout activation=%0d weights=%0d output=%0d error=%0d",
                    activation_index, weight_index, receive_index, error);
        end
    end
endmodule
