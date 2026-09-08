`timescale 1ns / 1ps

module hap_mlp_hadamard32_s32_norm_stream_tb;
    localparam integer VECTOR_COUNT = 96;
    localparam integer INPUT_W = 32*32;
    localparam integer OUTPUT_W = 32*35;
    reg clk = 1'b0, rst_n = 1'b0, clear = 1'b0;
    always #3.3335 clk = ~clk;

    wire in_valid, in_ready, out_valid, out_ready;
    wire [INPUT_W-1:0] in_s32;
    wire [OUTPUT_W-1:0] out_s35;
    wire [31:0] input_group_count, output_group_count, saturation_count;
    wire error;
    reg [INPUT_W-1:0] input_mem [0:VECTOR_COUNT-1];
    reg [OUTPUT_W-1:0] expected_mem [0:VECTOR_COUNT-1];
    integer cycle_count=0, send_index=0, recv_index=0, mismatch_count=0;
    integer last_accept=-1, unstalled_interval_max=0, stall_cycles=0;

    assign in_valid = rst_n && (send_index < VECTOR_COUNT);
    assign in_s32 = input_mem[send_index < VECTOR_COUNT ? send_index :
        VECTOR_COUNT-1];
    assign out_ready = rst_n && ((cycle_count < 40) ||
        ((cycle_count % 11) < 7));

    hap_mlp_hadamard32_s32_norm_stream #(.FIFO_DEPTH(8)) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready), .in_s32(in_s32),
        .out_valid(out_valid), .out_ready(out_ready), .out_s35(out_s35),
        .input_group_count(input_group_count),
        .output_group_count(output_group_count),
        .saturation_count(saturation_count), .error(error)
    );

    initial begin
        $readmemh("data/mlp_hadamard_s32/input_s32.mem", input_mem);
        $readmemh("data/mlp_hadamard_s32/expected_s35.mem", expected_mem);
        repeat (6) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle_count<=0; send_index<=0; recv_index<=0;
            mismatch_count<=0; last_accept<=-1;
            unstalled_interval_max<=0; stall_cycles<=0;
        end else begin
            cycle_count <= cycle_count + 1;
            if (in_valid && in_ready) begin
                if (send_index < 32 && last_accept >= 0 &&
                    cycle_count-last_accept > unstalled_interval_max)
                    unstalled_interval_max <= cycle_count-last_accept;
                last_accept <= cycle_count;
                send_index <= send_index + 1;
            end else if (in_valid)
                stall_cycles <= stall_cycles + 1;
            if (out_valid && out_ready) begin
                if (out_s35 !== expected_mem[recv_index]) begin
                    mismatch_count <= mismatch_count + 1;
                    $display("MISMATCH index=%0d got=%h expected=%h",
                        recv_index, out_s35, expected_mem[recv_index]);
                end
                recv_index <= recv_index + 1;
                if (recv_index + 1 == VECTOR_COUNT) begin
                    if (mismatch_count == 0 &&
                        out_s35 === expected_mem[recv_index] &&
                        saturation_count == 0 &&
                        unstalled_interval_max <= 1 && !error)
                        $display("PASS: MLP Hadamard S32 vectors=%0d cycles=%0d interval_max=%0d stalls=%0d",
                            VECTOR_COUNT, cycle_count,
                            unstalled_interval_max, stall_cycles);
                    else
                        $display("FAIL: MLP Hadamard mismatches=%0d sat=%0d interval=%0d error=%0d",
                            mismatch_count +
                            ((out_s35 !== expected_mem[recv_index]) ? 1 : 0),
                            saturation_count, unstalled_interval_max, error);
                    $finish;
                end
            end
            if (error) begin $display("FAIL: sticky error"); $finish; end
            if (cycle_count > 3000) begin
                $display("FAIL: timeout send=%0d recv=%0d", send_index,
                    recv_index); $finish;
            end
        end
    end
endmodule
