`timescale 1ns/1ps

module m8_mlp_input_frontend_tb #(
    parameter integer CASE_ID = 0,
    parameter integer BACKPRESSURE = 0,
    parameter DATA_DIR = "/tmp"
);
    localparam integer GROUPS = 128;
    localparam integer INPUT_W = 16*32*24;
    localparam integer DATA_W = 16*32*8;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire in_bank = 1'b0;
    wire [6:0] in_group;
    wire [INPUT_W-1:0] in_s24;
    wire rd_req_valid;
    wire rd_req_ready;
    wire rd_req_bank = 1'b0;
    wire [6:0] rd_req_group;
    wire rd_rsp_valid;
    wire rd_rsp_ready;
    wire rd_rsp_bank;
    wire [6:0] rd_rsp_group;
    wire [DATA_W-1:0] rd_rsp_u8;
    wire [383:0] rd_rsp_meta_narrow;
    wire [639:0] rd_rsp_meta_wide;
    wire release_valid;
    wire release_ready;
    wire release_bank = 1'b0;
    wire [1:0] bank_ready;
    wire [31:0] input_group_count;
    wire [31:0] read_group_count;
    wire [31:0] release_count;
    wire [31:0] hadamard_saturation_count;
    wire [31:0] format_error_count;
    wire error;
    wire cache_write_fire_observed;

    reg [INPUT_W-1:0] input_mem [0:GROUPS-1];
    reg [DATA_W-1:0] expected_sc_u8_mem [0:GROUPS-1];
    reg [383:0] expected_sc_meta_mem [0:GROUPS-1];
    reg [DATA_W-1:0] expected_fp_u8_mem [0:GROUPS-1];
    reg [383:0] expected_fp16_meta_mem [0:GROUPS-1];
    reg [639:0] expected_fp32_meta_mem [0:GROUPS-1];

    integer cycle = 0;
    integer send_index = 0;
    integer request_index = 0;
    integer receive_count = 0;
    integer write_count = 0;
    integer mismatch_count = 0;
    integer previous_accept_cycle = -1;
    integer input_ii_min = 32'h7fff_ffff;
    integer input_ii_max = 0;
    integer previous_write_cycle = -1;
    integer write_ii_min = 32'h7fff_ffff;
    integer write_ii_max = 0;
    integer first_input_cycle = -1;
    integer first_write_cycle = -1;
    integer last_write_cycle = -1;
    integer input_stall_cycles = 0;
    integer output_stall_cycles = 0;
    integer done_pending = 0;
    reg release_pending = 1'b0;
    reg rsp_was_stalled = 1'b0;
    reg [DATA_W-1:0] stalled_u8;
    reg [383:0] stalled_meta_narrow;
    reg [639:0] stalled_meta_wide;
    reg stalled_bank;
    reg [6:0] stalled_group;
    integer delta;
    reg response_mismatch;

    always #5 clk = ~clk;
    assign in_valid = rst_n && (send_index < GROUPS);
    assign in_group = send_index[6:0];
    assign in_s24 = input_mem[send_index];
    assign rd_req_valid = rst_n && bank_ready[0] &&
        (request_index < GROUPS);
    assign rd_req_group = request_index[6:0];
    assign rd_rsp_ready = rst_n &&
        ((BACKPRESSURE == 0) || ((cycle % 31) < 23));
    assign release_valid = release_pending;

    initial begin
        $readmemh({DATA_DIR, "/input_s24.mem"}, input_mem);
        $readmemh({DATA_DIR, "/expected_sc_u8.mem"}, expected_sc_u8_mem);
        $readmemh({DATA_DIR, "/expected_sc_meta.mem"}, expected_sc_meta_mem);
        $readmemh({DATA_DIR, "/expected_fp_u8.mem"}, expected_fp_u8_mem);
        $readmemh({DATA_DIR, "/expected_fp16_meta.mem"},
            expected_fp16_meta_mem);
        $readmemh({DATA_DIR, "/expected_fp32_meta.mem"},
            expected_fp32_meta_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    generate
        if (CASE_ID == 0) begin : g_sc
            assign rd_rsp_meta_wide = 640'd0;
            assign format_error_count = 32'd0;
            hap_mlp_input_frontend16_compact_cache dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready), .in_bank(in_bank),
                .in_group(in_group), .in_s24x16x32(in_s24),
                .rd_req_valid(rd_req_valid), .rd_req_ready(rd_req_ready),
                .rd_req_bank(rd_req_bank), .rd_req_group(rd_req_group),
                .rd_rsp_valid(rd_rsp_valid), .rd_rsp_ready(rd_rsp_ready),
                .rd_rsp_bank(rd_rsp_bank), .rd_rsp_group(rd_rsp_group),
                .rd_rsp_u8x16x32(rd_rsp_u8),
                .rd_rsp_meta_u24x16(rd_rsp_meta_narrow),
                .release_valid(release_valid), .release_ready(release_ready),
                .release_bank(release_bank), .bank_ready(bank_ready),
                .input_group_count(input_group_count),
                .read_group_count(read_group_count),
                .release_count(release_count),
                .hadamard_saturation_count(hadamard_saturation_count),
                .error(error)
            );
            assign cache_write_fire_observed = dut.cache_write_fire;
        end else if (CASE_ID == 1) begin : g_fp16
            assign rd_rsp_meta_wide = 640'd0;
            m8_fp16_mlp_input_frontend16_compact_cache dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready), .in_bank(in_bank),
                .in_group(in_group), .in_s24x16x32(in_s24),
                .rd_req_valid(rd_req_valid), .rd_req_ready(rd_req_ready),
                .rd_req_bank(rd_req_bank), .rd_req_group(rd_req_group),
                .rd_rsp_valid(rd_rsp_valid), .rd_rsp_ready(rd_rsp_ready),
                .rd_rsp_bank(rd_rsp_bank), .rd_rsp_group(rd_rsp_group),
                .rd_rsp_u8x16x32(rd_rsp_u8),
                .rd_rsp_meta(rd_rsp_meta_narrow),
                .release_valid(release_valid), .release_ready(release_ready),
                .release_bank(release_bank), .bank_ready(bank_ready),
                .input_group_count(input_group_count),
                .read_group_count(read_group_count),
                .release_count(release_count),
                .hadamard_saturation_count(hadamard_saturation_count),
                .format_error_count(format_error_count), .error(error)
            );
            assign cache_write_fire_observed = dut.u_frontend.cache_write_fire;
        end else begin : g_fp32
            assign rd_rsp_meta_narrow = 384'd0;
            m8_fp32_mlp_input_frontend16_compact_cache dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready), .in_bank(in_bank),
                .in_group(in_group), .in_s24x16x32(in_s24),
                .rd_req_valid(rd_req_valid), .rd_req_ready(rd_req_ready),
                .rd_req_bank(rd_req_bank), .rd_req_group(rd_req_group),
                .rd_rsp_valid(rd_rsp_valid), .rd_rsp_ready(rd_rsp_ready),
                .rd_rsp_bank(rd_rsp_bank), .rd_rsp_group(rd_rsp_group),
                .rd_rsp_u8x16x32(rd_rsp_u8),
                .rd_rsp_meta(rd_rsp_meta_wide),
                .release_valid(release_valid), .release_ready(release_ready),
                .release_bank(release_bank), .bank_ready(bank_ready),
                .input_group_count(input_group_count),
                .read_group_count(read_group_count),
                .release_count(release_count),
                .hadamard_saturation_count(hadamard_saturation_count),
                .format_error_count(format_error_count), .error(error)
            );
            assign cache_write_fire_observed = dut.u_frontend.cache_write_fire;
        end
    endgenerate

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            send_index <= 0;
            request_index <= 0;
            receive_count <= 0;
            write_count <= 0;
            mismatch_count <= 0;
            previous_accept_cycle <= -1;
            input_ii_min <= 32'h7fff_ffff;
            input_ii_max <= 0;
            previous_write_cycle <= -1;
            write_ii_min <= 32'h7fff_ffff;
            write_ii_max <= 0;
            first_input_cycle <= -1;
            first_write_cycle <= -1;
            last_write_cycle <= -1;
            input_stall_cycles <= 0;
            output_stall_cycles <= 0;
            done_pending <= 0;
            release_pending <= 1'b0;
            rsp_was_stalled <= 1'b0;
        end else begin
            cycle <= cycle + 1;
            if (in_valid && in_ready) begin
                if (first_input_cycle < 0)
                    first_input_cycle <= cycle;
                if (previous_accept_cycle >= 0) begin
                    delta = cycle - previous_accept_cycle;
                    if (delta < input_ii_min)
                        input_ii_min <= delta;
                    if (delta > input_ii_max)
                        input_ii_max <= delta;
                end
                previous_accept_cycle <= cycle;
                send_index <= send_index + 1;
            end else if (in_valid)
                input_stall_cycles <= input_stall_cycles + 1;

            if (cache_write_fire_observed) begin
                write_count <= write_count + 1;
                if (first_write_cycle < 0)
                    first_write_cycle <= cycle;
                if (previous_write_cycle >= 0) begin
                    delta = cycle - previous_write_cycle;
                    if (delta < write_ii_min)
                        write_ii_min <= delta;
                    if (delta > write_ii_max)
                        write_ii_max <= delta;
                end
                previous_write_cycle <= cycle;
                last_write_cycle <= cycle;
            end

            if (rd_req_valid && rd_req_ready)
                request_index <= request_index + 1;
            if (rd_rsp_valid && !rd_rsp_ready)
                output_stall_cycles <= output_stall_cycles + 1;

            if (rsp_was_stalled) begin
                if (!rd_rsp_valid || rd_rsp_bank !== stalled_bank ||
                        rd_rsp_group !== stalled_group ||
                        rd_rsp_u8 !== stalled_u8 ||
                        (CASE_ID != 2 &&
                         rd_rsp_meta_narrow !== stalled_meta_narrow) ||
                        (CASE_ID == 2 &&
                         rd_rsp_meta_wide !== stalled_meta_wide)) begin
                    $display("FAIL: M8 response changed under stall case=%0d",
                        CASE_ID);
                    $finish;
                end
            end
            rsp_was_stalled <= rd_rsp_valid && !rd_rsp_ready;
            if (rd_rsp_valid && !rd_rsp_ready) begin
                stalled_bank <= rd_rsp_bank;
                stalled_group <= rd_rsp_group;
                stalled_u8 <= rd_rsp_u8;
                stalled_meta_narrow <= rd_rsp_meta_narrow;
                stalled_meta_wide <= rd_rsp_meta_wide;
            end

            if (rd_rsp_valid && rd_rsp_ready) begin
                response_mismatch = 1'b0;
                if (rd_rsp_bank !== 1'b0)
                    response_mismatch = 1'b1;
                if (CASE_ID == 0) begin
                    if (rd_rsp_u8 !== expected_sc_u8_mem[rd_rsp_group] ||
                            rd_rsp_meta_narrow !==
                            expected_sc_meta_mem[rd_rsp_group])
                        response_mismatch = 1'b1;
                end else if (CASE_ID == 1) begin
                    if (rd_rsp_u8 !== expected_fp_u8_mem[rd_rsp_group] ||
                            rd_rsp_meta_narrow !==
                            expected_fp16_meta_mem[rd_rsp_group])
                        response_mismatch = 1'b1;
                end else begin
                    if (rd_rsp_u8 !== expected_fp_u8_mem[rd_rsp_group] ||
                            rd_rsp_meta_wide !==
                            expected_fp32_meta_mem[rd_rsp_group])
                        response_mismatch = 1'b1;
                end
                if (response_mismatch) begin
                    mismatch_count <= mismatch_count + 1;
                    if (mismatch_count < 12)
                        $display("M8_MISMATCH case=%0d group=%0d",
                            CASE_ID, rd_rsp_group);
                end
                receive_count <= receive_count + 1;
                if (receive_count == GROUPS-1)
                    release_pending <= 1'b1;
            end

            if (release_valid && release_ready) begin
                release_pending <= 1'b0;
                done_pending <= 1;
            end
            if (done_pending != 0)
                done_pending <= done_pending + 1;
            if (done_pending == 3) begin
                if (mismatch_count == 0 &&
                        input_group_count == GROUPS &&
                        write_count == GROUPS &&
                        read_group_count == GROUPS &&
                        receive_count == GROUPS &&
                        release_count == 1 && format_error_count == 0 &&
                        !bank_ready[0] && !error) begin
                    $display("M8_METRIC_JSON: {\"case_id\":%0d,\"backpressure\":%0d,\"groups\":%0d,\"rows\":16,\"mismatches\":0,\"input_ii_min\":%0d,\"input_ii_max\":%0d,\"write_ii_min\":%0d,\"write_ii_max\":%0d,\"first_write_latency\":%0d,\"first_input_to_last_write_cycles\":%0d,\"input_stall_cycles\":%0d,\"output_stall_cycles\":%0d,\"hadamard_saturations\":%0d,\"cycles\":%0d}",
                        CASE_ID, BACKPRESSURE, GROUPS, input_ii_min,
                        input_ii_max, write_ii_min, write_ii_max,
                        first_write_cycle-first_input_cycle+1,
                        last_write_cycle-first_input_cycle+1,
                        input_stall_cycles, output_stall_cycles,
                        hadamard_saturation_count, cycle+1);
                    $display("PASS: M8 MLP input frontend native-scale boundary");
                end else begin
                    $display("FAIL: M8 final case=%0d mismatch=%0d input=%0d write=%0d read=%0d receive=%0d release=%0d format=%0d bank=%b error=%b",
                        CASE_ID, mismatch_count, input_group_count,
                        write_count, read_group_count, receive_count,
                        release_count, format_error_count, bank_ready, error);
                end
                $finish;
            end
            if (error) begin
                $display("FAIL: M8 DUT error case=%0d cycle=%0d format=%0d",
                    CASE_ID, cycle, format_error_count);
                $finish;
            end
            if (cycle > 250000) begin
                $display("FAIL: M8 timeout case=%0d send=%0d write=%0d read=%0d",
                    CASE_ID, send_index, write_count, read_group_count);
                $finish;
            end
        end
    end

    initial begin
        if ((CASE_ID < 0) || (CASE_ID > 2) ||
                ((BACKPRESSURE != 0) && (BACKPRESSURE != 1)))
            $error("invalid M8 test parameters");
    end
endmodule
