`timescale 1ns / 1ps

// H32 impulse vectors exercise S32 Down input, five butterflies and signed
// 11585/65536 half-away normalization without relying on DUT helper code.
module hap_mlp_rebuild_hadamard_s35_tb;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0;
    reg clear = 0;
    reg in_valid = 0;
    wire in_ready;
    reg [32*32-1:0] in_s32 = '0;
    wire out_valid;
    reg out_ready = 0;
    wire [32*35-1:0] out_s35;
    wire [31:0] input_group_count;
    wire [31:0] output_group_count;
    wire [31:0] saturation_count;
    wire error;

    integer cycles = 0;
    integer received = 0;
    integer checks = 0;
    integer lane;
    reg held = 0;
    reg [32*35-1:0] held_payload;
    reg saw_stall = 0;

    hap_mlp_hadamard32_s32_norm_stream #(.FIFO_DEPTH(8)) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready), .in_s32(in_s32),
        .out_valid(out_valid), .out_ready(out_ready), .out_s35(out_s35),
        .input_group_count(input_group_count),
        .output_group_count(output_group_count),
        .saturation_count(saturation_count), .error(error)
    );

    task automatic send_impulse;
        input signed [31:0] value;
        begin
            @(negedge clk);
            in_s32 = '0;
            in_s32[0 +: 32] = value;
            in_valid = 1;
            do @(posedge clk); while (!in_ready);
            @(negedge clk);
            in_valid = 0;
        end
    endtask

    initial begin
        repeat (5) @(negedge clk);
        rst_n = 1;
        send_impulse(32'sd65536);
        send_impulse(32'sd14438400);
        send_impulse(-32'sd14438400);
        wait (received == 3);
        repeat (3) @(posedge clk);
        if (saw_stall !== 1'b1 || input_group_count !== 3 ||
            output_group_count !== 3 || saturation_count !== 0 ||
            error !== 1'b0)
            $fatal(1, "H32 S35 status mismatch in=%0d out=%0d sat=%0d error=%0d",
                   input_group_count, output_group_count,
                   saturation_count, error);
        $display("checks=%0d s32_input=14438400 s35_normalized=2552320", checks);
        $display("HARDWARE_AGENT_SIM_PASS");
        $finish;
    end

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            cycles <= 0;
            out_ready <= 0;
            held <= 0;
        end else begin
            cycles <= cycles + 1;
            out_ready <= saw_stall && (cycles % 7) >= 3;
            if (held && (out_valid !== 1'b1 || out_s35 !== held_payload))
                $fatal(1, "H32 S35 output changed under backpressure");
            held <= out_valid && !out_ready;
            if (out_valid && !out_ready) begin
                held_payload <= out_s35;
                saw_stall <= 1;
            end
            if (out_valid && out_ready) begin
                for (lane = 0; lane < 32; lane = lane + 1) begin
                    if ($signed(out_s35[lane*35 +: 35]) !==
                        (received == 0 ? 35'sd11585 :
                         received == 1 ? 35'sd2552320 : -35'sd2552320))
                        $fatal(1, "H32 S35 mismatch vector=%0d lane=%0d got=%0d",
                               received, lane,
                               $signed(out_s35[lane*35 +: 35]));
                    checks = checks + 1;
                end
                received <= received + 1;
            end
            if (cycles > 1000)
                $fatal(1, "H32 S35 timeout received=%0d", received);
        end
    end
endmodule
