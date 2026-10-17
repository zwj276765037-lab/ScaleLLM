`timescale 1ns / 1ps

module hap_mlp_input_frontend16_compact_cache_tb;
    localparam integer GROUPS = 128;
    reg clk = 1'b0;
    always #3.3335 clk = ~clk;

    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    wire in_ready;
    reg in_bank = 1'b0;
    reg [6:0] in_group = 7'd0;
    reg [16*32*24-1:0] in_s24x16x32 = '0;
    reg rd_req_valid = 1'b0;
    wire rd_req_ready;
    reg [6:0] rd_req_group = 7'd0;
    wire rd_rsp_valid;
    reg rd_rsp_ready = 1'b0;
    wire rd_rsp_bank;
    wire [6:0] rd_rsp_group;
    wire [16*32*8-1:0] rd_rsp_u8x16x32;
    wire [16*24-1:0] rd_rsp_meta_u24x16;
    reg release_valid = 1'b0;
    wire release_ready;
    wire [1:0] bank_ready;
    wire [31:0] input_group_count;
    wire [31:0] read_group_count;
    wire [31:0] release_count;
    wire [31:0] hadamard_saturation_count;
    wire error;

    reg [16*32*24-1:0] input_mem [0:GROUPS-1];
    reg [16*32*8-1:0] expected_u8_mem [0:GROUPS-1];
    reg [16*24-1:0] expected_meta_mem [0:GROUPS-1];
    integer cycle = 0;
    integer sent = 0;
    integer requested = 0;
    integer received = 0;
    integer mismatches = 0;
    integer half0_writes = 0;
    integer half1_writes = 0;
    integer half0_reads = 0;
    integer half1_reads = 0;
    integer half0_responses = 0;
    integer half1_responses = 0;
    integer half0_releases = 0;
    integer half1_releases = 0;
    reg stalled_response_r = 1'b0;
    reg [16*32*8-1:0] stalled_u8_r;
    reg [16*24-1:0] stalled_meta_r;
    reg stalled_bank_r;
    reg [6:0] stalled_group_r;

    hap_mlp_input_frontend16_compact_cache dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready), .in_bank(in_bank),
        .in_group(in_group), .in_s24x16x32(in_s24x16x32),
        .rd_req_valid(rd_req_valid), .rd_req_ready(rd_req_ready),
        .rd_req_bank(1'b0), .rd_req_group(rd_req_group),
        .rd_rsp_valid(rd_rsp_valid), .rd_rsp_ready(rd_rsp_ready),
        .rd_rsp_bank(rd_rsp_bank), .rd_rsp_group(rd_rsp_group),
        .rd_rsp_u8x16x32(rd_rsp_u8x16x32),
        .rd_rsp_meta_u24x16(rd_rsp_meta_u24x16),
        .release_valid(release_valid), .release_ready(release_ready),
        .release_bank(1'b0), .bank_ready(bank_ready),
        .input_group_count(input_group_count),
        .read_group_count(read_group_count), .release_count(release_count),
        .hadamard_saturation_count(hadamard_saturation_count),
        .error(error)
    );

    initial begin
        $readmemh("data/mlp_input_frontend16_cache/input_s24x16x32.mem",
            input_mem);
        $readmemh("data/mlp_input_frontend16_cache/expected_u8x16x32.mem",
            expected_u8_mem);
        $readmemh("data/mlp_input_frontend16_cache/expected_meta_u24x16.mem",
            expected_meta_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n) begin
            in_valid <= 1'b0;
            rd_req_valid <= 1'b0;
            rd_rsp_ready <= 1'b0;
            release_valid <= 1'b0;
        end else begin
            rd_rsp_ready <= cycle % 17 != 5 && cycle % 17 != 6;

            if (!in_valid && sent < GROUPS && in_ready) begin
                in_bank <= 1'b0;
                in_group <= sent[6:0];
                in_s24x16x32 <= input_mem[sent];
                in_valid <= 1'b1;
            end else if (in_valid && in_ready) begin
                in_valid <= 1'b0;
            end

            if (bank_ready[0] && requested < GROUPS) begin
                rd_req_group <= requested[6:0];
                rd_req_valid <= 1'b1;
            end else begin
                rd_req_valid <= 1'b0;
            end

            if (!release_valid && received == GROUPS)
                release_valid <= 1'b1;
            else if (release_valid && release_ready)
                release_valid <= 1'b0;
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            sent <= 0;
            requested <= 0;
            received <= 0;
            mismatches <= 0;
            half0_writes <= 0;
            half1_writes <= 0;
            half0_reads <= 0;
            half1_reads <= 0;
            half0_responses <= 0;
            half1_responses <= 0;
            half0_releases <= 0;
            half1_releases <= 0;
            stalled_response_r <= 1'b0;
        end else begin
            cycle <= cycle + 1;
            if (dut.u_cache0.wr_fire) half0_writes <= half0_writes + 1;
            if (dut.u_cache1.wr_fire) half1_writes <= half1_writes + 1;
            if (dut.u_cache0.rd_req_fire) half0_reads <= half0_reads + 1;
            if (dut.u_cache1.rd_req_fire) half1_reads <= half1_reads + 1;
            if (dut.u_cache0.rd_rsp_fire)
                half0_responses <= half0_responses + 1;
            if (dut.u_cache1.rd_rsp_fire)
                half1_responses <= half1_responses + 1;
            if (dut.u_cache0.release_fire)
                half0_releases <= half0_releases + 1;
            if (dut.u_cache1.release_fire)
                half1_releases <= half1_releases + 1;

            if (dut.u_cache0.wr_fire !== dut.u_cache1.wr_fire ||
                dut.u_cache0.rd_req_fire !== dut.u_cache1.rd_req_fire ||
                dut.u_cache0.rd_rsp_fire !== dut.u_cache1.rd_rsp_fire ||
                dut.u_cache0.release_fire !== dut.u_cache1.release_fire)
                $fatal(1, "FAIL compact cache local lockstep cycle=%0d",
                    cycle);
            if (stalled_response_r &&
                (rd_rsp_valid !== 1'b1 ||
                 rd_rsp_bank !== stalled_bank_r ||
                 rd_rsp_group !== stalled_group_r ||
                 rd_rsp_u8x16x32 !== stalled_u8_r ||
                 rd_rsp_meta_u24x16 !== stalled_meta_r))
                $fatal(1, "FAIL compact cache response changed under stall cycle=%0d",
                    cycle);
            stalled_response_r <= rd_rsp_valid && !rd_rsp_ready;
            if (rd_rsp_valid && !rd_rsp_ready) begin
                stalled_bank_r <= rd_rsp_bank;
                stalled_group_r <= rd_rsp_group;
                stalled_u8_r <= rd_rsp_u8x16x32;
                stalled_meta_r <= rd_rsp_meta_u24x16;
            end
            if (in_valid && in_ready)
                sent <= sent + 1;
            if (rd_req_valid && rd_req_ready)
                requested <= requested + 1;
            if (rd_rsp_valid && rd_rsp_ready) begin
                if (rd_rsp_bank !== 1'b0 || rd_rsp_group !== received[6:0] ||
                    rd_rsp_u8x16x32 !== expected_u8_mem[received] ||
                    rd_rsp_meta_u24x16 !== expected_meta_mem[received]) begin
                    $display("MISMATCH compact input group=%0d tag=%0d",
                        received, rd_rsp_group);
                    mismatches <= mismatches + 1;
                end
                received <= received + 1;
            end

            if (release_count == 1) begin
                if (mismatches == 0 && !error && sent == GROUPS &&
                    requested == GROUPS && received == GROUPS &&
                    input_group_count == GROUPS &&
                    read_group_count == GROUPS && bank_ready == 0 &&
                    half0_writes == GROUPS && half1_writes == GROUPS &&
                    half0_reads == GROUPS && half1_reads == GROUPS &&
                    half0_responses == GROUPS &&
                    half1_responses == GROUPS &&
                    half0_releases == 1 && half1_releases == 1) begin
                    $display("PASS: compact MLP input cache bit-exact groups=%0d cycles=%0d mismatches=0 saturation=%0d",
                        GROUPS, cycle, hadamard_saturation_count);
                    $finish;
                end
                $fatal(1, "FAIL compact cache err=%0d mismatch=%0d sent=%0d req=%0d rsp=%0d counts=%0d/%0d banks=%b",
                    error, mismatches, sent, requested, received,
                    input_group_count, read_group_count, bank_ready);
            end
            if (error)
                $fatal(1, "FAIL compact input frontend sticky error cycle=%0d",
                    cycle);
            if (cycle > 200000)
                $fatal(1, "FAIL compact cache timeout sent=%0d req=%0d rsp=%0d bank=%b",
                    sent, requested, received, bank_ready);
        end
    end
endmodule
