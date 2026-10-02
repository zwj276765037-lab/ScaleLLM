`timescale 1ns / 1ps

module m12_down_group_major_tb #(
    parameter integer CASE_ID = 0,
    parameter string DATA_DIR = "data"
);
    localparam integer GROUPS = 448;
    localparam integer TILES = 342;
    localparam integer TRANSACTIONS = GROUPS*TILES;

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire in_first_group;
    wire in_last_group;
    wire [8:0] in_tile_index;
    wire signed [16*32*9-1:0] activation_s9x16x32;
    wire signed [12*32*4-1:0] weights_s4x12x32;
    wire [127:0] activation_code_u8x16;
    wire [95:0] activation_shift_u6x16;
    wire [95:0] weight_code_u8x12;
    wire [71:0] weight_shift_u6x12;
    wire [255:0] activation_scale_fp16x16;
    wire [191:0] weight_scale_fp16x12;
    wire [511:0] activation_scale_fp32x16;
    wire [383:0] weight_scale_fp32x12;
    wire [11:0] column_valid_u12;
    wire out_valid;
    reg out_ready = 1'b1;
    wire [8:0] out_tile_index;
    wire signed [16*12*24-1:0] projection_s24x16x12;
    wire [31:0] input_transaction_count;
    wire [31:0] input_group_count;
    wire [31:0] output_tile_count;
    wire [31:0] saturation_count;
    wire error;

    reg [4607:0] activation_mem [0:GROUPS-1];
    reg [223:0] activation_sc_mem [0:GROUPS-1];
    reg [255:0] activation_fp16_mem [0:GROUPS-1];
    reg [511:0] activation_fp32_mem [0:GROUPS-1];
    reg [1535:0] weight_mem [0:TRANSACTIONS-1];
    reg [167:0] weight_sc_mem [0:TRANSACTIONS-1];
    reg [191:0] weight_fp16_mem [0:TRANSACTIONS-1];
    reg [383:0] weight_fp32_mem [0:TRANSACTIONS-1];
    reg [11:0] mask_mem [0:TILES-1];
    reg [4607:0] expected_sc [0:TILES-1];
    reg [4607:0] expected_fp16 [0:TILES-1];
    reg [4607:0] expected_fp32 [0:TILES-1];

    integer send_index = 0;
    integer receive_index = 0;
    integer cycle = 0;
    integer mismatch_count = 0;
    integer first_input_cycle = -1;
    integer last_input_cycle = -1;
    integer first_output_cycle = -1;
    integer final_cycle = -1;
    integer last_accept_cycle = -1;
    integer max_input_interval = 0;
    wire [31:0] bounded_index = send_index < TRANSACTIONS ?
        send_index : TRANSACTIONS-1;
    wire [8:0] source_tile = bounded_index % TILES;
    wire [8:0] source_group = bounded_index / TILES;

    assign in_valid = send_index < TRANSACTIONS;
    assign in_first_group = source_group == 0;
    assign in_last_group = source_group == GROUPS-1;
    assign in_tile_index = source_tile;
    assign activation_s9x16x32 = activation_mem[source_group];
    assign weights_s4x12x32 = weight_mem[bounded_index];
    assign activation_code_u8x16 = activation_sc_mem[source_group][127:0];
    assign activation_shift_u6x16 = activation_sc_mem[source_group][223:128];
    assign weight_code_u8x12 = weight_sc_mem[bounded_index][95:0];
    assign weight_shift_u6x12 = weight_sc_mem[bounded_index][167:96];
    assign activation_scale_fp16x16 = activation_fp16_mem[source_group];
    assign weight_scale_fp16x12 = weight_fp16_mem[bounded_index];
    assign activation_scale_fp32x16 = activation_fp32_mem[source_group];
    assign weight_scale_fp32x12 = weight_fp32_mem[bounded_index];
    assign column_valid_u12 = mask_mem[source_tile];

    generate
        if (CASE_ID == 0) begin : g_sc
            m12_sc_down_group_major dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_group(in_first_group),
                .in_last_group(in_last_group),
                .in_tile_index(in_tile_index),
                .activation_s9x16x32(activation_s9x16x32),
                .weights_s4x12x32(weights_s4x12x32),
                .activation_code_u8x16(activation_code_u8x16),
                .activation_shift_u6x16(activation_shift_u6x16),
                .weight_code_u8x12(weight_code_u8x12),
                .weight_shift_u6x12(weight_shift_u6x12),
                .column_valid_u12(column_valid_u12),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_tile_index(out_tile_index),
                .projection_s24x16x12(projection_s24x16x12),
                .input_transaction_count(input_transaction_count),
                .input_group_count(input_group_count),
                .output_tile_count(output_tile_count),
                .saturation_count(saturation_count), .error(error));
        end else if (CASE_ID == 1) begin : g_fp16
            assign saturation_count = 32'd0;
            m12_fp16_down_group_major dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_group(in_first_group),
                .in_last_group(in_last_group),
                .in_tile_index(in_tile_index),
                .activation_s9x16x32(activation_s9x16x32),
                .weights_s4x12x32(weights_s4x12x32),
                .activation_scale_fpx16(activation_scale_fp16x16),
                .weight_scale_fpx12(weight_scale_fp16x12),
                .column_valid_u12(column_valid_u12),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_tile_index(out_tile_index),
                .projection_s24x16x12(projection_s24x16x12),
                .input_transaction_count(input_transaction_count),
                .input_group_count(input_group_count),
                .output_tile_count(output_tile_count), .error(error));
        end else begin : g_fp32
            assign saturation_count = 32'd0;
            m12_fp32_down_group_major dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_group(in_first_group),
                .in_last_group(in_last_group),
                .in_tile_index(in_tile_index),
                .activation_s9x16x32(activation_s9x16x32),
                .weights_s4x12x32(weights_s4x12x32),
                .activation_scale_fpx16(activation_scale_fp32x16),
                .weight_scale_fpx12(weight_scale_fp32x12),
                .column_valid_u12(column_valid_u12),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_tile_index(out_tile_index),
                .projection_s24x16x12(projection_s24x16x12),
                .input_transaction_count(input_transaction_count),
                .input_group_count(input_group_count),
                .output_tile_count(output_tile_count), .error(error));
        end
    endgenerate

    function automatic [4607:0] expected_for_case;
        input integer index;
        begin
            case (CASE_ID)
                0: expected_for_case = expected_sc[index];
                1: expected_for_case = expected_fp16[index];
                default: expected_for_case = expected_fp32[index];
            endcase
        end
    endfunction

    initial begin
        $readmemh({DATA_DIR,"/activation_s9x16x32.mem"}, activation_mem);
        $readmemh({DATA_DIR,"/weights_s4x12x32.mem"}, weight_mem);
        $readmemh({DATA_DIR,"/column_mask_u12.mem"}, mask_mem);
        case (CASE_ID)
            0: begin
                $readmemh({DATA_DIR,"/activation_meta_sc_u224.mem"},
                    activation_sc_mem);
                $readmemh({DATA_DIR,"/weight_meta_sc_u168.mem"},
                    weight_sc_mem);
                $readmemh({DATA_DIR,"/expected_sc_s24x16x12.mem"},
                    expected_sc);
            end
            1: begin
                $readmemh({DATA_DIR,"/activation_scale_fp16x16.mem"},
                    activation_fp16_mem);
                $readmemh({DATA_DIR,"/weight_scale_fp16x12.mem"},
                    weight_fp16_mem);
                $readmemh({DATA_DIR,"/expected_fp16_s24x16x12.mem"},
                    expected_fp16);
            end
            default: begin
                $readmemh({DATA_DIR,"/activation_scale_fp32x16.mem"},
                    activation_fp32_mem);
                $readmemh({DATA_DIR,"/weight_scale_fp32x12.mem"},
                    weight_fp32_mem);
                $readmemh({DATA_DIR,"/expected_fp32_s24x16x12.mem"},
                    expected_fp32);
            end
        endcase
        repeat (10) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            send_index <= 0;
            receive_index <= 0;
            cycle <= 0;
            mismatch_count <= 0;
            first_input_cycle <= -1;
            last_input_cycle <= -1;
            first_output_cycle <= -1;
            final_cycle <= -1;
            last_accept_cycle <= -1;
            max_input_interval <= 0;
        end else begin
            cycle <= cycle + 1;
            if (error) begin
                $display("FAIL: M12 sticky error case=%0d cycle=%0d sent=%0d received=%0d",
                    CASE_ID, cycle, send_index, receive_index);
                $finish;
            end
            if (in_valid && in_ready) begin
                if (first_input_cycle < 0)
                    first_input_cycle <= cycle;
                if (last_accept_cycle >= 0 &&
                    cycle-last_accept_cycle > max_input_interval)
                    max_input_interval <= cycle-last_accept_cycle;
                last_accept_cycle <= cycle;
                if (send_index == TRANSACTIONS-1)
                    last_input_cycle <= cycle;
                send_index <= send_index + 1;
            end
            if (out_valid && out_ready) begin
                if (first_output_cycle < 0)
                    first_output_cycle <= cycle;
                if (out_tile_index !== receive_index[8:0] ||
                    projection_s24x16x12 !==
                        expected_for_case(receive_index)) begin
                    $display("MISMATCH: M12 case=%0d expected_tile=%0d got_tile=%0d",
                        CASE_ID, receive_index, out_tile_index);
                    mismatch_count <= mismatch_count + 1;
                end
                receive_index <= receive_index + 1;
                if (receive_index + 1 == TILES) begin
                    final_cycle <= cycle;
                    if (mismatch_count == 0 &&
                        out_tile_index === receive_index[8:0] &&
                        projection_s24x16x12 ===
                            expected_for_case(receive_index) &&
                        input_transaction_count == TRANSACTIONS &&
                        input_group_count == GROUPS &&
                        output_tile_count + 1 == TILES &&
                        max_input_interval <= 1) begin
                        $display("M12_METRIC_JSON: {\"case_id\":%0d,\"groups\":448,\"tiles\":342,\"transactions\":153216,\"valid_outputs\":65536,\"mismatches\":0,\"first_output_latency\":%0d,\"input_ii_max\":%0d,\"total_cycles\":%0d,\"saturation_count\":%0d}",
                            CASE_ID, first_output_cycle-first_input_cycle,
                            max_input_interval,
                            cycle-first_input_cycle+1, saturation_count);
                        $display("PASS: M12 full Down group-major case=%0d",
                            CASE_ID);
                        $finish;
                    end else begin
                        $display("FAIL: M12 final gate case=%0d mismatch=%0d tx=%0d groups=%0d outputs=%0d ii=%0d",
                            CASE_ID, mismatch_count,
                            input_transaction_count, input_group_count,
                            output_tile_count+1, max_input_interval);
                        $finish;
                    end
                end
            end
            if (cycle > 1000000) begin
                $display("FAIL: M12 timeout case=%0d sent=%0d received=%0d",
                    CASE_ID, send_index, receive_index);
                $finish;
            end
        end
    end
endmodule
