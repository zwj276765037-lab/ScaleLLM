`timescale 1ns / 1ps

// Protocol-contract test for one MIG-local ordered response unit.
//
// This test deliberately treats hap_axi512_ordered_local_issue as a black box.
// In particular, no internal FIFO/count signal is referenced.  The required
// depth-two response elasticity and the absence of a combinational path from a
// client RREADY to the MIG RREADY are inferred solely from external handshakes.
module hap_axi512_ordered_local_issue_protocol_tb;
  localparam integer AXI_ADDR_W = 32;
  localparam integer SEQ_W      = 16;
  localparam integer TAG_DEPTH  = 16;
  localparam integer DESC_W     = AXI_ADDR_W + 13;
  localparam integer EGRESS_W   = 1 + SEQ_W + DESC_W;

  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg rst_n = 1'b0;
  reg hard_reset_req = 1'b0;
  reg soft_reset = 1'b0;
  reg enable = 1'b1;

  reg desc_valid = 1'b0;
  wire desc_ready;
  reg [EGRESS_W-1:0] desc_data = '0;

  wire m_axi_arvalid;
  reg  m_axi_arready = 1'b1;
  wire [AXI_ADDR_W-1:0] m_axi_araddr;
  wire [7:0] m_axi_arlen;
  wire [2:0] m_axi_arsize;
  wire [1:0] m_axi_arburst;

  reg m_axi_rvalid = 1'b0;
  wire m_axi_rready;
  reg [511:0] m_axi_rdata = '0;
  reg [1:0] m_axi_rresp = 2'b00;
  reg m_axi_rlast = 1'b0;

  wire attn_rvalid;
  reg  attn_rready = 1'b0;
  wire [511:0] attn_rdata;
  wire [1:0] attn_rresp;
  wire attn_rlast;
  wire mlp_rvalid;
  reg  mlp_rready = 1'b0;
  wire [511:0] mlp_rdata;
  wire [1:0] mlp_rresp;
  wire mlp_rlast;

  wire quiescent;
  wire protocol_error;
  wire [31:0] physical_ar_count;
  wire [31:0] physical_r_count;
  wire [31:0] attn_burst_count;
  wire [31:0] mlp_burst_count;
  wire [31:0] hol_cycle_count;
  wire [31:0] tag_high_watermark;

  integer checks = 0;
  integer failures = 0;
  integer attn_deliveries = 0;
  integer mlp_deliveries = 0;
  reg [31:0] attn_log [0:31];
  reg [31:0] mlp_log [0:31];
  integer i;

  hap_axi512_ordered_local_issue #(
    .AXI_ADDR_W(AXI_ADDR_W),
    .SEQ_W(SEQ_W),
    .TAG_DEPTH(TAG_DEPTH)
  ) dut (
    .clk(clk),
    .rst_n(rst_n),
    .hard_reset(hard_reset_req),
    .soft_reset(soft_reset),
    .enable(enable),
    .freeze(1'b0),
    .desc_valid(desc_valid),
    .desc_ready(desc_ready),
    .desc_data(desc_data),
    .m_axi_arvalid(m_axi_arvalid),
    .m_axi_arready(m_axi_arready),
    .m_axi_araddr(m_axi_araddr),
    .m_axi_arlen(m_axi_arlen),
    .m_axi_arsize(m_axi_arsize),
    .m_axi_arburst(m_axi_arburst),
    .m_axi_rvalid(m_axi_rvalid),
    .m_axi_rready(m_axi_rready),
    .m_axi_rdata(m_axi_rdata),
    .m_axi_rresp(m_axi_rresp),
    .m_axi_rlast(m_axi_rlast),
    .attn_rvalid(attn_rvalid),
    .attn_rready(attn_rready),
    .attn_rdata(attn_rdata),
    .attn_rresp(attn_rresp),
    .attn_rlast(attn_rlast),
    .mlp_rvalid(mlp_rvalid),
    .mlp_rready(mlp_rready),
    .mlp_rdata(mlp_rdata),
    .mlp_rresp(mlp_rresp),
    .mlp_rlast(mlp_rlast),
    .quiescent(quiescent),
    .protocol_error(protocol_error),
    .physical_ar_count(physical_ar_count),
    .physical_r_count(physical_r_count),
    .attn_burst_count(attn_burst_count),
    .mlp_burst_count(mlp_burst_count),
    .hol_cycle_count(hol_cycle_count),
    .tag_high_watermark(tag_high_watermark)
  );

  function automatic [511:0] payload;
    input [31:0] id;
    begin
      payload = '0;
      payload[31:0]  = id;
      payload[63:32] = ~id;
      payload[95:64] = 32'h4C4F_434C; // "LOCL"
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

  // Record only real client handshakes.  A protocol-error beat must never
  // appear here, even for one cycle with the corresponding RREADY asserted.
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      attn_deliveries <= 0;
      mlp_deliveries <= 0;
      for (i = 0; i < 32; i = i + 1) begin
        attn_log[i] <= '0;
        mlp_log[i] <= '0;
      end
    end else begin
      if (attn_rvalid && attn_rready) begin
        attn_log[attn_deliveries] <= attn_rdata[31:0];
        attn_deliveries <= attn_deliveries + 1;
        if (attn_rresp != 2'b00) begin
          failures = failures + 1;
          $display("FAIL t=%0t bad RRESP reached Attention client", $time);
        end
      end
      if (mlp_rvalid && mlp_rready) begin
        mlp_log[mlp_deliveries] <= mlp_rdata[31:0];
        mlp_deliveries <= mlp_deliveries + 1;
        if (mlp_rresp != 2'b00) begin
          failures = failures + 1;
          $display("FAIL t=%0t bad RRESP reached MLP client", $time);
        end
      end
    end
  end

  task automatic reset_via_rst_n;
    begin
      @(negedge clk);
      rst_n = 1'b0;
      hard_reset_req = 1'b0;
      soft_reset = 1'b0;
      enable = 1'b1;
      desc_valid = 1'b0;
      desc_data = '0;
      m_axi_arready = 1'b1;
      m_axi_rvalid = 1'b0;
      m_axi_rdata = '0;
      m_axi_rresp = 2'b00;
      m_axi_rlast = 1'b0;
      attn_rready = 1'b0;
      mlp_rready = 1'b0;
      repeat (3) @(posedge clk);
      @(negedge clk);
      rst_n = 1'b1;
      @(posedge clk);
      #1;
      check(!protocol_error, "hard reset must clear sticky protocol_error");
      check(quiescent, "hard-reset state must be quiescent");
      check(!attn_rvalid && !mlp_rvalid,
        "rst_n reset must empty both client response FIFOs");
    end
  endtask

  task automatic pulse_hard_reset;
    begin
      @(negedge clk);
      hard_reset_req = 1'b1;
      soft_reset = 1'b0;
      @(posedge clk);
      #1;
      check(!protocol_error,
        "dedicated hard_reset must clear sticky protocol_error");
      check(quiescent,
        "dedicated hard_reset must clear all local queue state");
      check(!attn_rvalid && !mlp_rvalid,
        "dedicated hard_reset must empty both client response FIFOs");
      check(physical_ar_count == 0 && physical_r_count == 0,
        "dedicated hard_reset must clear local traffic counters");
      @(negedge clk);
      hard_reset_req = 1'b0;
    end
  endtask

  task automatic issue_desc;
    input owner;
    input [SEQ_W-1:0] seq_value;
    input [AXI_ADDR_W-1:0] address;
    input [7:0] length;
    input [8*48-1:0] label_text;
    integer timeout;
    begin
      @(negedge clk);
      desc_data = {owner, seq_value, address, length, 3'd6, 2'b01};
      desc_valid = 1'b1;
      timeout = 0;
      while (desc_ready !== 1'b1 && timeout < 40) begin
        @(negedge clk);
        timeout = timeout + 1;
      end
      check(timeout < 40, {label_text, ": descriptor-ready timeout"});
      if (desc_ready === 1'b1) begin
        @(posedge clk);
        #1;
      end
      desc_valid = 1'b0;
    end
  endtask

  task automatic wait_ar_count;
    input integer target;
    input [8*48-1:0] label_text;
    integer timeout;
    begin
      timeout = 0;
      while (physical_ar_count < target && timeout < 80) begin
        @(posedge clk);
        #1;
        timeout = timeout + 1;
      end
      check(timeout < 80, {label_text, ": physical AR timeout"});
      check(physical_ar_count == target,
        {label_text, ": unexpected physical AR count"});
    end
  endtask

  task automatic accept_r_beat;
    input [31:0] id;
    input [1:0] response;
    input last;
    input [8*48-1:0] label_text;
    begin
      @(negedge clk);
      m_axi_rdata = payload(id);
      m_axi_rresp = response;
      m_axi_rlast = last;
      m_axi_rvalid = 1'b1;
      #1;
      check(m_axi_rready, {label_text, ": MIG beat was not accepted"});
      @(posedge clk);
      #1;
      m_axi_rvalid = 1'b0;
      m_axi_rdata = '0;
      m_axi_rresp = 2'b00;
      m_axi_rlast = 1'b0;
    end
  endtask

  task automatic wait_quiescent;
    input [8*48-1:0] label_text;
    integer timeout;
    begin
      timeout = 0;
      while (quiescent !== 1'b1 && timeout < 80) begin
        @(posedge clk);
        #1;
        timeout = timeout + 1;
      end
      check(timeout < 80, {label_text, ": quiescent timeout"});
    end
  endtask

  // Fill one owner's depth-two elastic FIFO while its client is stalled.  A
  // third response is held at the MIG boundary.  Raising client RREADY must
  // not raise MIG RREADY in the same combinational cycle; FIFO occupancy may
  // change only at the clock edge, and MIG RREADY then recovers one cycle later.
  task automatic test_depth_two_fifo;
    input owner;
    reg [31:0] id0;
    reg [31:0] id1;
    reg [31:0] id2;
    integer before_count;
    begin
      reset_via_rst_n();
      id0 = owner ? 32'h4D00_0001 : 32'h4100_0001;
      id1 = owner ? 32'h4D00_0002 : 32'h4100_0002;
      id2 = owner ? 32'h4D00_0003 : 32'h4100_0003;

      issue_desc(owner, 16'd0, 32'h1000_0000, 8'd0, "fifo descriptor 0");
      issue_desc(owner, 16'd1, 32'h1000_0040, 8'd0, "fifo descriptor 1");
      issue_desc(owner, 16'd2, 32'h1000_0080, 8'd0, "fifo descriptor 2");
      wait_ar_count(3, "fifo fill");

      if (owner) begin
        mlp_rready = 1'b0;
        attn_rready = 1'b1;
      end else begin
        attn_rready = 1'b0;
        mlp_rready = 1'b1;
      end
      #1;
      check(m_axi_rready,
        "empty response FIFO must accept MIG data while selected client stalls");

      // Client RREADY changes while space is available must also be irrelevant
      // to MIG RREADY.
      if (owner) mlp_rready = 1'b1;
      else attn_rready = 1'b1;
      #1;
      check(m_axi_rready,
        "MIG RREADY changed incorrectly when client RREADY rose with free space");
      if (owner) mlp_rready = 1'b0;
      else attn_rready = 1'b0;
      #1;
      check(m_axi_rready,
        "MIG RREADY changed incorrectly when client RREADY fell with free space");

      accept_r_beat(id0, 2'b00, 1'b1, "fifo beat 0");
      check(owner ? mlp_rvalid : attn_rvalid,
        "first buffered response was not exposed to its client");
      check(owner ? (mlp_rdata[31:0] == id0) : (attn_rdata[31:0] == id0),
        "first buffered response payload mismatch");
      check(m_axi_rready,
        "depth-two FIFO did not retain one free entry after first beat");

      accept_r_beat(id1, 2'b00, 1'b1, "fifo beat 1");
      check(!m_axi_rready,
        "MIG RREADY must fall when the selected client FIFO reaches depth two");
      check(physical_r_count == 2,
        "exactly two physical beats must enter a stalled depth-two FIFO");
      check((owner ? mlp_deliveries : attn_deliveries) == 0,
        "stalled client consumed a response unexpectedly");

      // Hold the third physical beat stable while the FIFO is full.
      @(negedge clk);
      m_axi_rvalid = 1'b1;
      m_axi_rdata = payload(id2);
      m_axi_rresp = 2'b00;
      m_axi_rlast = 1'b1;
      #1;
      check(!m_axi_rready, "full client FIFO accepted a third physical beat");

      // This is the key combinational-path check.  There is still no clock edge
      // between changing client RREADY and observing MIG RREADY.
      if (owner) mlp_rready = 1'b1;
      else attn_rready = 1'b1;
      #1;
      check(!m_axi_rready,
        "MIG RREADY has a forbidden combinational dependency on client RREADY");

      before_count = physical_r_count;
      @(posedge clk);
      #1;
      check(physical_r_count == before_count,
        "third MIG beat handshook in the same cycle as the first client pop");
      check(m_axi_rready,
        "MIG RREADY did not recover on the cycle after a full-FIFO client pop");
      check((owner ? mlp_deliveries : attn_deliveries) == 1,
        "first buffered response did not pop during full-FIFO recovery");

      // RVALID/data were held stable, so the third physical beat is accepted at
      // this next edge while the second buffered beat is delivered.
      @(posedge clk);
      #1;
      check(physical_r_count == before_count + 1,
        "held third MIG beat was not accepted after FIFO recovery");
      check((owner ? mlp_deliveries : attn_deliveries) == 2,
        "second buffered response did not preserve FIFO order");
      m_axi_rvalid = 1'b0;
      m_axi_rdata = '0;
      m_axi_rlast = 1'b0;

      // Drain the third response.
      @(posedge clk);
      #1;
      check((owner ? mlp_deliveries : attn_deliveries) == 3,
        "third response did not drain from recovered FIFO");
      wait_quiescent("depth-two FIFO drain");
      check(!protocol_error, "legal depth-two FIFO flow raised protocol_error");

      if (owner) begin
        check(mlp_log[0] == id0 && mlp_log[1] == id1 && mlp_log[2] == id2,
          "MLP depth-two FIFO changed response order");
        check(attn_deliveries == 0,
          "MLP-owned response was delivered to Attention client");
      end else begin
        check(attn_log[0] == id0 && attn_log[1] == id1 && attn_log[2] == id2,
          "Attention depth-two FIFO changed response order");
        check(mlp_deliveries == 0,
          "Attention-owned response was delivered to MLP client");
      end
    end
  endtask

  task automatic check_fatal_freeze;
    input [8*48-1:0] label_text;
    begin
      check(protocol_error, {label_text, ": protocol_error not asserted"});
      check(!desc_ready && !m_axi_arvalid && !m_axi_rready,
        {label_text, ": fatal state did not freeze AXI/descriptor issue"});
      check(!attn_rvalid && !mlp_rvalid,
        {label_text, ": fatal state exposed client response data"});
    end
  endtask

  task automatic test_bad_rresp_and_sticky_reset;
    begin
      reset_via_rst_n();
      attn_rready = 1'b1;
      issue_desc(1'b0, 16'd0, 32'h2000_0000, 8'd0, "bad-RRESP descriptor");
      wait_ar_count(1, "bad-RRESP");

      @(negedge clk);
      m_axi_rvalid = 1'b1;
      m_axi_rdata = payload(32'hBAD0_0001);
      m_axi_rresp = 2'b10;
      m_axi_rlast = 1'b1;
      #1;
      check(m_axi_rready, "bad-RRESP beat must be consumed at MIG boundary");
      check(!attn_rvalid && !mlp_rvalid,
        "bad-RRESP beat was exposed combinationally to a client");
      @(posedge clk);
      #1;
      m_axi_rvalid = 1'b0;
      m_axi_rresp = 2'b00;
      m_axi_rlast = 1'b0;
      check(attn_deliveries == 0 && mlp_deliveries == 0,
        "bad-RRESP beat generated a client handshake");
      check_fatal_freeze("bad RRESP");

      // ERROR_FREEZE is sticky across any local soft reset request.
      @(negedge clk);
      soft_reset = 1'b1;
      repeat (2) begin
        @(posedge clk);
        #1;
        check(protocol_error,
          "soft_reset illegally cleared sticky protocol_error");
      end
      @(negedge clk);
      soft_reset = 1'b0;
      #1;
      check_fatal_freeze("post-soft-reset fatal");

      // Only rst_n is permitted to leave ERROR_FREEZE.
      pulse_hard_reset();
      check(!protocol_error,
        "dedicated hard reset failed after soft-reset attempt");
    end
  endtask

  task automatic test_early_rlast;
    begin
      reset_via_rst_n();
      attn_rready = 1'b1;
      issue_desc(1'b0, 16'd0, 32'h2100_0000, 8'd2, "early-RLAST descriptor");
      wait_ar_count(1, "early-RLAST");
      @(negedge clk);
      m_axi_rvalid = 1'b1;
      m_axi_rdata = payload(32'hBAD0_0002);
      m_axi_rresp = 2'b00;
      m_axi_rlast = 1'b1;
      #1;
      check(m_axi_rready, "early-RLAST beat was not accepted for validation");
      check(!attn_rvalid && !mlp_rvalid,
        "early-RLAST beat was exposed combinationally to a client");
      @(posedge clk);
      #1;
      m_axi_rvalid = 1'b0;
      m_axi_rlast = 1'b0;
      check(attn_deliveries == 0 && mlp_deliveries == 0,
        "early-RLAST beat generated a client handshake");
      check_fatal_freeze("early RLAST");
    end
  endtask

  task automatic test_late_rlast;
    begin
      reset_via_rst_n();
      mlp_rready = 1'b1;
      issue_desc(1'b1, 16'd0, 32'h2200_0000, 8'd0, "late-RLAST descriptor");
      wait_ar_count(1, "late-RLAST");
      @(negedge clk);
      m_axi_rvalid = 1'b1;
      m_axi_rdata = payload(32'hBAD0_0003);
      m_axi_rresp = 2'b00;
      m_axi_rlast = 1'b0;
      #1;
      check(m_axi_rready, "late-RLAST beat was not accepted for validation");
      check(!attn_rvalid && !mlp_rvalid,
        "late-RLAST beat was exposed combinationally to a client");
      @(posedge clk);
      #1;
      m_axi_rvalid = 1'b0;
      check(attn_deliveries == 0 && mlp_deliveries == 0,
        "late-RLAST beat generated a client handshake");
      check_fatal_freeze("late RLAST");
    end
  endtask

  task automatic test_no_owner_rvalid;
    begin
      reset_via_rst_n();
      attn_rready = 1'b1;
      mlp_rready = 1'b1;
      @(negedge clk);
      m_axi_rvalid = 1'b1;
      m_axi_rdata = payload(32'hBAD0_0004);
      m_axi_rresp = 2'b00;
      m_axi_rlast = 1'b1;
      #1;
      check(!m_axi_rready,
        "ownerless RVALID must not produce a physical AXI handshake");
      check(!attn_rvalid && !mlp_rvalid,
        "ownerless RVALID was exposed to a client");
      @(posedge clk);
      #1;
      m_axi_rvalid = 1'b0;
      m_axi_rlast = 1'b0;
      check(attn_deliveries == 0 && mlp_deliveries == 0,
        "ownerless RVALID generated a client handshake");
      check_fatal_freeze("ownerless RVALID");

      // Verify the asynchronous reset path independently of the dedicated
      // synchronous hard_reset input.
      reset_via_rst_n();
      check(!protocol_error,
        "rst_n failed to clear ownerless-response protocol_error");
    end
  endtask

  task automatic test_safe_soft_reset;
    begin
      reset_via_rst_n();
      attn_rready = 1'b1;
      issue_desc(1'b0, 16'd0, 32'h3000_0000, 8'd0,
        "pre-soft-reset descriptor");
      wait_ar_count(1, "pre-soft-reset");
      accept_r_beat(32'h6000_0001, 2'b00, 1'b1,
        "pre-soft-reset good beat");
      wait_quiescent("pre-soft-reset drain");
      check(attn_deliveries == 1,
        "good beat did not drain before safe soft reset");
      check(physical_ar_count == 1 && physical_r_count == 1,
        "pre-soft-reset traffic counters incorrect");

      @(negedge clk);
      soft_reset = 1'b1;
      @(posedge clk);
      #1;
      check(!protocol_error,
        "safe soft reset at quiescence raised protocol_error");
      check(physical_ar_count == 0 && physical_r_count == 0,
        "safe soft reset did not clear local traffic counters");
      check(attn_burst_count == 0 && mlp_burst_count == 0,
        "safe soft reset did not clear owner burst counters");
      check(quiescent, "safe soft reset did not retain quiescence");
      @(negedge clk);
      soft_reset = 1'b0;

      // Sequence zero must be legal again, proving that the safe reset also
      // restarted local descriptor sequencing without requiring rst_n.
      mlp_rready = 1'b1;
      attn_rready = 1'b0;
      issue_desc(1'b1, 16'd0, 32'h3000_0040, 8'd0,
        "post-soft-reset descriptor");
      wait_ar_count(1, "post-soft-reset");
      accept_r_beat(32'h6000_0002, 2'b00, 1'b1,
        "post-soft-reset good beat");
      wait_quiescent("post-soft-reset drain");
      check(!protocol_error,
        "legal sequence zero after safe soft reset raised protocol_error");
      check(mlp_deliveries == 1 && mlp_log[0] == 32'h6000_0002,
        "post-soft-reset response was not delivered to MLP client");
    end
  endtask

  task automatic test_illegal_soft_reset_active;
    integer before_deliveries;
    begin
      reset_via_rst_n();
      attn_rready = 1'b1;
      issue_desc(1'b0, 16'd0, 32'h3100_0000, 8'd0,
        "illegal-soft-reset descriptor");
      wait_ar_count(1, "illegal-soft-reset");
      before_deliveries = attn_deliveries;
      @(negedge clk);
      soft_reset = 1'b1;
      m_axi_rvalid = 1'b1;
      m_axi_rdata = payload(32'hBAD0_0005);
      m_axi_rresp = 2'b00;
      m_axi_rlast = 1'b1;
      #1;
      check(!m_axi_rready,
        "active soft_reset must suppress a physical R handshake");
      check(!attn_rvalid && !mlp_rvalid,
        "active soft_reset must suppress client response handshakes");
      @(posedge clk);
      #1;
      m_axi_rvalid = 1'b0;
      soft_reset = 1'b0;
      check(attn_deliveries == before_deliveries,
        "illegal soft_reset edge lost or duplicated a client beat");
      check_fatal_freeze("illegal active soft reset");
      pulse_hard_reset();
    end
  endtask

  initial begin
    $timeformat(-9, 1, " ns", 10);
    repeat (2) @(posedge clk);

    test_depth_two_fifo(1'b0);
    test_depth_two_fifo(1'b1);
    test_bad_rresp_and_sticky_reset();
    test_early_rlast();
    test_late_rlast();
    test_no_owner_rvalid();
    test_safe_soft_reset();
    test_illegal_soft_reset_active();

    if (failures != 0) begin
      $display("FAIL hap_axi512_ordered_local_issue_protocol checks=%0d failures=%0d",
        checks, failures);
      $fatal(1, "ordered-local-issue protocol contract failed");
    end
    $display("PASS hap_axi512_ordered_local_issue_protocol checks=%0d", checks);
    $finish;
  end

  initial begin
    #200000;
    $fatal(1, "hap_axi512_ordered_local_issue_protocol_tb global timeout");
  end
endmodule
