`timescale 1ns / 1ps

module hap_a8w4_group32_pack2_s17_tb;
    localparam integer VECTOR_COUNT = 2048;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire signed [287:0] activation_s9x32;
    wire signed [127:0] weight0_s4x32;
    wire signed [127:0] weight1_s4x32;
    wire out_valid;
    reg out_ready = 1'b1;
    wire signed [16:0] dot0_s17;
    wire signed [16:0] dot1_s17;

    reg [287:0] activation_mem [0:VECTOR_COUNT-1];
    reg [255:0] weights_mem [0:VECTOR_COUNT-1];
    reg [33:0] expected_mem [0:VECTOR_COUNT-1];
    reg [127:0] weight0_comb;
    reg [127:0] weight1_comb;
    integer lane;
    integer send_index = 0;
    integer receive_index = 0;
    integer cycle_count = 0;
    integer mismatch_count = 0;
    integer last_accept_cycle = -1;
    integer unstalled_accept_interval_max = 0;
    reg stalled_last_cycle = 1'b0;
    reg [33:0] stalled_data_r;
    wire [10:0] source_index = send_index < VECTOR_COUNT ? send_index :
        VECTOR_COUNT-1;

    assign in_valid = send_index < VECTOR_COUNT;
    assign activation_s9x32 = activation_mem[source_index];
    assign weight0_s4x32 = weight0_comb;
    assign weight1_s4x32 = weight1_comb;

    always @* begin
        weight0_comb = '0;
        weight1_comb = '0;
        for (lane = 0; lane < 32; lane = lane + 1) begin
            weight0_comb[lane*4 +: 4] = weights_mem[source_index][lane*8 +: 4];
            weight1_comb[lane*4 +: 4] = weights_mem[source_index][lane*8+4 +: 4];
        end
    end

    hap_a8w4_group32_pack2_s17 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .activation_s9x32(activation_s9x32),
        .weight0_s4x32(weight0_s4x32),
        .weight1_s4x32(weight1_s4x32),
        .out_valid(out_valid), .out_ready(out_ready),
        .dot0_s17(dot0_s17), .dot1_s17(dot1_s17)
    );

    initial begin
        $readmemh("data/a8w4_group32_pack2/activation_s9x32.mem",
            activation_mem);
        $readmemh("data/a8w4_group32_pack2/weights_s4x64.mem", weights_mem);
        $readmemh("data/a8w4_group32_pack2/expected_s17x2.mem", expected_mem);
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
            unstalled_accept_interval_max <= 0;
            stalled_last_cycle <= 1'b0;
        end else begin
            cycle_count <= cycle_count + 1;
            out_ready <= (receive_index < 1024) ? 1'b1 :
                ((cycle_count % 13) != 4 && (cycle_count % 19) != 8);
            if (in_valid && in_ready) begin
                send_index <= send_index + 1;
                if (send_index < 1024 && last_accept_cycle >= 0 &&
                    cycle_count-last_accept_cycle >
                    unstalled_accept_interval_max)
                    unstalled_accept_interval_max <=
                        cycle_count-last_accept_cycle;
                last_accept_cycle <= cycle_count;
            end
            if (out_valid && out_ready) begin
                if ({dot1_s17, dot0_s17} !== expected_mem[receive_index]) begin
                    $fatal(1, "MISMATCH index=%0d got=%h_%h expected=%h",
                        receive_index, dot1_s17, dot0_s17,
                        expected_mem[receive_index]);
                end
                receive_index <= receive_index + 1;
                if (receive_index + 1 == VECTOR_COUNT) begin
                    if (mismatch_count == 0 &&
                        unstalled_accept_interval_max <= 1) begin
                        $display("PASS: hap_a8w4_group32_pack2_s17 vectors=%0d cycles=%0d mismatches=0 unstalled_ii=%0d",
                            VECTOR_COUNT, cycle_count,
                            unstalled_accept_interval_max);
                        $display("HARDWARE_AGENT_SIM_PASS");
                    end else
                        $fatal(1, "FAIL: mismatches=%0d unstalled_ii=%0d",
                            mismatch_count, unstalled_accept_interval_max);
                    $finish;
                end
            end
            if (out_valid && !out_ready) begin
                if (stalled_last_cycle &&
                    {dot1_s17, dot0_s17} !== stalled_data_r)
                    $fatal(1, "stalled output changed old=%h new=%h",
                        stalled_data_r, {dot1_s17, dot0_s17});
                stalled_data_r <= {dot1_s17, dot0_s17};
                stalled_last_cycle <= 1'b1;
            end else begin
                stalled_last_cycle <= 1'b0;
            end
            if (cycle_count > 10000) begin
                $fatal(1, "FAIL: timeout send=%0d receive=%0d",
                    send_index, receive_index);
            end
        end
    end
endmodule
