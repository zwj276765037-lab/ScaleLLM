`timescale 1ns / 1ps

// End-to-end reduced-shape regression for the V5 serial command.  This TB
// drives both independent DDR clock domains through their public AXI ports,
// retains cache requests in a real FIFO, injects deterministic random AXI,
// cache, metadata and output backpressure, and checks both phase snapshots.
module hap_mlp_serial_ddr_command16_v5_s46_reduced_tb;
    localparam integer INTERMEDIATE_COLUMNS = 32;
    localparam integer HIDDEN_COLUMNS = 128;
    localparam integer HIDDEN_GROUPS = 128;
    localparam integer DOWN_GROUPS = 1;
    localparam integer GATE_SOURCE_RECORDS = 4;
    localparam integer GATE_TX = GATE_SOURCE_RECORDS*HIDDEN_GROUPS;
    localparam integer GATE_COMPUTE_TX =
        2*((INTERMEDIATE_COLUMNS+11)/12)*HIDDEN_GROUPS;
    localparam integer GATE_PASSES =
        2*((INTERMEDIATE_COLUMNS+11)/12);
    localparam integer GATE_OUTPUT_RECORDS =
        2*((INTERMEDIATE_COLUMNS+15)/16);
    localparam integer DOWN_SOURCE_RECORDS = HIDDEN_COLUMNS/16;
    localparam integer DOWN_TX = DOWN_SOURCE_RECORDS*DOWN_GROUPS;
    localparam integer DOWN_COMPUTE_TILES =
        (HIDDEN_COLUMNS+11)/12;
    localparam integer TOTAL_TX = GATE_TX+DOWN_TX;
    localparam integer TOTAL_BEATS = TOTAL_TX*2;
    localparam integer CACHE_DEPTH = 64;
    localparam integer MAX_CYCLES = 400000;

    reg core_clk = 1'b0;
    reg ddr0_clk = 1'b0;
    reg ddr1_clk = 1'b0;
    always #3.3335 core_clk = ~core_clk;
    always #1.6665 ddr0_clk = ~ddr0_clk;
    always #1.6675 ddr1_clk = ~ddr1_clk;

    reg core_rst_n = 1'b0;
    reg ddr0_rst_n = 1'b0;
    reg ddr1_rst_n = 1'b0;
    reg core_clear = 1'b0;
    reg command_valid = 1'b0;
    reg command_pause = 1'b0;
    wire command_ready;
    wire busy;
    wire done;
    wire error;
    wire [2:0] phase;

    wire cache_req_valid;
    reg cache_req_ready = 1'b0;
    wire cache_req_bank;
    wire [6:0] cache_req_group;
    reg cache_rsp_valid = 1'b0;
    wire cache_rsp_ready;
    reg cache_rsp_bank = 1'b0;
    reg [6:0] cache_rsp_group = '0;
    reg [4095:0] cache_rsp_u8 = '0;
    reg [383:0] cache_rsp_meta = '0;

    reg gate_meta_valid = 1'b0;
    wire gate_meta_ready;
    reg [223:0] gate_meta = '0;
    reg down_meta_valid = 1'b0;
    wire down_meta_ready;
    reg [223:0] down_meta = '0;

    wire d0_arvalid;
    reg d0_arready = 1'b0;
    wire [31:0] d0_araddr;
    wire [7:0] d0_arlen;
    wire [2:0] d0_arsize;
    wire [1:0] d0_arburst;
    reg d0_rvalid = 1'b0;
    wire d0_rready;
    reg [511:0] d0_rdata = '0;
    reg d0_rlast = 1'b0;
    wire d1_arvalid;
    reg d1_arready = 1'b0;
    wire [31:0] d1_araddr;
    wire [7:0] d1_arlen;
    wire [2:0] d1_arsize;
    wire [1:0] d1_arburst;
    reg d1_rvalid = 1'b0;
    wire d1_rready;
    reg [511:0] d1_rdata = '0;
    reg d1_rlast = 1'b0;

    wire out_valid;
    reg out_ready = 1'b0;
    wire [2:0] out_record_index;
    wire signed [6143:0] projection_s24;

    wire [31:0] gate_d0_raw;
    wire [31:0] gate_d1_raw;
    wire [31:0] gate_d0_elapsed;
    wire [31:0] gate_d1_elapsed;
    wire [31:0] gate_d0_bursts;
    wire [31:0] gate_d1_bursts;
    wire [31:0] gate_d0_ar_stalls;
    wire [31:0] gate_d1_ar_stalls;
    wire [31:0] gate_d0_r_backpressure;
    wire [31:0] gate_d1_r_backpressure;
    wire [31:0] gate_d0_response_idle;
    wire [31:0] gate_d1_response_idle;
    wire [31:0] gate_d0_max_outstanding;
    wire [31:0] gate_d1_max_outstanding;
    wire [63:0] gate_physical;
    wire [63:0] gate_useful;
    wire [31:0] down_d0_raw;
    wire [31:0] down_d1_raw;
    wire [31:0] down_d0_elapsed;
    wire [31:0] down_d1_elapsed;
    wire [31:0] down_d0_bursts;
    wire [31:0] down_d1_bursts;
    wire [31:0] down_d0_ar_stalls;
    wire [31:0] down_d1_ar_stalls;
    wire [31:0] down_d0_r_backpressure;
    wire [31:0] down_d1_r_backpressure;
    wire [31:0] down_d0_response_idle;
    wire [31:0] down_d1_response_idle;
    wire [31:0] down_d0_max_outstanding;
    wire [31:0] down_d1_max_outstanding;
    wire [63:0] down_physical;
    wire [63:0] down_useful;
    wire [31:0] gate_cache_requests;
    wire [31:0] gate_weights;
    wire [31:0] gate_projection_records;
    wire [31:0] product_groups;
    wire [31:0] activation_writes;
    wire [31:0] activation_reads;
    wire [31:0] down_weights;
    wire [31:0] output_records;
    wire [31:0] saturation_count;

    reg [4095:0] cache_u8_mem [0:HIDDEN_GROUPS-1];
    reg [383:0] cache_meta_mem [0:HIDDEN_GROUPS-1];
    reg [2047:0] gate_weight_mem [0:GATE_TX-1];
    reg [223:0] gate_meta_mem [0:GATE_TX-1];
    reg [2047:0] down_weight_mem [0:DOWN_TX-1];
    reg [223:0] down_meta_mem [0:DOWN_TX-1];
    reg [6143:0] expected_mem [0:DOWN_SOURCE_RECORDS-1];
    reg [4095:0] expected_activation_u8_mem [0:0];
    reg [383:0] expected_activation_meta_mem [0:0];

    reg [6:0] cache_fifo [0:CACHE_DEPTH-1];
    integer cache_wr_ptr = 0;
    integer cache_rd_ptr = 0;
    integer cache_count = 0;
    integer cache_requests_seen = 0;
    integer cache_responses_seen = 0;
    integer gate_meta_index = 0;
    integer down_meta_index = 0;
    integer outputs_seen = 0;
    integer core_cycle = 0;
    integer phase_switches = 0;
    reg [2:0] previous_phase = 3'd0;
    reg done_seen = 1'b0;
    reg runtime_error_seen = 1'b0;
    integer mismatches = 0;

    integer d0_cycle = 0;
    integer d0_ar_count = 0;
    integer d0_response = 0;
    integer d0_burst_beat = 0;
    integer d0_outstanding = 0;
    integer d1_cycle = 0;
    integer d1_ar_count = 0;
    integer d1_response = 0;
    integer d1_burst_beat = 0;
    integer d1_outstanding = 0;
    reg [31:0] core_lfsr = 32'h8d71_3b95;
    reg [31:0] d0_lfsr = 32'h16a5_c39d;
    reg [31:0] d1_lfsr = 32'hc713_2f59;
    reg cache_rsp_fire_seen = 1'b0;
    reg gate_meta_fire_seen = 1'b0;
    reg down_meta_fire_seen = 1'b0;
    reg d0_r_fire_seen = 1'b0;
    reg d1_r_fire_seen = 1'b0;

    integer cache_stalls = 0;
    integer response_stalls = 0;
    integer gate_meta_stalls = 0;
    integer down_meta_stalls = 0;
    integer output_stalls = 0;
    integer d0_ar_stall_cycles = 0;
    integer d1_ar_stall_cycles = 0;
    integer d0_r_stall_cycles = 0;
    integer d1_r_stall_cycles = 0;
    integer cache_stability = 0;
    integer response_stability = 0;
    integer gate_meta_stability = 0;
    integer down_meta_stability = 0;
    integer output_stability = 0;
    integer d0_ar_stability = 0;
    integer d1_ar_stability = 0;
    integer d0_r_stability = 0;
    integer d1_r_stability = 0;
    reg held_cache_stall = 1'b0;
    reg [7:0] held_cache_payload = '0;
    reg held_response_stall = 1'b0;
    reg [4487:0] held_response_payload = '0;
    reg held_gate_meta_stall = 1'b0;
    reg [223:0] held_gate_meta = '0;
    reg held_down_meta_stall = 1'b0;
    reg [223:0] held_down_meta = '0;
    reg held_output_stall = 1'b0;
    reg [6146:0] held_output_payload = '0;
    reg held_d0_ar_stall = 1'b0;
    reg [42:0] held_d0_ar_payload = '0;
    reg held_d1_ar_stall = 1'b0;
    reg [42:0] held_d1_ar_payload = '0;
    reg held_d0_r_stall = 1'b0;
    reg [512:0] held_d0_r_payload = '0;
    reg held_d1_r_stall = 1'b0;
    reg [512:0] held_d1_r_payload = '0;

    wire [7:0] cache_payload = {cache_req_bank, cache_req_group};
    wire [4487:0] response_payload = {
        cache_rsp_bank, cache_rsp_group, cache_rsp_meta, cache_rsp_u8
    };
    wire [6146:0] output_payload = {out_record_index, projection_s24};
    wire [42:0] d0_ar_payload = {
        d0_araddr, d0_arlen, d0_arsize, d0_arburst
    };
    wire [42:0] d1_ar_payload = {
        d1_araddr, d1_arlen, d1_arsize, d1_arburst
    };
    wire [512:0] d0_r_payload = {d0_rlast, d0_rdata};
    wire [512:0] d1_r_payload = {d1_rlast, d1_rdata};

    function automatic [2047:0] transaction_weight;
        input integer index;
        begin
            if (index < GATE_TX)
                transaction_weight = gate_weight_mem[index];
            else
                transaction_weight = down_weight_mem[index-GATE_TX];
        end
    endfunction

    function automatic [511:0] channel_beat;
        input integer channel;
        input integer beat_index;
        integer transaction;
        integer half;
        reg [2047:0] word;
        begin
            transaction = beat_index/2;
            half = beat_index%2;
            word = transaction_weight(transaction);
            if (channel == 0)
                channel_beat = word[half*512 +: 512];
            else
                channel_beat = word[1024+half*512 +: 512];
        end
    endfunction

    function automatic [31:0] expected_addr;
        input integer channel;
        input integer burst_index;
        integer phase_burst;
        begin
            if (burst_index < GATE_TX/8)
                expected_addr = (channel ? 32'h2000_0000 :
                    32'h1000_0000) + burst_index*1024;
            else begin
                phase_burst = burst_index-GATE_TX/8;
                expected_addr = (channel ? 32'h2100_0000 :
                    32'h1100_0000) + phase_burst*1024;
            end
        end
    endfunction

    hap_mlp_serial_ddr_command16_v5_s46 #(
        .INTERMEDIATE_COLUMNS(INTERMEDIATE_COLUMNS),
        .HIDDEN_COLUMNS(HIDDEN_COLUMNS),
        .HIDDEN_GROUPS(HIDDEN_GROUPS),
        .DOWN_GROUPS(DOWN_GROUPS),
        .ENFORCE_PRODUCTION_SHAPE(0)
    ) dut (
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_clear(core_clear), .command_pause(command_pause),
        .weight_source_quiescent(), .command_valid(command_valid),
        .command_ready(command_ready), .activation_bank(1'b0),
        .activation_bank_ready(1'b1),
        .gate_ddr0_base_addr(32'h1000_0000),
        .gate_ddr1_base_addr(32'h2000_0000),
        .down_ddr0_base_addr(32'h1100_0000),
        .down_ddr1_base_addr(32'h2100_0000),
        .cache_rd_req_valid(cache_req_valid),
        .cache_rd_req_ready(cache_req_ready),
        .cache_rd_req_bank(cache_req_bank),
        .cache_rd_req_group(cache_req_group),
        .cache_rd_rsp_valid(cache_rsp_valid),
        .cache_rd_rsp_ready(cache_rsp_ready),
        .cache_rd_rsp_bank(cache_rsp_bank),
        .cache_rd_rsp_group(cache_rsp_group),
        .cache_rd_rsp_u8x16x32(cache_rsp_u8),
        .cache_rd_rsp_meta_u24x16(cache_rsp_meta),
        .gate_meta_valid(gate_meta_valid),
        .gate_meta_ready(gate_meta_ready), .gate_meta_u224(gate_meta),
        .down_meta_valid(down_meta_valid),
        .down_meta_ready(down_meta_ready), .down_meta_u224(down_meta),
        .ddr0_clk(ddr0_clk), .ddr0_rst_n(ddr0_rst_n),
        .ddr0_axi_arvalid(d0_arvalid), .ddr0_axi_arready(d0_arready),
        .ddr0_axi_araddr(d0_araddr), .ddr0_axi_arlen(d0_arlen),
        .ddr0_axi_arsize(d0_arsize), .ddr0_axi_arburst(d0_arburst),
        .ddr0_axi_rvalid(d0_rvalid), .ddr0_axi_rready(d0_rready),
        .ddr0_axi_rdata(d0_rdata), .ddr0_axi_rresp(2'b00),
        .ddr0_axi_rlast(d0_rlast),
        .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n),
        .ddr1_axi_arvalid(d1_arvalid), .ddr1_axi_arready(d1_arready),
        .ddr1_axi_araddr(d1_araddr), .ddr1_axi_arlen(d1_arlen),
        .ddr1_axi_arsize(d1_arsize), .ddr1_axi_arburst(d1_arburst),
        .ddr1_axi_rvalid(d1_rvalid), .ddr1_axi_rready(d1_rready),
        .ddr1_axi_rdata(d1_rdata), .ddr1_axi_rresp(2'b00),
        .ddr1_axi_rlast(d1_rlast),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_tile_index(out_record_index),
        .projection_s24x16x16(projection_s24),
        .busy(busy), .done(done), .error(error), .phase(phase),
        .gate_ddr0_raw_beats(gate_d0_raw),
        .gate_ddr1_raw_beats(gate_d1_raw),
        .gate_ddr0_elapsed_cycles(gate_d0_elapsed),
        .gate_ddr1_elapsed_cycles(gate_d1_elapsed),
        .gate_ddr0_bursts(gate_d0_bursts),
        .gate_ddr1_bursts(gate_d1_bursts),
        .gate_ddr0_ar_stalls(gate_d0_ar_stalls),
        .gate_ddr1_ar_stalls(gate_d1_ar_stalls),
        .gate_ddr0_r_backpressure(gate_d0_r_backpressure),
        .gate_ddr1_r_backpressure(gate_d1_r_backpressure),
        .gate_ddr0_response_idle(gate_d0_response_idle),
        .gate_ddr1_response_idle(gate_d1_response_idle),
        .gate_ddr0_max_outstanding(gate_d0_max_outstanding),
        .gate_ddr1_max_outstanding(gate_d1_max_outstanding),
        .gate_physical_bytes(gate_physical),
        .gate_useful_bytes(gate_useful),
        .down_ddr0_raw_beats(down_d0_raw),
        .down_ddr1_raw_beats(down_d1_raw),
        .down_ddr0_elapsed_cycles(down_d0_elapsed),
        .down_ddr1_elapsed_cycles(down_d1_elapsed),
        .down_ddr0_bursts(down_d0_bursts),
        .down_ddr1_bursts(down_d1_bursts),
        .down_ddr0_ar_stalls(down_d0_ar_stalls),
        .down_ddr1_ar_stalls(down_d1_ar_stalls),
        .down_ddr0_r_backpressure(down_d0_r_backpressure),
        .down_ddr1_r_backpressure(down_d1_r_backpressure),
        .down_ddr0_response_idle(down_d0_response_idle),
        .down_ddr1_response_idle(down_d1_response_idle),
        .down_ddr0_max_outstanding(down_d0_max_outstanding),
        .down_ddr1_max_outstanding(down_d1_max_outstanding),
        .down_physical_bytes(down_physical),
        .down_useful_bytes(down_useful),
        .gate_cache_request_count(gate_cache_requests),
        .gate_weight_group_count(gate_weights),
        .gate_projection_tile_count(gate_projection_records),
        .product_group_count(product_groups),
        .down_activation_write_count(activation_writes),
        .down_activation_read_count(activation_reads),
        .down_weight_tile_count(down_weights),
        .output_tile_count(output_records),
        .saturation_count(saturation_count)
    );

    initial begin
        $readmemh("data/mlp_serial_ddr_command16_v5_reduced/cache_u8x16x32.mem", cache_u8_mem);
        $readmemh("data/mlp_serial_ddr_command16_v5_reduced/cache_meta_u24x16.mem", cache_meta_mem);
        $readmemh("data/mlp_serial_ddr_command16_v5_reduced/gate_weights_s4x16x32.mem", gate_weight_mem);
        $readmemh("data/mlp_serial_ddr_command16_v5_reduced/gate_weight_meta_u224.mem", gate_meta_mem);
        $readmemh("data/mlp_serial_ddr_command16_v5_reduced/down_weights_s4x16x32.mem", down_weight_mem);
        $readmemh("data/mlp_serial_ddr_command16_v5_reduced/down_weight_meta_u224.mem", down_meta_mem);
        $readmemh("data/mlp_serial_ddr_command16_v5_reduced/expected_s24x16x16.mem", expected_mem);
        $readmemh("data/mlp_serial_ddr_command16_v5_reduced/expected_activation_u8x16x32.mem", expected_activation_u8_mem);
        $readmemh("data/mlp_serial_ddr_command16_v5_reduced/expected_activation_meta_u24x16.mem", expected_activation_meta_mem);
        repeat (12) @(posedge core_clk);
        core_rst_n <= 1'b1;
        ddr0_rst_n <= 1'b1;
        ddr1_rst_n <= 1'b1;
        repeat (8) @(posedge core_clk);
        command_valid <= 1'b1;
        do @(posedge core_clk); while (!command_ready);
        command_valid <= 1'b0;
    end

    // Elastic core-domain sources.  Once VALID is asserted, neither VALID
    // nor payload is changed until READY accepts it.
    always @(negedge core_clk) begin
        if (!core_rst_n) begin
            cache_req_ready <= 1'b0;
            cache_rsp_valid <= 1'b0;
            gate_meta_valid <= 1'b0;
            down_meta_valid <= 1'b0;
            out_ready <= 1'b0;
        end else begin
            cache_req_ready <= cache_count < CACHE_DEPTH &&
                core_lfsr[0] && core_lfsr[5];
            out_ready <= core_lfsr[1] && core_lfsr[9];
            if (!cache_rsp_valid || cache_rsp_fire_seen) begin
                if (cache_count > 0 &&
                    (core_lfsr[2] && core_lfsr[6])) begin
                    cache_rsp_valid <= 1'b1;
                    cache_rsp_bank <= 1'b0;
                    cache_rsp_group <= cache_fifo[cache_rd_ptr];
                    cache_rsp_u8 <= cache_u8_mem[cache_fifo[cache_rd_ptr]];
                    cache_rsp_meta <= cache_meta_mem[cache_fifo[cache_rd_ptr]];
                end else begin
                    cache_rsp_valid <= 1'b0;
                end
            end
            if (!gate_meta_valid || gate_meta_fire_seen) begin
                if (gate_meta_index < GATE_TX && core_lfsr[3]) begin
                    gate_meta_valid <= 1'b1;
                    gate_meta <= gate_meta_mem[gate_meta_index];
                end else begin
                    gate_meta_valid <= 1'b0;
                end
            end
            if (!down_meta_valid || down_meta_fire_seen) begin
                if (down_meta_index < DOWN_TX && core_lfsr[4]) begin
                    down_meta_valid <= 1'b1;
                    down_meta <= down_meta_mem[down_meta_index];
                end else begin
                    down_meta_valid <= 1'b0;
                end
            end
        end
    end

    always @(posedge core_clk) begin
        if (!core_rst_n) begin
            core_lfsr <= 32'h8d71_3b95;
            cache_rsp_fire_seen <= 1'b0;
            gate_meta_fire_seen <= 1'b0;
            down_meta_fire_seen <= 1'b0;
        end else begin
            cache_rsp_fire_seen <= cache_rsp_valid && cache_rsp_ready;
            gate_meta_fire_seen <= gate_meta_valid && gate_meta_ready;
            down_meta_fire_seen <= down_meta_valid && down_meta_ready;
            core_lfsr <= {core_lfsr[30:0],
                core_lfsr[31]^core_lfsr[21]^core_lfsr[1]^core_lfsr[0]};
            core_cycle <= core_cycle+1;
            if (phase != previous_phase) begin
                if (previous_phase != 0)
                    phase_switches <= phase_switches+1;
                previous_phase <= phase;
            end
            if (cache_req_valid && cache_req_ready) begin
                if (cache_req_bank !== 1'b0 ||
                    cache_req_group !== cache_requests_seen%HIDDEN_GROUPS) begin
                    mismatches <= mismatches+1;
                    $display("MISMATCH: cache request %0d group=%0d", cache_requests_seen, cache_req_group);
                end
                cache_fifo[cache_wr_ptr] <= cache_req_group;
                cache_wr_ptr <= (cache_wr_ptr+1)%CACHE_DEPTH;
                cache_requests_seen <= cache_requests_seen+1;
            end
            if (cache_rsp_valid && cache_rsp_ready) begin
                cache_rd_ptr <= (cache_rd_ptr+1)%CACHE_DEPTH;
                cache_responses_seen <= cache_responses_seen+1;
            end
            case ({cache_req_valid&&cache_req_ready,
                   cache_rsp_valid&&cache_rsp_ready})
                2'b10: cache_count <= cache_count+1;
                2'b01: cache_count <= cache_count-1;
                default: cache_count <= cache_count;
            endcase
            if (gate_meta_valid && gate_meta_ready)
                gate_meta_index <= gate_meta_index+1;
            if (down_meta_valid && down_meta_ready)
                down_meta_index <= down_meta_index+1;
            if (out_valid && out_ready) begin
                if (out_record_index !== outputs_seen ||
                    projection_s24 !== expected_mem[outputs_seen]) begin
                    mismatches <= mismatches+1;
                    $display("MISMATCH: down record=%0d tag=%0d", outputs_seen, out_record_index);
                end
                outputs_seen <= outputs_seen+1;
            end
            if (dut.gate_activation_valid && dut.gate_activation_ready &&
                (dut.gate_activation_u8 !== expected_activation_u8_mem[0] ||
                 dut.gate_activation_meta !== expected_activation_meta_mem[0])) begin
                mismatches <= mismatches+1;
                $display("MISMATCH: gate product activation/cache payload");
            end
            if (error)
                runtime_error_seen <= 1'b1;
            if (done)
                done_seen <= 1'b1;

            if (held_cache_stall) begin
                cache_stability <= cache_stability+1;
                if (!cache_req_valid || cache_payload !== held_cache_payload) begin
                    mismatches <= mismatches+1;
                    $display("MISMATCH: cache request changed under stall");
                end
            end
            if (held_response_stall) begin
                response_stability <= response_stability+1;
                if (!cache_rsp_valid || response_payload !== held_response_payload) begin
                    mismatches <= mismatches+1;
                    $display("MISMATCH: cache response changed under stall");
                end
            end
            if (held_gate_meta_stall) begin
                gate_meta_stability <= gate_meta_stability+1;
                if (!gate_meta_valid || gate_meta !== held_gate_meta) begin
                    mismatches <= mismatches+1;
                    $display("MISMATCH: gate metadata changed under stall");
                end
            end
            if (held_down_meta_stall) begin
                down_meta_stability <= down_meta_stability+1;
                if (!down_meta_valid || down_meta !== held_down_meta) begin
                    mismatches <= mismatches+1;
                    $display("MISMATCH: down metadata changed under stall");
                end
            end
            if (held_output_stall) begin
                output_stability <= output_stability+1;
                if (!out_valid || output_payload !== held_output_payload) begin
                    mismatches <= mismatches+1;
                    $display("MISMATCH: command output changed under stall");
                end
            end
            held_cache_stall <= cache_req_valid && !cache_req_ready;
            held_response_stall <= cache_rsp_valid && !cache_rsp_ready;
            held_gate_meta_stall <= gate_meta_valid && !gate_meta_ready;
            held_down_meta_stall <= down_meta_valid && !down_meta_ready;
            held_output_stall <= out_valid && !out_ready;
            if (cache_req_valid && !cache_req_ready) begin
                held_cache_payload <= cache_payload;
                cache_stalls <= cache_stalls+1;
            end
            if (cache_rsp_valid && !cache_rsp_ready) begin
                held_response_payload <= response_payload;
                response_stalls <= response_stalls+1;
            end
            if (gate_meta_valid && !gate_meta_ready) begin
                held_gate_meta <= gate_meta;
                gate_meta_stalls <= gate_meta_stalls+1;
            end
            if (down_meta_valid && !down_meta_ready) begin
                held_down_meta <= down_meta;
                down_meta_stalls <= down_meta_stalls+1;
            end
            if (out_valid && !out_ready) begin
                held_output_payload <= output_payload;
                output_stalls <= output_stalls+1;
            end
        end
    end

    // AXI sources hold each accepted response beat until RREADY.  A channel
    // starts returning data only after at least one matching AR is accepted.
    always @(negedge ddr0_clk) begin
        if (!ddr0_rst_n) begin
            d0_arready <= 1'b0;
            d0_rvalid <= 1'b0;
            d0_rlast <= 1'b0;
        end else begin
            d0_arready <= d0_lfsr[0] && d0_lfsr[3];
            if (!d0_rvalid || d0_r_fire_seen) begin
                if (d0_outstanding > 0 && d0_response < TOTAL_BEATS &&
                    d0_lfsr[1]) begin
                    d0_rvalid <= 1'b1;
                    d0_rdata <= channel_beat(0, d0_response);
                    d0_rlast <= d0_burst_beat == 15;
                end else begin
                    d0_rvalid <= 1'b0;
                    d0_rlast <= 1'b0;
                end
            end
        end
    end

    always @(negedge ddr1_clk) begin
        if (!ddr1_rst_n) begin
            d1_arready <= 1'b0;
            d1_rvalid <= 1'b0;
            d1_rlast <= 1'b0;
        end else begin
            d1_arready <= d1_lfsr[0] && d1_lfsr[4];
            if (!d1_rvalid || d1_r_fire_seen) begin
                if (d1_outstanding > 0 && d1_response < TOTAL_BEATS &&
                    d1_lfsr[2]) begin
                    d1_rvalid <= 1'b1;
                    d1_rdata <= channel_beat(1, d1_response);
                    d1_rlast <= d1_burst_beat == 15;
                end else begin
                    d1_rvalid <= 1'b0;
                    d1_rlast <= 1'b0;
                end
            end
        end
    end

    always @(posedge ddr0_clk) begin
        if (!ddr0_rst_n) begin
            d0_r_fire_seen <= 1'b0;
        end else begin
            d0_r_fire_seen <= d0_rvalid && d0_rready;
            d0_cycle <= d0_cycle+1;
            d0_lfsr <= {d0_lfsr[30:0],
                d0_lfsr[31]^d0_lfsr[21]^d0_lfsr[1]^d0_lfsr[0]};
            if (d0_arvalid && d0_arready) begin
                if (d0_araddr !== expected_addr(0, d0_ar_count) ||
                    d0_arlen !== 8'd15 || d0_arsize !== 3'd6 ||
                    d0_arburst !== 2'b01) begin
                    mismatches <= mismatches+1;
                    $display("MISMATCH: d0 AR burst=%0d addr=%h", d0_ar_count, d0_araddr);
                end
                d0_ar_count <= d0_ar_count+1;
            end
            if (d0_rvalid && d0_rready) begin
                d0_response <= d0_response+1;
                d0_burst_beat <= d0_burst_beat == 15 ? 0 :
                    d0_burst_beat+1;
            end
            case ({d0_arvalid&&d0_arready,
                   d0_rvalid&&d0_rready&&d0_rlast})
                2'b10: d0_outstanding <= d0_outstanding+1;
                2'b01: d0_outstanding <= d0_outstanding-1;
                default: d0_outstanding <= d0_outstanding;
            endcase
            if (held_d0_ar_stall) begin
                d0_ar_stability <= d0_ar_stability+1;
                if (!d0_arvalid || d0_ar_payload !== held_d0_ar_payload) begin
                    mismatches <= mismatches+1;
                    $display("MISMATCH: d0 AR changed under stall");
                end
            end
            if (held_d0_r_stall) begin
                d0_r_stability <= d0_r_stability+1;
                if (!d0_rvalid || d0_r_payload !== held_d0_r_payload) begin
                    mismatches <= mismatches+1;
                    $display("MISMATCH: d0 R changed under stall");
                end
            end
            held_d0_ar_stall <= d0_arvalid && !d0_arready;
            held_d0_r_stall <= d0_rvalid && !d0_rready;
            if (d0_arvalid && !d0_arready) begin
                held_d0_ar_payload <= d0_ar_payload;
                d0_ar_stall_cycles <= d0_ar_stall_cycles+1;
            end
            if (d0_rvalid && !d0_rready) begin
                held_d0_r_payload <= d0_r_payload;
                d0_r_stall_cycles <= d0_r_stall_cycles+1;
            end
        end
    end

    always @(posedge ddr1_clk) begin
        if (!ddr1_rst_n) begin
            d1_r_fire_seen <= 1'b0;
        end else begin
            d1_r_fire_seen <= d1_rvalid && d1_rready;
            d1_cycle <= d1_cycle+1;
            d1_lfsr <= {d1_lfsr[30:0],
                d1_lfsr[31]^d1_lfsr[21]^d1_lfsr[1]^d1_lfsr[0]};
            if (d1_arvalid && d1_arready) begin
                if (d1_araddr !== expected_addr(1, d1_ar_count) ||
                    d1_arlen !== 8'd15 || d1_arsize !== 3'd6 ||
                    d1_arburst !== 2'b01) begin
                    mismatches <= mismatches+1;
                    $display("MISMATCH: d1 AR burst=%0d addr=%h", d1_ar_count, d1_araddr);
                end
                d1_ar_count <= d1_ar_count+1;
            end
            if (d1_rvalid && d1_rready) begin
                d1_response <= d1_response+1;
                d1_burst_beat <= d1_burst_beat == 15 ? 0 :
                    d1_burst_beat+1;
            end
            case ({d1_arvalid&&d1_arready,
                   d1_rvalid&&d1_rready&&d1_rlast})
                2'b10: d1_outstanding <= d1_outstanding+1;
                2'b01: d1_outstanding <= d1_outstanding-1;
                default: d1_outstanding <= d1_outstanding;
            endcase
            if (held_d1_ar_stall) begin
                d1_ar_stability <= d1_ar_stability+1;
                if (!d1_arvalid || d1_ar_payload !== held_d1_ar_payload) begin
                    mismatches <= mismatches+1;
                    $display("MISMATCH: d1 AR changed under stall");
                end
            end
            if (held_d1_r_stall) begin
                d1_r_stability <= d1_r_stability+1;
                if (!d1_rvalid || d1_r_payload !== held_d1_r_payload) begin
                    mismatches <= mismatches+1;
                    $display("MISMATCH: d1 R changed under stall");
                end
            end
            held_d1_ar_stall <= d1_arvalid && !d1_arready;
            held_d1_r_stall <= d1_rvalid && !d1_rready;
            if (d1_arvalid && !d1_arready) begin
                held_d1_ar_payload <= d1_ar_payload;
                d1_ar_stall_cycles <= d1_ar_stall_cycles+1;
            end
            if (d1_rvalid && !d1_rready) begin
                held_d1_r_payload <= d1_r_payload;
                d1_r_stall_cycles <= d1_r_stall_cycles+1;
            end
        end
    end

    initial begin
        wait (done_seen || core_cycle >= MAX_CYCLES);
        repeat (4) @(posedge core_clk);
        if (!done_seen || runtime_error_seen || error || mismatches != 0 ||
            busy || phase != 0 || gate_meta_index != GATE_TX ||
            down_meta_index != DOWN_TX ||
            cache_requests_seen != GATE_COMPUTE_TX ||
            cache_responses_seen != GATE_COMPUTE_TX || cache_count != 0 ||
            outputs_seen != DOWN_SOURCE_RECORDS ||
            gate_cache_requests != GATE_COMPUTE_TX ||
            gate_weights != GATE_TX ||
            gate_projection_records != GATE_OUTPUT_RECORDS ||
            product_groups != DOWN_GROUPS ||
            activation_writes != DOWN_GROUPS ||
            activation_reads != DOWN_GROUPS || down_weights != DOWN_TX ||
            output_records != DOWN_SOURCE_RECORDS || saturation_count != 0 ||
            gate_d0_raw != GATE_TX*2 || gate_d1_raw != GATE_TX*2 ||
            down_d0_raw != DOWN_TX*2 || down_d1_raw != DOWN_TX*2 ||
            gate_d0_bursts != GATE_TX/8 || gate_d1_bursts != GATE_TX/8 ||
            down_d0_bursts != DOWN_TX/8 || down_d1_bursts != DOWN_TX/8 ||
            gate_physical != GATE_TX*256 || gate_useful != GATE_TX*256 ||
            down_physical != DOWN_TX*256 || down_useful != DOWN_TX*256 ||
            d0_ar_count != TOTAL_TX/8 || d1_ar_count != TOTAL_TX/8 ||
            d0_response != TOTAL_BEATS || d1_response != TOTAL_BEATS ||
            // This integrated shape keeps response READY continuously high;
            // response-side VALID-hold coverage belongs to the independently
            // signed gate-scheduler smoke.  All other external sources and
            // both AXI channels must demonstrate real backpressure here.
            cache_stalls == 0 ||
            gate_meta_stalls == 0 || down_meta_stalls == 0 ||
            output_stalls == 0 || d0_ar_stall_cycles == 0 ||
            d1_ar_stall_cycles == 0 || d0_r_stall_cycles == 0 ||
            d1_r_stall_cycles == 0 || cache_stability == 0 ||
            gate_meta_stability == 0 ||
            down_meta_stability == 0 || output_stability == 0 ||
            d0_ar_stability == 0 || d1_ar_stability == 0 ||
            d0_r_stability == 0 || d1_r_stability == 0) begin
            $display("FAIL: V5 serial reduced done=%0d error=%0d mism=%0d phase=%0d busy=%0d gate=%0d/%0d/%0d down=%0d/%0d outputs=%0d cache=%0d/%0d/%0d bytes=%0d/%0d/%0d/%0d AR=%0d/%0d R=%0d/%0d stalls=%0d/%0d/%0d/%0d/%0d/%0d/%0d/%0d/%0d stable=%0d/%0d/%0d/%0d/%0d/%0d/%0d/%0d/%0d cycles=%0d",
                done_seen, runtime_error_seen||error, mismatches, phase, busy,
                gate_meta_index, gate_weights, gate_projection_records,
                down_meta_index, down_weights, outputs_seen,
                cache_requests_seen, cache_responses_seen, cache_count,
                gate_physical, gate_useful, down_physical, down_useful,
                d0_ar_count, d1_ar_count, d0_response, d1_response,
                cache_stalls, response_stalls, gate_meta_stalls,
                down_meta_stalls, output_stalls, d0_ar_stall_cycles,
                d1_ar_stall_cycles, d0_r_stall_cycles, d1_r_stall_cycles,
                cache_stability, response_stability, gate_meta_stability,
                down_meta_stability, output_stability, d0_ar_stability,
                d1_ar_stability, d0_r_stability, d1_r_stability, core_cycle);
            $fatal(1, "V5 serial reduced end-to-end regression failed");
        end else begin
            $display("PASS: V5 serial reduced end-to-end bit-exact gate_source=%0d gate_internal=%0d gate_records=%0d down_source=%0d down_internal=%0d outputs=%0d physical=%0d/%0d useful=%0d/%0d AR=%0d/%0d R=%0d/%0d stalls=%0d/%0d/%0d/%0d/%0d/%0d/%0d/%0d/%0d stable=%0d/%0d/%0d/%0d/%0d/%0d/%0d/%0d/%0d cycles=%0d mismatches=0",
                gate_weights, gate_cache_requests, gate_projection_records,
                down_weights, DOWN_COMPUTE_TILES, output_records,
                gate_physical, down_physical, gate_useful, down_useful,
                d0_ar_count, d1_ar_count, d0_response, d1_response,
                cache_stalls, response_stalls, gate_meta_stalls,
                down_meta_stalls, output_stalls, d0_ar_stall_cycles,
                d1_ar_stall_cycles, d0_r_stall_cycles, d1_r_stall_cycles,
                cache_stability, response_stability, gate_meta_stability,
                down_meta_stability, output_stability, d0_ar_stability,
                d1_ar_stability, d0_r_stability, d1_r_stability, core_cycle);
            $finish;
        end
    end
endmodule
