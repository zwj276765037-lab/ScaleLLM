`timescale 1ns / 1ps

module hap_mlp_down_ddr_command16_s45_tb;
    localparam integer GROUPS = 4;
    localparam integer TILES = 4;
    localparam integer TRANSACTIONS = GROUPS*TILES;
    localparam integer BEATS = TRANSACTIONS*2;
    localparam integer BURSTS = BEATS/16;
    reg core_clk = 1'b0;
    reg ddr0_clk = 1'b0;
    reg ddr1_clk = 1'b0;
    always #3.3335 core_clk = ~core_clk;
    always #1.6665 ddr0_clk = ~ddr0_clk;
    always #1.6675 ddr1_clk = ~ddr1_clk;
    reg core_rst_n = 1'b0, ddr0_rst_n = 1'b0, ddr1_rst_n = 1'b0;
    reg core_clear = 1'b0, command_valid = 1'b0;
    wire command_ready, busy, done, error;

    wire d0_arvalid, d0_rready;
    reg d0_arready = 1'b0, d0_rvalid = 1'b0, d0_rlast = 1'b0;
    wire [31:0] d0_araddr;
    wire [7:0] d0_arlen;
    wire [2:0] d0_arsize;
    wire [1:0] d0_arburst;
    reg [511:0] d0_rdata = '0;
    wire d1_arvalid, d1_rready;
    reg d1_arready = 1'b0, d1_rvalid = 1'b0, d1_rlast = 1'b0;
    wire [31:0] d1_araddr;
    wire [7:0] d1_arlen;
    wire [2:0] d1_arsize;
    wire [1:0] d1_arburst;
    reg [511:0] d1_rdata = '0;

    wire activation_valid, activation_ready;
    wire [4095:0] activation_u8x16x32;
    wire [383:0] activation_meta_u24x16;
    wire weight_meta_valid, weight_meta_ready;
    wire [223:0] weight_meta_u224;
    wire out_valid;
    reg out_ready = 1'b0;
    wire [1:0] out_tile_index;
    wire signed [6143:0] projection_s24x16x16;
    wire [31:0] activation_group_count, weight_tile_count;
    wire [31:0] output_tile_count, saturation_count;
    wire [31:0] ddr0_raw_beat_snapshot, ddr1_raw_beat_snapshot;
    wire [31:0] ddr0_elapsed_cycle_snapshot, ddr1_elapsed_cycle_snapshot;
    wire [63:0] physical_read_byte_count, useful_weight_byte_count;

    reg [4095:0] activation_mem [0:GROUPS-1];
    reg [383:0] activation_meta_mem [0:GROUPS-1];
    reg [2047:0] weights_mem [0:TRANSACTIONS-1];
    reg [223:0] weight_meta_mem [0:TRANSACTIONS-1];
    reg [6143:0] expected_mem [0:TILES-1];
    integer core_cycle=0, activation_send=0, meta_send=0, output_receive=0;
    integer d0_cycle=0, d0_ar_count=0, d0_response=0;
    integer d0_burst_beat=0, d0_outstanding=0;
    integer d1_cycle=0, d1_ar_count=0, d1_response=0;
    integer d1_burst_beat=0, d1_outstanding=0;
    wire [1:0] activation_source = activation_send < GROUPS ?
        activation_send : GROUPS-1;
    wire [4:0] meta_source = meta_send < TRANSACTIONS ?
        meta_send : TRANSACTIONS-1;

    assign activation_valid = activation_send < GROUPS &&
        (core_cycle % 5) != 1;
    assign activation_u8x16x32 = activation_mem[activation_source];
    assign activation_meta_u24x16 = activation_meta_mem[activation_source];
    assign weight_meta_valid = meta_send < TRANSACTIONS &&
        (core_cycle % 7) != 2;
    assign weight_meta_u224 = weight_meta_mem[meta_source];

    function automatic [511:0] channel_beat;
        input integer channel;
        input integer beat_index;
        integer transaction;
        integer half_beat;
        begin
            transaction = beat_index/2;
            half_beat = beat_index%2;
            if (channel == 0)
                channel_beat = weights_mem[transaction][half_beat*512 +: 512];
            else
                channel_beat = weights_mem[transaction][1024+half_beat*512 +: 512];
        end
    endfunction

    hap_mlp_down_ddr_command16_s45 #(
        .TILES(TILES), .GROUPS(GROUPS)
    ) dut (
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_clear(core_clear), .command_valid(command_valid),
        .command_ready(command_ready), .ddr0_base_addr(32'h1000_0000),
        .ddr1_base_addr(32'h2000_0000),
        .activation_valid(activation_valid),
        .activation_ready(activation_ready),
        .activation_u8x16x32(activation_u8x16x32),
        .activation_meta_u24x16(activation_meta_u24x16),
        .weight_meta_valid(weight_meta_valid),
        .weight_meta_ready(weight_meta_ready),
        .weight_meta_u224(weight_meta_u224),
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
        .ddr1_axi_rlast(d1_rlast), .out_valid(out_valid),
        .out_ready(out_ready), .out_tile_index(out_tile_index),
        .projection_s24x16x16(projection_s24x16x16), .busy(busy),
        .done(done), .error(error),
        .activation_group_count(activation_group_count),
        .weight_tile_count(weight_tile_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count),
        .ddr0_raw_beat_snapshot(ddr0_raw_beat_snapshot),
        .ddr1_raw_beat_snapshot(ddr1_raw_beat_snapshot),
        .ddr0_elapsed_cycle_snapshot(ddr0_elapsed_cycle_snapshot),
        .ddr1_elapsed_cycle_snapshot(ddr1_elapsed_cycle_snapshot),
        .physical_read_byte_count(physical_read_byte_count),
        .useful_weight_byte_count(useful_weight_byte_count)
    );

    initial begin
        $readmemh("data/mlp_down_ddr_command16_s45/activation_u8x16x32.mem", activation_mem);
        $readmemh("data/mlp_down_ddr_command16_s45/activation_meta_u24x16.mem", activation_meta_mem);
        $readmemh("data/mlp_down_ddr_command16_s45/weights_s4x16x32.mem", weights_mem);
        $readmemh("data/mlp_down_ddr_command16_s45/weight_meta_u224.mem", weight_meta_mem);
        $readmemh("data/mlp_down_ddr_command16_s45/expected_s24x16x16.mem", expected_mem);
        repeat (10) @(posedge core_clk);
        core_rst_n <= 1'b1; ddr0_rst_n <= 1'b1; ddr1_rst_n <= 1'b1;
        repeat (4) @(posedge core_clk);
        command_valid <= 1'b1;
        do @(posedge core_clk); while (!command_ready);
        command_valid <= 1'b0;
    end

    always @(negedge core_clk)
        out_ready <= core_rst_n && (core_cycle%9 != 4);

    always @(negedge ddr0_clk) begin
        d0_arready <= ddr0_rst_n && d0_cycle%11 != 4;
        if (!(d0_rvalid && !d0_rready)) begin
            if (ddr0_rst_n && d0_outstanding > 0 &&
                d0_cycle%17 != 6 && d0_response < BEATS) begin
                d0_rvalid <= 1'b1;
                d0_rdata <= channel_beat(0, d0_response);
                d0_rlast <= d0_burst_beat == 15;
            end else begin d0_rvalid <= 1'b0; d0_rlast <= 1'b0; end
        end
    end
    always @(negedge ddr1_clk) begin
        d1_arready <= ddr1_rst_n && d1_cycle%13 != 5;
        if (!(d1_rvalid && !d1_rready)) begin
            if (ddr1_rst_n && d1_outstanding > 0 &&
                d1_cycle%19 != 7 && d1_response < BEATS) begin
                d1_rvalid <= 1'b1;
                d1_rdata <= channel_beat(1, d1_response);
                d1_rlast <= d1_burst_beat == 15;
            end else begin d1_rvalid <= 1'b0; d1_rlast <= 1'b0; end
        end
    end

    always @(posedge ddr0_clk) if (ddr0_rst_n) begin
        d0_cycle <= d0_cycle+1;
        if (d0_arvalid && d0_arready) begin
            if (d0_araddr !== 32'h1000_0000+d0_ar_count*1024 ||
                d0_arlen !== 15 || d0_arsize !== 6 || d0_arburst !== 1)
                $fatal(1, "FAIL DDR0 AR contract");
            d0_ar_count <= d0_ar_count+1;
        end
        if (d0_rvalid && d0_rready) begin
            d0_response <= d0_response+1;
            d0_burst_beat <= d0_burst_beat == 15 ? 0 : d0_burst_beat+1;
        end
        case ({d0_arvalid&&d0_arready,d0_rvalid&&d0_rready&&d0_rlast})
            2'b10: d0_outstanding <= d0_outstanding+1;
            2'b01: d0_outstanding <= d0_outstanding-1;
            default: d0_outstanding <= d0_outstanding;
        endcase
    end
    always @(posedge ddr1_clk) if (ddr1_rst_n) begin
        d1_cycle <= d1_cycle+1;
        if (d1_arvalid && d1_arready) begin
            if (d1_araddr !== 32'h2000_0000+d1_ar_count*1024 ||
                d1_arlen !== 15 || d1_arsize !== 6 || d1_arburst !== 1)
                $fatal(1, "FAIL DDR1 AR contract");
            d1_ar_count <= d1_ar_count+1;
        end
        if (d1_rvalid && d1_rready) begin
            d1_response <= d1_response+1;
            d1_burst_beat <= d1_burst_beat == 15 ? 0 : d1_burst_beat+1;
        end
        case ({d1_arvalid&&d1_arready,d1_rvalid&&d1_rready&&d1_rlast})
            2'b10: d1_outstanding <= d1_outstanding+1;
            2'b01: d1_outstanding <= d1_outstanding-1;
            default: d1_outstanding <= d1_outstanding;
        endcase
    end

    always @(posedge core_clk) if (core_rst_n) begin
        core_cycle <= core_cycle+1;
        if (activation_valid && activation_ready)
            activation_send <= activation_send+1;
        if (weight_meta_valid && weight_meta_ready)
            meta_send <= meta_send+1;
        if (out_valid && out_ready) begin
            if (out_tile_index !== output_receive ||
                projection_s24x16x16 !== expected_mem[output_receive])
                $fatal(1, "FAIL output tile=%0d got_tile=%0d",
                    output_receive, out_tile_index);
            output_receive <= output_receive+1;
        end
        if (done) begin
            if (activation_send != GROUPS || meta_send != TRANSACTIONS ||
                output_receive != TILES || activation_group_count != GROUPS ||
                weight_tile_count != TRANSACTIONS || output_tile_count != TILES ||
                saturation_count != 0 || d0_ar_count != BURSTS ||
                d1_ar_count != BURSTS || ddr0_raw_beat_snapshot != BEATS ||
                ddr1_raw_beat_snapshot != BEATS ||
                physical_read_byte_count != TRANSACTIONS*256 ||
                useful_weight_byte_count != TRANSACTIONS*256)
                $fatal(1, "FAIL completion a=%0d m=%0d o=%0d beats=%0d/%0d physical=%0d useful=%0d",
                    activation_send, meta_send, output_receive,
                    ddr0_raw_beat_snapshot, ddr1_raw_beat_snapshot,
                    physical_read_byte_count, useful_weight_byte_count);
            $display("PASS: hap_mlp_down_ddr_command16_s45 groups=%0d tiles=%0d transactions=%0d outputs=%0d physical_bytes=%0d useful_bytes=%0d ddr_elapsed=%0d/%0d cycles=%0d",
                GROUPS, TILES, TRANSACTIONS, 16*16*TILES,
                physical_read_byte_count, useful_weight_byte_count,
                ddr0_elapsed_cycle_snapshot, ddr1_elapsed_cycle_snapshot,
                core_cycle);
            $finish;
        end
        if (error) $fatal(1, "FAIL sticky error cycle=%0d", core_cycle);
        if (core_cycle > 3000)
            $fatal(1, "FAIL timeout a=%0d m=%0d o=%0d d0=%0d d1=%0d",
                activation_send, meta_send, output_receive,
                d0_response, d1_response);
    end
endmodule
