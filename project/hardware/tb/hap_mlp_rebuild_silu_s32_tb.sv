`timescale 1ns / 1ps

// Fixed vectors from source/design.md section 2: packed S24 sign extension,
// SiLU outer branches and S32 SwiGLU product, independent of the DUT LUT.
module hap_mlp_rebuild_silu_s32_tb;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0;
    reg clear = 0;
    reg in_valid = 0;
    wire in_ready;
    reg signed [23:0] gate_s24 = 0;
    reg signed [23:0] up_s24 = 0;
    wire out_valid;
    reg out_ready = 0;
    wire signed [31:0] out_product_s32;
    wire product_overflow;

    integer cycles = 0;
    integer received = 0;
    integer checks = 0;
    reg held = 0;
    reg signed [31:0] held_payload;
    reg saw_stall = 0;

    hap_mlp_silu_mul #(.LUT_FILE("data/mlp_silu_q16.mem")) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .gate_s24(gate_s24), .up_s24(up_s24),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_product_s32(out_product_s32),
        .product_overflow(product_overflow)
    );

    task automatic send_pair;
        input signed [23:0] gate;
        input signed [23:0] up;
        begin
            @(negedge clk);
            gate_s24 = gate;
            up_s24 = up;
            in_valid = 1;
            do @(posedge clk); while (!in_ready);
            @(negedge clk);
            in_valid = 0;
        end
    endtask

    initial begin
        repeat (5) @(negedge clk);
        rst_n = 1;
        fork
            begin
                send_pair(24'hf0_0000, 24'h01_0000); // -16, +1 -> 0.
                send_pair(24'h10_0000, 24'h64_0000); // +16, +100 -> +1600.
                send_pair(24'h10_0000, 24'h9c_0000); // +16, -100 -> -1600.
                send_pair(24'h00_0000, 24'h64_0000); // SiLU(0) -> 0.
            end
            begin
                repeat (30) @(posedge clk);
                @(negedge clk);
                out_ready = 1;
            end
        join
        wait (received == 4);
        repeat (3) @(posedge clk);
        if (saw_stall !== 1'b1 || product_overflow !== 1'b0)
            $fatal(1, "SiLU stall/overflow status mismatch");
        $display("checks=%0d packed_negative_s24=1 wide_positive_negative_s32=1", checks);
        $display("HARDWARE_AGENT_SIM_PASS");
        $finish;
    end

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            cycles <= 0;
            held <= 0;
        end else begin
            cycles <= cycles + 1;
            if (held && (out_valid !== 1'b1 ||
                         out_product_s32 !== held_payload))
                $fatal(1, "SiLU output changed under backpressure");
            held <= out_valid && !out_ready;
            if (out_valid && !out_ready) begin
                held_payload <= out_product_s32;
                saw_stall <= 1;
            end
            if (out_valid && out_ready) begin
                case (received)
                    0, 3: if (out_product_s32 !== 32'sd0)
                        $fatal(1, "SiLU zero branch mismatch index=%0d got=%0d",
                               received, out_product_s32);
                    1: if (out_product_s32 !== 32'sd104857600)
                        $fatal(1, "SiLU positive S32 mismatch got=%0d", out_product_s32);
                    2: if (out_product_s32 !== -32'sd104857600)
                        $fatal(1, "SiLU negative S32 mismatch got=%0d", out_product_s32);
                    default: $fatal(1, "extra SiLU output");
                endcase
                if (product_overflow !== 1'b0)
                    $fatal(1, "SiLU product overflow on legal vector");
                checks = checks + 1;
                received <= received + 1;
            end
            if (cycles > 1000)
                $fatal(1, "SiLU timeout received=%0d", received);
        end
    end
endmodule
