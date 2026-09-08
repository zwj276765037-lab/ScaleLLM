`timescale 1ns / 1ps

// Production RTL integration boundary. The actual VCU118 block design still
// provides clocks, resets, XDMA/SmartConnect and both MIG controllers; this
// module owns all Attention/MLP command, metadata and DMA routing below them.
module hap_attention_mlp_production_core (
 input wire core_clk,input wire core_rst_n,input wire core_clear,
 input wire ddr0_clk,input wire ddr0_rst_n,input wire ddr1_clk,input wire ddr1_rst_n,
 input wire[11:0]ctrl_awaddr,input wire ctrl_awvalid,output wire ctrl_awready,
 input wire[31:0]ctrl_wdata,input wire[3:0]ctrl_wstrb,input wire ctrl_wvalid,
 output wire ctrl_wready,output wire[1:0]ctrl_bresp,output wire ctrl_bvalid,
 input wire ctrl_bready,input wire[11:0]ctrl_araddr,input wire ctrl_arvalid,
 output wire ctrl_arready,output wire[31:0]ctrl_rdata,output wire[1:0]ctrl_rresp,
 output wire ctrl_rvalid,input wire ctrl_rready,
 output wire data_axi_arvalid,input wire data_axi_arready,
 output wire[31:0]data_axi_araddr,output wire[7:0]data_axi_arlen,
 output wire[2:0]data_axi_arsize,output wire[1:0]data_axi_arburst,
 input wire data_axi_rvalid,output wire data_axi_rready,input wire[255:0]data_axi_rdata,
 input wire[1:0]data_axi_rresp,input wire data_axi_rlast,
 output wire data_axi_awvalid,input wire data_axi_awready,
 output wire[31:0]data_axi_awaddr,output wire[7:0]data_axi_awlen,
 output wire[2:0]data_axi_awsize,output wire[1:0]data_axi_awburst,
 output wire data_axi_wvalid,input wire data_axi_wready,output wire[255:0]data_axi_wdata,
 output wire[31:0]data_axi_wstrb,output wire data_axi_wlast,
 input wire data_axi_bvalid,output wire data_axi_bready,input wire[1:0]data_axi_bresp,
 output wire ddr0_axi_arvalid,input wire ddr0_axi_arready,
 output wire[31:0]ddr0_axi_araddr,output wire[7:0]ddr0_axi_arlen,
 output wire[2:0]ddr0_axi_arsize,output wire[1:0]ddr0_axi_arburst,
 input wire ddr0_axi_rvalid,output wire ddr0_axi_rready,input wire[511:0]ddr0_axi_rdata,
 input wire[1:0]ddr0_axi_rresp,input wire ddr0_axi_rlast,
 output wire ddr1_axi_arvalid,input wire ddr1_axi_arready,
 output wire[31:0]ddr1_axi_araddr,output wire[7:0]ddr1_axi_arlen,
 output wire[2:0]ddr1_axi_arsize,output wire[1:0]ddr1_axi_arburst,
 input wire ddr1_axi_rvalid,output wire ddr1_axi_rready,input wire[511:0]ddr1_axi_rdata,
 input wire[1:0]ddr1_axi_rresp,input wire ddr1_axi_rlast,
 output wire attention_irq,output wire mlp_irq,output wire integration_error);

 // Routed AXI-Lite endpoints.
 wire[11:0]s_axil_awaddr,s_axil_araddr,mlpc_awaddr,mlpc_araddr;
 wire s_axil_awvalid,s_axil_awready,s_axil_wvalid,s_axil_wready;
 wire[31:0]s_axil_wdata,s_axil_rdata;wire[3:0]s_axil_wstrb;
 wire[1:0]s_axil_bresp,s_axil_rresp;wire s_axil_bvalid,s_axil_bready;
 wire s_axil_arvalid,s_axil_arready,s_axil_rvalid,s_axil_rready;
 wire mlpc_awvalid,mlpc_awready,mlpc_wvalid,mlpc_wready;
 wire[31:0]mlpc_wdata,mlpc_rdata;wire[3:0]mlpc_wstrb;
 wire[1:0]mlpc_bresp,mlpc_rresp;wire mlpc_bvalid,mlpc_bready;
 wire mlpc_arvalid,mlpc_arready,mlpc_rvalid,mlpc_rready;
 hap_attention_mlp_axil_router u_ctrl_router(.clk(core_clk),.rst_n(core_rst_n),
  .s_awaddr(ctrl_awaddr),.s_awvalid(ctrl_awvalid),.s_awready(ctrl_awready),
  .s_wdata(ctrl_wdata),.s_wstrb(ctrl_wstrb),.s_wvalid(ctrl_wvalid),.s_wready(ctrl_wready),
  .s_bresp(ctrl_bresp),.s_bvalid(ctrl_bvalid),.s_bready(ctrl_bready),
  .s_araddr(ctrl_araddr),.s_arvalid(ctrl_arvalid),.s_arready(ctrl_arready),
  .s_rdata(ctrl_rdata),.s_rresp(ctrl_rresp),.s_rvalid(ctrl_rvalid),.s_rready(ctrl_rready),
  .attn_awaddr(s_axil_awaddr),.attn_awvalid(s_axil_awvalid),.attn_awready(s_axil_awready),
  .attn_wdata(s_axil_wdata),.attn_wstrb(s_axil_wstrb),.attn_wvalid(s_axil_wvalid),
  .attn_wready(s_axil_wready),.attn_bresp(s_axil_bresp),.attn_bvalid(s_axil_bvalid),
  .attn_bready(s_axil_bready),.attn_araddr(s_axil_araddr),.attn_arvalid(s_axil_arvalid),
  .attn_arready(s_axil_arready),.attn_rdata(s_axil_rdata),.attn_rresp(s_axil_rresp),
  .attn_rvalid(s_axil_rvalid),.attn_rready(s_axil_rready),
  .mlp_awaddr(mlpc_awaddr),.mlp_awvalid(mlpc_awvalid),.mlp_awready(mlpc_awready),
  .mlp_wdata(mlpc_wdata),.mlp_wstrb(mlpc_wstrb),.mlp_wvalid(mlpc_wvalid),
  .mlp_wready(mlpc_wready),.mlp_bresp(mlpc_bresp),.mlp_bvalid(mlpc_bvalid),
  .mlp_bready(mlpc_bready),.mlp_araddr(mlpc_araddr),.mlp_arvalid(mlpc_arvalid),
  .mlp_arready(mlpc_arready),.mlp_rdata(mlpc_rdata),.mlp_rresp(mlpc_rresp),
  .mlp_rvalid(mlpc_rvalid),.mlp_rready(mlpc_rready));

 // V4 paired-DDR maintenance. Software clear pulses are requests only; the
 // compute/read state is reset exclusively by the delayed post-drain pulse.
 wire attention_weight_source_quiescent,mlp_weight_source_quiescent;
 wire command_pause,maintenance_drain_active,engine_soft_clear;
 wire paired_core_quiescent,paired_error;
 wire[31:0]paired_attn_bursts,paired_mlp_bursts,paired_both_cycles;
 wire[31:0]paired_hol0,paired_hol1,paired_hwm0,paired_hwm1;
 reg[31:0]paired_attn_snapshot_r,paired_mlp_snapshot_r,paired_both_snapshot_r;
 reg mlp_maintenance_pending_r;
 wire maintenance_request=core_clear||mlp_maintenance_pending_r;
 wire early_pause;

 // V4 mode control reuses the established owner ABI:
 // 0=IDLE, 1=ATTN_ONLY, 2=MLP_ONLY, 3=SHARED.
 wire owner_request_valid,owner_request_ready,owner_request_done;
 wire[1:0]owner_request,active_owner;
 wire owner_switch_pending,attention_launch_enable,mlp_launch_enable,owner_protocol_error;
 // Legacy fields had live outstanding semantics that the paired leaf does
 // not expose. Keep them explicitly unsupported instead of misreporting HWM.
 wire[7:0]ddr0_outstanding=8'd0;
 wire[7:0]ddr1_outstanding=8'd0;
 wire attention_quiescent;
 wire mlp_busy,tensor_busy,tensor_axi_active,meta_dma_busy,scheduler_active;
 wire mode_attention_quiescent,mode_mlp_quiescent;
 wire paired_core_enable,paired_ddr0_enable,paired_ddr1_enable;
 hap_v4_ddr_mode_controller u_mode(
  .core_clk(core_clk),.core_rst_n(core_rst_n),
  .mode_request_valid(owner_request_valid&&!maintenance_request),
  .mode_request_ready(owner_request_ready),
  .mode_request(owner_request),.attention_quiescent(mode_attention_quiescent),
  .mlp_quiescent(mode_mlp_quiescent),.paired_leaf_quiescent(paired_core_quiescent),
  .paired_leaf_error(paired_error),.maintenance_busy(maintenance_drain_active),
  .active_mode(active_owner),.attention_launch_enable(attention_launch_enable),
  .mlp_launch_enable(mlp_launch_enable),.core_enable(paired_core_enable),
  .ddr0_enable(paired_ddr0_enable),.ddr1_enable(paired_ddr1_enable),
  .switch_pending(owner_switch_pending),.request_done(owner_request_done),
  .error(owner_protocol_error));
 assign early_pause=maintenance_request||command_pause||owner_switch_pending||
  (owner_request_valid&&owner_request_ready);

 // MLP command/control wires.
 wire mlp_command_valid,mlp_command_ready,mlp_clear,mlp_abort_pending;
 reg mlp_abort_clear_r,mlp_abort_clear_issued_r;
 wire mlp_engine_clear=engine_soft_clear||mlp_abort_clear_r;
 wire mlp_command_bank;wire[31:0]mlp_gate_ddr0_base_addr,mlp_gate_ddr1_base_addr;
 wire[31:0]mlp_down_ddr0_base_addr,mlp_down_ddr1_base_addr;
 wire[31:0]mlp_input_base_addr,mlp_output_base_addr,mlp_command_id,mlp_layer_id;
 wire[1:0]mlp_input_bank_ready;wire mlp_compute_done,mlp_error;wire[2:0]mlp_phase;
 wire[1567:0]mlp_telemetry;reg mlp_full_done_r,compute_done_seen_r;
 reg store_done_seen_r,mlp_transaction_busy_r;
 wire mlp_command_fire=mlp_command_valid&&mlp_command_ready;
 wire tensor_store_done,tensor_store_armed;
 always @(posedge core_clk or negedge core_rst_n)begin
  if(!core_rst_n)begin mlp_maintenance_pending_r<=0;end
  else if(engine_soft_clear)mlp_maintenance_pending_r<=0;
  else if(mlp_clear&&!maintenance_request&&!owner_protocol_error)
   mlp_maintenance_pending_r<=1;
 end
 // AXI-Lite telemetry reads only native core-domain counters. DDR-domain
 // HOL/HWM remain internal until a dedicated handshake snapshot is added;
 // exporting a live 128-bit cross-SLR status bus would add unsafe CDC and
 // needless timing pressure.
 always @(posedge core_clk or negedge core_rst_n)begin
  if(!core_rst_n)begin paired_attn_snapshot_r<=0;paired_mlp_snapshot_r<=0;
   paired_both_snapshot_r<=0;end
  else if(paired_core_quiescent)begin
   paired_attn_snapshot_r<=paired_attn_bursts;
   paired_mlp_snapshot_r<=paired_mlp_bursts;
   paired_both_snapshot_r<=paired_both_cycles;end
 end
 always @(posedge core_clk or negedge core_rst_n)begin
  if(!core_rst_n)begin mlp_full_done_r<=0;compute_done_seen_r<=0;
   store_done_seen_r<=0;mlp_transaction_busy_r<=0;end
  else if(mlp_engine_clear)begin mlp_full_done_r<=0;compute_done_seen_r<=0;
   store_done_seen_r<=0;mlp_transaction_busy_r<=0;end
  else begin mlp_full_done_r<=0;if(mlp_command_fire)compute_done_seen_r<=0;
   if(mlp_command_fire)begin store_done_seen_r<=0;mlp_transaction_busy_r<=1;end
   if(mlp_compute_done)compute_done_seen_r<=1;
   if(tensor_store_done)store_done_seen_r<=1;
   if((compute_done_seen_r||mlp_compute_done)&&
      (store_done_seen_r||tensor_store_done))begin
    mlp_full_done_r<=1;compute_done_seen_r<=0;store_done_seen_r<=0;
    mlp_transaction_busy_r<=0;end
  end
 end

 // Resident A/B metadata plus sequential consumer scheduler.
 wire meta_load_start,meta_load_start_ready,meta_load_bank;
 wire meta_commit_valid,meta_commit_ready,meta_commit_bank;wire[31:0]meta_commit_generation;
 wire meta_active_bank;wire[31:0]meta_active_generation;wire[1:0]meta_bank_valid,meta_bank_loading;
 wire[31:0]mgw0,mgw1,mdw0,mdw1;wire meta_error;
 wire bank_load_begin_valid,bank_load_begin_ready,bank_load_begin_bank;
 wire gate_wr_valid,gate_wr_ready,gate_wr_bank;wire[17:0]gate_wr_addr;wire[223:0]gate_wr_meta;
 wire down_wr_valid,down_wr_ready,down_wr_bank;wire[16:0]down_wr_addr;wire[223:0]down_wr_meta;
 wire gate_rd_valid,gate_rd_ready,gate_rsp_valid,gate_rsp_ready;wire[17:0]gate_rd_addr;
 wire down_rd_valid,down_rd_ready,down_rsp_valid,down_rsp_ready;wire[16:0]down_rd_addr;
 wire[223:0]gate_rsp_meta,down_rsp_meta;wire gate_meta_valid,gate_meta_ready;
 wire down_meta_valid,down_meta_ready;wire[223:0]gate_meta_u224,down_meta_u224;
 wire scheduler_done,scheduler_error;wire[31:0]sgi,sgd,sdi,sdd;
 wire gate_phase=mlp_phase==3'd2;wire down_phase=mlp_phase==3'd4;
 hap_mlp_metadata_scheduler u_meta_sched(.clk(core_clk),.rst_n(core_rst_n),.clear(mlp_engine_clear),
  .command_start(mlp_command_fire),.command_done(mlp_compute_done),.gate_enable(gate_phase),
  .down_enable(down_phase),.gate_rd_valid(gate_rd_valid),.gate_rd_ready(gate_rd_ready),
  .gate_rd_addr(gate_rd_addr),.gate_rsp_valid(gate_rsp_valid),.gate_rsp_ready(gate_rsp_ready),
  .gate_rsp_meta(gate_rsp_meta),.gate_meta_valid(gate_meta_valid),.gate_meta_ready(gate_meta_ready),
  .gate_meta(gate_meta_u224),.down_rd_valid(down_rd_valid),.down_rd_ready(down_rd_ready),
  .down_rd_addr(down_rd_addr),.down_rsp_valid(down_rsp_valid),.down_rsp_ready(down_rsp_ready),
  .down_rsp_meta(down_rsp_meta),.down_meta_valid(down_meta_valid),.down_meta_ready(down_meta_ready),
  .down_meta(down_meta_u224),.active(scheduler_active),.gate_issue_count(sgi),
  .gate_delivery_count(sgd),.down_issue_count(sdi),.down_delivery_count(sdd),
  .done(scheduler_done),.error(scheduler_error));
 hap_mlp_weight_meta_resident_ab u_meta_bank(.clk(core_clk),.rst_n(core_rst_n),.clear(mlp_engine_clear),
  .load_begin_valid(bank_load_begin_valid),.load_begin_ready(bank_load_begin_ready),
  .load_begin_bank(bank_load_begin_bank),.gate_wr_valid(gate_wr_valid),.gate_wr_ready(gate_wr_ready),
  .gate_wr_bank(gate_wr_bank),.gate_wr_addr(gate_wr_addr),.gate_wr_meta_u224(gate_wr_meta),
  .down_wr_valid(down_wr_valid),.down_wr_ready(down_wr_ready),.down_wr_bank(down_wr_bank),
  .down_wr_addr(down_wr_addr),.down_wr_meta_u224(down_wr_meta),.commit_valid(meta_commit_valid),
  .commit_ready(meta_commit_ready),.commit_bank(meta_commit_bank),
  .commit_generation(meta_commit_generation),.consumer_quiescent(!mlp_busy&&!scheduler_active),
  .active_bank(meta_active_bank),.active_generation(meta_active_generation),
  .bank_valid(meta_bank_valid),.bank_loading(meta_bank_loading),
  .gate_rd_valid(gate_rd_valid),.gate_rd_ready(gate_rd_ready),.gate_rd_addr(gate_rd_addr),
  .gate_rsp_valid(gate_rsp_valid),.gate_rsp_ready(gate_rsp_ready),.gate_rsp_meta_u224(gate_rsp_meta),
  .down_rd_valid(down_rd_valid),.down_rd_ready(down_rd_ready),.down_rd_addr(down_rd_addr),
  .down_rsp_valid(down_rsp_valid),.down_rsp_ready(down_rsp_ready),.down_rsp_meta_u224(down_rsp_meta),
  .gate_write_count_bank0(mgw0),.gate_write_count_bank1(mgw1),
  .down_write_count_bank0(mdw0),.down_write_count_bank1(mdw1),
  .gate_read_count(),.down_read_count(),.error(meta_error));

 // MLP tensor and metadata DMA clients.
 wire tensor_load_valid,tensor_load_ready,tensor_store_valid,tensor_store_ready;
 wire tensor_dma_load_ready,tensor_dma_store_ready;
 wire mlp_input_valid,mlp_input_ready,mlp_input_bank;wire[6:0]mlp_input_group;
 wire[12287:0]mlp_input_s24x16x32;wire mlp_out_valid,mlp_out_ready;wire[7:0]mlp_out_tile_index;
 wire signed[6143:0]mlp_projection_s24x16x16;wire tensor_done,tensor_load_done;
 wire tensor_error;wire[2:0]tensor_phase;wire[31:0]tib,tig,tob,tot;
 wire tensor_cancelable_arm=tensor_phase==3'd3&&!tensor_axi_active&&
  !mlp_busy&&!mlp_transaction_busy_r;
 wire meta_dma_done,meta_dma_error;wire[2:0]meta_dma_phase;
 wire[31:0]meta_gate_base_addr,meta_down_base_addr,meta_gate_count,meta_down_count;
 wire[63:0]meta_physical_bytes;wire meta_dma_start_ready;

 // Three AXI client bundles (c0 Attention, c1 tensor, c2 metadata).
 wire c0_req,c1_req,c2_req;wire c0_arvalid,c0_arready,c0_rvalid,c0_rready,c0_rlast;
 wire[31:0]c0_araddr;wire[7:0]c0_arlen;wire[2:0]c0_arsize;wire[1:0]c0_arburst,c0_rresp;
 wire[255:0]c0_rdata;wire c0_awvalid,c0_awready,c0_wvalid,c0_wready,c0_wlast,c0_bvalid,c0_bready;
 wire[31:0]c0_awaddr,c0_wstrb;wire[7:0]c0_awlen;wire[2:0]c0_awsize;wire[1:0]c0_awburst,c0_bresp;wire[255:0]c0_wdata;
 wire c1_arvalid,c1_arready,c1_rvalid,c1_rready,c1_rlast,c1_awvalid,c1_awready,c1_wvalid,c1_wready,c1_wlast,c1_bvalid,c1_bready;
 wire[31:0]c1_araddr,c1_awaddr,c1_wstrb;wire[7:0]c1_arlen,c1_awlen;wire[2:0]c1_arsize,c1_awsize;
 wire[1:0]c1_arburst,c1_rresp,c1_awburst,c1_bresp;wire[255:0]c1_rdata,c1_wdata;
 wire c2_arvalid,c2_arready,c2_rvalid,c2_rready,c2_rlast,c2_awvalid,c2_awready,c2_wvalid,c2_wready,c2_wlast,c2_bvalid,c2_bready;
 wire[31:0]c2_araddr,c2_awaddr,c2_wstrb;wire[7:0]c2_arlen,c2_awlen;wire[2:0]c2_arsize,c2_awsize;
 wire[1:0]c2_arburst,c2_rresp,c2_awburst,c2_bresp;wire[255:0]c2_rdata,c2_wdata;
 hap_mlp_tensor_dma_bridge u_tensor(.clk(core_clk),.rst_n(core_rst_n),.clear(mlp_engine_clear),
  .load_valid(tensor_load_valid&&!early_pause),.load_ready(tensor_dma_load_ready),
  .load_bank(mlp_command_bank),.input_base_addr(mlp_input_base_addr),
  .store_valid(tensor_store_valid&&!early_pause),.store_ready(tensor_dma_store_ready),
  .output_base_addr(mlp_output_base_addr),.mlp_input_valid(mlp_input_valid),
  .mlp_input_ready(mlp_input_ready),.mlp_input_bank(mlp_input_bank),.mlp_input_group(mlp_input_group),
  .mlp_input_s24x16x32(mlp_input_s24x16x32),.mlp_out_valid(mlp_out_valid),
  .mlp_out_ready(mlp_out_ready),.mlp_out_tile(mlp_out_tile_index),
  .mlp_out_s24x16x16(mlp_projection_s24x16x16),.busy(tensor_busy),.done(tensor_done),
  .load_done(tensor_load_done),.store_done(tensor_store_done),.store_armed(tensor_store_armed),
  .axi_active(tensor_axi_active),.error(tensor_error),.phase(tensor_phase),
  .input_beat_count(tib),.input_group_count(tig),.output_beat_count(tob),.output_tile_count(tot),
  .m_axi_arvalid(c1_arvalid),.m_axi_arready(c1_arready),.m_axi_araddr(c1_araddr),
  .m_axi_arlen(c1_arlen),.m_axi_arsize(c1_arsize),.m_axi_arburst(c1_arburst),
  .m_axi_rvalid(c1_rvalid),.m_axi_rready(c1_rready),.m_axi_rdata(c1_rdata),
  .m_axi_rresp(c1_rresp),.m_axi_rlast(c1_rlast),.m_axi_awvalid(c1_awvalid),
  .m_axi_awready(c1_awready),.m_axi_awaddr(c1_awaddr),.m_axi_awlen(c1_awlen),
  .m_axi_awsize(c1_awsize),.m_axi_awburst(c1_awburst),.m_axi_wvalid(c1_wvalid),
  .m_axi_wready(c1_wready),.m_axi_wdata(c1_wdata),.m_axi_wstrb(c1_wstrb),
 .m_axi_wlast(c1_wlast),.m_axi_bvalid(c1_bvalid),.m_axi_bready(c1_bready),.m_axi_bresp(c1_bresp));
 assign tensor_load_ready=!early_pause&&tensor_dma_load_ready;
 assign tensor_store_ready=!early_pause&&tensor_dma_store_ready;
 hap_mlp_meta_dma_loader u_meta_dma(.clk(core_clk),.rst_n(core_rst_n),.clear(mlp_engine_clear),
  .start_valid(meta_load_start&&!early_pause),.start_ready(meta_dma_start_ready),.target_bank(meta_load_bank),
  .gate_base_addr(meta_gate_base_addr),.down_base_addr(meta_down_base_addr),
  .bank_load_begin_valid(bank_load_begin_valid),.bank_load_begin_ready(bank_load_begin_ready),
  .bank_load_begin_bank(bank_load_begin_bank),.gate_wr_valid(gate_wr_valid),.gate_wr_ready(gate_wr_ready),
  .gate_wr_bank(gate_wr_bank),.gate_wr_addr(gate_wr_addr),.gate_wr_meta(gate_wr_meta),
  .down_wr_valid(down_wr_valid),.down_wr_ready(down_wr_ready),.down_wr_bank(down_wr_bank),
  .down_wr_addr(down_wr_addr),.down_wr_meta(down_wr_meta),.busy(meta_dma_busy),
  .done(meta_dma_done),.error(meta_dma_error),.phase(meta_dma_phase),
  .gate_record_count(meta_gate_count),.down_record_count(meta_down_count),.physical_bytes(meta_physical_bytes),
  .m_axi_arvalid(c2_arvalid),.m_axi_arready(c2_arready),.m_axi_araddr(c2_araddr),
  .m_axi_arlen(c2_arlen),.m_axi_arsize(c2_arsize),.m_axi_arburst(c2_arburst),
  .m_axi_rvalid(c2_rvalid),.m_axi_rready(c2_rready),.m_axi_rdata(c2_rdata),
  .m_axi_rresp(c2_rresp),.m_axi_rlast(c2_rlast),.m_axi_awvalid(c2_awvalid),
  .m_axi_awready(c2_awready),.m_axi_awaddr(c2_awaddr),.m_axi_awlen(c2_awlen),
  .m_axi_awsize(c2_awsize),.m_axi_awburst(c2_awburst),.m_axi_wvalid(c2_wvalid),
  .m_axi_wready(c2_wready),.m_axi_wdata(c2_wdata),.m_axi_wstrb(c2_wstrb),
  .m_axi_wlast(c2_wlast),.m_axi_bvalid(c2_bvalid),.m_axi_bready(c2_bready),.m_axi_bresp(c2_bresp));
 // Decode readiness against the software-selected target bank.  The loader's
 // bank_load_begin_bank does not update until after start acceptance.
 assign meta_load_start_ready=!early_pause&&meta_dma_start_ready&&
  meta_load_bank!=meta_active_bank&&!meta_bank_loading[meta_load_bank];

 hap_mlp_axil_control #(.PRODUCTION_INTEGRATION(1))u_mlp_ctrl(.clk(core_clk),.rst_n(core_rst_n),
  .s_axil_awaddr(mlpc_awaddr),.s_axil_awvalid(mlpc_awvalid),.s_axil_awready(mlpc_awready),
  .s_axil_wdata(mlpc_wdata),.s_axil_wstrb(mlpc_wstrb),.s_axil_wvalid(mlpc_wvalid),
  .s_axil_wready(mlpc_wready),.s_axil_bresp(mlpc_bresp),.s_axil_bvalid(mlpc_bvalid),
  .s_axil_bready(mlpc_bready),.s_axil_araddr(mlpc_araddr),.s_axil_arvalid(mlpc_arvalid),
  .s_axil_arready(mlpc_arready),.s_axil_rdata(mlpc_rdata),.s_axil_rresp(mlpc_rresp),
  .s_axil_rvalid(mlpc_rvalid),.s_axil_rready(mlpc_rready),.owner_request_valid(owner_request_valid),
  .owner_request_ready(owner_request_ready),.admission_pause(early_pause),
  .owner_request(owner_request),
  .owner_request_done(owner_request_done),.active_owner(active_owner),
  .owner_switch_pending(owner_switch_pending),.attention_launch_enable(attention_launch_enable),
  .mlp_launch_enable(mlp_launch_enable),.owner_protocol_error(owner_protocol_error),
  .ddr0_outstanding(ddr0_outstanding),.ddr1_outstanding(ddr1_outstanding),
  .maintenance_busy(maintenance_drain_active),
  .maintenance_request_pending(maintenance_request),
  .mlp_abort_complete(mlp_abort_clear_r),
  .paired_quiescent(paired_core_quiescent),
  .paired_attn_bursts(paired_attn_snapshot_r),
  .paired_mlp_bursts(paired_mlp_snapshot_r),
  .paired_both_cycles(paired_both_snapshot_r),
  .paired_hol0(32'd0),.paired_hol1(32'd0),
  .paired_hwm0(32'd0),.paired_hwm1(32'd0),
  .mlp_command_valid(mlp_command_valid),.mlp_command_ready(mlp_command_ready),
  .mlp_clear_pulse(mlp_clear),.mlp_abort_pending(mlp_abort_pending),
  .mlp_command_bank(mlp_command_bank),
  .mlp_gate_ddr0_base_addr(mlp_gate_ddr0_base_addr),.mlp_gate_ddr1_base_addr(mlp_gate_ddr1_base_addr),
  .mlp_down_ddr0_base_addr(mlp_down_ddr0_base_addr),.mlp_down_ddr1_base_addr(mlp_down_ddr1_base_addr),
  .mlp_input_base_addr(mlp_input_base_addr),.mlp_output_base_addr(mlp_output_base_addr),
  .mlp_command_id(mlp_command_id),.mlp_layer_id(mlp_layer_id),
  .mlp_input_bank_ready(mlp_input_bank_ready),.mlp_busy(mlp_transaction_busy_r),
  .mlp_done(mlp_full_done_r),
  .mlp_error(mlp_error||scheduler_error),.mlp_phase(mlp_phase),.mlp_telemetry(mlp_telemetry),
  .tensor_load_valid(tensor_load_valid),.tensor_load_ready(tensor_load_ready),
  .tensor_store_valid(tensor_store_valid),.tensor_store_ready(tensor_store_ready),
  .tensor_store_armed(tensor_store_armed),.tensor_dma_busy(tensor_busy),.tensor_dma_done(tensor_done),
  .tensor_dma_error(tensor_error),.tensor_dma_phase(tensor_phase),.tensor_input_beat_count(tib),
  .tensor_input_group_count(tig),.tensor_output_beat_count(tob),.tensor_output_tile_count(tot),
  .meta_gate_base_addr(meta_gate_base_addr),.meta_down_base_addr(meta_down_base_addr),
  .meta_dma_busy(meta_dma_busy),.meta_dma_done(meta_dma_done),.meta_dma_error(meta_dma_error),
  .meta_dma_phase(meta_dma_phase),.meta_dma_gate_record_count(meta_gate_count),
  .meta_dma_down_record_count(meta_down_count),.meta_dma_physical_bytes(meta_physical_bytes),
  .meta_load_begin_valid(meta_load_start),.meta_load_begin_ready(meta_load_start_ready),
  .meta_load_bank(meta_load_bank),.meta_commit_valid(meta_commit_valid),
  .meta_commit_ready(meta_commit_ready),.meta_commit_bank(meta_commit_bank),
  .meta_commit_generation(meta_commit_generation),.meta_active_bank(meta_active_bank),
  .meta_active_generation(meta_active_generation),.meta_bank_valid(meta_bank_valid),
  .meta_bank_loading(meta_bank_loading),.meta_gate_write_count_bank0(mgw0),
  .meta_gate_write_count_bank1(mgw1),.meta_down_write_count_bank0(mdw0),
  .meta_down_write_count_bank1(mdw1),.meta_error(meta_error),.irq(mlp_irq),
  .done_sticky(),.error_sticky());

 // Compute/resource top. Its engine-native DDR ports terminate only on the
 // V4 paired scheduler below; no command-level owner mux remains.
 wire m_axi_arvalid,m_axi_arready,m_axi_rvalid,m_axi_rready,m_axi_rlast;
 wire[31:0]m_axi_araddr;wire[7:0]m_axi_arlen;wire[2:0]m_axi_arsize;
 wire[1:0]m_axi_arburst,m_axi_rresp;wire[255:0]m_axi_rdata;
 wire m_axi_awvalid,m_axi_awready,m_axi_wvalid,m_axi_wready,m_axi_wlast,m_axi_bvalid,m_axi_bready;
 wire[31:0]m_axi_awaddr,m_axi_wstrb;wire[7:0]m_axi_awlen;wire[2:0]m_axi_awsize;
 wire[1:0]m_axi_awburst,m_axi_bresp;wire[255:0]m_axi_wdata;wire attention_data_axi_busy;
 wire mlp_gate_meta_valid=gate_meta_valid;wire mlp_gate_meta_ready;
 wire[223:0]mlp_gate_meta_u224=gate_meta_u224;
 wire mlp_down_meta_valid=down_meta_valid;wire mlp_down_meta_ready;
 wire[223:0]mlp_down_meta_u224=down_meta_u224;
 wire att_d0_arvalid,att_d0_arready,att_d0_rvalid,att_d0_rready,att_d0_rlast;
 wire[31:0]att_d0_araddr;wire[7:0]att_d0_arlen;wire[2:0]att_d0_arsize;
 wire[1:0]att_d0_arburst,att_d0_rresp;wire[511:0]att_d0_rdata;
 wire att_d1_arvalid,att_d1_arready,att_d1_rvalid,att_d1_rready,att_d1_rlast;
 wire[31:0]att_d1_araddr;wire[7:0]att_d1_arlen;wire[2:0]att_d1_arsize;
 wire[1:0]att_d1_arburst,att_d1_rresp;wire[511:0]att_d1_rdata;
 wire mlp_d0_arvalid,mlp_d0_arready,mlp_d0_rvalid,mlp_d0_rready,mlp_d0_rlast;
 wire[31:0]mlp_d0_araddr;wire[7:0]mlp_d0_arlen;wire[2:0]mlp_d0_arsize;
 wire[1:0]mlp_d0_arburst,mlp_d0_rresp;wire[511:0]mlp_d0_rdata;
 wire mlp_d1_arvalid,mlp_d1_arready,mlp_d1_rvalid,mlp_d1_rready,mlp_d1_rlast;
 wire[31:0]mlp_d1_araddr;wire[7:0]mlp_d1_arlen;wire[2:0]mlp_d1_arsize;
 wire[1:0]mlp_d1_arburst,mlp_d1_rresp;wire[511:0]mlp_d1_rdata;
 wire[1:0]active_client;wire data_conflict_error;
 assign gate_meta_ready=mlp_gate_meta_ready;
 assign down_meta_ready=mlp_down_meta_ready;
 // early_pause reaches both command-admission boundaries immediately; the
 // engine internals still allow already-accepted fixed commands to drain.
 hap_attention_mlp_resource_top u_compute(.*,
  .command_pause(early_pause),.mlp_abort_clear(mlp_abort_clear_r),
  .mlp_done(mlp_compute_done));

 // Clear safety covers every engine and the shared AXI256 command-locking
 // arbiter. A clear therefore waits for accepted whole commands, including
 // Attention output DMA and MLP tensor/meta DMA, to finish naturally.
 wire data_axi_quiescent=(active_client==2'd0)&&!c0_req&&!c1_req&&!c2_req;
 wire attention_clear_safe=attention_quiescent&&!attention_data_axi_busy;
 wire mlp_clear_safe=!mlp_transaction_busy_r&&!mlp_busy&&!scheduler_active&&
  (!tensor_busy||tensor_cancelable_arm)&&!tensor_axi_active&&!meta_dma_busy;
 wire attention_source_closed=attention_weight_source_quiescent&&
  attention_clear_safe&&data_axi_quiescent;
 wire mlp_source_closed=mlp_weight_source_quiescent&&mlp_clear_safe&&
  data_axi_quiescent;
 assign mode_attention_quiescent=attention_clear_safe&&data_axi_quiescent;
 // Mode changes have no cancel side effect. An armed tensor store therefore
 // blocks a mode commit; software must complete it or request maintenance.
 assign mode_mlp_quiescent=!mlp_transaction_busy_r&&!mlp_busy&&
  !scheduler_active&&!tensor_busy&&!tensor_axi_active&&!meta_dma_busy&&
  data_axi_quiescent;
 always @(posedge core_clk or negedge core_rst_n)begin
  if(!core_rst_n||engine_soft_clear)begin
   mlp_abort_clear_r<=0;mlp_abort_clear_issued_r<=0;
  end else begin
   mlp_abort_clear_r<=0;
   if(!mlp_abort_pending)mlp_abort_clear_issued_r<=0;
   else if(!mlp_abort_clear_issued_r&&maintenance_drain_active&&
       paired_core_quiescent&&data_axi_quiescent)begin
    mlp_abort_clear_r<=1;mlp_abort_clear_issued_r<=1;
   end
  end
 end
 hap_axi512_paired_2client_read_wrr u_paired_weight(
  .core_clk(core_clk),.core_rst_n(core_rst_n),.core_clear(maintenance_request),
  .core_enable(paired_core_enable),.attn_source_quiescent(attention_source_closed),
  .mlp_source_quiescent(mlp_source_closed),.maintenance_pause_sources(command_pause),
  .maintenance_drain_active(maintenance_drain_active),
  .maintenance_soft_clear_pulse(engine_soft_clear),
  .ddr0_clk(ddr0_clk),.ddr0_rst_n(ddr0_rst_n),.ddr0_enable(paired_ddr0_enable),
  .ddr1_clk(ddr1_clk),.ddr1_rst_n(ddr1_rst_n),.ddr1_enable(paired_ddr1_enable),
  .a0_arvalid(att_d0_arvalid),.a0_arready(att_d0_arready),
  .a0_araddr(att_d0_araddr),.a0_arlen(att_d0_arlen),
  .a0_arsize(att_d0_arsize),.a0_arburst(att_d0_arburst),
  .a0_rvalid(att_d0_rvalid),.a0_rready(att_d0_rready),.a0_rdata(att_d0_rdata),
  .a0_rresp(att_d0_rresp),.a0_rlast(att_d0_rlast),
  .m0_arvalid(mlp_d0_arvalid),.m0_arready(mlp_d0_arready),
  .m0_araddr(mlp_d0_araddr),.m0_arlen(mlp_d0_arlen),
  .m0_arsize(mlp_d0_arsize),.m0_arburst(mlp_d0_arburst),
  .m0_rvalid(mlp_d0_rvalid),.m0_rready(mlp_d0_rready),.m0_rdata(mlp_d0_rdata),
  .m0_rresp(mlp_d0_rresp),.m0_rlast(mlp_d0_rlast),
  .a1_arvalid(att_d1_arvalid),.a1_arready(att_d1_arready),
  .a1_araddr(att_d1_araddr),.a1_arlen(att_d1_arlen),
  .a1_arsize(att_d1_arsize),.a1_arburst(att_d1_arburst),
  .a1_rvalid(att_d1_rvalid),.a1_rready(att_d1_rready),.a1_rdata(att_d1_rdata),
  .a1_rresp(att_d1_rresp),.a1_rlast(att_d1_rlast),
  .m1_arvalid(mlp_d1_arvalid),.m1_arready(mlp_d1_arready),
  .m1_araddr(mlp_d1_araddr),.m1_arlen(mlp_d1_arlen),
  .m1_arsize(mlp_d1_arsize),.m1_arburst(mlp_d1_arburst),
  .m1_rvalid(mlp_d1_rvalid),.m1_rready(mlp_d1_rready),.m1_rdata(mlp_d1_rdata),
  .m1_rresp(mlp_d1_rresp),.m1_rlast(mlp_d1_rlast),
  .p0_arvalid(ddr0_axi_arvalid),.p0_arready(ddr0_axi_arready),
  .p0_araddr(ddr0_axi_araddr),.p0_arlen(ddr0_axi_arlen),
  .p0_arsize(ddr0_axi_arsize),.p0_arburst(ddr0_axi_arburst),
  .p0_rvalid(ddr0_axi_rvalid),.p0_rready(ddr0_axi_rready),
  .p0_rdata(ddr0_axi_rdata),.p0_rresp(ddr0_axi_rresp),.p0_rlast(ddr0_axi_rlast),
  .p1_arvalid(ddr1_axi_arvalid),.p1_arready(ddr1_axi_arready),
  .p1_araddr(ddr1_axi_araddr),.p1_arlen(ddr1_axi_arlen),
  .p1_arsize(ddr1_axi_arsize),.p1_arburst(ddr1_axi_arburst),
  .p1_rvalid(ddr1_axi_rvalid),.p1_rready(ddr1_axi_rready),
  .p1_rdata(ddr1_axi_rdata),.p1_rresp(ddr1_axi_rresp),.p1_rlast(ddr1_axi_rlast),
  .core_quiescent(paired_core_quiescent),.error(paired_error),
  .accepted_attn_bursts(paired_attn_bursts),
  .accepted_mlp_bursts(paired_mlp_bursts),.both_eligible_cycles(paired_both_cycles),
  .p0_hol_cycles(paired_hol0),.p1_hol_cycles(paired_hol1),
  .p0_tag_high_watermark(paired_hwm0),.p1_tag_high_watermark(paired_hwm1));
 assign c0_req=attention_data_axi_busy;assign c1_req=tensor_axi_active;assign c2_req=meta_dma_busy;
 assign c0_arvalid=m_axi_arvalid;assign m_axi_arready=c0_arready;assign c0_araddr=m_axi_araddr;
 assign c0_arlen=m_axi_arlen;assign c0_arsize=m_axi_arsize;assign c0_arburst=m_axi_arburst;
 assign m_axi_rvalid=c0_rvalid;assign c0_rready=m_axi_rready;assign m_axi_rdata=c0_rdata;
 assign m_axi_rresp=c0_rresp;assign m_axi_rlast=c0_rlast;assign c0_awvalid=m_axi_awvalid;
 assign m_axi_awready=c0_awready;assign c0_awaddr=m_axi_awaddr;assign c0_awlen=m_axi_awlen;
 assign c0_awsize=m_axi_awsize;assign c0_awburst=m_axi_awburst;assign c0_wvalid=m_axi_wvalid;
 assign m_axi_wready=c0_wready;assign c0_wdata=m_axi_wdata;assign c0_wstrb=m_axi_wstrb;
 assign c0_wlast=m_axi_wlast;assign m_axi_bvalid=c0_bvalid;assign c0_bready=m_axi_bready;
 assign m_axi_bresp=c0_bresp;

 wire m_arvalid,m_arready,m_rvalid,m_rready,m_rlast,m_awvalid,m_awready,m_wvalid,m_wready,m_wlast,m_bvalid,m_bready;
 wire[31:0]m_araddr,m_awaddr,m_wstrb;wire[7:0]m_arlen,m_awlen;wire[2:0]m_arsize,m_awsize;
 wire[1:0]m_arburst,m_rresp,m_awburst,m_bresp;wire[255:0]m_rdata,m_wdata;
 hap_axi256_3to1_arbiter u_data_arb(.clk(core_clk),.rst_n(core_rst_n),
  .clear(engine_soft_clear),.conflict_error(data_conflict_error),.*);
 assign data_axi_arvalid=m_arvalid;assign m_arready=data_axi_arready;assign data_axi_araddr=m_araddr;
 assign data_axi_arlen=m_arlen;assign data_axi_arsize=m_arsize;assign data_axi_arburst=m_arburst;
 assign m_rvalid=data_axi_rvalid;assign data_axi_rready=m_rready;assign m_rdata=data_axi_rdata;
 assign m_rresp=data_axi_rresp;assign m_rlast=data_axi_rlast;assign data_axi_awvalid=m_awvalid;
 assign m_awready=data_axi_awready;assign data_axi_awaddr=m_awaddr;assign data_axi_awlen=m_awlen;
 assign data_axi_awsize=m_awsize;assign data_axi_awburst=m_awburst;assign data_axi_wvalid=m_wvalid;
 assign m_wready=data_axi_wready;assign data_axi_wdata=m_wdata;assign data_axi_wstrb=m_wstrb;
 assign data_axi_wlast=m_wlast;assign m_bvalid=data_axi_bvalid;assign data_axi_bready=m_bready;
 assign m_bresp=data_axi_bresp;
 assign integration_error=owner_protocol_error||paired_error||mlp_error||
  meta_error||meta_dma_error||tensor_error||scheduler_error||
  data_conflict_error;
endmodule
