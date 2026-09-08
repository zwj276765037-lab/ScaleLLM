`timescale 1ns / 1ps

module hap_mlp_w4_dual_ddr_frontend_tb;
    localparam integer GROUPS = 24;
    localparam integer BEATS = GROUPS*2;
    localparam integer BURSTS = BEATS/16;

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
    wire command_ready;
    wire busy;
    wire done;
    wire error;

    wire d0_arvalid;
    reg d0_arready = 1'b0;
    wire [31:0] d0_araddr;
    wire [7:0] d0_arlen;
    wire [2:0] d0_arsize;
    wire [1:0] d0_arburst;
    reg d0_rvalid = 1'b0;
    wire d0_rready;
    reg [511:0] d0_rdata = '0;
    reg [1:0] d0_rresp = 2'b00;
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
    reg [1:0] d1_rresp = 2'b00;
    reg d1_rlast = 1'b0;

    reg meta_valid = 1'b0;
    wire meta_ready;
    reg [223:0] meta_u224 = '0;
    wire out_valid;
    reg out_ready = 1'b0;
    wire [2047:0] weights_s4x16x32;
    wire [223:0] weight_meta_u224;
    wire [31:0] ddr0_raw_beat_snapshot;
    wire [31:0] ddr1_raw_beat_snapshot;
    wire [31:0] ddr0_elapsed_cycle_snapshot;
    wire [31:0] ddr1_elapsed_cycle_snapshot;
    wire [31:0] ddr0_burst_snapshot;
    wire [31:0] ddr1_burst_snapshot;
    wire [31:0] ddr0_ar_stall_snapshot;
    wire [31:0] ddr1_ar_stall_snapshot;
    wire [31:0] ddr0_r_backpressure_snapshot;
    wire [31:0] ddr1_r_backpressure_snapshot;
    wire [31:0] ddr0_response_idle_snapshot;
    wire [31:0] ddr1_response_idle_snapshot;
    wire [31:0] ddr0_max_outstanding_snapshot;
    wire [31:0] ddr1_max_outstanding_snapshot;
    wire [63:0] physical_read_byte_count;
    wire [63:0] useful_weight_byte_count;
    wire [31:0] useful_group_count;

    integer core_cycle = 0;
    integer meta_send = 0;
    integer output_receive = 0;
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
    reg was_stalled = 1'b0;
    reg [2047:0] held_weight = '0;
    reg [223:0] held_meta = '0;

    function automatic [511:0] beat_pattern;
        input integer channel;
        input integer index;
        integer byte_index;
        begin
            for (byte_index = 0; byte_index < 64; byte_index=byte_index+1)
                beat_pattern[byte_index*8 +: 8] =
                    (channel*109 + index*17 + byte_index*29 + 7) & 8'hff;
        end
    endfunction

    function automatic [223:0] meta_pattern;
        input integer group_index;
        integer byte_index;
        begin
            for (byte_index = 0; byte_index < 28; byte_index=byte_index+1)
                meta_pattern[byte_index*8 +: 8] =
                    (group_index*19 + byte_index*31 + 3) & 8'hff;
        end
    endfunction

    function automatic [2047:0] group_pattern;
        input integer group_index;
        begin
            group_pattern[0 +: 512] =
                beat_pattern(0, group_index*2);
            group_pattern[512 +: 512] =
                beat_pattern(0, group_index*2+1);
            group_pattern[1024 +: 512] =
                beat_pattern(1, group_index*2);
            group_pattern[1536 +: 512] =
                beat_pattern(1, group_index*2+1);
        end
    endfunction

    hap_mlp_w4_dual_ddr_frontend dut (
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_clear(core_clear), .command_valid(command_valid),
        .command_ready(command_ready), .ddr0_base_addr(32'h1000_0000),
        .ddr1_base_addr(32'h2000_0000), .group_count(GROUPS[19:0]),
        .ddr0_clk(ddr0_clk), .ddr0_rst_n(ddr0_rst_n),
        .ddr0_axi_arvalid(d0_arvalid), .ddr0_axi_arready(d0_arready),
        .ddr0_axi_araddr(d0_araddr), .ddr0_axi_arlen(d0_arlen),
        .ddr0_axi_arsize(d0_arsize), .ddr0_axi_arburst(d0_arburst),
        .ddr0_axi_rvalid(d0_rvalid), .ddr0_axi_rready(d0_rready),
        .ddr0_axi_rdata(d0_rdata), .ddr0_axi_rresp(d0_rresp),
        .ddr0_axi_rlast(d0_rlast),
        .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n),
        .ddr1_axi_arvalid(d1_arvalid), .ddr1_axi_arready(d1_arready),
        .ddr1_axi_araddr(d1_araddr), .ddr1_axi_arlen(d1_arlen),
        .ddr1_axi_arsize(d1_arsize), .ddr1_axi_arburst(d1_arburst),
        .ddr1_axi_rvalid(d1_rvalid), .ddr1_axi_rready(d1_rready),
        .ddr1_axi_rdata(d1_rdata), .ddr1_axi_rresp(d1_rresp),
        .ddr1_axi_rlast(d1_rlast),
        .meta_valid(meta_valid), .meta_ready(meta_ready),
        .meta_u224(meta_u224), .out_valid(out_valid),
        .out_ready(out_ready), .weights_s4x16x32(weights_s4x16x32),
        .weight_meta_u224(weight_meta_u224), .busy(busy), .done(done),
        .error(error), .ddr0_raw_beat_snapshot(ddr0_raw_beat_snapshot),
        .ddr1_raw_beat_snapshot(ddr1_raw_beat_snapshot),
        .ddr0_elapsed_cycle_snapshot(ddr0_elapsed_cycle_snapshot),
        .ddr1_elapsed_cycle_snapshot(ddr1_elapsed_cycle_snapshot),
        .ddr0_burst_snapshot(ddr0_burst_snapshot),
        .ddr1_burst_snapshot(ddr1_burst_snapshot),
        .ddr0_ar_stall_snapshot(ddr0_ar_stall_snapshot),
        .ddr1_ar_stall_snapshot(ddr1_ar_stall_snapshot),
        .ddr0_r_backpressure_snapshot(ddr0_r_backpressure_snapshot),
        .ddr1_r_backpressure_snapshot(ddr1_r_backpressure_snapshot),
        .ddr0_response_idle_snapshot(ddr0_response_idle_snapshot),
        .ddr1_response_idle_snapshot(ddr1_response_idle_snapshot),
        .ddr0_max_outstanding_snapshot(ddr0_max_outstanding_snapshot),
        .ddr1_max_outstanding_snapshot(ddr1_max_outstanding_snapshot),
        .physical_read_byte_count(physical_read_byte_count),
        .useful_weight_byte_count(useful_weight_byte_count),
        .useful_group_count(useful_group_count)
    );

    initial begin
        repeat (10) @(posedge core_clk);
        core_rst_n <= 1'b1;
        ddr0_rst_n <= 1'b1;
        ddr1_rst_n <= 1'b1;
        repeat (4) @(posedge core_clk);
        command_valid <= 1'b1;
        do @(posedge core_clk); while (!command_ready);
        command_valid <= 1'b0;
    end

    always @(negedge core_clk) begin
        out_ready <= core_rst_n &&
            !(((core_cycle % 43) >= 27) && ((core_cycle % 43) <= 31));
        if (core_rst_n && busy && meta_send < GROUPS) begin
            meta_valid <= 1'b1;
            meta_u224 <= meta_pattern(meta_send);
        end else begin
            meta_valid <= 1'b0;
        end
    end

    always @(negedge ddr0_clk) begin
        d0_arready <= ddr0_rst_n && (d0_cycle % 11) != 4;
        if (!(d0_rvalid && !d0_rready)) begin
            if (ddr0_rst_n && d0_outstanding > 0 &&
                (d0_cycle % 17) != 6 && d0_response < BEATS) begin
                d0_rvalid <= 1'b1;
                d0_rdata <= beat_pattern(0, d0_response);
                d0_rlast <= d0_burst_beat == 15;
            end else begin
                d0_rvalid <= 1'b0;
                d0_rlast <= 1'b0;
            end
        end
    end

    always @(negedge ddr1_clk) begin
        d1_arready <= ddr1_rst_n && (d1_cycle % 13) != 5;
        if (!(d1_rvalid && !d1_rready)) begin
            if (ddr1_rst_n && d1_outstanding > 0 &&
                (d1_cycle % 19) != 7 && d1_response < BEATS) begin
                d1_rvalid <= 1'b1;
                d1_rdata <= beat_pattern(1, d1_response);
                d1_rlast <= d1_burst_beat == 15;
            end else begin
                d1_rvalid <= 1'b0;
                d1_rlast <= 1'b0;
            end
        end
    end

    always @(posedge ddr0_clk) begin
        if (ddr0_rst_n) begin
            d0_cycle <= d0_cycle + 1;
            if (d0_arvalid && d0_arready) begin
                if (d0_araddr !== 32'h1000_0000 + d0_ar_count*1024 ||
                    d0_arlen !== 15 || d0_arsize !== 6 ||
                    d0_arburst !== 1)
                    $fatal(1, "FAIL DDR0 AR contract burst=%0d", d0_ar_count);
                d0_ar_count <= d0_ar_count + 1;
            end
            if (d0_rvalid && d0_rready) begin
                d0_response <= d0_response + 1;
                if (d0_burst_beat == 15) d0_burst_beat <= 0;
                else d0_burst_beat <= d0_burst_beat + 1;
            end
            case ({d0_arvalid && d0_arready,
                   d0_rvalid && d0_rready && d0_rlast})
                2'b10: d0_outstanding <= d0_outstanding + 1;
                2'b01: d0_outstanding <= d0_outstanding - 1;
                default: d0_outstanding <= d0_outstanding;
            endcase
        end
    end

    always @(posedge ddr1_clk) begin
        if (ddr1_rst_n) begin
            d1_cycle <= d1_cycle + 1;
            if (d1_arvalid && d1_arready) begin
                if (d1_araddr !== 32'h2000_0000 + d1_ar_count*1024 ||
                    d1_arlen !== 15 || d1_arsize !== 6 ||
                    d1_arburst !== 1)
                    $fatal(1, "FAIL DDR1 AR contract burst=%0d", d1_ar_count);
                d1_ar_count <= d1_ar_count + 1;
            end
            if (d1_rvalid && d1_rready) begin
                d1_response <= d1_response + 1;
                if (d1_burst_beat == 15) d1_burst_beat <= 0;
                else d1_burst_beat <= d1_burst_beat + 1;
            end
            case ({d1_arvalid && d1_arready,
                   d1_rvalid && d1_rready && d1_rlast})
                2'b10: d1_outstanding <= d1_outstanding + 1;
                2'b01: d1_outstanding <= d1_outstanding - 1;
                default: d1_outstanding <= d1_outstanding;
            endcase
        end
    end

    always @(posedge core_clk) begin
        if (core_rst_n) begin
            core_cycle <= core_cycle + 1;
            if (meta_valid && meta_ready)
                meta_send <= meta_send + 1;
            if (was_stalled && (!out_valid ||
                weights_s4x16x32 !== held_weight ||
                weight_meta_u224 !== held_meta))
                $fatal(1, "FAIL frontend output changed under backpressure");
            was_stalled <= out_valid && !out_ready;
            if (out_valid && !out_ready) begin
                held_weight <= weights_s4x16x32;
                held_meta <= weight_meta_u224;
            end
            if (out_valid && out_ready) begin
                if (weights_s4x16x32 !== group_pattern(output_receive) ||
                    weight_meta_u224 !== meta_pattern(output_receive))
                    $fatal(1, "FAIL frontend output mismatch group=%0d",
                        output_receive);
                output_receive <= output_receive + 1;
            end
            if (done) begin
                if (output_receive != GROUPS || meta_send != GROUPS ||
                    d0_ar_count != BURSTS || d1_ar_count != BURSTS ||
                    d0_response != BEATS || d1_response != BEATS ||
                    ddr0_raw_beat_snapshot != BEATS ||
                    ddr1_raw_beat_snapshot != BEATS ||
                    ddr0_burst_snapshot != BURSTS ||
                    ddr1_burst_snapshot != BURSTS ||
                    physical_read_byte_count != GROUPS*256 ||
                    useful_weight_byte_count != GROUPS*256 ||
                    useful_group_count != GROUPS ||
                    ddr0_elapsed_cycle_snapshot <= BEATS ||
                    ddr1_elapsed_cycle_snapshot <= BEATS)
                    $fatal(1, "FAIL snapshot out=%0d meta=%0d d0beat=%0d d1beat=%0d d0elapsed=%0d d1elapsed=%0d physical=%0d useful=%0d",
                        output_receive, meta_send,
                        ddr0_raw_beat_snapshot, ddr1_raw_beat_snapshot,
                        ddr0_elapsed_cycle_snapshot,
                        ddr1_elapsed_cycle_snapshot,
                        physical_read_byte_count,
                        useful_weight_byte_count);
                $display("MLP_W4_DUAL_DDR_FRONTEND_METRIC_JSON: {\"groups\":24,\"bursts_per_channel\":3,\"beats_per_channel\":48,\"physical_bytes\":6144,\"useful_bytes\":6144,\"ddr0_elapsed\":%0d,\"ddr1_elapsed\":%0d}",
                    ddr0_elapsed_cycle_snapshot,
                    ddr1_elapsed_cycle_snapshot);
                $display("PASS: MLP W4 dual DDR frontend preserved payload/order across three clocks and returned atomic counter snapshots.");
                $finish;
            end
            if (error)
                $fatal(1, "FAIL frontend sticky error cycle=%0d", core_cycle);
            if (core_cycle > 3000)
                $fatal(1, "FAIL frontend timeout out=%0d meta=%0d d0=%0d d1=%0d",
                    output_receive, meta_send, d0_response, d1_response);
        end
    end
endmodule
