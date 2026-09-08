`timescale 1ns / 1ps

module hap_mlp_down_group_major_slice8x16_s45_tb;
    localparam integer GROUPS = 4;
    localparam integer TILES = 3;
    localparam integer TOTAL = GROUPS*TILES;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire signed [2303:0] activation_s9x8x32;
    wire signed [2047:0] weights_s4x16x32;
    wire [63:0] activation_code_u8x8;
    wire [47:0] activation_shift_u6x8;
    wire [127:0] weight_code_u8x16;
    wire [95:0] weight_shift_u6x16;
    wire out_valid;
    reg out_ready = 1'b1;
    wire [1:0] out_tile_index;
    wire signed [3071:0] projection_s24x8x16;
    wire [31:0] input_tile_count;
    wire [31:0] input_group_count;
    wire [31:0] output_tile_count;
    wire [31:0] saturation_count;
    wire error;

    reg [2303:0] activation_mem [0:TOTAL-1];
    reg [2047:0] weights_mem [0:TOTAL-1];
    reg [111:0] activation_meta_mem [0:TOTAL-1];
    reg [223:0] weight_meta_mem [0:TOTAL-1];
    reg [3071:0] expected_mem [0:TILES-1];
    integer send_index = 0;
    integer receive_index = 0;
    integer cycle_count = 0;
    integer last_accept_cycle = -1;
    integer max_interval = 0;
    integer mismatch_count = 0;
    wire [3:0] source_index = send_index < TOTAL ? send_index : TOTAL-1;
    wire [1:0] source_tile = source_index % TILES;
    wire [1:0] source_group = source_index / TILES;

    assign in_valid = send_index < TOTAL;
    assign activation_s9x8x32 = activation_mem[source_index];
    assign weights_s4x16x32 = weights_mem[source_index];
    assign activation_code_u8x8 = activation_meta_mem[source_index][63:0];
    assign activation_shift_u6x8 = activation_meta_mem[source_index][111:64];
    assign weight_code_u8x16 = weight_meta_mem[source_index][127:0];
    assign weight_shift_u6x16 = weight_meta_mem[source_index][223:128];

    hap_mlp_down_group_major_slice8x16_s45 #(
        .TILES(TILES), .GROUPS(GROUPS)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_first_group(source_group == 0),
        .in_last_group(source_group == GROUPS-1),
        .in_tile_index(source_tile),
        .activation_s9x8x32(activation_s9x8x32),
        .weights_s4x16x32(weights_s4x16x32),
        .activation_code_u8x8(activation_code_u8x8),
        .activation_shift_u6x8(activation_shift_u6x8),
        .weight_code_u8x16(weight_code_u8x16),
        .weight_shift_u6x16(weight_shift_u6x16),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_tile_index(out_tile_index),
        .projection_s24x8x16(projection_s24x8x16),
        .input_tile_count(input_tile_count),
        .input_group_count(input_group_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count), .error(error)
    );

    initial begin
        $readmemh("data/mlp_down_group_major_slice_s45/activation_s9x8x32.mem",
            activation_mem);
        $readmemh("data/mlp_down_group_major_slice_s45/weights_s4x16x32.mem",
            weights_mem);
        $readmemh("data/mlp_down_group_major_slice_s45/activation_meta_u112.mem",
            activation_meta_mem);
        $readmemh("data/mlp_down_group_major_slice_s45/weight_meta_u224.mem",
            weight_meta_mem);
        $readmemh("data/mlp_down_group_major_slice_s45/expected_s24x8x16.mem",
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
            last_accept_cycle <= -1;
            max_interval <= 0;
            mismatch_count <= 0;
        end else begin
            cycle_count <= cycle_count + 1;
            out_ready <= (cycle_count % 7) != 3 &&
                (cycle_count % 13) != 8;
            if (in_valid && in_ready) begin
                if (last_accept_cycle >= 0 &&
                    cycle_count-last_accept_cycle > max_interval)
                    max_interval <= cycle_count-last_accept_cycle;
                last_accept_cycle <= cycle_count;
                send_index <= send_index + 1;
            end
            if (out_valid && out_ready) begin
                if (out_tile_index !== receive_index ||
                    projection_s24x8x16 !== expected_mem[receive_index]) begin
                    $display("MISMATCH down group-major tile=%0d",
                        receive_index);
                    mismatch_count <= mismatch_count + 1;
                end
                receive_index <= receive_index + 1;
                if (receive_index + 1 == TILES) begin
                    if (mismatch_count == 0 && !error &&
                        input_tile_count == TOTAL &&
                        input_group_count == GROUPS &&
                        output_tile_count + 1 == TILES &&
                        saturation_count == 0 && max_interval <= 1) begin
                        $display("PASS: hap_mlp_down_group_major_slice8x16_s45 groups=%0d tiles=%0d cycles=%0d II=%0d mismatches=0",
                            GROUPS, TILES, cycle_count, max_interval);
                        $finish;
                    end else begin
                        $fatal(1,
                            "FAIL mismatch=%0d error=%0d in=%0d groups=%0d out=%0d sat=%0d II=%0d",
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
