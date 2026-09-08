`timescale 1ns / 1ps

// Directed CDC/contract test for the committed core-domain mode enables.
// It deliberately changes each enable near unrelated DDR clock edges, checks
// that only the destination XPM result controls admission, and proves that
// withdrawing an enable cannot retract an already-presented AXI ARVALID.
module hap_axi512_paired_2client_read_wrr_enable_cdc_tb;
  reg core_clk=0,ddr0_clk=0,ddr1_clk=0;
  always #3.333 core_clk=~core_clk;
  always #1.667 ddr0_clk=~ddr0_clk;
  always #1.923 ddr1_clk=~ddr1_clk;

  reg core_rst_n=0,ddr0_rst_n=0,ddr1_rst_n=0;
  reg core_enable=1,ddr0_enable=0,ddr1_enable=0;
  reg a0_arvalid=0,a1_arvalid=0;
  reg[31:0]a0_araddr=32'hA000_0000,a1_araddr=32'hA100_0000;
  wire a0_arready,a1_arready;
  wire p0_arvalid,p1_arvalid;
  reg p0_arready=0,p1_arready=0;
  wire[31:0]p0_araddr,p1_araddr;
  wire[7:0]p0_arlen,p1_arlen;wire[2:0]p0_arsize,p1_arsize;
  wire[1:0]p0_arburst,p1_arburst;
  wire p0_rready,p1_rready,core_quiescent,error;
  integer checks=0,failures=0,timeout=0;

  task automatic check;
    input condition;input[8*120-1:0]message;
    begin checks=checks+1;if(condition!==1'b1)begin failures=failures+1;
      $display("FAIL t=%0t check=%0d %0s",$time,checks,message);end end
  endtask

  hap_axi512_paired_2client_read_wrr #(.FIFO_DEPTH(16),.TAG_DEPTH(16))dut(
    .core_clk(core_clk),.core_rst_n(core_rst_n),.core_clear(1'b0),
    .core_enable(core_enable),.attn_source_quiescent(1'b1),
    .mlp_source_quiescent(1'b1),.maintenance_pause_sources(),
    .maintenance_drain_active(),.maintenance_soft_clear_pulse(),
    .ddr0_clk(ddr0_clk),.ddr0_rst_n(ddr0_rst_n),.ddr0_enable(ddr0_enable),
    .ddr1_clk(ddr1_clk),.ddr1_rst_n(ddr1_rst_n),.ddr1_enable(ddr1_enable),
    .a0_arvalid(a0_arvalid),.a0_arready(a0_arready),.a0_araddr(a0_araddr),
    .a0_arlen(8'd0),.a0_arsize(3'd6),.a0_arburst(2'b01),
    .a0_rvalid(),.a0_rready(1'b1),.a0_rdata(),.a0_rresp(),.a0_rlast(),
    .m0_arvalid(1'b0),.m0_arready(),.m0_araddr(32'd0),.m0_arlen(8'd0),
    .m0_arsize(3'd6),.m0_arburst(2'b01),.m0_rvalid(),.m0_rready(1'b1),
    .m0_rdata(),.m0_rresp(),.m0_rlast(),
    .a1_arvalid(a1_arvalid),.a1_arready(a1_arready),.a1_araddr(a1_araddr),
    .a1_arlen(8'd0),.a1_arsize(3'd6),.a1_arburst(2'b01),
    .a1_rvalid(),.a1_rready(1'b1),.a1_rdata(),.a1_rresp(),.a1_rlast(),
    .m1_arvalid(1'b0),.m1_arready(),.m1_araddr(32'd0),.m1_arlen(8'd0),
    .m1_arsize(3'd6),.m1_arburst(2'b01),.m1_rvalid(),.m1_rready(1'b1),
    .m1_rdata(),.m1_rresp(),.m1_rlast(),
    .p0_arvalid(p0_arvalid),.p0_arready(p0_arready),.p0_araddr(p0_araddr),
    .p0_arlen(p0_arlen),.p0_arsize(p0_arsize),.p0_arburst(p0_arburst),
    .p0_rvalid(1'b0),.p0_rready(p0_rready),.p0_rdata(512'd0),
    .p0_rresp(2'b00),.p0_rlast(1'b0),
    .p1_arvalid(p1_arvalid),.p1_arready(p1_arready),.p1_araddr(p1_araddr),
    .p1_arlen(p1_arlen),.p1_arsize(p1_arsize),.p1_arburst(p1_arburst),
    .p1_rvalid(1'b0),.p1_rready(p1_rready),.p1_rdata(512'd0),
    .p1_rresp(2'b00),.p1_rlast(1'b0),
    .core_quiescent(core_quiescent),.error(error),
    .accepted_attn_bursts(),.accepted_mlp_bursts(),.both_eligible_cycles(),
    .p0_hol_cycles(),.p1_hol_cycles(),.p0_tag_high_watermark(),
    .p1_tag_high_watermark());

  initial begin
    repeat(6)@(posedge core_clk);
    @(negedge core_clk);core_rst_n=1;ddr0_rst_n=1;ddr1_rst_n=1;
    repeat(24)@(posedge core_clk);
    check(!error,"reset raised error");
    check(!dut.ddr0_enable_sync&&!dut.ddr1_enable_sync,
      "destination enables did not initialize disabled");

    // Change at a non-core/non-DDR-aligned instant.  Admission must stay
    // closed until each destination synchronizer produces the committed level.
    #0.713;ddr0_enable=1;ddr1_enable=1;
    a0_arvalid=1;a1_arvalid=1;
    #0.1;check(!a0_arready&&!a1_arready,
      "raw asynchronous enable opened admission before synchronization");
    timeout=0;
    while((!a0_arready||!a1_arready)&&timeout<30)begin
      @(posedge core_clk);#0.1;timeout=timeout+1;end
    check(timeout<30,"synchronized enable did not open both DDR admissions");
    fork
      begin @(posedge ddr0_clk);#0.1;a0_arvalid=0;end
      begin @(posedge ddr1_clk);#0.1;a1_arvalid=0;end
    join

    timeout=0;
    while((!p0_arvalid||!p1_arvalid)&&timeout<100)begin
      @(posedge core_clk);#0.1;timeout=timeout+1;end
    check(timeout<100,"paired descriptors never reached physical AR outputs");
    check(p0_araddr==32'hA000_0000&&p1_araddr==32'hA100_0000,
      "paired AR payload mismatch before disable");

    // ARVALID is already committed while READY is low.  Disable both modes
    // asynchronously; AXI requires VALID/payload to remain stable until READY.
    #0.517;ddr0_enable=0;ddr1_enable=0;
    repeat(8)begin
      @(posedge ddr0_clk);#0.1;
      check(p0_arvalid&&p0_araddr==32'hA000_0000,
        "disable retracted or changed committed MIG0 AR");
    end
    repeat(8)begin
      @(posedge ddr1_clk);#0.1;
      check(p1_arvalid&&p1_araddr==32'hA100_0000,
        "disable retracted or changed committed MIG1 AR");
    end
    check(!dut.ddr0_enable_sync&&!dut.ddr1_enable_sync,
      "destination enables did not synchronously deassert");

    p0_arready=1;p1_arready=1;
    @(posedge ddr0_clk);#0.1;p0_arready=0;
    @(posedge ddr1_clk);#0.1;p1_arready=0;
    repeat(4)@(posedge core_clk);
    check(!p0_arvalid&&!p1_arvalid,
      "committed AR did not complete after disable");
    check(!a0_arready&&!a1_arready,
      "disabled destination admitted a new request");
    check(!error,"enable synchronization scenario raised protocol error");

    if(failures!=0)begin
      $display("FAIL hap_axi512_paired_2client_read_wrr_enable_cdc failures=%0d checks=%0d",
        failures,checks);$finish;end
    $display("PASS hap_axi512_paired_2client_read_wrr_enable_cdc checks=%0d",checks);
    $finish;
  end

  initial begin #500000;$fatal(1,"enable CDC test timeout");end
endmodule
