`timescale 1ns/1ps

// Real V4 production-core control/maintenance smoke test.
//
// This TB deliberately instantiates hap_attention_mlp_production_core rather
// than copying its control equations.  The very large datapath remains the
// production RTL; AXI memories are simple protocol-correct responders.  A few
// force/release operations hold deep compute endpoints quiescent or inject a
// fatal indication so the test can focus on the top-level AXI-Lite router,
// admission barrier, tensor DMA, mode controller and paired-DDR maintenance
// transaction without simulating a complete Llama layer.
module hap_v4_production_top_smoke_tb;
  reg core_clk=0,ddr0_clk=0,ddr1_clk=0;
  reg core_rst_n=0,ddr0_rst_n=0,ddr1_rst_n=0,core_clear=0;

  reg [11:0] ctrl_awaddr=0; reg ctrl_awvalid=0; wire ctrl_awready;
  reg [31:0] ctrl_wdata=0; reg [3:0] ctrl_wstrb=0; reg ctrl_wvalid=0;
  wire ctrl_wready; wire [1:0] ctrl_bresp; wire ctrl_bvalid;
  reg ctrl_bready=0;
  reg [11:0] ctrl_araddr=0; reg ctrl_arvalid=0; wire ctrl_arready;
  wire [31:0] ctrl_rdata; wire [1:0] ctrl_rresp; wire ctrl_rvalid;
  reg ctrl_rready=0;

  wire data_axi_arvalid; reg data_axi_arready=1;
  wire [31:0] data_axi_araddr; wire [7:0] data_axi_arlen;
  wire [2:0] data_axi_arsize; wire [1:0] data_axi_arburst;
  wire data_axi_rvalid; wire data_axi_rready; wire [255:0] data_axi_rdata;
  wire [1:0] data_axi_rresp; wire data_axi_rlast;
  wire data_axi_awvalid; reg data_axi_awready=1;
  wire [31:0] data_axi_awaddr; wire [7:0] data_axi_awlen;
  wire [2:0] data_axi_awsize; wire [1:0] data_axi_awburst;
  wire data_axi_wvalid; reg data_axi_wready=1; wire [255:0] data_axi_wdata;
  wire [31:0] data_axi_wstrb; wire data_axi_wlast;
  reg data_axi_bvalid=0; wire data_axi_bready; reg [1:0] data_axi_bresp=0;

  wire ddr0_axi_arvalid; reg ddr0_axi_arready=1;
  wire [31:0] ddr0_axi_araddr; wire [7:0] ddr0_axi_arlen;
  wire [2:0] ddr0_axi_arsize; wire [1:0] ddr0_axi_arburst;
  reg ddr0_axi_rvalid=0; wire ddr0_axi_rready; reg [511:0] ddr0_axi_rdata=0;
  reg [1:0] ddr0_axi_rresp=0; reg ddr0_axi_rlast=0;
  wire ddr1_axi_arvalid; reg ddr1_axi_arready=1;
  wire [31:0] ddr1_axi_araddr; wire [7:0] ddr1_axi_arlen;
  wire [2:0] ddr1_axi_arsize; wire [1:0] ddr1_axi_arburst;
  reg ddr1_axi_rvalid=0; wire ddr1_axi_rready; reg [511:0] ddr1_axi_rdata=0;
  reg [1:0] ddr1_axi_rresp=0; reg ddr1_axi_rlast=0;
  wire attention_irq,mlp_irq,integration_error;

  integer checks=0,cycles=0,soft_clear_count=0,mlp_abort_clear_count=0;
  integer data_rremain=0;
  reg data_read_active=0,data_read_hold=0;
  reg [1:0] bresp_q;
  reg [31:0] rdata_q;
  reg [1:0] rresp_q;

  always #3.333 core_clk=~core_clk;
  always #1.667 ddr0_clk=~ddr0_clk;
  always #1.667 ddr1_clk=~ddr1_clk;

  hap_attention_mlp_production_core dut(
    .core_clk(core_clk),.core_rst_n(core_rst_n),.core_clear(core_clear),
    .ddr0_clk(ddr0_clk),.ddr0_rst_n(ddr0_rst_n),
    .ddr1_clk(ddr1_clk),.ddr1_rst_n(ddr1_rst_n),
    .ctrl_awaddr(ctrl_awaddr),.ctrl_awvalid(ctrl_awvalid),
    .ctrl_awready(ctrl_awready),.ctrl_wdata(ctrl_wdata),
    .ctrl_wstrb(ctrl_wstrb),.ctrl_wvalid(ctrl_wvalid),
    .ctrl_wready(ctrl_wready),.ctrl_bresp(ctrl_bresp),
    .ctrl_bvalid(ctrl_bvalid),.ctrl_bready(ctrl_bready),
    .ctrl_araddr(ctrl_araddr),.ctrl_arvalid(ctrl_arvalid),
    .ctrl_arready(ctrl_arready),.ctrl_rdata(ctrl_rdata),
    .ctrl_rresp(ctrl_rresp),.ctrl_rvalid(ctrl_rvalid),
    .ctrl_rready(ctrl_rready),
    .data_axi_arvalid(data_axi_arvalid),.data_axi_arready(data_axi_arready),
    .data_axi_araddr(data_axi_araddr),.data_axi_arlen(data_axi_arlen),
    .data_axi_arsize(data_axi_arsize),.data_axi_arburst(data_axi_arburst),
    .data_axi_rvalid(data_axi_rvalid),.data_axi_rready(data_axi_rready),
    .data_axi_rdata(data_axi_rdata),.data_axi_rresp(data_axi_rresp),
    .data_axi_rlast(data_axi_rlast),
    .data_axi_awvalid(data_axi_awvalid),.data_axi_awready(data_axi_awready),
    .data_axi_awaddr(data_axi_awaddr),.data_axi_awlen(data_axi_awlen),
    .data_axi_awsize(data_axi_awsize),.data_axi_awburst(data_axi_awburst),
    .data_axi_wvalid(data_axi_wvalid),.data_axi_wready(data_axi_wready),
    .data_axi_wdata(data_axi_wdata),.data_axi_wstrb(data_axi_wstrb),
    .data_axi_wlast(data_axi_wlast),.data_axi_bvalid(data_axi_bvalid),
    .data_axi_bready(data_axi_bready),.data_axi_bresp(data_axi_bresp),
    .ddr0_axi_arvalid(ddr0_axi_arvalid),.ddr0_axi_arready(ddr0_axi_arready),
    .ddr0_axi_araddr(ddr0_axi_araddr),.ddr0_axi_arlen(ddr0_axi_arlen),
    .ddr0_axi_arsize(ddr0_axi_arsize),.ddr0_axi_arburst(ddr0_axi_arburst),
    .ddr0_axi_rvalid(ddr0_axi_rvalid),.ddr0_axi_rready(ddr0_axi_rready),
    .ddr0_axi_rdata(ddr0_axi_rdata),.ddr0_axi_rresp(ddr0_axi_rresp),
    .ddr0_axi_rlast(ddr0_axi_rlast),
    .ddr1_axi_arvalid(ddr1_axi_arvalid),.ddr1_axi_arready(ddr1_axi_arready),
    .ddr1_axi_araddr(ddr1_axi_araddr),.ddr1_axi_arlen(ddr1_axi_arlen),
    .ddr1_axi_arsize(ddr1_axi_arsize),.ddr1_axi_arburst(ddr1_axi_arburst),
    .ddr1_axi_rvalid(ddr1_axi_rvalid),.ddr1_axi_rready(ddr1_axi_rready),
    .ddr1_axi_rdata(ddr1_axi_rdata),.ddr1_axi_rresp(ddr1_axi_rresp),
    .ddr1_axi_rlast(ddr1_axi_rlast),.attention_irq(attention_irq),
    .mlp_irq(mlp_irq),.integration_error(integration_error));

  task tick; begin @(posedge core_clk); #1; end endtask
  task check(input c,input [8*120-1:0]m); begin
    checks=checks+1;
    if(!c)begin $display("FAIL %0s",m);$fatal(1);end
  end endtask
  task wait_soft_clear(input integer previous_count); integer guard; begin
    guard=0;
    while(soft_clear_count==previous_count&&guard<600)begin tick();guard=guard+1;end
    check(soft_clear_count==previous_count+1,"soft-clear pulse missing or repeated");
  end endtask
  task wait_mode(input [1:0]mode); integer guard; begin
    guard=0;
    while(dut.active_owner!=mode&&guard<600)begin tick();guard=guard+1;end
    check(dut.active_owner==mode,"mode request did not commit");
  end endtask

  // AW and W are intentionally presented together; completion is defined by
  // the B handshake.  back_to_back=1 leaves no idle cycle after that handshake
  // so the next task can drive the following transaction immediately.
  task axil_write(input [11:0]addr,input [31:0]data,input [3:0]strb,
                  input back_to_back); reg aw_done,w_done; begin
    aw_done=0;w_done=0;
    ctrl_awaddr=addr;ctrl_awvalid=1;ctrl_wdata=data;ctrl_wstrb=strb;
    ctrl_wvalid=1;ctrl_bready=0;
    while(!aw_done||!w_done)begin
      @(posedge core_clk);
      if(!aw_done&&ctrl_awvalid&&ctrl_awready)aw_done=1;
      if(!w_done&&ctrl_wvalid&&ctrl_wready)w_done=1;
      #1;
      if(aw_done)ctrl_awvalid=0;
      if(w_done)ctrl_wvalid=0;
    end
    while(!ctrl_bvalid)tick();
    bresp_q=ctrl_bresp;ctrl_bready=1;tick();ctrl_bready=0;
    if(!back_to_back)tick();
  end endtask
  task axil_read(input [11:0]addr); reg ar_done; begin
    ar_done=0;
    ctrl_araddr=addr;ctrl_arvalid=1;ctrl_rready=0;
    while(!ar_done)begin
      @(posedge core_clk);
      if(ctrl_arvalid&&ctrl_arready)ar_done=1;
      #1;if(ar_done)ctrl_arvalid=0;
    end
    while(!ctrl_rvalid)tick();
    rdata_q=ctrl_rdata;rresp_q=ctrl_rresp;ctrl_rready=1;tick();ctrl_rready=0;
    tick();
  end endtask

  always @(posedge core_clk)begin
    cycles<=cycles+1;
    if(dut.engine_soft_clear)soft_clear_count<=soft_clear_count+1;
    if(dut.mlp_abort_clear_r)mlp_abort_clear_count<=mlp_abort_clear_count+1;
    if(cycles>6000)begin
      $display("FAIL timeout mode=%0d pending=%0d maint=%0d tensor=%0d phase=%0d soft=%0d",
        dut.active_owner,dut.owner_switch_pending,dut.maintenance_request,
        dut.tensor_busy,dut.tensor_phase,soft_clear_count);
      $fatal(1);
    end
  end

  // AXI256 read responder.  data_read_hold freezes the current tensor LOAD
  // after the AR handshake so maintenance must remain pending until released.
  assign data_axi_rvalid=data_read_active&&!data_read_hold;
  assign data_axi_rdata=256'd0;
  assign data_axi_rresp=2'b00;
  assign data_axi_rlast=data_read_active&&!data_read_hold&&data_rremain==1;
  always @(posedge core_clk)begin
    if(data_axi_arvalid&&data_axi_arready)begin
      if(data_axi_arsize!=3'd5||data_axi_arburst!=2'b01)begin
        $display("FAIL malformed AXI256 read");$fatal(1);
      end
      data_read_active<=1;data_rremain<=data_axi_arlen+1;
    end
    if(data_axi_rvalid&&data_axi_rready)begin
      data_rremain<=data_rremain-1;
      if(data_rremain==1)data_read_active<=0;
    end
  end

  initial begin
    // The smoke test does not execute the compute kernels.  Holding their
    // native command/read endpoints idle is preferable to replacing the
    // production control/fabric modules with toy models.
    force dut.u_compute.att_d0_arvalid=1'b0;
    force dut.u_compute.att_d1_arvalid=1'b0;
    force dut.u_compute.mlp_d0_arvalid=1'b0;
    force dut.u_compute.mlp_d1_arvalid=1'b0;
    force dut.u_compute.attention_weight_source_quiescent=1'b1;
    force dut.u_compute.mlp_weight_source_quiescent=1'b1;
    force dut.u_compute.attention_quiescent=1'b1;
    force dut.u_compute.attention_data_axi_busy=1'b0;
    force dut.u_compute.mlp_busy=1'b0;
    force dut.u_compute.mlp_done=1'b0;
    force dut.u_compute.mlp_error=1'b0;
    force dut.u_compute.mlp_phase=3'd0;
    force dut.u_compute.mlp_input_ready=1'b1;
    force dut.u_compute.mlp_input_bank_ready=2'b00;
    force dut.u_compute.mlp_out_valid=1'b0;
    force dut.u_compute.mlp_out_tile_index=8'd0;
    force dut.u_compute.mlp_projection_s24x16x16=6144'd0;
    force dut.u_compute.mlp_gate_meta_ready=1'b0;
    force dut.u_compute.mlp_down_meta_ready=1'b0;

    repeat(8)tick();
    core_rst_n=1;ddr0_rst_n=1;ddr1_rst_n=1;
    repeat(40)tick();
    check(dut.paired_core_quiescent,"paired leaf did not leave reset quiescent");

    // Enter SHARED so both Attention and MLP launch enables are visible.
    axil_write(12'h108,32'd3,4'hf,0);check(bresp_q==0,"SHARED request rejected");
    wait_mode(2'd3);
    axil_write(12'h018,32'h00080800,4'hf,0);
    check(bresp_q==0,"Attention query configuration rejected");

    // 1) MLP clear B response, then the very next write is Attention start.
    // The start must be rejected by the real Attention control because the
    // captured maintenance request already closed admission.
    force dut.u_compute.attention_weight_source_quiescent=1'b0;
    axil_write(12'h110,32'h2,4'h1,1);check(bresp_q==0,"initial clear rejected");
    // bits 2/3 make this command otherwise launchable even with empty
    // metadata/RoPE state, isolating maintenance admission as the rejection.
    axil_write(12'h008,32'hd,4'h1,0);
    check(bresp_q==2'b10,"Attention start escaped after clear B response");
    check(!dut.u_compute.u_attention.u_control.start_pulse,
      "Attention start pulse escaped maintenance barrier");
    force dut.u_compute.attention_weight_source_quiescent=1'b1;
    wait_soft_clear(0);

    // 2) Active tensor LOAD: accept a real production LOAD, hold its first
    // AXI response, then clear.  No cancellation/soft-clear is allowed until
    // the accepted read command drains.  The command length is forced to one
    // complete 48-beat group and its group tag to the final production group;
    // all AXI/DMA/P_LOAD_DRAIN behavior remains real while avoiding a 6144-beat
    // data-transfer regression inside this control smoke.
    axil_write(12'h124,32'h00001000,4'hf,0);
    force dut.u_tensor.dma_cmd_beats=32'd48;
    force dut.u_compute.mlp_input_ready=1'b0;
    data_read_hold=1;
    axil_write(12'h174,32'h1,4'h1,0);check(bresp_q==0,"tensor LOAD rejected");
    while(!data_read_active)tick();
    force dut.u_tensor.input_group_r=7'd127;
    force dut.u_tensor.input_group_count=32'd127;
    axil_write(12'h110,32'h2,4'h1,0);check(bresp_q==0,"LOAD clear rejected");
    repeat(16)tick();
    check(dut.maintenance_request&&dut.tensor_axi_active,
      "active LOAD did not hold maintenance pending");
    check(soft_clear_count==1,"active LOAD was canceled before AXI drain");
    data_read_hold=0;
    while(dut.tensor_phase!=3'd2)tick();
    force dut.u_compute.mlp_input_ready=1'b1;
    while(dut.tensor_busy)tick();
    release dut.u_tensor.dma_cmd_beats;
    release dut.u_tensor.input_group_r;
    release dut.u_tensor.input_group_count;
    wait_soft_clear(1);

    // 3) P_STORE_ARM is cancelable only by final soft-clear.  Also request a
    // mode switch while armed and prove that mode commit remains pending.
    axil_write(12'h174,32'h2,4'h1,0);check(bresp_q==0,"tensor STORE arm rejected");
    check(dut.tensor_store_armed&&dut.tensor_phase==3,
      "tensor bridge did not enter P_STORE_ARM");
    axil_write(12'h108,32'd1,4'hf,0);check(bresp_q==0,"mode request rejected");
    repeat(12)tick();
    check(dut.owner_switch_pending&&dut.active_owner==3,
      "armed store failed to block mode switch");
    // mode-pending is itself an admission pause, so clear cannot be submitted
    // through AXI-Lite until that request is resolved.  Cancel P_STORE_ARM
    // through the real external maintenance request, then verify the queued
    // mode commits only after soft-clear.
    core_clear=1;tick();core_clear=0;
    wait_soft_clear(2);
    check(!dut.tensor_store_armed,"soft-clear did not cancel P_STORE_ARM");
    wait_mode(2'd1);

    // Return SHARED for the final software-clear/fatal cases.
    axil_write(12'h108,32'd3,4'hf,0);check(bresp_q==0,"second SHARED rejected");
    wait_mode(2'd3);

    // 4) Repeated clear while pending/active returns SLVERR and cannot create
    // a second soft-clear.  Hold source closure low long enough to guarantee
    // the repeated write lands inside the pending window.
    force dut.u_compute.attention_weight_source_quiescent=1'b0;
    axil_write(12'h110,32'h2,4'h1,0);check(bresp_q==0,"repeat test first clear rejected");
    axil_write(12'h110,32'h2,4'h1,0);
    check(bresp_q==2'b10,"repeated clear did not return SLVERR");
    check(soft_clear_count==3,"repeated clear generated an early soft-clear");
    force dut.u_compute.attention_weight_source_quiescent=1'b1;
    wait_soft_clear(3);
    repeat(40)tick();check(soft_clear_count==4,"repeated clear generated two pulses");

    // 5) An active MLP clear first resets only the MLP children after the
    // paired DDR and data AXI paths drain.  Holding the Attention source open
    // proves that this local abort completion does not require or generate the
    // later whole-engine maintenance soft-clear.
    force dut.u_compute.mlp_input_bank_ready=2'b01;
    force dut.u_compute.mlp_command_ready=1'b1;
    force dut.meta_active_bank=1'b0;
    force dut.meta_active_generation=32'd1;
    force dut.meta_bank_valid=2'b01;
    axil_write(12'h118,32'h13572468,4'hf,0);
    axil_write(12'h11c,32'd13,4'hf,0);
    axil_write(12'h13c,32'd0,4'hf,0);
    axil_write(12'h140,32'd1,4'hf,0);
    axil_write(12'h280,32'hdeadbeef,4'hf,0);
    axil_write(12'h284,32'h24681357,4'hf,0);
    axil_write(12'h174,32'h2,4'h1,0);
    check(bresp_q==0&&dut.tensor_store_armed,"active-abort tensor STORE arm failed");
    axil_write(12'h110,32'h1,4'h1,0);
    check(bresp_q==0&&dut.u_mlp_ctrl.command_active_r&&
      dut.mlp_transaction_busy_r,"active-abort MLP launch failed");
    force dut.u_compute.attention_weight_source_quiescent=1'b0;
    axil_write(12'h110,32'h2,4'h1,1);
    check(bresp_q==0&&dut.u_mlp_ctrl.command_abort_pending_r,
      "active MLP clear did not enter abort pending");
    begin:wait_local_abort integer guard;guard=0;
      while(!dut.u_mlp_ctrl.completion_valid_r&&guard<600)begin
        tick();guard=guard+1;
      end
      check(guard<600,"local MLP abort completion timeout");
    end
    tick();
    check(mlp_abort_clear_count==1&&!dut.u_mlp_ctrl.command_active_r,
      "local MLP abort clear missing or repeated");
    check(soft_clear_count==4,
      "local MLP abort prematurely cleared the Attention engine");
    check(!dut.tensor_store_armed&&!dut.mlp_transaction_busy_r,
      "local MLP abort left child transaction state active");
    axil_read(12'h288);check(rresp_q==0&&rdata_q==32'hdeadbeef,
      "active-abort request identity mismatch");
    axil_read(12'h28c);check(rresp_q==0&&rdata_q==32'h13572468,
      "active-abort command identity mismatch");
    axil_read(12'h290);check(rresp_q==0&&rdata_q==32'h24681357,
      "active-abort owner identity mismatch");
    axil_read(12'h294);check(rresp_q==0&&rdata_q==32'd13,
      "active-abort layer identity mismatch");
    axil_read(12'h298);check(rresp_q==0&&rdata_q==32'h00292468,
      "active-abort completion status mismatch");
    axil_read(12'h148);check(rresp_q==0&&rdata_q==32'h00010000,
      "active-abort error code mismatch");
    force dut.u_compute.attention_weight_source_quiescent=1'b1;
    wait_soft_clear(4);
    axil_write(12'h2a0,32'h13572468,4'hf,0);
    check(bresp_q==0&&!dut.u_mlp_ctrl.completion_valid_r&&!mlp_irq,
      "active-abort completion ACK failed");
    release dut.u_compute.mlp_command_ready;
    release dut.u_compute.mlp_input_bank_ready;
    release dut.meta_active_bank;
    release dut.meta_active_generation;
    release dut.meta_bank_valid;

    // 6) Fatal clear: inject the production owner-protocol fatal status and
    // ensure MLP clear returns SLVERR without entering maintenance.
    force dut.u_mode.error_r=1'b1;
    tick();
    axil_write(12'h110,32'h2,4'h1,0);
    check(bresp_q==2'b10,"fatal clear did not return SLVERR");
    check(!dut.mlp_maintenance_pending_r&&!dut.maintenance_drain_active,
      "fatal clear entered maintenance");
    check(soft_clear_count==5,"fatal clear generated soft-clear");
    release dut.u_mode.error_r;

    // The real router and endpoint remain readable after all legal clears.
    axil_read(12'h104);
    check(rresp_q==0&&rdata_q==32'h00040003,"V4 ABI readback mismatch");
    $display("PASS hap_v4_production_top_smoke checks=%0d soft_clear=%0d cycles=%0d",
      checks,soft_clear_count,cycles);
    $finish;
  end

  initial begin #2000000;$fatal(1,"wall-clock timeout");end
endmodule
