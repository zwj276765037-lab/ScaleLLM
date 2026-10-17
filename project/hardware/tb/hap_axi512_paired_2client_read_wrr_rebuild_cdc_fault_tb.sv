`timescale 1ns / 1ps

// Directed fatal-response and paired-descriptor checks on the unmodified
// production three-clock transport. The phase offsets are simulation stress,
// not physical CDC signoff.
module hap_axi512_paired_2client_read_wrr_rebuild_cdc_fault_tb;
  localparam integer K_SLVERR = 0;
  localparam integer K_EARLY_LAST = 1;
  localparam integer K_MISSING_LAST = 2;
  localparam integer K_ATTN_LEN_MISMATCH = 3;
  localparam integer K_MLP_LEN_MISMATCH = 4;
  localparam integer K_HEALTHY = 5;
  localparam integer RESP_HOLD = 0;
  localparam integer RESP_HEALTHY = 1;
  localparam integer RESP_FAULT = 2;

  reg core_clk = 0, ddr0_clk = 0, ddr1_clk = 0;
  always #5 core_clk = ~core_clk;
  initial begin #0.8; forever #2.5 ddr0_clk = ~ddr0_clk; end
  initial begin #1.7; forever #2.5 ddr1_clk = ~ddr1_clk; end

  reg core_rst_n = 0, ddr0_rst_n = 0, ddr1_rst_n = 0;
  reg core_clear = 0, core_enable = 0, ddr0_enable = 0, ddr1_enable = 0;
  reg tb_epoch_reset = 1, monitor_live = 0, sticky_observe = 0;
  reg freeze_watch = 0;
  reg physical_accept = 0, pair_active = 0, mismatch_active = 0;
  integer response_mode = RESP_HOLD, active_kind = -1, active_owner = -1;
  integer fault_channel = -1, fault_beat = -1;
  integer epoch = 0, pair_serial = 0;
  reg [3:0] src_valid = 0;
  reg [31:0] src_addr [0:3];
  reg [7:0] src_len [0:3];
  wire [3:0] src_ready, client_valid, client_last, client_ready;
  wire [511:0] client_data [0:3];
  wire [1:0] client_resp [0:3];
  wire maintenance_pause_sources, maintenance_drain_active;
  wire maintenance_soft_clear_pulse, core_quiescent, error;
  wire [31:0] accepted_attn_bursts, accepted_mlp_bursts;
  wire [31:0] both_eligible_cycles, p0_hol_cycles, p1_hol_cycles;
  wire [31:0] p0_tag_high_watermark, p1_tag_high_watermark;

  wire [1:0] p_arvalid, p_arready, p_rready;
  wire [31:0] p_araddr [0:1];
  wire [7:0] p_arlen [0:1];
  wire [2:0] p_arsize [0:1];
  wire [1:0] p_arburst [0:1];
  reg [1:0] p_rvalid = 0, p_rlast = 0;
  reg [511:0] p_rdata [0:1];
  reg [1:0] p_rresp [0:1];

  integer checks = 0, cases = 0, healthy_restarts = 0, reset_events = 0;
  integer core_cycles = 0, total_ddr_cycles [0:1];
  integer ddr_cycles [0:1], source_fires [0:3], client_fires [0:3];
  integer ar_fires [0:1], r_fires [0:1];
  integer total_source = 0, total_ar = 0, total_r = 0, total_client = 0;
  integer source_stalls = 0, ar_stalls = 0, r_stalls = 0;
  integer client_stalls = 0, soft_pulses = 0;
  integer prefix_by_case [0:4], legal_prefix_delivered = 0;
  integer pair_source_base [0:3], pair_client_base [0:3];
  integer pair_ar_base [0:1], pair_r_base [0:1];
  reg [31:0] pair_addr [0:1];
  reg [7:0] pair_len [0:1];
  reg ar_seen [0:1], pending [0:1], fault_handshake [0:1];
  integer response_beat [0:1], client_beat_index [0:3];
  reg client_done [0:3];
  reg [31:0] saved_ar_addr [0:1];
  reg [7:0] saved_ar_len [0:1];
  reg [3:0] source_was_stalled = 0, client_was_stalled = 0;
  reg [1:0] ar_was_stalled = 0, r_was_stalled = 0;
  reg [31:0] held_source_addr [0:3], held_ar_addr [0:1];
  reg [7:0] held_source_len [0:3], held_ar_len [0:1];
  reg [2:0] held_ar_size [0:1];
  reg [1:0] held_ar_burst [0:1], held_r_resp [0:1];
  reg [511:0] held_client_data [0:3], held_r_data [0:1];
  reg [1:0] held_client_resp [0:3];
  reg [3:0] held_client_last = 0;
  reg [1:0] held_r_last = 0;
  integer pair_attn_base, pair_mlp_base;

  function automatic [31:0] address_for;
    input integer port_index, epoch_id, serial;
    reg [31:0] base;
    begin
      case (port_index)
        0: base = 32'hA000_0000;
        1: base = 32'hB000_0000;
        2: base = 32'hA100_0000;
        default: base = 32'hB100_0000;
      endcase
      address_for = base | (epoch_id << 16) | (serial << 11);
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
        $fatal(1, "FAIL t=%0t check=%0d case=%0d epoch=%0d %0s",
          $time, checks, active_kind, epoch, message);
    end
  endtask

  assign client_ready[0] = !tb_epoch_reset &&
    (response_mode != RESP_HEALTHY || (ddr_cycles[0] % 7) >= 2);
  assign client_ready[1] = !tb_epoch_reset &&
    (response_mode != RESP_HEALTHY || (ddr_cycles[0] % 11) >= 4);
  assign client_ready[2] = !tb_epoch_reset &&
    (response_mode != RESP_HEALTHY || (ddr_cycles[1] % 9) >= 3);
  assign client_ready[3] = !tb_epoch_reset &&
    (response_mode != RESP_HEALTHY || (ddr_cycles[1] % 13) >= 5);
  assign p_arready[0] = !tb_epoch_reset && ddr0_rst_n &&
    physical_accept && (ddr_cycles[0] % 5) >= 2;
  assign p_arready[1] = !tb_epoch_reset && ddr1_rst_n &&
    physical_accept && (ddr_cycles[1] % 7) >= 3;

  // No parameter override: FIFO_DEPTH=16, TAG_DEPTH=32, SEQ_W=16.
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
    .p0_arvalid(p_arvalid[0]), .p0_arready(p_arready[0]),
    .p0_araddr(p_araddr[0]), .p0_arlen(p_arlen[0]),
    .p0_arsize(p_arsize[0]), .p0_arburst(p_arburst[0]),
    .p0_rvalid(p_rvalid[0]), .p0_rready(p_rready[0]),
    .p0_rdata(p_rdata[0]), .p0_rresp(p_rresp[0]), .p0_rlast(p_rlast[0]),
    .p1_arvalid(p_arvalid[1]), .p1_arready(p_arready[1]),
    .p1_araddr(p_araddr[1]), .p1_arlen(p_arlen[1]),
    .p1_arsize(p_arsize[1]), .p1_arburst(p_arburst[1]),
    .p1_rvalid(p_rvalid[1]), .p1_rready(p_rready[1]),
    .p1_rdata(p_rdata[1]), .p1_rresp(p_rresp[1]), .p1_rlast(p_rlast[1]),
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
          "source AR changed before handshake");
      source_was_stalled[port_index] =
        src_valid[port_index] === 1'b1 && src_ready[port_index] === 1'b0;
      if (source_was_stalled[port_index]) begin
        held_source_addr[port_index] = src_addr[port_index];
        held_source_len[port_index] = src_len[port_index];
        source_stalls = source_stalls + 1;
      end
      if (src_valid[port_index] === 1'b1 &&
          src_ready[port_index] === 1'b1) begin
        source_fires[port_index] = source_fires[port_index] + 1;
        total_source = total_source + 1;
      end
    end
  endtask

  task automatic check_client;
    input integer port_index, channel;
    reg [31:0] expected_addr;
    begin
      require_true(client_valid[port_index] === 1'b0 ||
        client_valid[port_index] === 1'b1, "client VALID unknown");
      require_true(client_ready[port_index] === 1'b0 ||
        client_ready[port_index] === 1'b1, "client READY unknown");
      if (client_was_stalled[port_index] && active_kind == K_HEALTHY)
        require_true(client_valid[port_index] === 1'b1 &&
          client_data[port_index] === held_client_data[port_index] &&
          client_resp[port_index] === held_client_resp[port_index] &&
          client_last[port_index] === held_client_last[port_index],
          "healthy client R changed before handshake");
      else if (client_was_stalled[port_index] &&
               client_valid[port_index] === 1'b1)
        require_true(client_data[port_index] === held_client_data[port_index] &&
          client_resp[port_index] === held_client_resp[port_index] &&
          client_last[port_index] === held_client_last[port_index],
          "fault-prefix client R payload changed during stall");
      client_was_stalled[port_index] =
        client_valid[port_index] === 1'b1 &&
        client_ready[port_index] === 1'b0;
      if (client_was_stalled[port_index]) begin
        held_client_data[port_index] = client_data[port_index];
        held_client_resp[port_index] = client_resp[port_index];
        held_client_last[port_index] = client_last[port_index];
        client_stalls = client_stalls + 1;
      end
      if (client_valid[port_index] === 1'b1) begin
        require_true(pair_active && port_index % 2 == active_owner &&
          !client_done[port_index],
          "unsolicited, duplicate, or cross-client RVALID");
        require_true(client_beat_index[port_index] <
          r_fires[channel] - pair_r_base[channel],
          "client beat preceded accepted physical R");
        if (active_kind != K_HEALTHY)
          require_true(active_kind <= K_MISSING_LAST &&
            channel == fault_channel &&
            client_beat_index[port_index] < fault_beat,
            "malformed or nonfault-channel beat presented");
      end
      if (client_valid[port_index] === 1'b1 &&
          client_ready[port_index] === 1'b1) begin
        expected_addr = pair_addr[channel];
        require_true(client_beat_index[port_index] <= pair_len[channel] &&
          client_data[port_index] ===
            make_data(expected_addr, client_beat_index[port_index], channel) &&
          client_resp[port_index] === 2'b00 &&
          client_last[port_index] ===
            (client_beat_index[port_index] == pair_len[channel]),
          "client payload, response, or framing mismatch");
        if (active_kind != K_HEALTHY)
          legal_prefix_delivered = legal_prefix_delivered + 1;
        client_fires[port_index] = client_fires[port_index] + 1;
        total_client = total_client + 1;
        if (client_beat_index[port_index] == pair_len[channel])
          client_done[port_index] = 1;
        client_beat_index[port_index] = client_beat_index[port_index] + 1;
      end
    end
  endtask

  task automatic check_physical;
    input integer channel;
    reg [1:0] expected_resp;
    reg expected_last;
    begin
      require_true(p_arvalid[channel] === 1'b0 ||
        p_arvalid[channel] === 1'b1, "physical ARVALID unknown");
      require_true(p_arready[channel] === 1'b0 ||
        p_arready[channel] === 1'b1, "physical ARREADY unknown");
      require_true(p_rvalid[channel] === 1'b0 ||
        p_rvalid[channel] === 1'b1, "physical RVALID unknown");
      require_true(p_rready[channel] === 1'b0 ||
        p_rready[channel] === 1'b1, "physical RREADY unknown");
      if (ar_was_stalled[channel])
        require_true(p_arvalid[channel] === 1'b1 &&
          p_araddr[channel] === held_ar_addr[channel] &&
          p_arlen[channel] === held_ar_len[channel] &&
          p_arsize[channel] === held_ar_size[channel] &&
          p_arburst[channel] === held_ar_burst[channel],
          "physical AR changed before handshake");
      ar_was_stalled[channel] =
        p_arvalid[channel] === 1'b1 && p_arready[channel] === 1'b0;
      if (ar_was_stalled[channel]) begin
        held_ar_addr[channel] = p_araddr[channel];
        held_ar_len[channel] = p_arlen[channel];
        held_ar_size[channel] = p_arsize[channel];
        held_ar_burst[channel] = p_arburst[channel];
        ar_stalls = ar_stalls + 1;
      end
      if (mismatch_active)
        require_true(p_arvalid[channel] === 1'b0,
          "mismatched pair presented a physical AR");
      if (p_arvalid[channel] === 1'b1) begin
        require_true(pair_active && !mismatch_active &&
          source_fires[active_owner] == pair_source_base[active_owner] + 1 &&
          source_fires[2 + active_owner] ==
            pair_source_base[2 + active_owner] + 1 &&
          p_araddr[channel] === pair_addr[channel] &&
          p_arlen[channel] === pair_len[channel] &&
          p_arsize[channel] === 3'd6 &&
          p_arburst[channel] === 2'b01,
          "physical AR owner, address, length, or shape mismatch");
      end
      if (p_arvalid[channel] === 1'b1 &&
          p_arready[channel] === 1'b1) begin
        require_true(!ar_seen[channel] && !pending[channel],
          "duplicate physical AR");
        ar_seen[channel] = 1;
        ar_fires[channel] = ar_fires[channel] + 1;
        total_ar = total_ar + 1;
      end
      if (r_was_stalled[channel])
        require_true(p_rvalid[channel] === 1'b1 &&
          p_rdata[channel] === held_r_data[channel] &&
          p_rresp[channel] === held_r_resp[channel] &&
          p_rlast[channel] === held_r_last[channel],
          "physical R changed before handshake");
      r_was_stalled[channel] =
        p_rvalid[channel] === 1'b1 && p_rready[channel] === 1'b0;
      if (r_was_stalled[channel]) begin
        held_r_data[channel] = p_rdata[channel];
        held_r_resp[channel] = p_rresp[channel];
        held_r_last[channel] = p_rlast[channel];
        r_stalls = r_stalls + 1;
      end
      if (p_rvalid[channel] === 1'b1) begin
        expected_resp = 2'b00;
        expected_last = response_beat[channel] == saved_ar_len[channel];
        if (response_mode == RESP_FAULT && channel == fault_channel) begin
          if (active_kind == K_SLVERR && response_beat[channel] == 0)
            expected_resp = 2'b10;
          if (active_kind == K_EARLY_LAST && response_beat[channel] == 0)
            expected_last = 1'b1;
          if (active_kind == K_MISSING_LAST && response_beat[channel] == 3)
            expected_last = 1'b0;
        end
        require_true(pair_active && pending[channel] &&
          (response_mode == RESP_HEALTHY ||
           (response_mode == RESP_FAULT && channel == fault_channel)) &&
          p_rdata[channel] ===
            make_data(saved_ar_addr[channel], response_beat[channel], channel) &&
          p_rresp[channel] === expected_resp &&
          p_rlast[channel] === expected_last,
          "physical R source, payload, or injected fault mismatch");
        if (active_kind == K_MISSING_LAST && channel == fault_channel &&
            response_beat[channel] == 3)
          require_true(legal_prefix_delivered == 3 &&
            client_fires[2*channel + active_owner] ==
              pair_client_base[2*channel + active_owner] + 3 &&
            client_beat_index[2*channel + active_owner] == 3 &&
            client_ready[2*channel + active_owner] === 1'b1,
            "missing-LAST beat 3 presented before three verified good-prefix deliveries");
      end
      if (p_rvalid[channel] === 1'b1 &&
          p_rready[channel] === 1'b1) begin
        r_fires[channel] = r_fires[channel] + 1;
        total_r = total_r + 1;
      end
    end
  endtask

  always @(posedge ddr0_clk or posedge tb_epoch_reset) begin
    if (tb_epoch_reset || !ddr0_rst_n) begin
      ddr_cycles[0] <= 0;
      src_valid[0] <= 0; src_valid[1] <= 0;
      source_fires[0] = 0; source_fires[1] = 0;
      client_fires[0] = 0; client_fires[1] = 0;
      source_was_stalled[0] = 0; source_was_stalled[1] = 0;
      client_was_stalled[0] = 0; client_was_stalled[1] = 0;
      ar_fires[0] = 0; r_fires[0] = 0;
      ar_was_stalled[0] = 0; r_was_stalled[0] = 0;
      pending[0] <= 0; response_beat[0] <= 0; fault_handshake[0] <= 0;
      p_rvalid[0] <= 0; p_rdata[0] <= 0;
      p_rresp[0] <= 0; p_rlast[0] <= 0;
    end else begin
      ddr_cycles[0] <= ddr_cycles[0] + 1;
      if (monitor_live) begin
        check_source(0); check_source(1);
        check_client(0, 0); check_client(1, 0);
        check_physical(0);
        if (freeze_watch)
          require_true(src_ready[1:0] === 2'b00 &&
            client_valid[1:0] === 2'b00,
            "DDR0 source admission or client output reopened after fault");
      end
      if (src_valid[0] && src_ready[0]) src_valid[0] <= 0;
      if (src_valid[1] && src_ready[1]) src_valid[1] <= 0;
      if (p_arvalid[0] && p_arready[0]) begin
        pending[0] <= 1;
        response_beat[0] <= 0;
        saved_ar_addr[0] <= p_araddr[0];
        saved_ar_len[0] <= p_arlen[0];
      end
      if (p_rvalid[0] && p_rready[0]) begin
        p_rvalid[0] <= 0;
        if (response_mode == RESP_FAULT && fault_channel == 0 &&
            response_beat[0] == fault_beat) begin
          pending[0] <= 0;
          fault_handshake[0] <= 1;
        end else if (response_beat[0] == saved_ar_len[0])
          pending[0] <= 0;
        else response_beat[0] <= response_beat[0] + 1;
      end else if (!p_rvalid[0] && pending[0] &&
                   (response_mode == RESP_HEALTHY ||
                    (response_mode == RESP_FAULT && fault_channel == 0))) begin
        if (active_kind == K_MISSING_LAST && response_beat[0] == 3)
          require_true(legal_prefix_delivered == 3 &&
            client_fires[1] == pair_client_base[1] + 3 &&
            client_beat_index[1] == 3 && client_ready[1] === 1'b1,
            "missing-LAST beat 3 scheduled before three verified good-prefix deliveries");
        p_rvalid[0] <= 1;
        p_rdata[0] <= make_data(saved_ar_addr[0], response_beat[0], 0);
        p_rresp[0] <= (response_mode == RESP_FAULT &&
          active_kind == K_SLVERR && response_beat[0] == 0) ? 2'b10 : 2'b00;
        p_rlast[0] <= (response_mode == RESP_FAULT &&
          active_kind == K_MISSING_LAST && response_beat[0] == 3) ? 1'b0 :
          (response_beat[0] == saved_ar_len[0]);
      end
    end
  end

  always @(posedge ddr1_clk or posedge tb_epoch_reset) begin
    if (tb_epoch_reset || !ddr1_rst_n) begin
      ddr_cycles[1] <= 0;
      src_valid[2] <= 0; src_valid[3] <= 0;
      source_fires[2] = 0; source_fires[3] = 0;
      client_fires[2] = 0; client_fires[3] = 0;
      source_was_stalled[2] = 0; source_was_stalled[3] = 0;
      client_was_stalled[2] = 0; client_was_stalled[3] = 0;
      ar_fires[1] = 0; r_fires[1] = 0;
      ar_was_stalled[1] = 0; r_was_stalled[1] = 0;
      pending[1] <= 0; response_beat[1] <= 0; fault_handshake[1] <= 0;
      p_rvalid[1] <= 0; p_rdata[1] <= 0;
      p_rresp[1] <= 0; p_rlast[1] <= 0;
    end else begin
      ddr_cycles[1] <= ddr_cycles[1] + 1;
      if (monitor_live) begin
        check_source(2); check_source(3);
        check_client(2, 1); check_client(3, 1);
        check_physical(1);
        if (freeze_watch)
          require_true(src_ready[3:2] === 2'b00 &&
            client_valid[3:2] === 2'b00,
            "DDR1 source admission or client output reopened after fault");
      end
      if (src_valid[2] && src_ready[2]) src_valid[2] <= 0;
      if (src_valid[3] && src_ready[3]) src_valid[3] <= 0;
      if (p_arvalid[1] && p_arready[1]) begin
        pending[1] <= 1;
        response_beat[1] <= 0;
        saved_ar_addr[1] <= p_araddr[1];
        saved_ar_len[1] <= p_arlen[1];
      end
      if (p_rvalid[1] && p_rready[1]) begin
        p_rvalid[1] <= 0;
        if (response_mode == RESP_FAULT && fault_channel == 1 &&
            response_beat[1] == fault_beat) begin
          pending[1] <= 0;
          fault_handshake[1] <= 1;
        end else if (response_beat[1] == saved_ar_len[1])
          pending[1] <= 0;
        else response_beat[1] <= response_beat[1] + 1;
      end else if (!p_rvalid[1] && pending[1] &&
                   (response_mode == RESP_HEALTHY ||
                    (response_mode == RESP_FAULT && fault_channel == 1))) begin
        p_rvalid[1] <= 1;
        p_rdata[1] <= make_data(saved_ar_addr[1], response_beat[1], 1);
        p_rresp[1] <= 2'b00;
        p_rlast[1] <= (response_mode == RESP_FAULT &&
          active_kind == K_EARLY_LAST && response_beat[1] == 0) ? 1'b1 :
          (response_beat[1] == saved_ar_len[1]);
      end
    end
  end

  always @(posedge core_clk) begin
    core_cycles = core_cycles + 1;
    if (monitor_live) begin
      require_true(error === 1'b0 || error === 1'b1,
        "global error unknown");
      require_true(core_quiescent === 1'b0 || core_quiescent === 1'b1,
        "core quiescence unknown");
      require_true(maintenance_pause_sources === 1'b0 ||
        maintenance_pause_sources === 1'b1, "maintenance pause unknown");
      require_true(maintenance_drain_active === maintenance_pause_sources,
        "maintenance pause/drain diverged");
      if (maintenance_soft_clear_pulse === 1'b1)
        soft_pulses = soft_pulses + 1;
      require_true(maintenance_soft_clear_pulse === 1'b0,
        "fault test unexpectedly soft-cleared");
      if (sticky_observe)
        require_true(error === 1'b1, "sticky error recovered without hard reset");
      if (freeze_watch)
        require_true(src_ready === 4'b0000 && client_valid === 4'b0000,
          "core-sampled source admission or client output reopened after fault");
      if (active_kind == K_MISSING_LAST && response_mode == RESP_FAULT)
        require_true(client_ready === 4'b1111,
          "missing-LAST clients were not continuously ready");
      if (active_kind == K_HEALTHY)
        require_true(error === 1'b0, "healthy restart raised error");
    end
  end
  always @(posedge ddr0_clk) total_ddr_cycles[0] = total_ddr_cycles[0] + 1;
  always @(posedge ddr1_clk) total_ddr_cycles[1] = total_ddr_cycles[1] + 1;

  task automatic wait_reset_ready;
    integer elapsed;
    begin
      elapsed = 0;
      while ((dut.fifo_rst_core !== 1'b0 ||
              dut.fifo_rst_ddr0 !== 1'b0 ||
              dut.fifo_rst_ddr1 !== 1'b0 ||
              dut.a0_wr_ready !== 1'b1 || dut.m0_wr_ready !== 1'b1 ||
              dut.a1_wr_ready !== 1'b1 || dut.m1_wr_ready !== 1'b1 ||
              dut.o0_wr_ready !== 1'b1 || dut.o1_wr_ready !== 1'b1 ||
              core_quiescent !== 1'b1) && elapsed < 1000) begin
        @(posedge core_clk); #0.1; elapsed = elapsed + 1;
      end
      require_true(elapsed < 1000 && error === 1'b0 &&
        accepted_attn_bursts === 0 && accepted_mlp_bursts === 0 &&
        p_arvalid === 2'b00 && client_valid === 4'b0000,
        "coordinated reset did not complete cleanly");
    end
  endtask

  task automatic coordinated_reset;
    integer elapsed;
    begin
      @(negedge core_clk);
      monitor_live = 0;
      sticky_observe = 0;
      freeze_watch = 0;
      pair_active = 0;
      mismatch_active = 0;
      active_kind = -1;
      response_mode = RESP_HOLD;
      physical_accept = 0;
      core_clear = 0;
      core_enable = 0; ddr0_enable = 0; ddr1_enable = 0;
      core_rst_n = 0; ddr0_rst_n = 0; ddr1_rst_n = 0;
      tb_epoch_reset = 1;
      reset_events = reset_events + 1;
      epoch = epoch + 1;
      elapsed = 0;
      while ((dut.hard_rst_core !== 1'b1 ||
              dut.hard_rst_ddr0 !== 1'b1 ||
              dut.hard_rst_ddr1 !== 1'b1 ||
              dut.fifo_reset_request_r !== 1'b1) && elapsed < 100) begin
        @(posedge core_clk); #0.1; elapsed = elapsed + 1;
      end
      require_true(elapsed < 100,
        "coordinated hard reset did not enter all domains");
      repeat (8) @(posedge core_clk);
      @(negedge core_clk);
      core_rst_n = 1; ddr0_rst_n = 1; ddr1_rst_n = 1;
      wait_reset_ready();
      @(negedge core_clk);
      tb_epoch_reset = 0;
      core_enable = 1; ddr0_enable = 1; ddr1_enable = 1;
      monitor_live = 1;
      repeat (12) @(posedge core_clk);
      #0.1;
      require_true(error === 1'b0 && core_quiescent === 1'b1 &&
        src_valid === 4'b0000 && client_valid === 4'b0000,
        "reset restart was not ready and quiescent");
    end
  endtask

  task automatic start_pair;
    input integer owner, len0, len1, kind;
    integer port_index, channel;
    begin
      require_true(!pair_active && src_valid === 4'b0000 &&
        p_arvalid === 2'b00 && p_rvalid === 2'b00 &&
        core_quiescent === 1'b1 && error === 1'b0,
        "new pair started before prior traffic drained");
      @(negedge core_clk);
      active_owner = owner;
      active_kind = kind;
      pair_active = 1;
      mismatch_active = kind == K_ATTN_LEN_MISMATCH ||
        kind == K_MLP_LEN_MISMATCH;
      response_mode = RESP_HOLD;
      physical_accept = 0;
      legal_prefix_delivered = 0;
      fault_channel = -1;
      fault_beat = -1;
      if (kind == K_SLVERR) begin fault_channel = 0; fault_beat = 0; end
      if (kind == K_EARLY_LAST) begin fault_channel = 1; fault_beat = 0; end
      if (kind == K_MISSING_LAST) begin fault_channel = 0; fault_beat = 3; end
      pair_attn_base = accepted_attn_bursts;
      pair_mlp_base = accepted_mlp_bursts;
      for (port_index = 0; port_index < 4; port_index = port_index + 1) begin
        pair_source_base[port_index] = source_fires[port_index];
        pair_client_base[port_index] = client_fires[port_index];
        client_beat_index[port_index] = 0;
        client_done[port_index] = 0;
      end
      for (channel = 0; channel < 2; channel = channel + 1) begin
        pair_ar_base[channel] = ar_fires[channel];
        pair_r_base[channel] = r_fires[channel];
        ar_seen[channel] = 0;
        pair_addr[channel] = address_for(2*channel + owner,
          epoch, pair_serial);
        pair_len[channel] = channel == 0 ? len0 : len1;
      end
      src_addr[owner] = pair_addr[0];
      src_addr[2 + owner] = pair_addr[1];
      src_len[owner] = len0;
      src_len[2 + owner] = len1;
      src_valid[owner] = 1;
      src_valid[2 + owner] = 1;
      pair_serial = pair_serial + 1;
    end
  endtask

  task automatic wait_source_accept;
    integer elapsed;
    begin
      elapsed = 0;
      while ((source_fires[active_owner] !=
                pair_source_base[active_owner] + 1 ||
              source_fires[2 + active_owner] !=
                pair_source_base[2 + active_owner] + 1) && elapsed < 500) begin
        @(posedge core_clk); #0.1; elapsed = elapsed + 1;
      end
      require_true(elapsed < 500 && src_valid === 4'b0000,
        "paired source AR not accepted and retired");
      require_true(source_fires[1 - active_owner] ==
        pair_source_base[1 - active_owner] &&
        source_fires[3 - active_owner] ==
          pair_source_base[3 - active_owner],
        "unrequested source AR accepted");
    end
  endtask

  task automatic open_physical_pair;
    integer elapsed;
    begin
      elapsed = 0;
      while ((p_arvalid[0] !== 1'b1 || p_arvalid[1] !== 1'b1) &&
             elapsed < 500) begin
        @(posedge core_clk); #0.1; elapsed = elapsed + 1;
      end
      require_true(elapsed < 500 && p_arready === 2'b00,
        "paired physical AR did not present under stall");
      repeat (6) begin
        @(posedge core_clk); #0.1;
        require_true(p_arvalid === 2'b11 && p_arready === 2'b00,
          "presented physical AR was retracted before handshake");
      end
      @(negedge core_clk); physical_accept = 1;
      elapsed = 0;
      while ((ar_fires[0] != pair_ar_base[0] + 1 ||
              ar_fires[1] != pair_ar_base[1] + 1) && elapsed < 500) begin
        @(posedge core_clk); #0.1; elapsed = elapsed + 1;
      end
      require_true(elapsed < 500 && pending[0] === 1'b1 &&
        pending[1] === 1'b1, "paired physical AR handshake missing");
      @(negedge core_clk); physical_accept = 0;
    end
  endtask

  task automatic wait_sticky_error;
    integer elapsed;
    begin
      elapsed = 0;
      while (error !== 1'b1 && elapsed < 500) begin
        @(posedge core_clk); #0.1; elapsed = elapsed + 1;
      end
      require_true(elapsed < 500 && error === 1'b1 &&
        core_quiescent === 1'b0,
        "bounded sticky error or nonquiescent indication missing");
      sticky_observe = 1;
    end
  endtask

  task automatic prove_soft_clear_refusal;
    integer elapsed, old_pulses;
    begin
      elapsed = 0;
      while ((src_ready !== 4'b0000 || client_valid !== 4'b0000) &&
             elapsed < 100) begin
        @(posedge core_clk); #0.1; elapsed = elapsed + 1;
      end
      require_true(elapsed < 100 && error === 1'b1 &&
        src_ready === 4'b0000 && client_valid === 4'b0000,
        "bounded CDC fault-freeze settlement failed");
      freeze_watch = 1;
      old_pulses = soft_pulses;
      @(negedge core_clk); core_clear = 1;
      @(negedge core_clk); core_clear = 0;
      for (elapsed = 0; elapsed < 50; elapsed = elapsed + 1) begin
        @(posedge core_clk); #0.1;
        require_true(error === 1'b1 && core_quiescent === 1'b0 &&
          maintenance_soft_clear_pulse === 1'b0 &&
          src_ready === 4'b0000 && client_valid === 4'b0000,
          "soft clear recovered fatal state");
      end
      require_true(soft_pulses == old_pulses &&
        maintenance_pause_sources === 1'b0 &&
        maintenance_drain_active === 1'b0 &&
        src_ready === 4'b0000 && client_valid === 4'b0000 &&
        p_arvalid === 2'b00,
        "fatal freeze or soft-clear refusal did not persist");
    end
  endtask

  task automatic run_fault_case;
    input integer kind;
    integer owner, len0, len1, elapsed, port_index;
    begin
      owner = (kind == K_SLVERR || kind == K_ATTN_LEN_MISMATCH) ? 0 : 1;
      len0 = 3;
      len1 = (kind == K_ATTN_LEN_MISMATCH ||
              kind == K_MLP_LEN_MISMATCH) ? 7 : 3;
      start_pair(owner, len0, len1, kind);
      wait_source_accept();
      if (kind <= K_MISSING_LAST) begin
        open_physical_pair();
        require_true(error === 1'b0,
          "error preceded injected physical R fault");
        @(negedge core_clk); response_mode = RESP_FAULT;
        elapsed = 0;
        while (fault_handshake[fault_channel] !== 1'b1 && elapsed < 500) begin
          @(posedge core_clk); #0.1; elapsed = elapsed + 1;
        end
        require_true(elapsed < 500 &&
          r_fires[fault_channel] == pair_r_base[fault_channel] + fault_beat + 1 &&
          legal_prefix_delivered == fault_beat,
          "malformed physical R was not accepted at required beat");
      end
      wait_sticky_error();
      prove_soft_clear_refusal();
      require_true(source_fires[owner] == pair_source_base[owner] + 1 &&
        source_fires[2 + owner] == pair_source_base[2 + owner] + 1,
        "fault pair did not contain both accepted source descriptors");
      if (kind <= K_MISSING_LAST) begin
        require_true(ar_fires[0] == pair_ar_base[0] + 1 &&
          ar_fires[1] == pair_ar_base[1] + 1 &&
          r_fires[1 - fault_channel] == pair_r_base[1 - fault_channel] &&
          client_fires[2*(1 - fault_channel) + owner] ==
            pair_client_base[2*(1 - fault_channel) + owner] &&
          legal_prefix_delivered == fault_beat &&
          client_fires[2*fault_channel + owner] ==
            pair_client_base[2*fault_channel + owner] + fault_beat,
          "fault-side AR/R or legal-prefix accounting mismatch");
        require_true(accepted_attn_bursts == pair_attn_base + (owner == 0) &&
          accepted_mlp_bursts == pair_mlp_base + (owner == 1),
          "fault pair was not scheduled exactly once");
      end else begin
        require_true(ar_fires[0] == pair_ar_base[0] &&
          ar_fires[1] == pair_ar_base[1] &&
          r_fires[0] == pair_r_base[0] &&
          r_fires[1] == pair_r_base[1] &&
          p_arvalid === 2'b00 && legal_prefix_delivered == 0 &&
          accepted_attn_bursts == pair_attn_base &&
          accepted_mlp_bursts == pair_mlp_base,
          "mismatched pair reached physical AR/R or scheduler");
      end
      for (port_index = 0; port_index < 4; port_index = port_index + 1)
        if (port_index % 2 != owner)
          require_true(client_fires[port_index] == pair_client_base[port_index],
            "fault beat crossed client owner");
      prefix_by_case[kind] = legal_prefix_delivered;
      cases = cases + 1;
      $display("CDC_FAULT_CASE kind=%0d epoch=%0d source=2 physical_ar=%0d physical_r=%0d legal_prefix=%0d sticky=1 soft_recovery=0",
        kind, epoch, kind <= K_MISSING_LAST ? 2 : 0,
        kind == K_MISSING_LAST ? 4 :
          (kind <= K_EARLY_LAST ? 1 : 0), legal_prefix_delivered);
    end
  endtask

  task automatic run_healthy_pair;
    input integer owner, burst_len;
    integer elapsed, port_index;
    begin
      start_pair(owner, burst_len, burst_len, K_HEALTHY);
      wait_source_accept();
      open_physical_pair();
      @(negedge core_clk); response_mode = RESP_HEALTHY;
      elapsed = 0;
      while ((client_done[owner] !== 1'b1 ||
              client_done[2 + owner] !== 1'b1 ||
              pending[0] !== 1'b0 || pending[1] !== 1'b0 ||
              core_quiescent !== 1'b1) && elapsed < 2000) begin
        @(posedge core_clk); #0.1; elapsed = elapsed + 1;
      end
      require_true(elapsed < 2000 && error === 1'b0 &&
        accepted_attn_bursts == pair_attn_base + (owner == 0) &&
        accepted_mlp_bursts == pair_mlp_base + (owner == 1) &&
        ar_fires[0] == pair_ar_base[0] + 1 &&
        ar_fires[1] == pair_ar_base[1] + 1 &&
        r_fires[0] == pair_r_base[0] + burst_len + 1 &&
        r_fires[1] == pair_r_base[1] + burst_len + 1 &&
        client_fires[owner] == pair_client_base[owner] + burst_len + 1 &&
        client_fires[2 + owner] ==
          pair_client_base[2 + owner] + burst_len + 1 &&
        p_arvalid === 2'b00 && p_rvalid === 2'b00 &&
        client_valid === 4'b0000,
        "healthy restart payload count, drain, or health mismatch");
      for (port_index = 0; port_index < 4; port_index = port_index + 1)
        if (port_index % 2 != owner)
          require_true(client_fires[port_index] == pair_client_base[port_index],
            "healthy response crossed client owner");
      @(negedge core_clk);
      pair_active = 0;
      active_kind = -1;
      response_mode = RESP_HOLD;
      repeat (12) @(posedge core_clk);
      #0.1;
      require_true(core_quiescent === 1'b1 && error === 1'b0 &&
        client_valid === 4'b0000 && p_arvalid === 2'b00 &&
        p_rvalid === 2'b00,
        "stale response appeared after healthy drain");
    end
  endtask

  task automatic run_healthy_restart;
    input integer after_kind;
    begin
      require_true(error === 1'b0 && core_quiescent === 1'b1,
        "hard reset did not restore clean restart state");
      run_healthy_pair(0, 3);
      run_healthy_pair(1, 7);
      healthy_restarts = healthy_restarts + 1;
      $display("CDC_HEALTHY_RESTART after_kind=%0d epoch=%0d attn_beats=4/4 mlp_beats=8/8",
        after_kind, epoch);
    end
  endtask

  integer index;
  initial begin
    total_ddr_cycles[0] = 0;
    total_ddr_cycles[1] = 0;
    for (index = 0; index < 4; index = index + 1) begin
      src_addr[index] = 0;
      src_len[index] = 0;
      client_beat_index[index] = 0;
      client_done[index] = 0;
    end
    for (index = 0; index < 5; index = index + 1)
      prefix_by_case[index] = 0;
    coordinated_reset();
    for (index = 0; index < 5; index = index + 1) begin
      run_fault_case(index);
      coordinated_reset();
      run_healthy_restart(index);
    end
    require_true(cases == 5 && healthy_restarts == 5 &&
      reset_events == 6 && checks > 0 &&
      core_cycles > 0 && total_ddr_cycles[0] > 0 &&
      total_ddr_cycles[1] > 0 && ar_stalls > 0 &&
      total_source == 30 && total_ar == 26 && total_r == 126 &&
      total_client == 123 && prefix_by_case[K_MISSING_LAST] == 3 &&
      prefix_by_case[K_SLVERR] == 0 &&
      prefix_by_case[K_EARLY_LAST] == 0 &&
      prefix_by_case[K_ATTN_LEN_MISMATCH] == 0 &&
      prefix_by_case[K_MLP_LEN_MISMATCH] == 0 && soft_pulses == 0,
      "finite negative and healthy-restart coverage missing");
    $display("CDC_FAULT_COUNTS cases=%0d healthy_restarts=%0d checks=%0d core_cycles=%0d ddr0_cycles=%0d ddr1_cycles=%0d source_requests=%0d physical_ars=%0d physical_r_beats=%0d client_beats=%0d legal_prefix=%0d source_stalls=%0d ar_stalls=%0d r_stalls=%0d client_stalls=%0d hard_resets=%0d soft_clears=%0d phase_ns=0/0.8/1.7 periods_ns=10/5/5",
      cases, healthy_restarts, checks, core_cycles, total_ddr_cycles[0],
      total_ddr_cycles[1], total_source, total_ar, total_r, total_client,
      prefix_by_case[K_MISSING_LAST], source_stalls, ar_stalls, r_stalls,
      client_stalls, reset_events, soft_pulses);
    $display("HARDWARE_AGENT_SIM_PASS");
    $finish;
  end

  initial begin
    #500000;
    $fatal(1, "FAIL CDC fault bench global timeout");
  end

endmodule
