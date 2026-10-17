`timescale 1ns / 1ps

// Source-only candidate for the production three-clock paired read transport.
// Deterministic phase offsets (0, 0.8, 1.7 ns) exercise distinct sampling
// phases at core 10 ns and both DDR UI 5 ns; they do not prove clock closure.
module hap_axi512_paired_2client_read_wrr_rebuild_cdc_tb;
  localparam integer MAX_REQ = 32;
  reg core_clk = 0, ddr0_clk = 0, ddr1_clk = 0;
  always #5 core_clk = ~core_clk;
  initial begin #0.8; forever #2.5 ddr0_clk = ~ddr0_clk; end
  initial begin #1.7; forever #2.5 ddr1_clk = ~ddr1_clk; end

  reg core_rst_n = 0, ddr0_rst_n = 0, ddr1_rst_n = 0;
  reg core_clear = 0, core_enable = 0, ddr0_enable = 0, ddr1_enable = 0;
  reg epoch_reset = 1, source_go = 0, hold_responses = 0;
  reg block_clients = 0, monitor_live = 0;
  integer epoch = 1;
  integer src_target [0:3];
  integer src_sent [0:3];
  reg [3:0] src_valid = 0;
  wire [3:0] src_ready, client_valid, client_ready;
  wire [31:0] src_addr [0:3];
  wire [7:0] src_len [0:3];
  wire [511:0] client_data [0:3];
  wire [1:0] client_resp [0:3];
  wire [3:0] client_last;
  wire maintenance_pause_sources, maintenance_drain_active;
  wire maintenance_soft_clear_pulse, core_quiescent, error;
  wire [31:0] accepted_attn_bursts, accepted_mlp_bursts;
  wire [31:0] both_eligible_cycles, p0_hol_cycles, p1_hol_cycles;
  wire [31:0] p0_tag_high_watermark, p1_tag_high_watermark;

  wire p0_arvalid, p1_arvalid, p0_arready, p1_arready;
  wire [31:0] p0_araddr, p1_araddr;
  wire [7:0] p0_arlen, p1_arlen;
  wire [2:0] p0_arsize, p1_arsize;
  wire [1:0] p0_arburst, p1_arburst;
  reg p0_rvalid = 0, p1_rvalid = 0;
  wire p0_rready, p1_rready;
  reg [511:0] p0_rdata = 0, p1_rdata = 0;
  reg p0_rlast = 0, p1_rlast = 0;

  integer checks = 0, cases = 0, core_cycles = 0;
  integer ddr0_cycles = 0, ddr1_cycles = 0;
  integer total_ddr0_cycles = 0, total_ddr1_cycles = 0;
  integer source_stalls = 0, physical_ar_stalls = 0, client_stalls = 0;
  integer physical_r_stalls = 0, total_physical_beats = 0;
  integer total_client_beats = 0, total_source_requests = 0;
  integer total_physical_ars = 0, discarded_source_requests = 0;
  integer reset_events = 0, soft_clear_pulses = 0;
  reg saw_maintenance_core_reset = 0;
  reg saw_maintenance_ddr0_reset = 0, saw_maintenance_ddr1_reset = 0;
  integer ar_wr [0:1], ar_rd [0:1], response_beat [0:1];
  integer physical_beats [0:1], client_beats [0:3];
  integer client_id [0:3], client_beat [0:3];
  reg [31:0] ar_addr [0:1][0:MAX_REQ-1];
  reg [7:0] ar_len [0:1][0:MAX_REQ-1];
  reg ar_owner [0:1][0:MAX_REQ-1];
  integer ar_id [0:1][0:MAX_REQ-1];
  reg ar_seen [0:1][0:1][0:MAX_REQ-1];
  reg [1:0] ar_was_stalled = 0;
  reg [31:0] held_ar_addr [0:1];
  reg [7:0] held_ar_len [0:1];
  reg [2:0] held_ar_size [0:1];
  reg [1:0] held_ar_burst [0:1];
  reg [3:0] source_was_stalled = 0, client_was_stalled = 0;
  reg [31:0] held_source_addr [0:3];
  reg [7:0] held_source_len [0:3];
  reg [511:0] held_client_data [0:3];
  reg [1:0] held_client_resp [0:3];
  reg [3:0] held_client_last = 0;

  function automatic [31:0] address_for;
    input integer port_index, request_id, epoch_id;
    reg [31:0] base;
    begin
      case (port_index)
        0: base = 32'hA000_0000;
        1: base = 32'hB000_0000;
        2: base = 32'hA100_0000;
        default: base = 32'hB100_0000;
      endcase
      address_for = base | (epoch_id << 16) | (request_id << 11);
    end
  endfunction

  function automatic [7:0] length_for;
    input integer owner, request_id;
    begin
      case ((owner + request_id) % 4)
        0: length_for = 8'd3;
        1: length_for = 8'd7;
        2: length_for = 8'd15;
        default: length_for = 8'd31;
      endcase
    end
  endfunction

  function automatic [511:0] make_data;
    input [31:0] address;
    input integer beat, channel;
    integer word_index;
    reg [511:0] value;
    begin
      value = 0;
      for (word_index = 0; word_index < 16; word_index = word_index + 1)
        value[word_index*32 +: 32] = address ^
          (32'h9e37_79b9 * (word_index + 1)) ^
          (32'h0001_0101 * beat) ^ (32'h1357_9bdf * channel);
      value[31:0] = address;
      value[63:32] = beat;
      value[95:64] = channel;
      make_data = value;
    end
  endfunction

  task automatic require_true;
    input condition;
    input [8*128-1:0] message;
    begin
      checks = checks + 1;
      if (condition !== 1'b1)
        $fatal(1, "FAIL t=%0t check=%0d epoch=%0d %0s",
          $time, checks, epoch, message);
    end
  endtask

  genvar g;
  generate for (g = 0; g < 4; g = g + 1) begin : source_wires
    assign src_addr[g] = address_for(g, src_sent[g], epoch);
    assign src_len[g] = length_for(g % 2, src_sent[g]);
  end endgenerate
  assign client_ready[0] = !epoch_reset && !block_clients &&
    ((ddr0_cycles % 7) >= 3);
  assign client_ready[1] = !epoch_reset && !block_clients &&
    ((ddr0_cycles % 11) >= 4);
  assign client_ready[2] = !epoch_reset && !block_clients &&
    ((ddr1_cycles % 9) >= 4);
  assign client_ready[3] = !epoch_reset && !block_clients &&
    ((ddr1_cycles % 13) >= 5);
  assign p0_arready = !epoch_reset && ddr0_rst_n &&
    ((ddr0_cycles % 5) >= 2);
  assign p1_arready = !epoch_reset && ddr1_rst_n &&
    ((ddr1_cycles % 7) >= 3);

  hap_axi512_paired_2client_read_wrr dut (
    .core_clk(core_clk), .core_rst_n(core_rst_n), .core_clear(core_clear),
    .core_enable(core_enable),
    .attn_source_quiescent(!src_valid[0] && !src_valid[2]),
    .mlp_source_quiescent(!src_valid[1] && !src_valid[3]),
    .maintenance_pause_sources(maintenance_pause_sources),
    .maintenance_drain_active(maintenance_drain_active),
    .maintenance_soft_clear_pulse(maintenance_soft_clear_pulse),
    .ddr0_clk(ddr0_clk), .ddr0_rst_n(ddr0_rst_n), .ddr0_enable(ddr0_enable),
    .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n), .ddr1_enable(ddr1_enable),
    .a0_arvalid(src_valid[0]), .a0_arready(src_ready[0]),
    .a0_araddr(src_addr[0]), .a0_arlen(src_len[0]), .a0_arsize(3'd6),
    .a0_arburst(2'b01), .a0_rvalid(client_valid[0]),
    .a0_rready(client_ready[0]), .a0_rdata(client_data[0]),
    .a0_rresp(client_resp[0]), .a0_rlast(client_last[0]),
    .m0_arvalid(src_valid[1]), .m0_arready(src_ready[1]),
    .m0_araddr(src_addr[1]), .m0_arlen(src_len[1]), .m0_arsize(3'd6),
    .m0_arburst(2'b01), .m0_rvalid(client_valid[1]),
    .m0_rready(client_ready[1]), .m0_rdata(client_data[1]),
    .m0_rresp(client_resp[1]), .m0_rlast(client_last[1]),
    .a1_arvalid(src_valid[2]), .a1_arready(src_ready[2]),
    .a1_araddr(src_addr[2]), .a1_arlen(src_len[2]), .a1_arsize(3'd6),
    .a1_arburst(2'b01), .a1_rvalid(client_valid[2]),
    .a1_rready(client_ready[2]), .a1_rdata(client_data[2]),
    .a1_rresp(client_resp[2]), .a1_rlast(client_last[2]),
    .m1_arvalid(src_valid[3]), .m1_arready(src_ready[3]),
    .m1_araddr(src_addr[3]), .m1_arlen(src_len[3]), .m1_arsize(3'd6),
    .m1_arburst(2'b01), .m1_rvalid(client_valid[3]),
    .m1_rready(client_ready[3]), .m1_rdata(client_data[3]),
    .m1_rresp(client_resp[3]), .m1_rlast(client_last[3]),
    .p0_arvalid(p0_arvalid), .p0_arready(p0_arready),
    .p0_araddr(p0_araddr), .p0_arlen(p0_arlen),
    .p0_arsize(p0_arsize), .p0_arburst(p0_arburst),
    .p0_rvalid(p0_rvalid), .p0_rready(p0_rready),
    .p0_rdata(p0_rdata), .p0_rresp(2'b00), .p0_rlast(p0_rlast),
    .p1_arvalid(p1_arvalid), .p1_arready(p1_arready),
    .p1_araddr(p1_araddr), .p1_arlen(p1_arlen),
    .p1_arsize(p1_arsize), .p1_arburst(p1_arburst),
    .p1_rvalid(p1_rvalid), .p1_rready(p1_rready),
    .p1_rdata(p1_rdata), .p1_rresp(2'b00), .p1_rlast(p1_rlast),
    .core_quiescent(core_quiescent), .error(error),
    .accepted_attn_bursts(accepted_attn_bursts),
    .accepted_mlp_bursts(accepted_mlp_bursts),
    .both_eligible_cycles(both_eligible_cycles),
    .p0_hol_cycles(p0_hol_cycles), .p1_hol_cycles(p1_hol_cycles),
    .p0_tag_high_watermark(p0_tag_high_watermark),
    .p1_tag_high_watermark(p1_tag_high_watermark)
  );

  task automatic check_source;
    input integer port_index;
    begin
      require_true(src_valid[port_index] === 1'b0 ||
        src_valid[port_index] === 1'b1, "source VALID unknown");
      require_true(src_ready[port_index] === 1'b0 ||
        src_ready[port_index] === 1'b1, "source READY unknown");
      if (source_was_stalled[port_index])
        require_true(src_valid[port_index] === 1'b1 &&
          src_addr[port_index] === held_source_addr[port_index] &&
          src_len[port_index] === held_source_len[port_index],
          "source AR changed during stall");
      source_was_stalled[port_index] =
        src_valid[port_index] === 1'b1 && src_ready[port_index] === 1'b0;
      if (source_was_stalled[port_index]) begin
        held_source_addr[port_index] = src_addr[port_index];
        held_source_len[port_index] = src_len[port_index];
        source_stalls = source_stalls + 1;
      end
      if (src_valid[port_index] === 1'b1 &&
          src_ready[port_index] === 1'b1)
        total_source_requests = total_source_requests + 1;
    end
  endtask

  task automatic check_client;
    input integer port_index, channel;
    reg [31:0] expected_addr;
    reg [7:0] expected_len;
    begin
      require_true(client_valid[port_index] === 1'b0 ||
        client_valid[port_index] === 1'b1, "client VALID unknown");
      require_true(client_ready[port_index] === 1'b0 ||
        client_ready[port_index] === 1'b1, "client READY unknown");
      if (client_was_stalled[port_index])
        require_true(client_valid[port_index] === 1'b1 &&
          client_data[port_index] === held_client_data[port_index] &&
          client_resp[port_index] === held_client_resp[port_index] &&
          client_last[port_index] === held_client_last[port_index],
          "client R changed during stall");
      client_was_stalled[port_index] =
        client_valid[port_index] === 1'b1 &&
        client_ready[port_index] === 1'b0;
      if (client_was_stalled[port_index]) begin
        held_client_data[port_index] = client_data[port_index];
        held_client_resp[port_index] = client_resp[port_index];
        held_client_last[port_index] = client_last[port_index];
        client_stalls = client_stalls + 1;
      end
      if (client_valid[port_index] === 1'b1 &&
          client_ready[port_index] === 1'b1) begin
        require_true(client_id[port_index] < src_target[port_index],
          "duplicate or unsolicited client response");
        expected_addr = address_for(port_index, client_id[port_index], epoch);
        expected_len = length_for(port_index % 2, client_id[port_index]);
        require_true(client_data[port_index] ===
          make_data(expected_addr, client_beat[port_index], channel),
          "client payload lost, duplicated, reordered, or misrouted");
        require_true(client_resp[port_index] === 2'b00 &&
          client_last[port_index] ===
            (client_beat[port_index] == expected_len),
          "client response framing mismatch");
        client_beats[port_index] = client_beats[port_index] + 1;
        total_client_beats = total_client_beats + 1;
        if (client_beat[port_index] == expected_len) begin
          client_id[port_index] = client_id[port_index] + 1;
          client_beat[port_index] = 0;
        end else client_beat[port_index] = client_beat[port_index] + 1;
      end
    end
  endtask

  task automatic check_physical_ar;
    input integer channel;
    input valid, ready;
    input [31:0] addr;
    input [7:0] burst_len;
    input [2:0] burst_size;
    input [1:0] burst_type;
    integer id, owner, port_index;
    begin
      require_true(valid === 1'b0 || valid === 1'b1,
        "physical ARVALID unknown");
      require_true(ready === 1'b0 || ready === 1'b1,
        "physical ARREADY unknown");
      if (ar_was_stalled[channel])
        require_true(valid === 1'b1 && addr === held_ar_addr[channel] &&
          burst_len === held_ar_len[channel] &&
          burst_size === held_ar_size[channel] &&
          burst_type === held_ar_burst[channel],
          "physical AR changed during stall");
      ar_was_stalled[channel] = valid === 1'b1 && ready === 1'b0;
      if (ar_was_stalled[channel]) begin
        held_ar_addr[channel] = addr;
        held_ar_len[channel] = burst_len;
        held_ar_size[channel] = burst_size;
        held_ar_burst[channel] = burst_type;
        physical_ar_stalls = physical_ar_stalls + 1;
      end
      if (valid === 1'b1 && ready === 1'b1) begin
        require_true(ar_wr[channel] < MAX_REQ, "physical AR log overflow");
        owner = (addr[31:28] == 4'hB);
        id = addr[15:11];
        port_index = 2*channel + owner;
        require_true(id < src_target[port_index] &&
          addr === address_for(port_index, id, epoch) &&
          burst_len === length_for(owner, id) &&
          burst_size === 3'd6 && burst_type === 2'b01,
          "physical AR shape, epoch, address, or owner mismatch");
        require_true(ar_seen[channel][owner][id] === 1'b0,
          "duplicate physical AR");
        ar_seen[channel][owner][id] = 1'b1;
        ar_addr[channel][ar_wr[channel]] = addr;
        ar_len[channel][ar_wr[channel]] = burst_len;
        ar_owner[channel][ar_wr[channel]] = owner;
        ar_id[channel][ar_wr[channel]] = id;
        ar_wr[channel] = ar_wr[channel] + 1;
        total_physical_ars = total_physical_ars + 1;
      end
    end
  endtask

  // Client sources are independent of the core scheduler. Each presented
  // request remains valid until its own DDR-domain READY handshake.
  always @(posedge ddr0_clk or posedge epoch_reset) begin
    if (epoch_reset || !ddr0_rst_n) begin
      src_valid[0] <= 0; src_valid[1] <= 0;
      src_sent[0] <= 0; src_sent[1] <= 0;
    end else begin
      if (monitor_live) begin check_source(0); check_source(1); end
      if (src_valid[0] && src_ready[0]) begin
        src_sent[0] <= src_sent[0] + 1;
        if (src_sent[0] + 1 >= src_target[0] || !source_go)
          src_valid[0] <= 0;
      end else if (!src_valid[0] && source_go &&
                   !maintenance_pause_sources && src_sent[0] < src_target[0])
        src_valid[0] <= 1;
      if (src_valid[1] && src_ready[1]) begin
        src_sent[1] <= src_sent[1] + 1;
        if (src_sent[1] + 1 >= src_target[1] || !source_go)
          src_valid[1] <= 0;
      end else if (!src_valid[1] && source_go &&
                   !maintenance_pause_sources && src_sent[1] < src_target[1])
        src_valid[1] <= 1;
    end
  end
  always @(posedge ddr1_clk or posedge epoch_reset) begin
    if (epoch_reset || !ddr1_rst_n) begin
      src_valid[2] <= 0; src_valid[3] <= 0;
      src_sent[2] <= 0; src_sent[3] <= 0;
    end else begin
      if (monitor_live) begin check_source(2); check_source(3); end
      if (src_valid[2] && src_ready[2]) begin
        src_sent[2] <= src_sent[2] + 1;
        if (src_sent[2] + 1 >= src_target[2] || !source_go)
          src_valid[2] <= 0;
      end else if (!src_valid[2] && source_go &&
                   !maintenance_pause_sources && src_sent[2] < src_target[2])
        src_valid[2] <= 1;
      if (src_valid[3] && src_ready[3]) begin
        src_sent[3] <= src_sent[3] + 1;
        if (src_sent[3] + 1 >= src_target[3] || !source_go)
          src_valid[3] <= 0;
      end else if (!src_valid[3] && source_go &&
                   !maintenance_pause_sources && src_sent[3] < src_target[3])
        src_valid[3] <= 1;
    end
  end

  // Ordered physical DDR responders. The response queue belongs to the TB;
  // the DUT still uses its actual XPM FIFO and CDC synchronizer instances.
  always @(posedge ddr0_clk or posedge epoch_reset) begin
    if (epoch_reset || !ddr0_rst_n) begin
      ddr0_cycles <= 0; ar_wr[0] = 0; ar_rd[0] <= 0;
      response_beat[0] <= 0; physical_beats[0] <= 0;
      p0_rvalid <= 0; p0_rdata <= 0; p0_rlast <= 0;
      ar_was_stalled[0] = 0;
      for (integer owner = 0; owner < 2; owner = owner + 1)
        for (integer id = 0; id < MAX_REQ; id = id + 1)
          ar_seen[0][owner][id] = 0;
    end else begin
      ddr0_cycles <= ddr0_cycles + 1;
      if (monitor_live) begin
        check_physical_ar(0, p0_arvalid, p0_arready, p0_araddr,
          p0_arlen, p0_arsize, p0_arburst);
        check_client(0, 0); check_client(1, 0);
        require_true(p0_rready === 1'b0 || p0_rready === 1'b1,
          "DDR0 physical RREADY unknown");
        if (p0_rvalid && !p0_rready)
          physical_r_stalls = physical_r_stalls + 1;
      end
      if (p0_rvalid && p0_rready) begin
        physical_beats[0] <= physical_beats[0] + 1;
        total_physical_beats = total_physical_beats + 1;
        p0_rvalid <= 0;
        if (response_beat[0] == ar_len[0][ar_rd[0]]) begin
          ar_rd[0] <= ar_rd[0] + 1;
          response_beat[0] <= 0;
        end else response_beat[0] <= response_beat[0] + 1;
      end else if (!p0_rvalid && ar_rd[0] < ar_wr[0] &&
                   !hold_responses && (ddr0_cycles % 4 != 0)) begin
        p0_rvalid <= 1;
        p0_rdata <= make_data(ar_addr[0][ar_rd[0]], response_beat[0], 0);
        p0_rlast <= response_beat[0] == ar_len[0][ar_rd[0]];
      end
    end
  end
  always @(posedge ddr1_clk or posedge epoch_reset) begin
    if (epoch_reset || !ddr1_rst_n) begin
      ddr1_cycles <= 0; ar_wr[1] = 0; ar_rd[1] <= 0;
      response_beat[1] <= 0; physical_beats[1] <= 0;
      p1_rvalid <= 0; p1_rdata <= 0; p1_rlast <= 0;
      ar_was_stalled[1] = 0;
      for (integer owner = 0; owner < 2; owner = owner + 1)
        for (integer id = 0; id < MAX_REQ; id = id + 1)
          ar_seen[1][owner][id] = 0;
    end else begin
      ddr1_cycles <= ddr1_cycles + 1;
      if (monitor_live) begin
        check_physical_ar(1, p1_arvalid, p1_arready, p1_araddr,
          p1_arlen, p1_arsize, p1_arburst);
        check_client(2, 1); check_client(3, 1);
        require_true(p1_rready === 1'b0 || p1_rready === 1'b1,
          "DDR1 physical RREADY unknown");
        if (p1_rvalid && !p1_rready)
          physical_r_stalls = physical_r_stalls + 1;
      end
      if (p1_rvalid && p1_rready) begin
        physical_beats[1] <= physical_beats[1] + 1;
        total_physical_beats = total_physical_beats + 1;
        p1_rvalid <= 0;
        if (response_beat[1] == ar_len[1][ar_rd[1]]) begin
          ar_rd[1] <= ar_rd[1] + 1;
          response_beat[1] <= 0;
        end else response_beat[1] <= response_beat[1] + 1;
      end else if (!p1_rvalid && ar_rd[1] < ar_wr[1] &&
                   !hold_responses && (ddr1_cycles % 6 != 0)) begin
        p1_rvalid <= 1;
        p1_rdata <= make_data(ar_addr[1][ar_rd[1]], response_beat[1], 1);
        p1_rlast <= response_beat[1] == ar_len[1][ar_rd[1]];
      end
    end
  end

  always @(posedge core_clk) begin
    core_cycles = core_cycles + 1;
    if (monitor_live) begin
      require_true(error === 1'b0, "unexpected sticky transport error");
      require_true(maintenance_pause_sources === 1'b0 ||
        maintenance_pause_sources === 1'b1, "pause output unknown");
      require_true(maintenance_drain_active === maintenance_pause_sources,
        "maintenance pause/drain outputs diverged");
      if (maintenance_soft_clear_pulse === 1'b1)
        soft_clear_pulses = soft_clear_pulses + 1;
      else require_true(maintenance_soft_clear_pulse === 1'b0,
        "soft-clear pulse unknown");
    end
  end
  always @(posedge ddr0_clk) total_ddr0_cycles = total_ddr0_cycles + 1;
  always @(posedge ddr1_clk) total_ddr1_cycles = total_ddr1_cycles + 1;

  always @(posedge epoch_reset) begin
    for (integer port_index = 0; port_index < 4; port_index = port_index + 1) begin
      client_id[port_index] = 0;
      client_beat[port_index] = 0;
      client_beats[port_index] = 0;
      source_was_stalled[port_index] = 0;
      client_was_stalled[port_index] = 0;
    end
  end

  function automatic integer expected_beats;
    input integer owner, request_count;
    integer id;
    begin
      expected_beats = 0;
      for (id = 0; id < request_count; id = id + 1)
        expected_beats = expected_beats + length_for(owner, id) + 1;
    end
  endfunction

  task automatic wait_reset_ready;
    integer elapsed;
    begin
      elapsed = 0;
      while ((dut.fifo_rst_core !== 1'b0 ||
              dut.fifo_rst_ddr0 !== 1'b0 ||
              dut.fifo_rst_ddr1 !== 1'b0 ||
              core_quiescent !== 1'b1) && elapsed < 1000) begin
        @(posedge core_clk); #0.1; elapsed = elapsed + 1;
      end
      require_true(elapsed < 1000, "reset did not reach quiescence");
      require_true(error === 1'b0 && accepted_attn_bursts === 0 &&
        accepted_mlp_bursts === 0 && both_eligible_cycles === 0,
        "reset left error or stale counters");
    end
  endtask

  task automatic new_tb_epoch;
    begin
      @(negedge core_clk);
      monitor_live = 0;
      source_go = 0;
      epoch_reset = 1;
      epoch = epoch + 1;
      for (integer port_index = 0; port_index < 4; port_index = port_index + 1)
        src_target[port_index] = 0;
      repeat (3) @(posedge core_clk);
      @(negedge core_clk);
      epoch_reset = 0;
      monitor_live = 1;
      repeat (12) @(posedge core_clk);
      #0.1;
      require_true(core_quiescent === 1'b1 && error === 1'b0 &&
        p0_arvalid === 1'b0 && p1_arvalid === 1'b0 &&
        client_valid === 4'b0000,
        "old epoch leaked after drained clear or hard reset");
    end
  endtask

  task automatic pulse_hard_reset;
    input integer domain;
    integer elapsed;
    begin
      @(negedge core_clk);
      monitor_live = 0;
      source_go = 0;
      epoch_reset = 1;
      if (domain == 0) ddr0_rst_n = 0;
      else if (domain == 1) ddr1_rst_n = 0;
      else core_rst_n = 0;
      reset_events = reset_events + 1;
      repeat (3) @(posedge core_clk);
      #0.1;
      elapsed = 0;
      while (dut.hard_rst_core !== 1'b1 && elapsed < 30) begin
        @(posedge core_clk); #0.1; elapsed = elapsed + 1;
      end
      require_true(elapsed < 30 && dut.fifo_reset_request_r === 1'b1,
        "hard reset did not reach registered FIFO reset manager");
      @(negedge core_clk);
      if (domain == 0) ddr0_rst_n = 1;
      else if (domain == 1) ddr1_rst_n = 1;
      else core_rst_n = 1;
      wait_reset_ready();
      new_tb_epoch();
    end
  endtask

  task automatic set_targets;
    input integer attention_count, mlp_count;
    begin
      require_true(attention_count + mlp_count <= MAX_REQ,
        "test request log capacity exceeded");
      @(negedge core_clk);
      src_target[0] = attention_count;
      src_target[2] = attention_count;
      src_target[1] = mlp_count;
      src_target[3] = mlp_count;
      source_go = 1;
    end
  endtask

  task automatic wait_sources;
    integer elapsed;
    begin
      elapsed = 0;
      while ((src_sent[0] != src_target[0] || src_sent[1] != src_target[1] ||
              src_sent[2] != src_target[2] || src_sent[3] != src_target[3]) &&
             elapsed < 2000) begin
        @(posedge core_clk); #0.1; elapsed = elapsed + 1;
      end
      require_true(elapsed < 2000, "source acceptance timeout");
      source_go = 0;
    end
  endtask

  task automatic wait_issued;
    input integer attention_count, mlp_count;
    integer elapsed;
    begin
      elapsed = 0;
      while ((accepted_attn_bursts !== attention_count ||
              accepted_mlp_bursts !== mlp_count ||
              ar_wr[0] != attention_count + mlp_count ||
              ar_wr[1] != attention_count + mlp_count) && elapsed < 3000) begin
        @(posedge core_clk); #0.1; elapsed = elapsed + 1;
      end
      require_true(elapsed < 3000, "paired scheduler/physical AR timeout");
    end
  endtask

  task automatic check_delivered;
    input integer attention_count, mlp_count;
    integer expected_physical, index;
    begin
      expected_physical = expected_beats(0, attention_count) +
        expected_beats(1, mlp_count);
      require_true(client_id[0] == attention_count &&
        client_id[2] == attention_count &&
        client_id[1] == mlp_count && client_id[3] == mlp_count,
        "missing client bursts");
      require_true(client_beat[0] == 0 && client_beat[1] == 0 &&
        client_beat[2] == 0 && client_beat[3] == 0,
        "incomplete final client burst");
      require_true(client_beats[0] == expected_beats(0, attention_count) &&
        client_beats[2] == expected_beats(0, attention_count) &&
        client_beats[1] == expected_beats(1, mlp_count) &&
        client_beats[3] == expected_beats(1, mlp_count),
        "client beat count mismatch");
      require_true(physical_beats[0] == expected_physical &&
        physical_beats[1] == expected_physical &&
        ar_wr[0] == attention_count + mlp_count &&
        ar_wr[1] == attention_count + mlp_count &&
        ar_rd[0] == attention_count + mlp_count &&
        ar_rd[1] == attention_count + mlp_count,
        "physical AR, beat, or completed-burst count mismatch");
      for (index = 0; index < attention_count + mlp_count; index = index + 1)
        require_true(ar_owner[0][index] === ar_owner[1][index] &&
          ar_id[0][index] == ar_id[1][index],
          "paired DDR physical issue order diverged");
    end
  endtask

  task automatic wait_complete;
    input integer attention_count, mlp_count;
    integer elapsed;
    begin
      elapsed = 0;
      while ((client_id[0] != attention_count ||
              client_id[2] != attention_count ||
              client_id[1] != mlp_count || client_id[3] != mlp_count ||
              core_quiescent !== 1'b1) && elapsed < 5000) begin
        @(posedge core_clk); #0.1; elapsed = elapsed + 1;
      end
      require_true(elapsed < 5000, "complete packet drain timeout");
      require_true(accepted_attn_bursts === attention_count &&
        accepted_mlp_bursts === mlp_count && error === 1'b0,
        "accepted burst counters or health mismatch");
      check_delivered(attention_count, mlp_count);
      repeat (12) @(posedge core_clk);
      #0.1;
      require_true(core_quiescent === 1'b1 && client_valid === 4'b0000 &&
        p0_arvalid === 1'b0 && p1_arvalid === 1'b0,
        "extra post-drain response or AR");
    end
  endtask

  integer elapsed, index;
  initial begin
    for (index = 0; index < 4; index = index + 1) begin
      src_target[index] = 0;
      client_id[index] = 0;
      client_beat[index] = 0;
      client_beats[index] = 0;
      source_was_stalled[index] = 0;
      client_was_stalled[index] = 0;
    end
    repeat (8) @(posedge core_clk);
    @(negedge core_clk);
    core_rst_n = 1; ddr0_rst_n = 1; ddr1_rst_n = 1;
    wait_reset_ready();
    epoch_reset = 0;
    monitor_live = 1;
    repeat (12) @(posedge core_clk);
    #0.1;
    require_true(src_ready === 4'b0000,
      "disabled DDR admission was not refused");

    // Queue both clients behind a disabled scheduler, then require A,M,M
    // paired issue and every beat from mixed 4/8/16/32-beat bursts.
    @(negedge core_clk); ddr0_enable = 1; ddr1_enable = 1;
    repeat (12) @(posedge core_clk);
    set_targets(4, 8);
    wait_sources();
    repeat (12) @(posedge core_clk);
    #0.1;
    require_true(accepted_attn_bursts === 0 &&
      accepted_mlp_bursts === 0 && ar_wr[0] == 0 && ar_wr[1] == 0,
      "disabled core scheduler issued queued traffic");
    @(negedge core_clk); block_clients = 1; core_enable = 1;
    repeat (25) @(posedge core_clk);
    @(negedge core_clk); block_clients = 0;
    wait_complete(4, 8);
    require_true(both_eligible_cycles > 0 && p0_hol_cycles > 0 &&
      p1_hol_cycles > 0 && p0_tag_high_watermark > 0 &&
      p1_tag_high_watermark > 0,
      "WRR contention, HOL, or response-tag coverage missing");
    for (index = 0; index < 12; index = index + 1)
      require_true(ar_owner[0][index] === ((index % 3) != 0) &&
        ar_owner[1][index] === ((index % 3) != 0),
        "queued weighted A,M,M issue order mismatch");
    cases = cases + 1;

    // A legal maintenance clear drains outstanding complete packets even
    // after the three run enables are withdrawn. Producers acknowledge pause
    // only after their last presented AR has handshaken.
    @(negedge core_clk); hold_responses = 1;
    set_targets(7, 11);
    wait_sources();
    wait_issued(7, 11);
    require_true(core_quiescent === 1'b0,
      "held physical responses were unexpectedly quiescent");
    @(negedge core_clk);
    core_clear = 1; core_enable = 0; ddr0_enable = 0; ddr1_enable = 0;
    @(negedge core_clk); core_clear = 0;
    elapsed = 0;
    while ((dut.maintenance_stop_ddr0 !== 1'b1 ||
            dut.maintenance_stop_ddr1 !== 1'b1) && elapsed < 500) begin
      @(posedge core_clk); #0.1; elapsed = elapsed + 1;
    end
    require_true(elapsed < 500 && maintenance_pause_sources === 1'b1 &&
      maintenance_drain_active === 1'b1 && src_ready === 4'b0000,
      "maintenance pause barrier did not refuse new AR");
    saw_maintenance_core_reset = 0;
    saw_maintenance_ddr0_reset = 0;
    saw_maintenance_ddr1_reset = 0;
    @(negedge core_clk); hold_responses = 0;
    elapsed = 0;
    while ((soft_clear_pulses != 1 || !saw_maintenance_core_reset ||
            !saw_maintenance_ddr0_reset || !saw_maintenance_ddr1_reset) &&
           elapsed < 5000) begin
      @(posedge core_clk); #0.1; elapsed = elapsed + 1;
      if (dut.fifo_rst_core === 1'b1) saw_maintenance_core_reset = 1;
      if (dut.fifo_rst_ddr0 === 1'b1) saw_maintenance_ddr0_reset = 1;
      if (dut.fifo_rst_ddr1 === 1'b1) saw_maintenance_ddr1_reset = 1;
    end
    require_true(elapsed < 5000 && soft_clear_pulses == 1 &&
      saw_maintenance_core_reset && saw_maintenance_ddr0_reset &&
      saw_maintenance_ddr1_reset,
      "maintenance soft clear did not enter all FIFO reset domains");
    elapsed = 0;
    while ((dut.fifo_reset_request_r !== 1'b0 ||
            dut.fifo_rst_core !== 1'b0 ||
            dut.fifo_rst_ddr0 !== 1'b0 ||
            dut.fifo_rst_ddr1 !== 1'b0 ||
            dut.a0_wr_ready !== 1'b1 || dut.m0_wr_ready !== 1'b1 ||
            dut.a1_wr_ready !== 1'b1 || dut.m1_wr_ready !== 1'b1 ||
            dut.o0_wr_ready !== 1'b1 || dut.o1_wr_ready !== 1'b1 ||
            core_quiescent !== 1'b1) && elapsed < 5000) begin
      @(posedge core_clk); #0.1; elapsed = elapsed + 1;
    end
    require_true(elapsed < 5000 && error === 1'b0 &&
      accepted_attn_bursts === 0 && accepted_mlp_bursts === 0,
      "maintenance FIFO reset completion/readiness failed");
    check_delivered(7, 11);
    require_true(soft_clear_pulses == 1 && src_ready === 4'b0000,
      "maintenance pulse count or disabled mode refusal mismatch");
    cases = cases + 1;
    new_tb_epoch();
    require_true(src_ready === 4'b0000,
      "disabled DDR mode admitted after safe clear");
    @(negedge core_clk);
    src_target[0] = 1; src_target[2] = 1; source_go = 1;
    repeat (12) @(posedge core_clk);
    #0.1;
    require_true(src_valid[0] === 1'b1 && src_valid[2] === 1'b1 &&
      src_sent[0] == 0 && src_sent[2] == 0 &&
      src_ready === 4'b0000 && error === 1'b0,
      "disabled DDR admission did not hold and refuse source AR");
    // The unaccepted requests are canceled by hard reset. Enabling a mode
    // while its producer still presents AR would violate the mode protocol.
    pulse_hard_reset(2);
    cases = cases + 1;
    @(negedge core_clk); core_enable = 1; ddr0_enable = 1; ddr1_enable = 1;
    repeat (12) @(posedge core_clk);

    // A hard reset of one DDR domain while only its unmatched ingress
    // descriptor exists discards that epoch. No physical read is in flight.
    @(negedge core_clk);
    src_target[0] = 1; source_go = 1;
    elapsed = 0;
    while (src_sent[0] != 1 && elapsed < 200) begin
      @(posedge core_clk); #0.1; elapsed = elapsed + 1;
    end
    require_true(elapsed < 200, "DDR0 half-pair was not admitted");
    source_go = 0;
    repeat (12) @(posedge core_clk);
    require_true(accepted_attn_bursts === 0 && ar_wr[0] == 0 &&
      ar_wr[1] == 0, "unpaired pre-reset request reached a physical DDR");
    require_true(total_source_requests == total_physical_ars +
      discarded_source_requests + 1,
      "DDR0 unmatched accepted-source accounting mismatch");
    discarded_source_requests = discarded_source_requests + 1;
    pulse_hard_reset(0);
    set_targets(2, 3);
    wait_sources();
    wait_complete(2, 3);
    cases = cases + 1;

    pulse_hard_reset(2);
    @(negedge core_clk);
    src_target[3] = 1; source_go = 1;
    elapsed = 0;
    while (src_sent[3] != 1 && elapsed < 200) begin
      @(posedge core_clk); #0.1; elapsed = elapsed + 1;
    end
    require_true(elapsed < 200, "DDR1 half-pair was not admitted");
    source_go = 0;
    repeat (12) @(posedge core_clk);
    require_true(accepted_mlp_bursts === 0 && ar_wr[0] == 0 &&
      ar_wr[1] == 0, "unpaired pre-reset request reached a physical DDR");
    require_true(total_source_requests == total_physical_ars +
      discarded_source_requests + 1,
      "DDR1 unmatched accepted-source accounting mismatch");
    discarded_source_requests = discarded_source_requests + 1;
    pulse_hard_reset(1);
    set_targets(3, 2);
    wait_sources();
    wait_complete(3, 2);
    cases = cases + 1;

    require_true(source_stalls > 0 && physical_ar_stalls > 0 &&
      physical_r_stalls > 0 && client_stalls > 0 &&
      total_source_requests == 58 && total_physical_ars == 56 &&
      discarded_source_requests == 2 &&
      total_source_requests == total_physical_ars + discarded_source_requests &&
      total_physical_beats == 768 && total_client_beats == 768 &&
      reset_events == 4,
      "required stall, beat, request, or reset coverage missing");
    require_true(cases == 5 && checks > 0 && core_cycles > 0 &&
      total_ddr0_cycles > 0 && total_ddr1_cycles > 0,
      "finite case, assertion, or clock coverage missing");
    $display("CDC_COUNTS cases=%0d checks=%0d core_cycles=%0d ddr0_cycles=%0d ddr1_cycles=%0d source_requests=%0d physical_ars=%0d discarded_sources=%0d physical_beats=%0d client_beats=%0d src_stalls=%0d ar_stalls=%0d r_stalls=%0d client_stalls=%0d resets=%0d soft_clears=%0d phase_ns=0/0.8/1.7 periods_ns=10/5/5",
      cases, checks, core_cycles, total_ddr0_cycles, total_ddr1_cycles,
      total_source_requests, total_physical_ars, discarded_source_requests,
      total_physical_beats, total_client_beats,
      source_stalls, physical_ar_stalls, physical_r_stalls, client_stalls,
      reset_events, soft_clear_pulses);
    $display("HARDWARE_AGENT_SIM_PASS");
    $finish;
  end

  initial begin
    #500000;
    $fatal(1, "FAIL CDC bench global timeout");
  end
endmodule
