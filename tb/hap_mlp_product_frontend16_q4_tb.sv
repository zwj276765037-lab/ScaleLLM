`timescale 1ns / 1ps

module hap_mlp_product_frontend16_q4_tb;
    localparam integer GROUPS = 4;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire signed [16383:0] product_s32x16x32;
    wire out_valid;
    reg out_ready = 1'b1;
    wire [4095:0] activation_u8x16x32;
    wire [383:0] activation_meta_u24x16;
    wire [31:0] input_group_count;
    wire [31:0] output_group_count;
    wire [31:0] busy_cycle_count;
    wire error;

    reg [16383:0] product_mem [0:GROUPS-1];
    reg [4095:0] expected_u8_mem [0:GROUPS-1];
    reg [383:0] expected_meta_mem [0:GROUPS-1];
    integer send_index = 0;
    integer receive_index = 0;
    integer cycle_count = 0;
    integer mismatch_count = 0;
    integer group_start_cycle = 0;
    integer max_group_cycles = 0;
    integer observed_cycles = 0;
    wire [1:0] source_index = send_index < GROUPS ? send_index : GROUPS-1;

    assign in_valid = send_index < GROUPS;
    assign product_s32x16x32 = product_mem[source_index];

    hap_mlp_product_frontend16_q4 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .product_s32x16x32(product_s32x16x32),
        .out_valid(out_valid), .out_ready(out_ready),
        .activation_u8x16x32(activation_u8x16x32),
        .activation_meta_u24x16(activation_meta_u24x16),
        .input_group_count(input_group_count),
        .output_group_count(output_group_count),
        .busy_cycle_count(busy_cycle_count), .error(error)
    );

    initial begin
        $readmemh("data/mlp_product_frontend16_q4/product_s32x16x32.mem",
            product_mem);
        $readmemh("data/mlp_product_frontend16_q4/expected_u8x16x32.mem",
            expected_u8_mem);
        $readmemh("data/mlp_product_frontend16_q4/expected_meta_u24x16.mem",
            expected_meta_mem);
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
            group_start_cycle <= 0;
            max_group_cycles <= 0;
        end else begin
            cycle_count <= cycle_count + 1;
            out_ready <= ((cycle_count % 7) != 3 &&
                          (cycle_count % 11) != 5);
            if (in_valid && in_ready) begin
                send_index <= send_index + 1;
                group_start_cycle <= cycle_count;
            end
            if (out_valid && out_ready) begin
                observed_cycles = cycle_count-group_start_cycle;
                if (observed_cycles > max_group_cycles)
                    max_group_cycles <= observed_cycles;
                if (activation_u8x16x32 !== expected_u8_mem[receive_index] ||
                    activation_meta_u24x16 !==
                    expected_meta_mem[receive_index]) begin
                    $display("MISMATCH group=%0d", receive_index);
                    mismatch_count <= mismatch_count + 1;
                end
                receive_index <= receive_index + 1;
                if (receive_index + 1 == GROUPS) begin
                    if (mismatch_count == 0 && !error &&
                        input_group_count == GROUPS &&
                        output_group_count + 1 == GROUPS &&
                        observed_cycles <= 900) begin
                        $display("PASS: hap_mlp_product_frontend16_q4 groups=%0d cycles=%0d max_group_cycles=%0d mismatches=0",
                            GROUPS, cycle_count,
                            observed_cycles > max_group_cycles ?
                            observed_cycles : max_group_cycles);
                        $finish;
                    end else begin
                        $fatal(1,
                            "FAIL: mismatch=%0d error=%0d in=%0d out=%0d group_cycles=%0d busy=%0d",
                            mismatch_count, error, input_group_count,
                            output_group_count + 1, observed_cycles,
                            busy_cycle_count);
                    end
                end
            end
            if (cycle_count > 5000)
                $fatal(1, "FAIL: timeout send=%0d receive=%0d error=%0d",
                    send_index, receive_index, error);
        end
    end
endmodule
