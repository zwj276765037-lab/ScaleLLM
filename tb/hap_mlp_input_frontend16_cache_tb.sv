`timescale 1ns / 1ps

module hap_mlp_input_frontend16_cache_tb;
    localparam integer GROUPS = 128;
    reg clk = 1'b0;
    always #3.3335 clk = ~clk;
    reg rst_n = 1'b0, clear = 1'b0;
    reg in_valid = 1'b0;
    wire in_ready;
    reg in_bank = 1'b0;
    reg [6:0] in_group = 7'd0;
    reg [12287:0] in_s24x16x32 = '0;
    wire rd_req_valid;
    wire rd_req_ready;
    wire rd_req_bank = 1'b0;
    wire [6:0] rd_req_group;
    wire rd_rsp_valid;
    reg rd_rsp_ready = 1'b0;
    wire rd_rsp_bank;
    wire [6:0] rd_rsp_group;
    wire [4095:0] rd_rsp_u8x16x32;
    wire [383:0] rd_rsp_meta_u24x16;
    reg release_valid = 1'b0;
    wire release_ready;
    reg release_bank = 1'b0;
    wire [1:0] bank_ready;
    wire [31:0] input_group_count, read_group_count, release_count;
    wire [31:0] hadamard_saturation_count;
    wire error;

    reg [12287:0] input_mem [0:GROUPS-1];
    reg [4095:0] expected_u8_mem [0:GROUPS-1];
    reg [383:0] expected_meta_mem [0:GROUPS-1];
    integer cycle=0, send_group=0, request_group=0, response_count=0;
    integer mismatch_count=0;
    assign rd_req_valid = bank_ready[0] && request_group < GROUPS &&
        (cycle%11 != 4);
    assign rd_req_group = request_group[6:0];

    hap_mlp_input_frontend16_cache dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready), .in_bank(in_bank),
        .in_group(in_group), .in_s24x16x32(in_s24x16x32),
        .rd_req_valid(rd_req_valid), .rd_req_ready(rd_req_ready),
        .rd_req_bank(rd_req_bank), .rd_req_group(rd_req_group),
        .rd_rsp_valid(rd_rsp_valid), .rd_rsp_ready(rd_rsp_ready),
        .rd_rsp_bank(rd_rsp_bank), .rd_rsp_group(rd_rsp_group),
        .rd_rsp_u8x16x32(rd_rsp_u8x16x32),
        .rd_rsp_meta_u24x16(rd_rsp_meta_u24x16),
        .release_valid(release_valid), .release_ready(release_ready),
        .release_bank(release_bank), .bank_ready(bank_ready),
        .input_group_count(input_group_count),
        .read_group_count(read_group_count), .release_count(release_count),
        .hadamard_saturation_count(hadamard_saturation_count),
        .error(error)
    );

    initial begin
        $readmemh("data/mlp_input_frontend16_cache/input_s24x16x32.mem", input_mem);
        $readmemh("data/mlp_input_frontend16_cache/expected_u8x16x32.mem", expected_u8_mem);
        $readmemh("data/mlp_input_frontend16_cache/expected_meta_u24x16.mem", expected_meta_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n) begin
            in_valid <= 1'b0;
            rd_rsp_ready <= 1'b0;
            release_valid <= 1'b0;
        end else begin
            rd_rsp_ready <= (cycle%17 != 5) && (cycle%17 != 6);
            if (!in_valid && send_group < GROUPS && in_ready) begin
                in_bank <= 1'b0;
                in_group <= send_group[6:0];
                in_s24x16x32 <= input_mem[send_group];
                in_valid <= 1'b1;
            end else if (in_valid && in_ready) begin
                in_valid <= 1'b0;
            end

            if (!release_valid && response_count == GROUPS) begin
                release_bank <= 1'b0;
                release_valid <= 1'b1;
            end else if (release_valid && release_ready) begin
                release_valid <= 1'b0;
            end
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            send_group <= 0;
            request_group <= 0;
            response_count <= 0;
            mismatch_count <= 0;
        end else begin
            cycle <= cycle+1;
            if (in_valid && in_ready)
                send_group <= send_group+1;
            if (rd_req_valid && rd_req_ready)
                request_group <= request_group+1;
            if (rd_rsp_valid && rd_rsp_ready) begin
                if (rd_rsp_bank !== 0 ||
                    rd_rsp_group !== response_count ||
                    rd_rsp_u8x16x32 !== expected_u8_mem[response_count] ||
                    rd_rsp_meta_u24x16 !== expected_meta_mem[response_count]) begin
                    $display("MISMATCH MLP input cache group=%0d got=%0d",
                        response_count, rd_rsp_group);
                    mismatch_count <= mismatch_count+1;
                end
                response_count <= response_count+1;
            end
            if (release_count == 1) begin
                if (mismatch_count == 0 && !error &&
                    send_group == GROUPS && request_group == GROUPS &&
                    response_count == GROUPS &&
                    input_group_count == GROUPS &&
                    read_group_count == GROUPS &&
                    hadamard_saturation_count == 0 && bank_ready == 0) begin
                    $display("PASS: hap_mlp_input_frontend16_cache groups=%0d requests=16 reads=%0d cycles=%0d mismatches=0 saturation=0",
                        GROUPS, read_group_count, cycle);
                    $finish;
                end else begin
                    $fatal(1,
                        "FAIL mismatch=%0d error=%0d sent=%0d req=%0d rsp=%0d input=%0d read=%0d sat=%0d banks=%b",
                        mismatch_count, error, send_group, request_group,
                        response_count, input_group_count, read_group_count,
                        hadamard_saturation_count, bank_ready);
                end
            end
            if (error)
                $fatal(1, "FAIL input frontend sticky error cycle=%0d wrapper=%0d half0=%0d half1=%0d banks=%b/%b input_stage=%0d pending=%b%b",
                    cycle, dut.error, dut.half0_error, dut.half1_error,
                    dut.half0_bank_ready, dut.half1_bank_ready,
                    dut.input_stage_valid_r, dut.input_pending1_r,
                    dut.input_pending0_r);
            if (cycle > 50000)
                $fatal(1, "FAIL timeout sent=%0d req=%0d rsp=%0d bank=%b",
                    send_group, request_group, response_count, bank_ready);
        end
    end
endmodule
