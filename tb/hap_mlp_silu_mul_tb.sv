`timescale 1ns / 1ps

module hap_mlp_silu_mul_tb;
    localparam int VECTOR_COUNT = 512;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;

    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire signed [23:0] gate_s24;
    wire signed [23:0] up_s24;
    wire out_valid;
    reg out_ready = 1'b1;
    wire signed [31:0] out_product_s32;

    reg [23:0] gate_mem [0:VECTOR_COUNT-1];
    reg [23:0] up_mem [0:VECTOR_COUNT-1];
    reg [31:0] expected_mem [0:VECTOR_COUNT-1];
    integer send_index = 0;
    integer recv_index = 0;
    integer cycle_count = 0;
    integer mismatch_count = 0;
    integer last_accept_cycle = -1;
    integer unstalled_accept_interval_max = 0;

    wire [8:0] source_index = send_index < VECTOR_COUNT ? send_index :
        VECTOR_COUNT-1;
    assign in_valid = send_index < VECTOR_COUNT;
    assign gate_s24 = gate_mem[source_index];
    assign up_s24 = up_mem[source_index];

    hap_mlp_silu_mul #(.LUT_FILE("data/mlp_silu_q16.mem")) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .gate_s24(gate_s24), .up_s24(up_s24),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_product_s32(out_product_s32)
    );

    initial begin
        $readmemh("data/mlp_silu_gate_s24.mem", gate_mem);
        $readmemh("data/mlp_silu_up_s24.mem", up_mem);
        $readmemh("data/mlp_silu_expected_s32.mem", expected_mem);
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            out_ready <= 1'b1;
            send_index <= 0;
            recv_index <= 0;
            cycle_count <= 0;
            mismatch_count <= 0;
            last_accept_cycle <= -1;
            unstalled_accept_interval_max <= 0;
        end else begin
            cycle_count <= cycle_count + 1;
            // First half proves II=1.  The second half injects deterministic
            // local backpressure and verifies the elastic boundary.
            out_ready <= (recv_index < 256) ? 1'b1 :
                ((cycle_count % 11) != 5);

            if (in_valid && in_ready) begin
                send_index <= send_index + 1;
                if (send_index < 256 && last_accept_cycle >= 0 &&
                    cycle_count-last_accept_cycle >
                    unstalled_accept_interval_max)
                    unstalled_accept_interval_max <=
                        cycle_count-last_accept_cycle;
                last_accept_cycle <= cycle_count;
            end

            if (out_valid && out_ready) begin
                if (out_product_s32 !== expected_mem[recv_index]) begin
                    $display("MISMATCH index=%0d got=%h expected=%h",
                        recv_index, out_product_s32,
                        expected_mem[recv_index]);
                    mismatch_count <= mismatch_count + 1;
                end
                recv_index <= recv_index + 1;
                if (recv_index + 1 == VECTOR_COUNT) begin
                    if (mismatch_count == 0)
                        $display("PASS: hap_mlp_silu_mul vectors=%0d cycles=%0d unstalled_accept_interval_max=%0d",
                            VECTOR_COUNT, cycle_count,
                            unstalled_accept_interval_max);
                    else
                        $display("FAIL: hap_mlp_silu_mul mismatches=%0d",
                            mismatch_count);
                    $finish;
                end
            end
            if (cycle_count > 5000) begin
                $display("FAIL: timeout send=%0d recv=%0d", send_index,
                    recv_index);
                $finish;
            end
        end
    end
endmodule
