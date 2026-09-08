`timescale 1ns / 1ps

// Directed mode/maintenance test for the three-clock paired read arbiter.
// All client requests are one-beat INCR bursts.  The two MIG models accept AR
// independently and return ordered one-beat responses at different rates.
module hap_axi512_paired_2client_read_wrr_modes_tb;
  localparam integer N_SINGLE = 6;
  localparam integer N_DUAL_A = 6;
  localparam integer N_DUAL_M = 12;
  localparam integer MAX_LOG  = 128;

  reg core_clk = 1'b0, ddr0_clk = 1'b0, ddr1_clk = 1'b0;
  always #3.333 core_clk = ~core_clk;
  always #1.667 ddr0_clk = ~ddr0_clk;
  always #1.923 ddr1_clk = ~ddr1_clk;

  reg core_rst_n = 1'b0, ddr0_rst_n = 1'b0, ddr1_rst_n = 1'b0;
  reg core_clear = 1'b0, core_enable = 1'b1;
  reg ddr0_enable = 1'b1, ddr1_enable = 1'b1;
  reg attn_source_quiescent = 1'b1, mlp_source_quiescent = 1'b1;
  wire maintenance_pause_sources, maintenance_drain_active;
  wire maintenance_soft_clear_pulse;

  reg a0_arvalid = 1'b0, m0_arvalid = 1'b0;
  reg a1_arvalid = 1'b0, m1_arvalid = 1'b0;
  wire a0_arready, m0_arready, a1_arready, m1_arready;
  reg [31:0] a0_araddr = '0, m0_araddr = '0;
  reg [31:0] a1_araddr = '0, m1_araddr = '0;
  reg [7:0] a0_arlen = 0, m0_arlen = 0, a1_arlen = 0, m1_arlen = 0;
  reg [2:0] a0_arsize = 3'd6, m0_arsize = 3'd6;
  reg [2:0] a1_arsize = 3'd6, m1_arsize = 3'd6;
  reg [1:0] a0_arburst = 2'b01, m0_arburst = 2'b01;
  reg [1:0] a1_arburst = 2'b01, m1_arburst = 2'b01;

  wire a0_rvalid, m0_rvalid, a1_rvalid, m1_rvalid;
  reg a0_rready = 1'b1, m0_rready = 1'b1;
  reg a1_rready = 1'b1, m1_rready = 1'b1;
  wire [511:0] a0_rdata, m0_rdata, a1_rdata, m1_rdata;
  wire [1:0] a0_rresp, m0_rresp, a1_rresp, m1_rresp;
  wire a0_rlast, m0_rlast, a1_rlast, m1_rlast;

  wire p0_arvalid, p1_arvalid;
  reg p0_arready = 1'b1, p1_arready = 1'b1;
  wire [31:0] p0_araddr, p1_araddr;
  wire [7:0] p0_arlen, p1_arlen;
  wire [2:0] p0_arsize, p1_arsize;
  wire [1:0] p0_arburst, p1_arburst;
  reg p0_rvalid = 1'b0, p1_rvalid = 1'b0;
  wire p0_rready, p1_rready;
  reg [511:0] p0_rdata = '0, p1_rdata = '0;
  reg [1:0] p0_rresp = 2'b00, p1_rresp = 2'b00;
  reg p0_rlast = 1'b0, p1_rlast = 1'b0;

  wire core_quiescent, error;
  wire [31:0] accepted_attn_bursts, accepted_mlp_bursts;
  wire [31:0] both_eligible_cycles;
  wire [31:0] p0_hol_cycles, p1_hol_cycles;
  wire [31:0] p0_tag_high_watermark, p1_tag_high_watermark;

  integer failures = 0, checks = 0;
  integer p0_wr = 0, p0_rd = 0, p1_wr = 0, p1_rd = 0;
  integer p0_rsp_delay = 0, p1_rsp_delay = 0;
  integer a0_rcvd = 0, m0_rcvd = 0, a1_rcvd = 0, m1_rcvd = 0;
  integer phase_base0, phase_base1;
  reg responders_enable = 1'b1;
  reg [31:0] p0_addr_q [0:MAX_LOG-1];
  reg [31:0] p1_addr_q [0:MAX_LOG-1];
  reg p0_owner_log [0:MAX_LOG-1];
  reg p1_owner_log [0:MAX_LOG-1];

  hap_axi512_paired_2client_read_wrr #(
    .FIFO_DEPTH(16), .TAG_DEPTH(16), .SEQ_W(16)
  ) dut (
    .core_clk(core_clk), .core_rst_n(core_rst_n), .core_clear(core_clear),
    .core_enable(core_enable),
    .attn_source_quiescent(attn_source_quiescent),
    .mlp_source_quiescent(mlp_source_quiescent),
    .maintenance_pause_sources(maintenance_pause_sources),
    .maintenance_drain_active(maintenance_drain_active),
    .maintenance_soft_clear_pulse(maintenance_soft_clear_pulse),
    .ddr0_clk(ddr0_clk), .ddr0_rst_n(ddr0_rst_n), .ddr0_enable(ddr0_enable),
    .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n), .ddr1_enable(ddr1_enable),
    .a0_arvalid(a0_arvalid), .a0_arready(a0_arready), .a0_araddr(a0_araddr),
    .a0_arlen(a0_arlen), .a0_arsize(a0_arsize), .a0_arburst(a0_arburst),
    .a0_rvalid(a0_rvalid), .a0_rready(a0_rready), .a0_rdata(a0_rdata),
    .a0_rresp(a0_rresp), .a0_rlast(a0_rlast),
    .m0_arvalid(m0_arvalid), .m0_arready(m0_arready), .m0_araddr(m0_araddr),
    .m0_arlen(m0_arlen), .m0_arsize(m0_arsize), .m0_arburst(m0_arburst),
    .m0_rvalid(m0_rvalid), .m0_rready(m0_rready), .m0_rdata(m0_rdata),
    .m0_rresp(m0_rresp), .m0_rlast(m0_rlast),
    .a1_arvalid(a1_arvalid), .a1_arready(a1_arready), .a1_araddr(a1_araddr),
    .a1_arlen(a1_arlen), .a1_arsize(a1_arsize), .a1_arburst(a1_arburst),
    .a1_rvalid(a1_rvalid), .a1_rready(a1_rready), .a1_rdata(a1_rdata),
    .a1_rresp(a1_rresp), .a1_rlast(a1_rlast),
    .m1_arvalid(m1_arvalid), .m1_arready(m1_arready), .m1_araddr(m1_araddr),
    .m1_arlen(m1_arlen), .m1_arsize(m1_arsize), .m1_arburst(m1_arburst),
    .m1_rvalid(m1_rvalid), .m1_rready(m1_rready), .m1_rdata(m1_rdata),
    .m1_rresp(m1_rresp), .m1_rlast(m1_rlast),
    .p0_arvalid(p0_arvalid), .p0_arready(p0_arready), .p0_araddr(p0_araddr),
    .p0_arlen(p0_arlen), .p0_arsize(p0_arsize), .p0_arburst(p0_arburst),
    .p0_rvalid(p0_rvalid), .p0_rready(p0_rready), .p0_rdata(p0_rdata),
    .p0_rresp(p0_rresp), .p0_rlast(p0_rlast),
    .p1_arvalid(p1_arvalid), .p1_arready(p1_arready), .p1_araddr(p1_araddr),
    .p1_arlen(p1_arlen), .p1_arsize(p1_arsize), .p1_arburst(p1_arburst),
    .p1_rvalid(p1_rvalid), .p1_rready(p1_rready), .p1_rdata(p1_rdata),
    .p1_rresp(p1_rresp), .p1_rlast(p1_rlast),
    .core_quiescent(core_quiescent), .error(error),
    .accepted_attn_bursts(accepted_attn_bursts),
    .accepted_mlp_bursts(accepted_mlp_bursts),
    .both_eligible_cycles(both_eligible_cycles),
    .p0_hol_cycles(p0_hol_cycles), .p1_hol_cycles(p1_hol_cycles),
    .p0_tag_high_watermark(p0_tag_high_watermark),
    .p1_tag_high_watermark(p1_tag_high_watermark)
  );

  function automatic [511:0] make_data;
    input [31:0] address;
    input integer channel;
    begin
      make_data = '0;
      make_data[31:0] = address;
      make_data[40] = channel[0];
      make_data[41] = address[31:28] == 4'hB;
    end
  endfunction

  task automatic check;
    input condition;
    input [8*120-1:0] message;
    begin
      checks = checks + 1;
      if (condition !== 1'b1) begin
        failures = failures + 1;
        $display("FAIL t=%0t check=%0d %0s", $time, checks, message);
      end
    end
  endtask

  // Physical MIG0: ordered AR queue, one-cycle minimum response latency.
  always @(posedge ddr0_clk or negedge ddr0_rst_n) begin
    if (!ddr0_rst_n) begin
      p0_wr <= 0; p0_rd <= 0; p0_rsp_delay <= 0;
      p0_rvalid <= 1'b0; p0_rdata <= '0; p0_rlast <= 1'b0;
      a0_rcvd <= 0; m0_rcvd <= 0;
    end else begin
      if (p0_arvalid && p0_arready) begin
        if (p0_wr >= MAX_LOG) $fatal(1, "MIG0 AR log overflow");
        p0_addr_q[p0_wr] <= p0_araddr;
        p0_owner_log[p0_wr] <= p0_araddr[31:28] == 4'hB;
        p0_wr <= p0_wr + 1;
      end
      if (p0_rsp_delay != 0) p0_rsp_delay <= p0_rsp_delay - 1;
      if (!p0_rvalid && responders_enable && p0_rd < p0_wr &&
          p0_rsp_delay == 0) begin
        p0_rvalid <= 1'b1;
        p0_rdata <= make_data(p0_addr_q[p0_rd], 0);
        p0_rlast <= 1'b1;
      end else if (p0_rvalid && p0_rready) begin
        p0_rvalid <= 1'b0;
        p0_rlast <= 1'b0;
        p0_rd <= p0_rd + 1;
        p0_rsp_delay <= 1;
      end
      if (a0_rvalid && a0_rready) begin
        if (a0_rdata[41] || a0_rdata[40] || !a0_rlast || a0_rresp != 0)
          $fatal(1, "MIG0 Attention response misroute/framing error");
        a0_rcvd <= a0_rcvd + 1;
      end
      if (m0_rvalid && m0_rready) begin
        if (!m0_rdata[41] || m0_rdata[40] || !m0_rlast || m0_rresp != 0)
          $fatal(1, "MIG0 MLP response misroute/framing error");
        m0_rcvd <= m0_rcvd + 1;
      end
    end
  end

  // Physical MIG1 responds on a different clock and with a different gap.
  always @(posedge ddr1_clk or negedge ddr1_rst_n) begin
    if (!ddr1_rst_n) begin
      p1_wr <= 0; p1_rd <= 0; p1_rsp_delay <= 0;
      p1_rvalid <= 1'b0; p1_rdata <= '0; p1_rlast <= 1'b0;
      a1_rcvd <= 0; m1_rcvd <= 0;
    end else begin
      if (p1_arvalid && p1_arready) begin
        if (p1_wr >= MAX_LOG) $fatal(1, "MIG1 AR log overflow");
        p1_addr_q[p1_wr] <= p1_araddr;
        p1_owner_log[p1_wr] <= p1_araddr[31:28] == 4'hB;
        p1_wr <= p1_wr + 1;
      end
      if (p1_rsp_delay != 0) p1_rsp_delay <= p1_rsp_delay - 1;
      if (!p1_rvalid && responders_enable && p1_rd < p1_wr &&
          p1_rsp_delay == 0) begin
        p1_rvalid <= 1'b1;
        p1_rdata <= make_data(p1_addr_q[p1_rd], 1);
        p1_rlast <= 1'b1;
      end else if (p1_rvalid && p1_rready) begin
        p1_rvalid <= 1'b0;
        p1_rlast <= 1'b0;
        p1_rd <= p1_rd + 1;
        p1_rsp_delay <= 2;
      end
      if (a1_rvalid && a1_rready) begin
        if (a1_rdata[41] || !a1_rdata[40] || !a1_rlast || a1_rresp != 0)
          $fatal(1, "MIG1 Attention response misroute/framing error");
        a1_rcvd <= a1_rcvd + 1;
      end
      if (m1_rvalid && m1_rready) begin
        if (!m1_rdata[41] || !m1_rdata[40] || !m1_rlast || m1_rresp != 0)
          $fatal(1, "MIG1 MLP response misroute/framing error");
        m1_rcvd <= m1_rcvd + 1;
      end
    end
  end

  task automatic set_idle_requests;
    begin
      a0_arvalid = 1'b0; a1_arvalid = 1'b0;
      m0_arvalid = 1'b0; m1_arvalid = 1'b0;
    end
  endtask

  task automatic hard_reset;
    begin
      set_idle_requests();
      core_clear = 1'b0;
      responders_enable = 1'b1;
      p0_rresp = 2'b00; p1_rresp = 2'b00;
      p0_rlast = 1'b0; p1_rlast = 1'b0;
      @(negedge core_clk);
      core_rst_n = 1'b0; ddr0_rst_n = 1'b0; ddr1_rst_n = 1'b0;
      repeat (8) @(posedge core_clk);
      @(negedge core_clk);
      core_rst_n = 1'b1; ddr0_rst_n = 1'b1; ddr1_rst_n = 1'b1;
      repeat (24) @(posedge core_clk);
      check(!error, "hard reset did not clear sticky global error");
      check(accepted_attn_bursts == 0 && accepted_mlp_bursts == 0,
        "hard reset did not clear scheduler counters");
      check(dut.sequence_r == 0 && dut.wrr_phase_r == 0,
        "hard reset did not clear scheduler sequence/phase");
    end
  endtask

  task automatic send_a0;
    input [31:0] address; input [7:0] length; input [2:0] size;
    integer timeout;
    begin
      @(negedge ddr0_clk);
      a0_araddr = address; a0_arlen = length; a0_arsize = size;
      a0_arburst = 2'b01; a0_arvalid = 1'b1; timeout = 0;
      while (a0_arready !== 1'b1 && timeout < 200) begin
        @(negedge ddr0_clk); timeout = timeout + 1;
      end
      check(timeout < 200, "a0 request handshake timeout");
      if (a0_arready === 1'b1) @(posedge ddr0_clk);
      #0.1; a0_arvalid = 1'b0;
    end
  endtask

  task automatic send_m0;
    input [31:0] address; input [7:0] length; input [2:0] size;
    integer timeout;
    begin
      @(negedge ddr0_clk);
      m0_araddr = address; m0_arlen = length; m0_arsize = size;
      m0_arburst = 2'b01; m0_arvalid = 1'b1; timeout = 0;
      while (m0_arready !== 1'b1 && timeout < 200) begin
        @(negedge ddr0_clk); timeout = timeout + 1;
      end
      check(timeout < 200, "m0 request handshake timeout");
      if (m0_arready === 1'b1) @(posedge ddr0_clk);
      #0.1; m0_arvalid = 1'b0;
    end
  endtask

  task automatic send_a1;
    input [31:0] address; input [7:0] length; input [2:0] size;
    integer timeout;
    begin
      @(negedge ddr1_clk);
      a1_araddr = address; a1_arlen = length; a1_arsize = size;
      a1_arburst = 2'b01; a1_arvalid = 1'b1; timeout = 0;
      while (a1_arready !== 1'b1 && timeout < 200) begin
        @(negedge ddr1_clk); timeout = timeout + 1;
      end
      check(timeout < 200, "a1 request handshake timeout");
      if (a1_arready === 1'b1) @(posedge ddr1_clk);
      #0.1; a1_arvalid = 1'b0;
    end
  endtask

  task automatic send_m1;
    input [31:0] address; input [7:0] length; input [2:0] size;
    integer timeout;
    begin
      @(negedge ddr1_clk);
      m1_araddr = address; m1_arlen = length; m1_arsize = size;
      m1_arburst = 2'b01; m1_arvalid = 1'b1; timeout = 0;
      while (m1_arready !== 1'b1 && timeout < 200) begin
        @(negedge ddr1_clk); timeout = timeout + 1;
      end
      check(timeout < 200, "m1 request handshake timeout");
      if (m1_arready === 1'b1) @(posedge ddr1_clk);
      #0.1; m1_arvalid = 1'b0;
    end
  endtask

  task automatic send_attn_pair;
    input [31:0] offset; input [7:0] len0; input [7:0] len1;
    begin
      fork
        send_a0(32'hA000_0000 + offset, len0, 3'd6);
        send_a1(32'hA100_0000 + offset, len1, 3'd6);
      join
    end
  endtask

  task automatic send_mlp_pair;
    input [31:0] offset; input [7:0] len0; input [7:0] len1;
    begin
      fork
        send_m0(32'hB000_0000 + offset, len0, 3'd6);
        send_m1(32'hB100_0000 + offset, len1, 3'd6);
      join
    end
  endtask

  task automatic wait_counts;
    input integer expected_a; input integer expected_m;
    input [8*48-1:0] label_text;
    integer timeout;
    begin
      timeout = 0;
      while ((accepted_attn_bursts != expected_a ||
              accepted_mlp_bursts != expected_m) && timeout < 2000) begin
        @(posedge core_clk); #0.1; timeout = timeout + 1;
      end
      check(timeout < 2000, {label_text, ": scheduler count timeout"});
      check(accepted_attn_bursts == expected_a &&
            accepted_mlp_bursts == expected_m,
        {label_text, ": scheduler count mismatch"});
    end
  endtask

  task automatic wait_drained;
    input integer expected_a0; input integer expected_m0;
    input integer expected_a1; input integer expected_m1;
    input [8*48-1:0] label_text;
    integer timeout;
    begin
      timeout = 0;
      while ((a0_rcvd != expected_a0 || m0_rcvd != expected_m0 ||
              a1_rcvd != expected_a1 || m1_rcvd != expected_m1 ||
              core_quiescent !== 1'b1) && timeout < 4000) begin
        @(posedge core_clk); #0.1; timeout = timeout + 1;
      end
      check(timeout < 4000, {label_text, ": response drain timeout"});
      check(a0_rcvd == expected_a0 && m0_rcvd == expected_m0 &&
            a1_rcvd == expected_a1 && m1_rcvd == expected_m1,
        {label_text, ": client response counts"});
      check(core_quiescent, {label_text, ": core did not become quiescent"});
    end
  endtask

  task automatic wait_error;
    input [8*48-1:0] label_text;
    integer timeout;
    begin
      timeout = 0;
      while (error !== 1'b1 && timeout < 400) begin
        @(posedge core_clk); #0.1; timeout = timeout + 1;
      end
      check(timeout < 400, {label_text, ": sticky global error timeout"});
      check(error, {label_text, ": global error not asserted"});
      repeat (8) @(posedge core_clk);
      check(error, {label_text, ": global error was not sticky"});
    end
  endtask

  task automatic pulse_safe_clear;
    integer timeout;
    integer soft_clear_pulses;
    reg saw_reset;
    begin
      timeout = 0;
      while (core_quiescent !== 1'b1 && timeout < 1000) begin
        @(posedge core_clk); timeout = timeout + 1;
      end
      check(timeout < 1000, "safe clear precondition did not drain");
      @(negedge core_clk); core_clear = 1'b1;
      @(posedge core_clk); #0.1;
      check(!error, "safe quiescent clear raised global error");
      @(negedge core_clk); core_clear = 1'b0;
      saw_reset = 1'b0;
      soft_clear_pulses = 0;
      timeout = 0;
      while ((!saw_reset || core_quiescent !== 1'b1) && timeout < 1000) begin
        @(posedge core_clk); #0.1;
        if (dut.fifo_rst_core === 1'b1) saw_reset = 1'b1;
        if (maintenance_soft_clear_pulse) soft_clear_pulses = soft_clear_pulses + 1;
        timeout = timeout + 1;
      end
      check(timeout < 1000 && saw_reset,
        "safe clear reset interval did not complete");
      check(!error, "safe clear reset interval raised global error");
      check(soft_clear_pulses == 1,
        "safe clear did not produce exactly one engine soft-clear pulse");
      check(accepted_attn_bursts == 0 && accepted_mlp_bursts == 0 &&
            both_eligible_cycles == 0,
        "safe clear did not reset scheduler counters");
      check(dut.sequence_r == 0 && dut.wrr_phase_r == 0,
        "safe clear did not reset scheduler sequence/phase");
      check(dut.a0_skid_valid_r == 0 && dut.a1_skid_valid_r == 0 &&
            dut.m0_skid_valid_r == 0 && dut.m1_skid_valid_r == 0,
        "safe clear left a source skid descriptor pending");
      check(dut.a0_src_seq_r == 0 && dut.a1_src_seq_r == 0 &&
            dut.m0_src_seq_r == 0 && dut.m1_src_seq_r == 0,
        "safe clear did not reset all source sequences");
      check(dut.u_local0.next_issue_seq_r == 0 &&
            dut.u_local1.next_issue_seq_r == 0,
        "safe clear did not reset both local issue sequences");
    end
  endtask

  // Clear a live set of already accepted requests while all three external
  // enables are withdrawn.  Maintenance must override those enables only for
  // draining; source admission remains closed after the pause barrier.
  task automatic pulse_busy_clear_disable_enables;
    integer timeout;
    integer reset_edges;
    begin
      @(negedge core_clk); core_clear = 1'b1;
      core_enable = 1'b0; ddr0_enable = 1'b0; ddr1_enable = 1'b0;
      @(posedge core_clk); #0.1;
      check(maintenance_pause_sources,
        "busy clear did not pause source producers");
      @(negedge core_clk); core_clear = 1'b0;
      reset_edges = 0; timeout = 0;
      while ((dut.fifo_rst_core !== 1'b1 || error === 1'b1) &&
             timeout < 4000) begin
        @(posedge core_clk); #0.1;
        if (maintenance_soft_clear_pulse) reset_edges = reset_edges + 1;
        timeout = timeout + 1;
      end
      check(timeout < 4000,
        "maintenance drain deadlocked after enable withdrawal");
      check(!error, "enable-withdrawn maintenance raised global error");
      check(reset_edges == 1,
        "enable-withdrawn maintenance soft-clear pulse count");
      core_enable = 1'b1; ddr0_enable = 1'b1; ddr1_enable = 1'b1;
      timeout = 0;
      while (core_quiescent !== 1'b1 && timeout < 1000) begin
        @(posedge core_clk); #0.1; timeout = timeout + 1;
      end
      check(timeout < 1000,
        "enable-withdrawn maintenance did not return quiescent");
    end
  endtask

  integer i;
  initial begin
    // (1) Attention-only: all six pairs must issue even though WRR nominally
    // prefers MLP for two phases.  This is the work-conserving fallback check.
    hard_reset();
    phase_base0 = p0_wr; phase_base1 = p1_wr;
    for (i = 0; i < N_SINGLE; i = i + 1)
      send_attn_pair(i * 32'h40, 0, 0);
    wait_counts(N_SINGLE, 0, "Attention-only");
    wait_drained(N_SINGLE, 0, N_SINGLE, 0, "Attention-only");
    check(p0_wr - phase_base0 == N_SINGLE && p1_wr - phase_base1 == N_SINGLE,
      "Attention-only was not work-conserving on both MIGs");
    for (i = 0; i < N_SINGLE; i = i + 1) begin
      check(!p0_owner_log[phase_base0+i], "Attention-only MIG0 owner mismatch");
      check(!p1_owner_log[phase_base1+i], "Attention-only MIG1 owner mismatch");
    end

    pulse_safe_clear();

    // (2) MLP-only: likewise, the initial Attention preference may not idle.
    phase_base0 = p0_wr; phase_base1 = p1_wr;
    for (i = 0; i < N_SINGLE; i = i + 1)
      send_mlp_pair(i * 32'h40, 0, 0);
    wait_counts(0, N_SINGLE, "MLP-only");
    wait_drained(N_SINGLE, N_SINGLE, N_SINGLE, N_SINGLE, "MLP-only");
    check(p0_wr - phase_base0 == N_SINGLE && p1_wr - phase_base1 == N_SINGLE,
      "MLP-only was not work-conserving on both MIGs");
    for (i = 0; i < N_SINGLE; i = i + 1) begin
      check(p0_owner_log[phase_base0+i], "MLP-only MIG0 owner mismatch");
      check(p1_owner_log[phase_base1+i], "MLP-only MIG1 owner mismatch");
    end

    pulse_safe_clear();

    // (3) Queue both streams while scheduling is disabled, then release them
    // together.  The exact logical/physical order must be A,M,M repeated.
    core_enable = 1'b0;
    phase_base0 = p0_wr; phase_base1 = p1_wr;
    fork
      begin
        for (i = 0; i < N_DUAL_A; i = i + 1)
          send_attn_pair(i * 32'h40, 0, 0);
      end
      begin : dual_mlp_stimulus
        integer j;
        for (j = 0; j < N_DUAL_M; j = j + 1)
          send_mlp_pair(j * 32'h40, 0, 0);
      end
    join
    repeat (12) @(posedge core_clk);
    check(accepted_attn_bursts == 0 && accepted_mlp_bursts == 0,
      "disabled scheduler accepted paired traffic");
    core_enable = 1'b1;
    wait_counts(N_DUAL_A, N_DUAL_M, "dual saturation");
    wait_drained(N_SINGLE+N_DUAL_A, N_SINGLE+N_DUAL_M,
                 N_SINGLE+N_DUAL_A, N_SINGLE+N_DUAL_M, "dual saturation");
    check(both_eligible_cycles >= N_DUAL_A,
      "dual saturation did not exercise simultaneous eligibility");
    check(p0_wr - phase_base0 == N_DUAL_A+N_DUAL_M &&
          p1_wr - phase_base1 == N_DUAL_A+N_DUAL_M,
      "dual saturation physical AR totals mismatch");
    for (i = 0; i < N_DUAL_A+N_DUAL_M; i = i + 1) begin
      check(p0_owner_log[phase_base0+i] == ((i % 3) != 0),
        "MIG0 owner order is not exact A,M,M");
      check(p1_owner_log[phase_base1+i] == ((i % 3) != 0),
        "MIG1 owner order is not exact A,M,M");
      check(p0_owner_log[phase_base0+i] == p1_owner_log[phase_base1+i],
        "paired MIG owner sequences diverged");
    end

    pulse_safe_clear();

    // Safe clear must restart scheduler/source/local sequence state.  A fresh
    // sequence-zero request is accepted and returned after the maintenance reset.
    send_attn_pair(32'h0000_1000, 0, 0);
    wait_counts(1, 0, "post-clear sequence restart");
    wait_drained(N_SINGLE+N_DUAL_A+1, N_SINGLE+N_DUAL_M,
                 N_SINGLE+N_DUAL_A+1, N_SINGLE+N_DUAL_M,
                 "post-clear sequence restart");
    check(dut.sequence_r == 1 && dut.u_local0.next_issue_seq_r == 1 &&
          dut.u_local1.next_issue_seq_r == 1,
      "post-clear first request did not restart sequence at zero");

    // (4a) Paired sequence mismatch: inject a corrupted DDR0 source sequence
    // on the otherwise matching pair.  Sequence is not a top-level input, so
    // hierarchical force is the fault-injection mechanism for this case.
    hard_reset();
    force dut.a0_src_seq_r = 16'd1;
    send_attn_pair(32'h0000_2000, 0, 0);
    release dut.a0_src_seq_r;
    wait_error("paired sequence mismatch");
    check(accepted_attn_bursts == 0,
      "sequence-mismatched pair was incorrectly scheduled");
    @(negedge core_clk); core_clear = 1'b1;
    @(posedge core_clk); #0.1;
    @(negedge core_clk); core_clear = 1'b0;
    repeat (8) @(posedge core_clk);
    check(error, "core_clear illegally cleared sequence mismatch error");

    // (4b) Shape mismatch is independently fatal even with matched sequence.
    hard_reset();
    send_attn_pair(32'h0000_3000, 0, 1);
    wait_error("paired shape mismatch");
    check(accepted_attn_bursts == 0,
      "shape-mismatched pair was incorrectly scheduled");

    // (5a) Unsafe clear while a paired burst is outstanding must freeze with a
    // sticky error; maintenance clear itself may not recover it.
    hard_reset();
    responders_enable = 1'b0;
    phase_base0 = p0_wr; phase_base1 = p1_wr;
    send_mlp_pair(32'h0000_4000, 0, 0);
    wait_counts(0, 1, "unsafe-clear setup");
    i = 0;
    while ((p0_wr < phase_base0+1 || p1_wr < phase_base1+1 ||
            core_quiescent !== 1'b0) && i < 400) begin
      @(posedge core_clk); #0.1; i = i + 1;
    end
    check(i < 400, "unsafe-clear setup did not become observably active");
    check(!core_quiescent, "unsafe-clear setup unexpectedly quiescent");
    // Presenting clear over an outstanding burst starts a coordinated drain;
    // corrupting that outstanding R beat makes the drain unsafe/fatal.
    @(negedge ddr0_clk);
    p0_rvalid = 1'b1; p0_rdata = make_data(32'hB000_4000, 0);
    p0_rresp = 2'b10; p0_rlast = 1'b1;
    @(negedge core_clk); core_clear = 1'b1;
    @(posedge core_clk); #0.1;
    @(negedge core_clk); core_clear = 1'b0;
    wait_error("unsafe core_clear");
    check(accepted_mlp_bursts == 1,
      "unsafe clear altered accepted counter before hard reset");

    // (5b) Hard reset recovers fatal state.  Drain a normal request, then legal
    // clear resets all counters and sequence state a second time.
    hard_reset();
    send_mlp_pair(32'h0000_5000, 0, 0);
    wait_counts(0, 1, "safe-drain setup");
    wait_drained(0, 1, 0, 1, "safe-drain setup");
    pulse_safe_clear();
    check(core_quiescent, "safe drain/clear did not return to quiescent state");

    // (6) Queue both owners, prevent physical responses long enough to make
    // the request observably live, then clear while all enables are removed.
    // The source pause acknowledgement is already high in this leaf-level TB;
    // production must derive it from the actual readers.
    hard_reset();
    responders_enable = 1'b0;
    send_attn_pair(32'h0000_6000, 0, 0);
    send_mlp_pair(32'h0000_6040, 0, 0);
    wait_counts(1, 1, "enable-withdrawn maintenance setup");
    responders_enable = 1'b1;
    pulse_busy_clear_disable_enables();
    check(a0_rcvd == 1 && a1_rcvd == 1 && m0_rcvd == 1 && m1_rcvd == 1,
      "enable-withdrawn maintenance lost an accepted response");

    // (7) A producer that violates the post-barrier pause is a sticky fatal
    // protocol error.  A soft clear may not hide the half-pair risk.
    hard_reset();
    @(negedge core_clk); core_clear = 1'b1;
    @(negedge core_clk); core_clear = 1'b0;
    i = 0;
    while (!dut.maintenance_stop_ddr0 && i < 400) begin
      @(posedge ddr0_clk); i = i + 1;
    end
    check(i < 400, "maintenance stop did not reach DDR0");
    @(negedge ddr0_clk); a0_arvalid = 1'b1;
    @(posedge ddr0_clk); #0.1;
    @(negedge ddr0_clk); a0_arvalid = 1'b0;
    wait_error("post-stop source violation");
    @(negedge core_clk); core_clear = 1'b1;
    @(posedge core_clk); #0.1;
    @(negedge core_clk); core_clear = 1'b0;
    repeat (8) @(posedge core_clk);
    check(error, "soft clear hid post-stop source violation");

    if (failures != 0) begin
      $display("FAIL hap_axi512_paired_2client_read_wrr_modes failures=%0d checks=%0d",
        failures, checks);
      $finish;
    end
    $display("PASS hap_axi512_paired_2client_read_wrr_modes checks=%0d", checks);
    $finish;
  end

  initial begin
    #2000000;
    $fatal(1, "hap_axi512_paired_2client_read_wrr_modes global timeout");
  end
endmodule
