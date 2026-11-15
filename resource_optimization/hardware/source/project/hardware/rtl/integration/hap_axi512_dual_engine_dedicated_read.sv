`timescale 1ns / 1ps

// M002 dedicated physical DDR routing. Attention's two logical weight streams
// share DDR0; MLP's two logical streams share DDR1. No halfgroup is discarded.
// Narrow descriptors cross to core_clk, complete pairs are serialized into
// separate DDR-local egress queues, and ordered response tags select the
// original logical half. Existing engine reader payload CDC remains intact.
//
// The reset, pause, drain, error freeze and delayed soft-clear machinery is
// retained from hap_axi512_paired_2client_read_wrr. Its FIFO and ordered-local
// helper modules are compiled from that existing source. accepted_*_bursts
// count logical pairs; each accepted pair produces two physical AR bursts.
module hap_axi512_dual_engine_dedicated_read #(
    parameter integer AXI_ADDR_W=32,
    parameter integer FIFO_DEPTH=16,
    parameter integer TAG_DEPTH=32,
    parameter integer SEQ_W=16
) (
    input wire core_clk,input wire core_rst_n,input wire core_clear,
    input wire core_enable,
    // Producers acknowledge this pause only after they can no longer create
    // new paired AR requests and all already-presented AR have handshaken.
    input wire attn_source_quiescent,input wire mlp_source_quiescent,
    output wire maintenance_pause_sources,
    output wire maintenance_drain_active,
    output wire maintenance_soft_clear_pulse,
    // a0/a1 and p0 are in ddr0_clk; m0/m1 and p1 are in ddr1_clk.
    // All four ARADDR fields are DDR-local byte offsets, unchanged here.
    // Both enables are committed core_clk levels.  This leaf owns their
    // synchronization before either level is consumed in a DDR clock domain.
    input wire ddr0_clk,input wire ddr0_rst_n,input wire ddr0_enable,
    input wire ddr1_clk,input wire ddr1_rst_n,input wire ddr1_enable,

    input wire a0_arvalid,output wire a0_arready,input wire[AXI_ADDR_W-1:0]a0_araddr,
    input wire[7:0]a0_arlen,input wire[2:0]a0_arsize,input wire[1:0]a0_arburst,
    output wire a0_rvalid,input wire a0_rready,output wire[511:0]a0_rdata,
    output wire[1:0]a0_rresp,output wire a0_rlast,
    input wire a1_arvalid,output wire a1_arready,input wire[AXI_ADDR_W-1:0]a1_araddr,
    input wire[7:0]a1_arlen,input wire[2:0]a1_arsize,input wire[1:0]a1_arburst,
    output wire a1_rvalid,input wire a1_rready,output wire[511:0]a1_rdata,
    output wire[1:0]a1_rresp,output wire a1_rlast,

    input wire m0_arvalid,output wire m0_arready,input wire[AXI_ADDR_W-1:0]m0_araddr,
    input wire[7:0]m0_arlen,input wire[2:0]m0_arsize,input wire[1:0]m0_arburst,
    output wire m0_rvalid,input wire m0_rready,output wire[511:0]m0_rdata,
    output wire[1:0]m0_rresp,output wire m0_rlast,
    input wire m1_arvalid,output wire m1_arready,input wire[AXI_ADDR_W-1:0]m1_araddr,
    input wire[7:0]m1_arlen,input wire[2:0]m1_arsize,input wire[1:0]m1_arburst,
    output wire m1_rvalid,input wire m1_rready,output wire[511:0]m1_rdata,
    output wire[1:0]m1_rresp,output wire m1_rlast,

    output wire p0_arvalid,input wire p0_arready,output wire[AXI_ADDR_W-1:0]p0_araddr,
    output wire[7:0]p0_arlen,output wire[2:0]p0_arsize,output wire[1:0]p0_arburst,
    input wire p0_rvalid,output wire p0_rready,input wire[511:0]p0_rdata,
    input wire[1:0]p0_rresp,input wire p0_rlast,
    output wire p1_arvalid,input wire p1_arready,output wire[AXI_ADDR_W-1:0]p1_araddr,
    output wire[7:0]p1_arlen,output wire[2:0]p1_arsize,output wire[1:0]p1_arburst,
    input wire p1_rvalid,output wire p1_rready,input wire[511:0]p1_rdata,
    input wire[1:0]p1_rresp,input wire p1_rlast,

    output wire core_quiescent,output wire error,
    output reg[31:0]accepted_attn_bursts,output reg[31:0]accepted_mlp_bursts,
    output reg[31:0]both_eligible_cycles,
    output wire[31:0]p0_hol_cycles,output wire[31:0]p1_hol_cycles,
    output wire[31:0]p0_tag_high_watermark,output wire[31:0]p1_tag_high_watermark
);
    localparam integer DESC_W=AXI_ADDR_W+13;
    localparam integer INGRESS_W=SEQ_W+DESC_W;
    localparam integer EGRESS_W=1+SEQ_W+DESC_W;
    // Each active-low reset is qualified at its source.  Assertion sets the
    // source request even if that source clock is stopped; release waits for
    // one source edge.  Only these registered levels cross clock domains.
    reg core_hard_req_r=1'b1;
    reg ddr0_hard_req_r=1'b1;
    reg ddr1_hard_req_r=1'b1;
    always @(posedge core_clk or negedge core_rst_n) begin
      if(!core_rst_n) core_hard_req_r<=1'b1;
      else core_hard_req_r<=1'b0;
    end
    always @(posedge ddr0_clk or negedge ddr0_rst_n) begin
      if(!ddr0_rst_n) ddr0_hard_req_r<=1'b1;
      else ddr0_hard_req_r<=1'b0;
    end
    always @(posedge ddr1_clk or negedge ddr1_rst_n) begin
      if(!ddr1_rst_n) ddr1_hard_req_r<=1'b1;
      else ddr1_hard_req_r<=1'b0;
    end
    wire ddr0_req_core,ddr1_req_core;
    wire core_req_ddr0,ddr1_req_ddr0;
    wire core_req_ddr1,ddr0_req_ddr1;
    reg[4:0]reset_shift_r;
    reg[2:0]source_closed_stable_r;
    reg[2:0]clear_stable_r;
    reg maintenance_req_r;
    reg maintenance_stop_req_r;
    reg maintenance_soft_clear_pulse_r;
    reg clear_armed_r;
    reg fifo_reset_request_r;
    // core_rst_n asserts this registered request asynchronously.  Remote DDR
    // resets reach the manager through hard_rst_core and assert it on a core
    // edge.  Its Q, not a combinational reset OR, is the only source presented
    // to the three destination reset synchronizers.
    wire fifo_reset_source=fifo_reset_request_r;
    wire fifo_rst_core,fifo_rst_ddr0,fifo_rst_ddr1;
    // Combine only after each remote request has passed its own two-stage
    // destination synchronizer.  Consumers still sample hard reset on their
    // local clock; local asynchronous reset pins retain their original role.
    wire hard_rst_core=core_hard_req_r||ddr0_req_core||ddr1_req_core;
    wire hard_rst_ddr0=ddr0_hard_req_r||core_req_ddr0||ddr1_req_ddr0;
    wire hard_rst_ddr1=ddr1_hard_req_r||core_req_ddr1||ddr0_req_ddr1;

    reg[SEQ_W-1:0]a0_src_seq_r,m0_src_seq_r,a1_src_seq_r,m1_src_seq_r;
    reg a0_skid_valid_r,m0_skid_valid_r,a1_skid_valid_r,m1_skid_valid_r;
    reg[INGRESS_W-1:0]a0_skid_data_r,m0_skid_data_r;
    reg[INGRESS_W-1:0]a1_skid_data_r,m1_skid_data_r;
    wire a0_wr_ready,m0_wr_ready,a1_wr_ready,m1_wr_ready;
    wire a0_wr_empty,m0_wr_empty,a1_wr_empty,m1_wr_empty;
    wire a0_in_error,m0_in_error,a1_in_error,m1_in_error;
    wire a0_q_valid,m0_q_valid,a1_q_valid,m1_q_valid;
    wire a0_q_ready,m0_q_ready,a1_q_ready,m1_q_ready;
    wire[INGRESS_W-1:0]a0_q,m0_q,a1_q,m1_q;

    wire o0_wr_ready,o1_wr_ready,o0_wr_empty,o1_wr_empty;
    wire o0_q_valid,o1_q_valid,o0_q_ready,o1_q_ready;
    wire[EGRESS_W-1:0]o0_q,o1_q;
    wire o0_error,o1_error;
    // Each engine owns one physical DDR. Both descriptors are consumed
    // atomically, then emitted as stream 0 followed by stream 1. The saved
    // second descriptor cannot be lost when the egress FIFO backpressures.
    reg [SEQ_W-1:0] sequence0_r,sequence1_r;
    reg second0_valid_r,second1_valid_r;
    reg [DESC_W-1:0] second0_r,second1_r;
    reg core_error_r;
    wire a_pair_present=a0_q_valid&&a1_q_valid;
    wire m_pair_present=m0_q_valid&&m1_q_valid;
    wire a_pair_match=a0_q[INGRESS_W-1:DESC_W]==a1_q[INGRESS_W-1:DESC_W]&&
        a0_q[12:0]==a1_q[12:0];
    wire m_pair_match=m0_q[INGRESS_W-1:DESC_W]==m1_q[INGRESS_W-1:DESC_W]&&
        m0_q[12:0]==m1_q[12:0];
    wire scheduler_run=core_enable||maintenance_req_r;
    wire a_eligible=scheduler_run&&a_pair_present&&a_pair_match&&
        !second0_valid_r&&o0_wr_ready;
    wire m_eligible=scheduler_run&&m_pair_present&&m_pair_match&&
        !second1_valid_r&&o1_wr_ready;
    wire grant_attn,grant_mlp;
    wire global_freeze_core;
    wire o0_push=!global_freeze_core&&scheduler_run&&o0_wr_ready&&
        (second0_valid_r||grant_attn);
    wire o1_push=!global_freeze_core&&scheduler_run&&o1_wr_ready&&
        (second1_valid_r||grant_mlp);
    // The local issuer's historical owner bit now selects the logical half,
    // not the compute engine. Sequence numbers are physical-DDR-local.
    wire [EGRESS_W-1:0] o0_in={second0_valid_r,sequence0_r,
        (second0_valid_r?second0_r:a0_q[DESC_W-1:0])};
    wire [EGRESS_W-1:0] o1_in={second1_valid_r,sequence1_r,
        (second1_valid_r?second1_r:m0_q[DESC_W-1:0])};

    wire local0_quiescent,local1_quiescent,local0_error,local1_error;
    wire local0_q_core,local1_q_core,local0_error_core,local1_error_core;
    wire o0_error_core,o1_error_core;
    reg maintenance_violation0_r,maintenance_violation1_r;
    wire maintenance_violation0_core,maintenance_violation1_core;
    assign global_freeze_core=core_error_r||local0_error_core||local1_error_core||
        a0_in_error||m0_in_error||a1_in_error||m1_in_error||
        o0_error_core||o1_error_core||maintenance_violation0_core||
        maintenance_violation1_core;
    wire global_freeze_ddr0,global_freeze_ddr1;
    wire maintenance_active_ddr0,maintenance_active_ddr1;
    wire maintenance_stop_ddr0,maintenance_stop_ddr1;
    wire maintenance_ack0_core,maintenance_ack1_core;
    wire a0_skid_push=a0_skid_valid_r&&!local0_error&&
        !global_freeze_ddr0&&a0_wr_ready;
    wire a1_skid_push=a1_skid_valid_r&&!local0_error&&
        !global_freeze_ddr0&&a1_wr_ready;
    wire m0_skid_push=m0_skid_valid_r&&!local1_error&&
        !global_freeze_ddr1&&m0_wr_ready;
    wire m1_skid_push=m1_skid_valid_r&&!local1_error&&
        !global_freeze_ddr1&&m1_wr_ready;
    wire a0_source_empty_ddr0=!a0_skid_valid_r&&a0_wr_empty;
    wire a1_source_empty_ddr0=!a1_skid_valid_r&&a1_wr_empty;
    wire m0_source_empty_ddr1=!m0_skid_valid_r&&m0_wr_empty;
    wire m1_source_empty_ddr1=!m1_skid_valid_r&&m1_wr_empty;
    wire a0_source_empty_core,a1_source_empty_core;
    wire m0_source_empty_core,m1_source_empty_core;
    // The mode controller changes both enables only after the core-domain
    // quiescence contract has drained every producer, FIFO and local issuer.
    // They nevertheless originate in core_clk and must not directly control
    // the 200-MHz admission/issue state.  Synchronize the committed level once
    // at each DDR boundary; every local consumer below uses only this copy.
    // The synchronizer latency is paid only on a quiescent mode transition,
    // never between steady-state requests, so normal request II is unchanged.
    wire ddr0_enable_sync,ddr1_enable_sync;
    wire ddr0_run=ddr0_enable_sync||maintenance_active_ddr0;
    wire ddr1_run=ddr1_enable_sync||maintenance_active_ddr1;
    wire sources_closed_level=maintenance_req_r&&attn_source_quiescent&&
        mlp_source_quiescent;
    wire sources_closed_seen=sources_closed_level&&
        (source_closed_stable_r==3'b111);
    wire clear_drain_level=maintenance_req_r&&maintenance_ack0_core&&
        maintenance_ack1_core&&core_quiescent;
    wire clear_drain_seen=clear_drain_level&&(clear_stable_r==3'b111);
    wire unsafe_clear=core_clear&&global_freeze_core;
    assign maintenance_pause_sources=maintenance_req_r;
    assign maintenance_drain_active=maintenance_req_r;
    assign maintenance_soft_clear_pulse=maintenance_soft_clear_pulse_r;
    assign grant_attn=!global_freeze_core&&a_eligible;
    assign grant_mlp=!global_freeze_core&&m_eligible;
    assign core_quiescent=!fifo_rst_core&&!global_freeze_core&&
        a0_source_empty_core&&m0_source_empty_core&&
        a1_source_empty_core&&m1_source_empty_core&&
        !a0_q_valid&&!m0_q_valid&&!a1_q_valid&&!m1_q_valid&&
        !second0_valid_r&&!second1_valid_r&&
        o0_wr_empty&&o1_wr_empty&&local0_q_core&&local1_q_core;
    assign error=global_freeze_core;

    assign a0_arready=ddr0_run&&!fifo_rst_ddr0&&!local0_error&&
        !global_freeze_ddr0&&!maintenance_stop_ddr0&&!a0_skid_valid_r;
    assign a1_arready=ddr0_run&&!fifo_rst_ddr0&&!local0_error&&
        !global_freeze_ddr0&&!maintenance_stop_ddr0&&!a1_skid_valid_r;
    assign m0_arready=ddr1_run&&!fifo_rst_ddr1&&!local1_error&&
        !global_freeze_ddr1&&!maintenance_stop_ddr1&&!m0_skid_valid_r;
    assign m1_arready=ddr1_run&&!fifo_rst_ddr1&&!local1_error&&
        !global_freeze_ddr1&&!maintenance_stop_ddr1&&!m1_skid_valid_r;
    assign a0_q_ready=grant_attn;assign a1_q_ready=grant_attn;
    assign m0_q_ready=grant_mlp;assign m1_q_ready=grant_mlp;

    // Descriptor payloads are resetless; skid valid bits below own their
    // visibility.  Keeping data in a separate process removes wide reset
    // control sets from both 200-MHz source domains.
    always @(posedge ddr0_clk)begin
      if(a0_arvalid&&a0_arready)
        a0_skid_data_r<={a0_src_seq_r,a0_araddr,a0_arlen,a0_arsize,a0_arburst};
      if(a1_arvalid&&a1_arready)
        a1_skid_data_r<={a1_src_seq_r,a1_araddr,a1_arlen,a1_arsize,a1_arburst};
    end
    always @(posedge ddr1_clk)begin
      if(m0_arvalid&&m0_arready)
        m0_skid_data_r<={m0_src_seq_r,m0_araddr,m0_arlen,m0_arsize,m0_arburst};
      if(m1_arvalid&&m1_arready)
        m1_skid_data_r<={m1_src_seq_r,m1_araddr,m1_arlen,m1_arsize,m1_arburst};
    end

    hap_v4_async_fifo #(.WIDTH(INGRESS_W),.DEPTH(FIFO_DEPTH))u_a0_in(
      .wr_rst(fifo_rst_ddr0),.rd_rst(fifo_rst_core),.wr_clk(ddr0_clk),
      .wr_valid(a0_skid_valid_r&&!local0_error&&!global_freeze_ddr0),
      .wr_ready(a0_wr_ready),.wr_data(a0_skid_data_r),.rd_clk(core_clk),
      .rd_valid(a0_q_valid),.rd_ready(a0_q_ready),.rd_data(a0_q),
      .wr_empty(a0_wr_empty),.error(a0_in_error));
    hap_v4_async_fifo #(.WIDTH(INGRESS_W),.DEPTH(FIFO_DEPTH))u_m0_in(
      .wr_rst(fifo_rst_ddr1),.rd_rst(fifo_rst_core),.wr_clk(ddr1_clk),
      .wr_valid(m0_skid_valid_r&&!local1_error&&!global_freeze_ddr1),
      .wr_ready(m0_wr_ready),.wr_data(m0_skid_data_r),.rd_clk(core_clk),
      .rd_valid(m0_q_valid),.rd_ready(m0_q_ready),.rd_data(m0_q),
      .wr_empty(m0_wr_empty),.error(m0_in_error));
    hap_v4_async_fifo #(.WIDTH(INGRESS_W),.DEPTH(FIFO_DEPTH))u_a1_in(
      .wr_rst(fifo_rst_ddr0),.rd_rst(fifo_rst_core),.wr_clk(ddr0_clk),
      .wr_valid(a1_skid_valid_r&&!local0_error&&!global_freeze_ddr0),
      .wr_ready(a1_wr_ready),.wr_data(a1_skid_data_r),.rd_clk(core_clk),
      .rd_valid(a1_q_valid),.rd_ready(a1_q_ready),.rd_data(a1_q),
      .wr_empty(a1_wr_empty),.error(a1_in_error));
    hap_v4_async_fifo #(.WIDTH(INGRESS_W),.DEPTH(FIFO_DEPTH))u_m1_in(
      .wr_rst(fifo_rst_ddr1),.rd_rst(fifo_rst_core),.wr_clk(ddr1_clk),
      .wr_valid(m1_skid_valid_r&&!local1_error&&!global_freeze_ddr1),
      .wr_ready(m1_wr_ready),.wr_data(m1_skid_data_r),.rd_clk(core_clk),
      .rd_valid(m1_q_valid),.rd_ready(m1_q_ready),.rd_data(m1_q),
      .wr_empty(m1_wr_empty),.error(m1_in_error));
    hap_v4_async_fifo #(.WIDTH(EGRESS_W),.DEPTH(FIFO_DEPTH))u_o0(
      .wr_rst(fifo_rst_core),.rd_rst(fifo_rst_ddr0),.wr_clk(core_clk),
      .wr_valid(o0_push),
      .wr_ready(o0_wr_ready),.wr_data(o0_in),.rd_clk(ddr0_clk),
      .rd_valid(o0_q_valid),.rd_ready(o0_q_ready),.rd_data(o0_q),
      .wr_empty(o0_wr_empty),.error(o0_error));
    hap_v4_async_fifo #(.WIDTH(EGRESS_W),.DEPTH(FIFO_DEPTH))u_o1(
      .wr_rst(fifo_rst_core),.rd_rst(fifo_rst_ddr1),.wr_clk(core_clk),
      .wr_valid(o1_push),
      .wr_ready(o1_wr_ready),.wr_data(o1_in),.rd_clk(ddr1_clk),
      .rd_valid(o1_q_valid),.rd_ready(o1_q_ready),.rd_data(o1_q),
      .wr_empty(o1_wr_empty),.error(o1_error));

    always @(posedge core_clk or negedge core_rst_n)begin
      if(!core_rst_n||hard_rst_core)begin
        reset_shift_r<=5'b11111;fifo_reset_request_r<=1;
        maintenance_soft_clear_pulse_r<=0;
      end else begin
        maintenance_soft_clear_pulse_r<=0;
        fifo_reset_request_r<=|reset_shift_r;
        if(|reset_shift_r)reset_shift_r<={1'b0,reset_shift_r[4:1]};
        else if(clear_drain_seen)begin
          reset_shift_r<=5'b11111;fifo_reset_request_r<=1;
          maintenance_soft_clear_pulse_r<=1;
        end
      end
    end
    always @(posedge core_clk or negedge core_rst_n)begin
      if(!core_rst_n)begin maintenance_req_r<=0;clear_armed_r<=1;end
      else if(hard_rst_core)begin maintenance_req_r<=0;clear_armed_r<=1;end
      else begin
        if(!core_clear)clear_armed_r<=1;
        if(|reset_shift_r)maintenance_req_r<=0;
        else if(core_clear&&clear_armed_r&&!global_freeze_core)begin
          maintenance_req_r<=1;clear_armed_r<=0;end
      end
    end
    always @(posedge core_clk or negedge core_rst_n)begin
      if(!core_rst_n)begin
        source_closed_stable_r<=0;maintenance_stop_req_r<=0;
      end else if(hard_rst_core||fifo_rst_core||!maintenance_req_r)begin
        source_closed_stable_r<=0;maintenance_stop_req_r<=0;
      end else begin
        if(!sources_closed_level)source_closed_stable_r<=0;
        else if(!(&source_closed_stable_r))source_closed_stable_r<=
          {source_closed_stable_r[1:0],1'b1};
        if(sources_closed_seen)maintenance_stop_req_r<=1;
      end
    end
    always @(posedge core_clk or negedge core_rst_n)begin
      if(!core_rst_n)clear_stable_r<=0;
      else if(hard_rst_core||!clear_drain_level)clear_stable_r<=0;
      else if(!(&clear_stable_r))clear_stable_r<=
        {clear_stable_r[1:0],1'b1};
    end
    always @(posedge ddr0_clk or negedge ddr0_rst_n)begin
      if(!ddr0_rst_n)begin a0_src_seq_r<=0;a1_src_seq_r<=0;
        a0_skid_valid_r<=0;a1_skid_valid_r<=0;
        maintenance_violation0_r<=0;end
      else if(hard_rst_ddr0)begin a0_src_seq_r<=0;a1_src_seq_r<=0;
        a0_skid_valid_r<=0;a1_skid_valid_r<=0;
        maintenance_violation0_r<=0;end
      else if(fifo_rst_ddr0&&!hard_rst_ddr0)begin
        a0_src_seq_r<=0;a1_src_seq_r<=0;
        a0_skid_valid_r<=0;a1_skid_valid_r<=0;
      end
      else begin
        if(maintenance_stop_ddr0&&(a0_arvalid||a1_arvalid))
          maintenance_violation0_r<=1;
        if(a0_skid_push)a0_skid_valid_r<=0;
        if(a1_skid_push)a1_skid_valid_r<=0;
        if(a0_arvalid&&a0_arready)begin
          a0_skid_valid_r<=1;
          a0_src_seq_r<=a0_src_seq_r+1'b1;end
        if(a1_arvalid&&a1_arready)begin
          a1_skid_valid_r<=1;
          a1_src_seq_r<=a1_src_seq_r+1'b1;end
      end
    end
    always @(posedge ddr1_clk or negedge ddr1_rst_n)begin
      if(!ddr1_rst_n)begin m0_src_seq_r<=0;m1_src_seq_r<=0;
        m0_skid_valid_r<=0;m1_skid_valid_r<=0;
        maintenance_violation1_r<=0;end
      else if(hard_rst_ddr1)begin m0_src_seq_r<=0;m1_src_seq_r<=0;
        m0_skid_valid_r<=0;m1_skid_valid_r<=0;
        maintenance_violation1_r<=0;end
      else if(fifo_rst_ddr1&&!hard_rst_ddr1)begin
        m0_src_seq_r<=0;m1_src_seq_r<=0;
        m0_skid_valid_r<=0;m1_skid_valid_r<=0;
      end
      else begin
        if(maintenance_stop_ddr1&&(m0_arvalid||m1_arvalid))
          maintenance_violation1_r<=1;
        if(m0_skid_push)m0_skid_valid_r<=0;
        if(m1_skid_push)m1_skid_valid_r<=0;
        if(m0_arvalid&&m0_arready)begin
          m0_skid_valid_r<=1;
          m0_src_seq_r<=m0_src_seq_r+1'b1;end
        if(m1_arvalid&&m1_arready)begin
          m1_skid_valid_r<=1;
          m1_src_seq_r<=m1_src_seq_r+1'b1;end
      end
    end
    always @(posedge core_clk)begin
      if(grant_attn)second0_r<=a1_q[DESC_W-1:0];
      if(grant_mlp)second1_r<=m1_q[DESC_W-1:0];
    end
    always @(posedge core_clk or negedge core_rst_n)begin
      if(!core_rst_n)begin
        sequence0_r<=0;sequence1_r<=0;
        second0_valid_r<=0;second1_valid_r<=0;core_error_r<=0;
        accepted_attn_bursts<=0;accepted_mlp_bursts<=0;both_eligible_cycles<=0;
      end else if(hard_rst_core)begin
        sequence0_r<=0;sequence1_r<=0;
        second0_valid_r<=0;second1_valid_r<=0;core_error_r<=0;
        accepted_attn_bursts<=0;accepted_mlp_bursts<=0;both_eligible_cycles<=0;
      end else if(fifo_rst_core)begin
        sequence0_r<=0;sequence1_r<=0;
        second0_valid_r<=0;second1_valid_r<=0;
        accepted_attn_bursts<=0;accepted_mlp_bursts<=0;both_eligible_cycles<=0;
      end else begin
        if(unsafe_clear||local0_error_core||local1_error_core||
           a0_in_error||a1_in_error||m0_in_error||m1_in_error||
           o0_error_core||o1_error_core||maintenance_violation0_core||
           maintenance_violation1_core)core_error_r<=1;
        if((a_pair_present&&!a_pair_match)||(m_pair_present&&!m_pair_match))
          core_error_r<=1;
        if(a_eligible&&m_eligible)both_eligible_cycles<=both_eligible_cycles+1'b1;
        if(o0_push)sequence0_r<=sequence0_r+1'b1;
        if(o1_push)sequence1_r<=sequence1_r+1'b1;
        if(grant_attn)begin
          second0_valid_r<=1;
          accepted_attn_bursts<=accepted_attn_bursts+1'b1;
        end else if(o0_push)second0_valid_r<=0;
        if(grant_mlp)begin
          second1_valid_r<=1;
          accepted_mlp_bursts<=accepted_mlp_bursts+1'b1;
        end else if(o1_push)second1_valid_r<=0;
      end
    end

    hap_axi512_ordered_local_issue #(.AXI_ADDR_W(AXI_ADDR_W),.SEQ_W(SEQ_W),
      .TAG_DEPTH(TAG_DEPTH))u_local0(
      .clk(ddr0_clk),.rst_n(ddr0_rst_n),.hard_reset(hard_rst_ddr0),
      .soft_reset(fifo_rst_ddr0&&!hard_rst_ddr0),.enable(ddr0_run),
      .freeze(global_freeze_ddr0),
      .desc_valid(o0_q_valid),.desc_ready(o0_q_ready),.desc_data(o0_q),
      .m_axi_arvalid(p0_arvalid),.m_axi_arready(p0_arready),.m_axi_araddr(p0_araddr),
      .m_axi_arlen(p0_arlen),.m_axi_arsize(p0_arsize),.m_axi_arburst(p0_arburst),
      .m_axi_rvalid(p0_rvalid),.m_axi_rready(p0_rready),.m_axi_rdata(p0_rdata),
      .m_axi_rresp(p0_rresp),.m_axi_rlast(p0_rlast),
      .attn_rvalid(a0_rvalid),.attn_rready(a0_rready),.attn_rdata(a0_rdata),
      .attn_rresp(a0_rresp),.attn_rlast(a0_rlast),.mlp_rvalid(a1_rvalid),
      .mlp_rready(a1_rready),.mlp_rdata(a1_rdata),.mlp_rresp(a1_rresp),
      .mlp_rlast(a1_rlast),.quiescent(local0_quiescent),
      .protocol_error(local0_error),.physical_ar_count(),.physical_r_count(),
      .attn_burst_count(),.mlp_burst_count(),.hol_cycle_count(p0_hol_cycles),
      .tag_high_watermark(p0_tag_high_watermark));
    hap_axi512_ordered_local_issue #(.AXI_ADDR_W(AXI_ADDR_W),.SEQ_W(SEQ_W),
      .TAG_DEPTH(TAG_DEPTH))u_local1(
      .clk(ddr1_clk),.rst_n(ddr1_rst_n),.hard_reset(hard_rst_ddr1),
      .soft_reset(fifo_rst_ddr1&&!hard_rst_ddr1),.enable(ddr1_run),
      .freeze(global_freeze_ddr1),
      .desc_valid(o1_q_valid),.desc_ready(o1_q_ready),.desc_data(o1_q),
      .m_axi_arvalid(p1_arvalid),.m_axi_arready(p1_arready),.m_axi_araddr(p1_araddr),
      .m_axi_arlen(p1_arlen),.m_axi_arsize(p1_arsize),.m_axi_arburst(p1_arburst),
      .m_axi_rvalid(p1_rvalid),.m_axi_rready(p1_rready),.m_axi_rdata(p1_rdata),
      .m_axi_rresp(p1_rresp),.m_axi_rlast(p1_rlast),
      .attn_rvalid(m0_rvalid),.attn_rready(m0_rready),.attn_rdata(m0_rdata),
      .attn_rresp(m0_rresp),.attn_rlast(m0_rlast),.mlp_rvalid(m1_rvalid),
      .mlp_rready(m1_rready),.mlp_rdata(m1_rdata),.mlp_rresp(m1_rresp),
      .mlp_rlast(m1_rlast),.quiescent(local1_quiescent),
      .protocol_error(local1_error),.physical_ar_count(),.physical_r_count(),
      .attn_burst_count(),.mlp_burst_count(),.hol_cycle_count(p1_hol_cycles),
      .tag_high_watermark(p1_tag_high_watermark));

    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_q0_cdc(.src_clk(ddr0_clk),.src_in(local0_quiescent),
      .dest_clk(core_clk),.dest_out(local0_q_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_q1_cdc(.src_clk(ddr1_clk),.src_in(local1_quiescent),
      .dest_clk(core_clk),.dest_out(local1_q_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_e0_cdc(.src_clk(ddr0_clk),.src_in(local0_error),
      .dest_clk(core_clk),.dest_out(local0_error_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_e1_cdc(.src_clk(ddr1_clk),.src_in(local1_error),
      .dest_clk(core_clk),.dest_out(local1_error_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_oe0_cdc(.src_clk(ddr0_clk),.src_in(o0_error),
      .dest_clk(core_clk),.dest_out(o0_error_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_oe1_cdc(.src_clk(ddr1_clk),.src_in(o1_error),
      .dest_clk(core_clk),.dest_out(o1_error_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_mv0_cdc(.src_clk(ddr0_clk),
      .src_in(maintenance_violation0_r),.dest_clk(core_clk),
      .dest_out(maintenance_violation0_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_mv1_cdc(.src_clk(ddr1_clk),
      .src_in(maintenance_violation1_r),.dest_clk(core_clk),
      .dest_out(maintenance_violation1_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_freeze0_cdc(.src_clk(core_clk),.src_in(global_freeze_core),
      .dest_clk(ddr0_clk),.dest_out(global_freeze_ddr0));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_freeze1_cdc(.src_clk(core_clk),.src_in(global_freeze_core),
      .dest_clk(ddr1_clk),.dest_out(global_freeze_ddr1));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_maint_stop0_cdc(.src_clk(core_clk),
      .src_in(maintenance_stop_req_r),.dest_clk(ddr0_clk),
      .dest_out(maintenance_stop_ddr0));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_maint_stop1_cdc(.src_clk(core_clk),
      .src_in(maintenance_stop_req_r),.dest_clk(ddr1_clk),
      .dest_out(maintenance_stop_ddr1));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_maint_active0_cdc(.src_clk(core_clk),
      .src_in(maintenance_req_r),.dest_clk(ddr0_clk),
      .dest_out(maintenance_active_ddr0));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_maint_active1_cdc(.src_clk(core_clk),
      .src_in(maintenance_req_r),.dest_clk(ddr1_clk),
      .dest_out(maintenance_active_ddr1));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_enable0_cdc(.src_clk(core_clk),
      .src_in(ddr0_enable),.dest_clk(ddr0_clk),.dest_out(ddr0_enable_sync));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_enable1_cdc(.src_clk(core_clk),
      .src_in(ddr1_enable),.dest_clk(ddr1_clk),.dest_out(ddr1_enable_sync));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_maint_ack0_cdc(.src_clk(ddr0_clk),
      .src_in(maintenance_stop_ddr0),.dest_clk(core_clk),
      .dest_out(maintenance_ack0_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_maint_ack1_cdc(.src_clk(ddr1_clk),
      .src_in(maintenance_stop_ddr1),.dest_clk(core_clk),
      .dest_out(maintenance_ack1_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_a0_empty_cdc(.src_clk(ddr0_clk),
      .src_in(a0_source_empty_ddr0),.dest_clk(core_clk),
      .dest_out(a0_source_empty_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_a1_empty_cdc(.src_clk(ddr0_clk),
      .src_in(a1_source_empty_ddr0),.dest_clk(core_clk),
      .dest_out(a1_source_empty_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_m0_empty_cdc(.src_clk(ddr1_clk),
      .src_in(m0_source_empty_ddr1),.dest_clk(core_clk),
      .dest_out(m0_source_empty_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_m1_empty_cdc(.src_clk(ddr1_clk),
      .src_in(m1_source_empty_ddr1),.dest_clk(core_clk),
      .dest_out(m1_source_empty_core));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_reset_core(.src_rst(fifo_reset_source),
      .dest_clk(core_clk),.dest_rst(fifo_rst_core));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_reset_ddr0(.src_rst(fifo_reset_source),
      .dest_clk(ddr0_clk),.dest_rst(fifo_rst_ddr0));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_reset_ddr1(.src_rst(fifo_reset_source),
      .dest_clk(ddr1_clk),.dest_rst(fifo_rst_ddr1));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_ddr0_req_core(.src_rst(ddr0_hard_req_r),
      .dest_clk(core_clk),.dest_rst(ddr0_req_core));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_ddr1_req_core(.src_rst(ddr1_hard_req_r),
      .dest_clk(core_clk),.dest_rst(ddr1_req_core));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_core_req_ddr0(.src_rst(core_hard_req_r),
      .dest_clk(ddr0_clk),.dest_rst(core_req_ddr0));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_ddr1_req_ddr0(.src_rst(ddr1_hard_req_r),
      .dest_clk(ddr0_clk),.dest_rst(ddr1_req_ddr0));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_core_req_ddr1(.src_rst(core_hard_req_r),
      .dest_clk(ddr1_clk),.dest_rst(core_req_ddr1));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_ddr0_req_ddr1(.src_rst(ddr0_hard_req_r),
      .dest_clk(ddr1_clk),.dest_rst(ddr0_req_ddr1));

    initial begin
      if(FIFO_DEPTH<16||TAG_DEPTH<16)
        $error("Dedicated DDR FIFO/tag depths must be >=16");
    end
endmodule
