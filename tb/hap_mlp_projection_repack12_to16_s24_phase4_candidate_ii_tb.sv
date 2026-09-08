`timescale 1ns / 1ps

module hap_mlp_projection_repack12_to16_s24_phase4_candidate_ii_tb;
    localparam integer ROWS = 16;
    localparam integer IN_W = ROWS*12*24;
    localparam integer OUT_W = ROWS*16*24;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    wire in_ready;
    reg signed [IN_W-1:0] in_payload = '0;
    reg [8:0] in_tag = '0;
    reg [1:0] in_pass = '0;
    reg in_matrix = 1'b0;
    reg [11:0] in_mask = 12'hfff;
    reg in_last = 1'b0;
    wire out_valid;
    reg out_ready = 1'b1;
    wire signed [OUT_W-1:0] out_payload;
    wire [8:0] out_tag;
    wire [1:0] out_record;
    wire out_matrix;
    wire [15:0] out_mask;
    wire out_last;
    wire [31:0] input_count;
    wire [31:0] output_count;
    wire error;

    integer cycle_count = 0;
    integer input_fires = 0;
    integer output_fires = 0;
    integer last_input_cycle = -1;
    integer last_output_cycle = -1;
    integer consecutive_inputs = 0;
    integer consecutive_outputs = 0;
    integer row_index;
    integer lane_index;

    always #3.333 clk = ~clk;
    always @(posedge clk) cycle_count <= cycle_count + 1;

    hap_mlp_projection_repack12_to16_s24_phase4_candidate #(
        .ROWS(ROWS), .MATRICES(2), .TAG_W(9), .MATRIX_W(1)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_projection_s24xrowsx12(in_payload),
        .in_block_tag(in_tag), .in_pass_index(in_pass),
        .in_matrix(in_matrix), .in_col_valid_u12(in_mask),
        .in_last_pass(in_last), .out_valid(out_valid),
        .out_ready(out_ready),
        .out_projection_s24xrowsx16(out_payload),
        .out_block_tag(out_tag), .out_record_index(out_record),
        .out_matrix(out_matrix), .out_col_valid_u16(out_mask),
        .out_last_record(out_last), .input_pass_count(input_count),
        .output_record_count(output_count), .error(error)
    );

    always @(posedge clk) begin
        if (rst_n && in_valid && in_ready) begin
            if (last_input_cycle >= 0) begin
                if (cycle_count != last_input_cycle + 1)
                    $fatal(1, "input II regression cycle=%0d previous=%0d",
                           cycle_count, last_input_cycle);
                consecutive_inputs = consecutive_inputs + 1;
            end
            last_input_cycle = cycle_count;
            input_fires = input_fires + 1;
        end
        if (rst_n && out_valid && out_ready) begin
            if (last_output_cycle >= 0) begin
                if (cycle_count != last_output_cycle + 1)
                    $fatal(1, "output II regression cycle=%0d previous=%0d",
                           cycle_count, last_output_cycle);
                consecutive_outputs = consecutive_outputs + 1;
            end
            last_output_cycle = cycle_count;
            output_fires = output_fires + 1;
        end
    end

    task automatic drive_record;
        input integer pass_value;
        input integer matrix_value;
        begin
            @(negedge clk);
            in_valid = 1'b1;
            in_tag = 9'h12a;
            in_pass = pass_value[1:0];
            in_matrix = matrix_value[0:0];
            in_last = (pass_value == 3);
            for (row_index = 0; row_index < ROWS;
                 row_index = row_index + 1)
                for (lane_index = 0; lane_index < 12;
                     lane_index = lane_index + 1)
                    in_payload[(row_index*12+lane_index)*24 +: 24] =
                        {pass_value[1:0], matrix_value[0:0],
                         row_index[3:0], lane_index[3:0], 13'h155};
        end
    endtask

    integer pass_index;
    integer matrix_index;
    initial begin
        repeat (8) @(posedge clk);
        rst_n = 1'b1;
        // Eight gate/up records are presented on eight consecutive cycles.
        // Once asserted for the first record, valid remains high throughout.
        for (pass_index = 0; pass_index < 4; pass_index = pass_index + 1)
            for (matrix_index = 0; matrix_index < 2;
                 matrix_index = matrix_index + 1)
                drive_record(pass_index, matrix_index);
        @(negedge clk);
        in_valid = 1'b0;

        wait (output_fires == 6);
        repeat (3) @(posedge clk);
        if (input_fires != 8 || consecutive_inputs != 7 ||
            output_fires != 6 || consecutive_outputs != 5 || error ||
            input_count != 8 || output_count != 6)
            $fatal(1, "II/count failure in=%0d cin=%0d out=%0d cout=%0d err=%0d counters=%0d/%0d",
                   input_fires, consecutive_inputs, output_fires,
                   consecutive_outputs, error, input_count, output_count);
        $display("PASS: phase4 candidate 8 consecutive gate/up input records and 6 consecutive output records, II=1");
        $finish;
    end

    initial begin
        #1000000;
        $fatal(1, "phase4 II test timeout");
    end
endmodule
