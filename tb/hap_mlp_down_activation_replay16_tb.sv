`timescale 1ns / 1ps

module hap_mlp_down_activation_replay16_tb;
    localparam integer TILES = 4;
    localparam integer GROUPS = 3;
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
    wire [2047:0] weights_s4x16x32;
    wire [223:0] weight_meta_u224;
    wire out_valid;
    reg out_ready = 1'b1;
    wire out_first_group;
    wire out_last_group;
    wire [1:0] out_tile_index;
    wire signed [4607:0] out_activation_s9x16x32;
    wire [2047:0] out_weights_s4x16x32;
    wire [127:0] out_activation_code_u8x16;
    wire [95:0] out_activation_shift_u6x16;
    wire [127:0] out_weight_code_u8x16;
    wire [95:0] out_weight_shift_u6x16;
    wire [31:0] activation_group_count;
    wire [31:0] weight_tile_count;
    wire [31:0] completed_group_count;
    wire error;

    integer activation_index = 0;
    integer weight_index = 0;
    integer output_index = 0;
    integer cycle_count = 0;
    wire [4095:0] activation_payload;
    wire [383:0] activation_meta_payload;
    wire [2047:0] weight_payload;
    wire [223:0] weight_meta_payload;
    wire [1:0] expected_group = output_index / TILES;
    wire [1:0] expected_tile = output_index % TILES;

    assign activation_valid = activation_index < GROUPS &&
        cycle_count % 5 != 1;
    assign activation_u8x16x32 = activation_payload;
    assign activation_meta_u24x16 = activation_meta_payload;
    assign weight_valid = weight_index < GROUPS*TILES &&
        cycle_count % 7 != 2;
    assign weights_s4x16x32 = weight_payload;
    assign weight_meta_u224 = weight_meta_payload;

    assign weight_payload = {64{32'h5500_0000 + weight_index}};
    genvar stimulus_row;
    genvar stimulus_lane;
    generate
        for (stimulus_row = 0; stimulus_row < 16;
             stimulus_row = stimulus_row + 1) begin : gen_row_stimulus
            assign activation_meta_payload[stimulus_row*24 +: 8] =
                8'd100 + stimulus_row;
            assign activation_meta_payload[stimulus_row*24+8 +: 8] =
                8'd21 + stimulus_row;
            assign activation_meta_payload[stimulus_row*24+16 +: 6] =
                6'd13 + activation_index;
            assign activation_meta_payload[stimulus_row*24+22 +: 2] =
                2'b00;
            assign weight_meta_payload[stimulus_row*8 +: 8] =
                8'd31 + stimulus_row;
            assign weight_meta_payload[128+stimulus_row*6 +: 6] =
                6'd12 + stimulus_row%4;
            for (stimulus_lane = 0; stimulus_lane < 32;
                 stimulus_lane = stimulus_lane + 1) begin : gen_lane_stimulus
                assign activation_payload[
                    (stimulus_row*32+stimulus_lane)*8 +: 8] =
                    8'd100 + stimulus_row + stimulus_lane%5 +
                    activation_index;
            end
        end
    endgenerate

    hap_mlp_down_activation_replay16 #(
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
        .out_first_group(out_first_group),
        .out_last_group(out_last_group),
        .out_tile_index(out_tile_index),
        .out_activation_s9x16x32(out_activation_s9x16x32),
        .out_weights_s4x16x32(out_weights_s4x16x32),
        .out_activation_code_u8x16(out_activation_code_u8x16),
        .out_activation_shift_u6x16(out_activation_shift_u6x16),
        .out_weight_code_u8x16(out_weight_code_u8x16),
        .out_weight_shift_u6x16(out_weight_shift_u6x16),
        .activation_group_count(activation_group_count),
        .weight_tile_count(weight_tile_count),
        .completed_group_count(completed_group_count), .error(error)
    );

    initial begin
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            activation_index <= 0;
            weight_index <= 0;
            output_index <= 0;
            cycle_count <= 0;
            out_ready <= 1'b1;
        end else begin
            cycle_count <= cycle_count + 1;
            out_ready <= cycle_count % 9 != 4;
            if (activation_valid && activation_ready)
                activation_index <= activation_index + 1;
            if (weight_valid && weight_ready)
                weight_index <= weight_index + 1;
            if (out_valid && out_ready) begin
                if (out_tile_index !== expected_tile ||
                    out_first_group !== (expected_group == 0) ||
                    out_last_group !== (expected_group == GROUPS-1) ||
                    out_activation_s9x16x32[0 +: 9] !==
                        $signed(9'(expected_group)) ||
                    out_activation_s9x16x32[31*9 +: 9] !==
                        $signed(9'(1+expected_group)) ||
                    out_activation_code_u8x16[0 +: 8] !== 21 ||
                    out_activation_shift_u6x16[0 +: 6] !==
                        13+expected_group ||
                    out_weights_s4x16x32[31:0] !==
                        32'h5500_0000 + output_index ||
                    out_weight_code_u8x16[0 +: 8] !== 31 ||
                    out_weight_shift_u6x16[0 +: 6] !== 12)
                    $fatal(1, "FAIL output=%0d group=%0d tile=%0d got_tile=%0d first=%0d last=%0d a0=%0d a31=%0d acode=%0d ashift=%0d weight=%h wcode=%0d wshift=%0d",
                        output_index, expected_group, expected_tile,
                        out_tile_index, out_first_group, out_last_group,
                        $signed(out_activation_s9x16x32[0 +: 9]),
                        $signed(out_activation_s9x16x32[31*9 +: 9]),
                        out_activation_code_u8x16[0 +: 8],
                        out_activation_shift_u6x16[0 +: 6],
                        out_weights_s4x16x32[31:0],
                        out_weight_code_u8x16[0 +: 8],
                        out_weight_shift_u6x16[0 +: 6]);
                output_index <= output_index + 1;
                if (output_index + 1 == GROUPS*TILES) begin
                    if (!error && activation_group_count == GROUPS &&
                        weight_tile_count + 1 == GROUPS*TILES &&
                        completed_group_count + 1 == GROUPS) begin
                        $display("PASS: hap_mlp_down_activation_replay16 groups=%0d tiles=%0d transactions=%0d cycles=%0d",
                            GROUPS, TILES, GROUPS*TILES, cycle_count);
                        $finish;
                    end else begin
                        $fatal(1,
                            "FAIL error=%0d activations=%0d weights=%0d completed=%0d",
                            error, activation_group_count,
                            weight_tile_count + 1,
                            completed_group_count + 1);
                    end
                end
            end
            if (cycle_count > 300)
                $fatal(1, "FAIL timeout");
        end
    end
endmodule
