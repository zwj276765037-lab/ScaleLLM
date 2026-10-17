`timescale 1ns / 1ps

// Directed reset-contract regression for the V4 paired DDR leaf.
//
// core_rst_n is the local master reset and must assert the registered FIFO
// reset request immediately.  Each remote DDR reset is source-qualified and
// sampled by its own hard_rst_core synchronizer.  The production contract
// keeps a remote reset low across at least two rising core_clk edges while
// core_clk is running.  Exercise that minimum and overlapping release, then
// prove a clean functional restart at core100 / DDR200+200 MHz.
module hap_axi512_paired_2client_read_wrr_resets_tb;
  reg core_clk = 1'b0, ddr0_clk = 1'b0, ddr1_clk = 1'b0;
  always #5 core_clk = ~core_clk;
  always #2.5 ddr0_clk = ~ddr0_clk;
  initial begin #0.625; forever #2.5 ddr1_clk = ~ddr1_clk; end

  reg core_rst_n = 1'b0, ddr0_rst_n = 1'b0, ddr1_rst_n = 1'b0;
  reg a0_arvalid = 1'b0, a1_arvalid = 1'b0;
  reg [31:0] a0_araddr = 0, a1_araddr = 0;
  wire a0_arready, a1_arready;
  wire a0_rvalid, a1_rvalid;
  wire [511:0] a0_rdata, a1_rdata;
  wire [1:0] a0_rresp, a1_rresp;
  wire a0_rlast, a1_rlast;

  wire p0_arvalid, p1_arvalid;
  wire p0_arready, p1_arready;
  wire [31:0] p0_araddr, p1_araddr;
  wire [7:0] p0_arlen, p1_arlen;
  wire [2:0] p0_arsize, p1_arsize;
  wire [1:0] p0_arburst, p1_arburst;
  reg p0_rvalid = 1'b0, p1_rvalid = 1'b0;
  wire p0_rready, p1_rready;
  reg [511:0] p0_rdata = 0, p1_rdata = 0;
  reg p0_rlast = 1'b0, p1_rlast = 1'b0;
  reg p0_pending = 1'b0, p1_pending = 1'b0;
  reg [31:0] p0_pending_addr = 0, p1_pending_addr = 0;

  wire core_quiescent, error;
  wire [31:0] accepted_attn_bursts, accepted_mlp_bursts;
  wire [31:0] both_eligible_cycles;
  wire [31:0] p0_hol_cycles, p1_hol_cycles;
  wire [31:0] p0_tag_high_watermark, p1_tag_high_watermark;
  integer failures = 0, checks = 0;
  integer a0_received = 0, a1_received = 0;
  reg [31:0] expected_a0_addr = 0, expected_a1_addr = 0;

  assign p0_arready = ddr0_rst_n && !p0_pending && !p0_rvalid;
  assign p1_arready = ddr1_rst_n && !p1_pending && !p1_rvalid;

  hap_axi512_paired_2client_read_wrr #(
    .FIFO_DEPTH(16), .TAG_DEPTH(16), .SEQ_W(16)
  ) dut (
    .core_clk(core_clk), .core_rst_n(core_rst_n), .core_clear(1'b0),
    .core_enable(1'b1), .attn_source_quiescent(1'b1),
    .mlp_source_quiescent(1'b1), .maintenance_pause_sources(),
    .maintenance_drain_active(), .maintenance_soft_clear_pulse(),
    .ddr0_clk(ddr0_clk), .ddr0_rst_n(ddr0_rst_n), .ddr0_enable(1'b1),
    .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n), .ddr1_enable(1'b1),
    .a0_arvalid(a0_arvalid), .a0_arready(a0_arready),
    .a0_araddr(a0_araddr), .a0_arlen(8'd0), .a0_arsize(3'd6),
    .a0_arburst(2'b01), .a0_rvalid(a0_rvalid), .a0_rready(1'b1),
    .a0_rdata(a0_rdata), .a0_rresp(a0_rresp), .a0_rlast(a0_rlast),
    .m0_arvalid(1'b0), .m0_arready(), .m0_araddr(32'd0),
    .m0_arlen(8'd0), .m0_arsize(3'd6), .m0_arburst(2'b01),
    .m0_rvalid(), .m0_rready(1'b1), .m0_rdata(), .m0_rresp(), .m0_rlast(),
    .a1_arvalid(a1_arvalid), .a1_arready(a1_arready),
    .a1_araddr(a1_araddr), .a1_arlen(8'd0), .a1_arsize(3'd6),
    .a1_arburst(2'b01), .a1_rvalid(a1_rvalid), .a1_rready(1'b1),
    .a1_rdata(a1_rdata), .a1_rresp(a1_rresp), .a1_rlast(a1_rlast),
    .m1_arvalid(1'b0), .m1_arready(), .m1_araddr(32'd0),
    .m1_arlen(8'd0), .m1_arsize(3'd6), .m1_arburst(2'b01),
    .m1_rvalid(), .m1_rready(1'b1), .m1_rdata(), .m1_rresp(), .m1_rlast(),
    .p0_arvalid(p0_arvalid), .p0_arready(p0_arready),
    .p0_araddr(p0_araddr), .p0_arlen(p0_arlen),
    .p0_arsize(p0_arsize), .p0_arburst(p0_arburst),
    .p0_rvalid(p0_rvalid), .p0_rready(p0_rready), .p0_rdata(p0_rdata),
    .p0_rresp(2'b00), .p0_rlast(p0_rlast),
    .p1_arvalid(p1_arvalid), .p1_arready(p1_arready),
    .p1_araddr(p1_araddr), .p1_arlen(p1_arlen),
    .p1_arsize(p1_arsize), .p1_arburst(p1_arburst),
    .p1_rvalid(p1_rvalid), .p1_rready(p1_rready), .p1_rdata(p1_rdata),
    .p1_rresp(2'b00), .p1_rlast(p1_rlast),
    .core_quiescent(core_quiescent), .error(error),
    .accepted_attn_bursts(accepted_attn_bursts),
    .accepted_mlp_bursts(accepted_mlp_bursts),
    .both_eligible_cycles(both_eligible_cycles),
    .p0_hol_cycles(p0_hol_cycles), .p1_hol_cycles(p1_hol_cycles),
    .p0_tag_high_watermark(p0_tag_high_watermark),
    .p1_tag_high_watermark(p1_tag_high_watermark)
  );

  task automatic check;
    input condition;
    input [8*96-1:0] message;
    begin
      checks = checks + 1;
      if (condition !== 1'b1) begin
        failures = failures + 1;
        $display("FAIL t=%0t check=%0d %0s", $time, checks, message);
      end
    end
  endtask

  // Minimal ordered one-beat physical responders.  Testbench receive counters
  // deliberately survive individual DUT reset pulses so restart traffic can
  // be checked against a monotonic baseline.
  always @(posedge ddr0_clk or negedge ddr0_rst_n) begin
    if (!ddr0_rst_n) begin
      p0_pending <= 1'b0; p0_rvalid <= 1'b0; p0_rlast <= 1'b0;
    end else begin
      if (p0_arvalid && p0_arready) begin
        check(p0_araddr == expected_a0_addr,
          "DDR0 physical address changed across restart");
        p0_pending <= 1'b1; p0_pending_addr <= p0_araddr;
      end
      if (p0_pending && !p0_rvalid) begin
        p0_rvalid <= 1'b1; p0_rlast <= 1'b1;
        p0_rdata <= {480'd0, p0_pending_addr};
      end
      if (p0_rvalid && p0_rready) begin
        p0_pending <= 1'b0; p0_rvalid <= 1'b0; p0_rlast <= 1'b0;
      end
      if (a0_rvalid) begin
        check(a0_rlast && a0_rresp == 0,
          "DDR0 Attention restart response framing");
        check(a0_rdata[31:0] == expected_a0_addr,
          "DDR0 Attention restart response payload");
        a0_received = a0_received + 1;
      end
    end
  end

  always @(posedge ddr1_clk or negedge ddr1_rst_n) begin
    if (!ddr1_rst_n) begin
      p1_pending <= 1'b0; p1_rvalid <= 1'b0; p1_rlast <= 1'b0;
    end else begin
      if (p1_arvalid && p1_arready) begin
        check(p1_araddr == expected_a1_addr,
          "DDR1 physical address changed across restart");
        p1_pending <= 1'b1; p1_pending_addr <= p1_araddr;
      end
      if (p1_pending && !p1_rvalid) begin
        p1_rvalid <= 1'b1; p1_rlast <= 1'b1;
        p1_rdata <= {480'd0, p1_pending_addr};
      end
      if (p1_rvalid && p1_rready) begin
        p1_pending <= 1'b0; p1_rvalid <= 1'b0; p1_rlast <= 1'b0;
      end
      if (a1_rvalid) begin
        check(a1_rlast && a1_rresp == 0,
          "DDR1 Attention restart response framing");
        check(a1_rdata[31:0] == expected_a1_addr,
          "DDR1 Attention restart response payload");
        a1_received = a1_received + 1;
      end
    end
  end

  task automatic send_a0;
    input [31:0] address;
    integer timeout;
    begin
      @(negedge ddr0_clk); a0_araddr = address; a0_arvalid = 1'b1;
      timeout = 0;
      while (a0_arready !== 1'b1 && timeout < 200) begin
        @(posedge ddr0_clk); #0.1; timeout = timeout + 1;
      end
      check(timeout < 200, "DDR0 Attention AR restart timeout");
      @(negedge ddr0_clk); a0_arvalid = 1'b0;
    end
  endtask

  task automatic send_a1;
    input [31:0] address;
    integer timeout;
    begin
      @(negedge ddr1_clk); a1_araddr = address; a1_arvalid = 1'b1;
      timeout = 0;
      while (a1_arready !== 1'b1 && timeout < 200) begin
        @(posedge ddr1_clk); #0.1; timeout = timeout + 1;
      end
      check(timeout < 200, "DDR1 Attention AR restart timeout");
      @(negedge ddr1_clk); a1_arvalid = 1'b0;
    end
  endtask

  task automatic exercise_restart;
    input [31:0] offset;
    integer base0, base1, timeout;
    begin
      base0 = a0_received; base1 = a1_received;
      expected_a0_addr = 32'hA000_0000 + offset;
      expected_a1_addr = 32'hA100_0000 + offset;
      fork
        send_a0(expected_a0_addr);
        send_a1(expected_a1_addr);
      join
      timeout = 0;
      while ((accepted_attn_bursts != 1 || a0_received != base0 + 1 ||
              a1_received != base1 + 1 || core_quiescent !== 1'b1) &&
             timeout < 1000) begin
        @(posedge core_clk); #0.1; timeout = timeout + 1;
      end
      check(timeout < 1000, "post-reset paired Attention restart timeout");
      check(accepted_attn_bursts == 1 && accepted_mlp_bursts == 0,
        "post-reset scheduler counters");
      check(dut.sequence_r == 1 && dut.u_local0.next_issue_seq_r == 1 &&
            dut.u_local1.next_issue_seq_r == 1,
        "post-reset sequence did not restart at zero");
      check(!error, "post-reset traffic raised error");
    end
  endtask

  task automatic wait_reset_complete;
    input [8*32-1:0] label_text;
    integer timeout;
    reg saw_fifo_reset;
    begin
      timeout = 0; saw_fifo_reset = 1'b0;
      while ((dut.fifo_reset_request_r !== 1'b0 ||
              dut.fifo_rst_core !== 1'b0 ||
              dut.fifo_rst_ddr0 !== 1'b0 ||
              dut.fifo_rst_ddr1 !== 1'b0 ||
              core_quiescent !== 1'b1) && timeout < 1000) begin
        @(posedge core_clk); #0.1;
        if (dut.fifo_rst_core === 1'b1) saw_fifo_reset = 1'b1;
        timeout = timeout + 1;
      end
      check(timeout < 1000, {label_text, " reset completion timeout"});
      check(saw_fifo_reset, {label_text, " did not reach FIFO reset"});
      check(!error, {label_text, " left sticky error"});
      check(accepted_attn_bursts == 0 && accepted_mlp_bursts == 0 &&
            both_eligible_cycles == 0,
        {label_text, " did not clear scheduler counters"});
      check(dut.sequence_r == 0 && dut.wrr_phase_r == 0 &&
            dut.a0_src_seq_r == 0 && dut.a1_src_seq_r == 0 &&
            dut.m0_src_seq_r == 0 && dut.m1_src_seq_r == 0 &&
            dut.u_local0.next_issue_seq_r == 0 &&
            dut.u_local1.next_issue_seq_r == 0,
        {label_text, " did not clear sequence state"});
    end
  endtask

  task automatic pulse_core_reset;
    begin
      @(negedge core_clk); core_rst_n = 1'b0; #0.1;
      check(dut.fifo_reset_request_r === 1'b1 &&
            dut.reset_shift_r === 5'b11111,
        "core_rst_n did not asynchronously assert reset manager");
    repeat (2) @(posedge core_clk);
      @(negedge core_clk); core_rst_n = 1'b1;
      wait_reset_complete("core-only");
    end
  endtask

  task automatic pulse_remote_min;
    input integer channel;
    integer timeout;
    begin
      @(negedge core_clk);
      if (channel == 0) ddr0_rst_n = 1'b0;
      else ddr1_rst_n = 1'b0;
      #0.1;
      check(channel == 0 ? dut.ddr0_hard_req_r === 1'b1 :
                           dut.ddr1_hard_req_r === 1'b1,
        "minimum remote pulse did not set source request");
      check(dut.fifo_reset_request_r === 1'b0,
        "minimum remote pulse bypassed core reset manager");
      // Release at the next falling edge after exactly two core rising edges.
      repeat (2) @(posedge core_clk);
      @(negedge core_clk);
      if (channel == 0) ddr0_rst_n = 1'b1;
      else ddr1_rst_n = 1'b1;
      timeout = 0;
      while (dut.fifo_reset_request_r !== 1'b1 && timeout < 20) begin
        @(posedge core_clk); #0.1; timeout = timeout + 1;
      end
      check(timeout < 20,
        "two-core-edge remote pulse missed registered FIFO reset manager");
      if (channel == 0) wait_reset_complete("ddr0-minimum");
      else wait_reset_complete("ddr1-minimum");
    end
  endtask

  task automatic overlap_remote_resets;
    begin
      @(negedge core_clk); ddr0_rst_n = 1'b0;
      repeat (2) @(posedge core_clk);
      @(negedge core_clk); ddr1_rst_n = 1'b0;
      repeat (2) @(posedge core_clk);
      @(negedge core_clk); ddr0_rst_n = 1'b1;
      repeat (2) @(posedge core_clk); #0.1;
      check(dut.hard_rst_core === 1'b1 &&
            dut.fifo_reset_request_r === 1'b1,
        "DDR1 did not hold core hard reset through DDR0 release");
      @(negedge core_clk); ddr1_rst_n = 1'b1;
      wait_reset_complete("overlap-ddr0-ddr1");
    end
  endtask

  task automatic overlap_core_remote_reset;
    begin
      @(negedge core_clk); ddr0_rst_n = 1'b0;
      repeat (2) @(posedge core_clk);
      @(negedge core_clk); core_rst_n = 1'b0;
      #0.1;
      check(dut.fifo_reset_request_r === 1'b1,
        "overlapping core reset did not asynchronously set FIFO request");
      repeat (2) @(posedge core_clk);
      @(negedge core_clk); core_rst_n = 1'b1;
      repeat (2) @(posedge core_clk); #0.1;
      check(dut.hard_rst_core === 1'b1 &&
            dut.fifo_reset_request_r === 1'b1,
        "DDR0 did not hold core hard reset through core release");
      @(negedge core_clk); ddr0_rst_n = 1'b1;
      wait_reset_complete("overlap-core-ddr0");
    end
  endtask

  task automatic pulse_remote_reset;
    input integer channel;
    integer timeout;
    begin
      @(negedge core_clk);
      if (channel == 0) ddr0_rst_n = 1'b0;
      else ddr1_rst_n = 1'b0;
      #0.1;
      check(dut.fifo_reset_request_r === 1'b0,
        "remote reset bypassed registered/synchronized manager");
      // Production minimum: hold the remote request across at least two rising
      // core edges while core_clk remains active.  XPM's two-stage behavioral
      // model may expose hard_rst_core after an additional delta/edge, so wait
      // for the actual synchronized level before releasing the source reset.
      repeat (2) @(posedge core_clk); #0.1;
      timeout = 0;
      while (dut.hard_rst_core !== 1'b1 && timeout < 20) begin
        @(posedge core_clk); #0.1; timeout = timeout + 1;
      end
      check(timeout < 20,
        "remote reset did not reach synchronized hard_rst_core");
      timeout = 0;
      while (dut.fifo_reset_request_r !== 1'b1 && timeout < 20) begin
        @(posedge core_clk); #0.1; timeout = timeout + 1;
      end
      check(timeout < 20,
        "remote reset was not captured by registered FIFO reset manager");
      @(negedge core_clk);
      if (channel == 0) ddr0_rst_n = 1'b1;
      else ddr1_rst_n = 1'b1;
      if (channel == 0) wait_reset_complete("ddr0-only");
      else wait_reset_complete("ddr1-only");
    end
  endtask

  initial begin
    repeat (8) @(posedge core_clk);
    @(negedge core_clk);
    core_rst_n = 1'b1; ddr0_rst_n = 1'b1; ddr1_rst_n = 1'b1;
    repeat (40) @(posedge core_clk); #0.1;
    check(core_quiescent && !error, "initial reset release did not quiesce");
    check(!dut.core_hard_req_r && !dut.ddr0_hard_req_r &&
          !dut.ddr1_hard_req_r && !dut.hard_rst_core &&
          !dut.hard_rst_ddr0 && !dut.hard_rst_ddr1,
      "source-qualified hard resets did not release after initialization");

    exercise_restart(32'h0000_0000);
    pulse_core_reset();
    exercise_restart(32'h0000_0040);
    pulse_remote_reset(0);
    exercise_restart(32'h0000_0080);
    pulse_remote_reset(1);
    exercise_restart(32'h0000_00C0);
    pulse_remote_min(0);
    exercise_restart(32'h0000_0100);
    pulse_remote_min(1);
    exercise_restart(32'h0000_0140);
    overlap_remote_resets();
    exercise_restart(32'h0000_0180);
    overlap_core_remote_reset();
    exercise_restart(32'h0000_01C0);

    if (failures != 0) begin
      $display("FAIL hap_axi512_paired_2client_read_wrr_resets failures=%0d checks=%0d",
        failures, checks);
      $finish;
    end
    $display("PASS hap_axi512_paired_2client_read_wrr_resets checks=%0d", checks);
    $display("HARDWARE_AGENT_SIM_PASS");
    $finish;
  end

  initial begin
    #2000000;
    $fatal(1, "hap_axi512_paired_2client_read_wrr_resets global timeout");
  end
endmodule
