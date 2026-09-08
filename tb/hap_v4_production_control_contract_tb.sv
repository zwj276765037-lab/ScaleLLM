`timescale 1ns/1ps

// Production-level control contract for the maintenance pending register and
// composite MLP quiescence policy.  This isolates the safety decisions from
// the very large compute datapath while using the exact production equations.
module hap_v4_production_control_contract_tb;
  reg clk=0,rst_n=0,core_clear=0,mlp_clear=0,engine_soft_clear=0;
  reg owner_protocol_error=0;
  reg mlp_transaction_busy=0,mlp_busy=0,scheduler_active=0;
  reg tensor_busy=0,tensor_axi_active=0,meta_dma_busy=0;
  reg[2:0]tensor_phase=0;reg data_axi_quiescent=1;
  reg paired_quiescent=1,maintenance_busy=0;
  reg mode_valid=0;reg[1:0]mode_request=0;wire mode_ready;
  wire[1:0]active_mode;wire mode_done,mode_error,mode_pending;
  wire attn_launch,mlp_launch,core_enable,d0_enable,d1_enable;
  reg mlp_maintenance_pending=0;integer checks=0,soft_count=0;
  wire maintenance_request=core_clear||mlp_maintenance_pending;
  wire tensor_cancelable_arm=tensor_phase==3&&!tensor_axi_active&&
    !mlp_busy&&!mlp_transaction_busy;
  wire mlp_clear_safe=!mlp_transaction_busy&&!mlp_busy&&!scheduler_active&&
    (!tensor_busy||tensor_cancelable_arm)&&!tensor_axi_active&&!meta_dma_busy;
  wire mode_mlp_quiescent=!mlp_transaction_busy&&!mlp_busy&&
    !scheduler_active&&!tensor_busy&&!tensor_axi_active&&!meta_dma_busy&&
    data_axi_quiescent;

  always #3.333 clk=~clk;
  always @(posedge clk or negedge rst_n)begin
    if(!rst_n)mlp_maintenance_pending<=0;
    else if(engine_soft_clear)mlp_maintenance_pending<=0;
    else if(mlp_clear&&!maintenance_request&&!owner_protocol_error)
      mlp_maintenance_pending<=1;
  end
  always @(posedge clk)if(engine_soft_clear)soft_count<=soft_count+1;
  hap_v4_ddr_mode_controller mode(
    .core_clk(clk),.core_rst_n(rst_n),.mode_request_valid(mode_valid),
    .mode_request_ready(mode_ready),.mode_request(mode_request),
    .attention_quiescent(1'b1),.mlp_quiescent(mode_mlp_quiescent),
    .paired_leaf_quiescent(paired_quiescent),.paired_leaf_error(1'b0),
    .maintenance_busy(maintenance_busy),.active_mode(active_mode),
    .attention_launch_enable(attn_launch),.mlp_launch_enable(mlp_launch),
    .core_enable(core_enable),.ddr0_enable(d0_enable),.ddr1_enable(d1_enable),
    .switch_pending(mode_pending),.request_done(mode_done),.error(mode_error));
  task tick;begin @(posedge clk);#1;end endtask
  task check(input c,input[8*96-1:0]m);begin checks=checks+1;
    if(!c)begin $display("FAIL %0s",m);$fatal(1);end end endtask
  task clear_pulse;begin mlp_clear=1;tick();mlp_clear=0;tick();end endtask
  task request_mode(input[1:0]m);begin mode_request=m;mode_valid=1;
    while(!mode_ready)tick();tick();mode_valid=0;end endtask
  initial begin
    repeat(4)tick();rst_n=1;tick();
    // A standalone tensor LOAD is not cancelable: maintenance is accepted but
    // cannot clear until its AXI command drains.
    tensor_busy=1;tensor_axi_active=1;tensor_phase=1;clear_pulse();
    check(mlp_maintenance_pending,"load clear was ignored");
    check(!mlp_clear_safe,"active load reported clear safe");
    tensor_busy=0;tensor_axi_active=0;tensor_phase=0;tick();
    check(mlp_clear_safe,"drained load not clear safe");
    engine_soft_clear=1;tick();engine_soft_clear=0;tick();
    check(!mlp_maintenance_pending&&soft_count==1,"load soft clear priority");

    // Store-arm has not issued AXI and no MLP owns it, so maintenance may
    // cancel it only through the final soft-clear pulse.
    tensor_busy=1;tensor_phase=3;clear_pulse();
    check(mlp_maintenance_pending&&tensor_cancelable_arm&&mlp_clear_safe,
      "store-arm maintenance contract");
    mlp_clear=1;engine_soft_clear=1;tick();mlp_clear=0;engine_soft_clear=0;tick();
    check(!mlp_maintenance_pending,"same-cycle repeated clear re-armed pending");
    tensor_busy=0;tensor_phase=0;

    // Fatal ERROR_FREEZE cannot be acknowledged as recoverable maintenance.
    owner_protocol_error=1;clear_pulse();
    check(!mlp_maintenance_pending,"fatal clear entered maintenance");
    owner_protocol_error=0;

    // Mode switch has no cancel semantics: armed store must block commit.
    request_mode(2'd3);while(!mode_done)tick();
    tensor_busy=1;tensor_phase=3;request_mode(2'd1);
    repeat(6)tick();check(mode_pending&&active_mode==3,
      "armed store failed to block mode switch");
    tensor_busy=0;tensor_phase=0;while(!mode_done)tick();
    check(active_mode==1&&!mode_pending,"mode switch did not drain");
    $display("PASS hap_v4_production_control_contract checks=%0d",checks);
    $finish;
  end
  initial begin #1000000;$fatal(1,"timeout");end
endmodule
