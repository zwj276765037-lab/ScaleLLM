`timescale 1ns / 1ps

module hap_a8w4_pack2_dsp_tb;
    localparam integer VECTOR_COUNT = 8192;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire signed [8:0] activation_s9;
    wire signed [3:0] weight0_s4;
    wire signed [3:0] weight1_s4;
    wire out_valid;
    reg out_ready = 1'b1;
    wire signed [11:0] product0_s12;
    wire signed [11:0] product1_s12;

    reg [8:0] activation_mem [0:VECTOR_COUNT-1];
    reg [7:0] weights_mem [0:VECTOR_COUNT-1];
    reg [23:0] expected_mem [0:VECTOR_COUNT-1];
    integer send_index = 0;
    integer receive_index = 0;
    integer cycle_count = 0;
    integer mismatch_count = 0;
    integer last_accept_cycle = -1;
    integer unstalled_accept_interval_max = 0;

    wire [12:0] source_index = send_index < VECTOR_COUNT ? send_index :
        VECTOR_COUNT-1;
    assign in_valid = send_index < VECTOR_COUNT;
    assign activation_s9 = activation_mem[source_index];
    assign weight0_s4 = weights_mem[source_index][3:0];
    assign weight1_s4 = weights_mem[source_index][7:4];

    hap_a8w4_pack2_dsp dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .activation_s9(activation_s9), .weight0_s4(weight0_s4),
        .weight1_s4(weight1_s4), .out_valid(out_valid),
        .out_ready(out_ready), .product0_s12(product0_s12),
        .product1_s12(product1_s12)
    );

    initial begin
        $readmemh("data/a8w4_pack2/activation_s9.mem", activation_mem);
        $readmemh("data/a8w4_pack2/weights_s4x2.mem", weights_mem);
        $readmemh("data/a8w4_pack2/expected_s12x2.mem", expected_mem);
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
        end else begin
            cycle_count <= cycle_count + 1;
            out_ready <= (receive_index < 4096) ? 1'b1 :
                ((cycle_count % 17) != 5 && (cycle_count % 23) != 9);
            if (in_valid && in_ready) begin
                send_index <= send_index + 1;
                if (send_index < 4096 && last_accept_cycle >= 0 &&
                    cycle_count-last_accept_cycle >
                    unstalled_accept_interval_max)
                    unstalled_accept_interval_max <=
                        cycle_count-last_accept_cycle;
                last_accept_cycle <= cycle_count;
            end
            if (out_valid && out_ready) begin
                if ({product1_s12, product0_s12} !==
                    expected_mem[receive_index]) begin
                    $display("MISMATCH index=%0d got=%h_%h expected=%h",
                        receive_index, product1_s12, product0_s12,
                        expected_mem[receive_index]);
                    mismatch_count <= mismatch_count + 1;
                end
                receive_index <= receive_index + 1;
                if (receive_index + 1 == VECTOR_COUNT) begin
                    if (mismatch_count == 0 &&
                        unstalled_accept_interval_max <= 1)
                        $display("PASS: hap_a8w4_pack2_dsp vectors=%0d cycles=%0d mismatches=0 unstalled_ii=%0d",
                            VECTOR_COUNT, cycle_count,
                            unstalled_accept_interval_max);
                    else
                        $display("FAIL: mismatches=%0d unstalled_ii=%0d",
                            mismatch_count, unstalled_accept_interval_max);
                    $finish;
                end
            end
            if (cycle_count > 20000) begin
                $display("FAIL: timeout send=%0d receive=%0d",
                    send_index, receive_index);
                $finish;
            end
        end
    end
endmodule
