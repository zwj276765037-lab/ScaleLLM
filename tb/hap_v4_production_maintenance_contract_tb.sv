`timescale 1ns/1ps

// Integration-contract model for production admission around the signed-off
// paired DDR leaf.  Small finite producers represent the existing fixed-size
// Attention and MLP reader commands: pause blocks a new top-level command but
// never retracts an ARVALID already presented by an accepted command.
module hap_v4_contract_producer #(
    parameter integer BURSTS=4,
    parameter [31:0] BASE0=32'h1000,
    parameter [31:0] BASE1=32'h2000
) (
    input wire clk,input wire rst_n,input wire start,input wire pause,
    output wire busy,output wire source_quiescent,
    output wire a0_arvalid,input wire a0_arready,output wire[31:0]a0_araddr,
    output wire[7:0]a0_arlen,output wire[2:0]a0_arsize,output wire[1:0]a0_arburst,
    output wire a1_arvalid,input wire a1_arready,output wire[31:0]a1_araddr,
    output wire[7:0]a1_arlen,output wire[2:0]a1_arsize,output wire[1:0]a1_arburst,
    input wire a0_rvalid,output wire a0_rready,input wire a0_rlast,
    input wire a1_rvalid,output wire a1_rready,input wire a1_rlast
);
    reg active_r,v0_r,v1_r;reg[7:0]issued0_r,issued1_r,done0_r,done1_r;
    assign busy=active_r;
    assign source_quiescent=pause&&!active_r&&!v0_r&&!v1_r;
    assign a0_arvalid=v0_r;assign a1_arvalid=v1_r;
    assign a0_araddr=BASE0+({24'd0,issued0_r}<<10);
    assign a1_araddr=BASE1+({24'd0,issued1_r}<<10);
    assign a0_arlen=8'd15;assign a1_arlen=8'd15;
    assign a0_arsize=3'd6;assign a1_arsize=3'd6;
    assign a0_arburst=2'b01;assign a1_arburst=2'b01;
    assign a0_rready=1'b1;assign a1_rready=1'b1;
    always @(posedge clk or negedge rst_n)begin
      if(!rst_n)begin active_r<=0;v0_r<=0;v1_r<=0;issued0_r<=0;
        issued1_r<=0;done0_r<=0;done1_r<=0;end
      else begin
        if(start&&!pause&&!active_r)begin active_r<=1;v0_r<=1;v1_r<=1;
          issued0_r<=0;issued1_r<=0;done0_r<=0;done1_r<=0;end
        if(v0_r&&a0_arready)begin
          if(issued0_r+1==BURSTS)v0_r<=0;
          issued0_r<=issued0_r+1'b1;end
        if(v1_r&&a1_arready)begin
          if(issued1_r+1==BURSTS)v1_r<=0;
          issued1_r<=issued1_r+1'b1;end
        if(a0_rvalid&&a0_rready&&a0_rlast)done0_r<=done0_r+1'b1;
        if(a1_rvalid&&a1_rready&&a1_rlast)done1_r<=done1_r+1'b1;
        if(active_r&&
          (done0_r+(a0_rvalid&&a0_rready&&a0_rlast)==BURSTS)&&
          (done1_r+(a1_rvalid&&a1_rready&&a1_rlast)==BURSTS))active_r<=0;
      end
    end
endmodule

module hap_v4_production_maintenance_contract_tb;
    reg core_clk=0,d0_clk=0,d1_clk=0,core_rst_n=0,d0_rst_n=0,d1_rst_n=0;
    // Contract-model producers use a common clock so their finite completion
    // state is deterministic; independent asynchronous behavior is already
    // covered by the paired leaf's 158/59/275/55 regressions.
    always #3.333 core_clk=~core_clk;
    always @* begin d0_clk=core_clk;d1_clk=core_clk;end
    reg core_clear=0,start_a=0,start_m=0;wire pause,drain,soft_clear;
    wire aq,mq,ab,mb,leaf_q,error;integer checks=0,clear_count=0;
    wire a0v,a0r,a1v,a1r,m0v,m0r,m1v,m1r;
    wire[31:0]a0a,a1a,m0a,m1a;wire[7:0]a0l,a1l,m0l,m1l;
    wire[2:0]a0s,a1s,m0s,m1s;wire[1:0]a0b,a1b,m0b,m1b;
    wire ar0v,ar0r,ar1v,ar1r;wire[31:0]ar0a,ar1a;wire[7:0]ar0l,ar1l;
    wire[2:0]ar0s,ar1s;wire[1:0]ar0b,ar1b;
    reg rv0=0,rv1=0;wire rr0,rr1;reg[511:0]rd0=0,rd1=0;
    reg[1:0]rp0=0,rp1=0;reg rl0=0,rl1=0;integer beat0=0,beat1=0;
    reg[31:0]q0_addr[0:31],q1_addr[0:31];reg[7:0]q0_len[0:31],q1_len[0:31];
    integer q0_wr=0,q0_rd=0,q1_wr=0,q1_rd=0,d0_cycle=0,d1_cycle=0;
    wire av0,am0,av1,am1,arl0,mrl0,arl1,mrl1;
    wire car0,cmr0,car1,cmr1;wire[511:0]dummy0,dummy1;
    reg saw_pause_busy=0,saw_held_valid=0;

    hap_v4_contract_producer #(.BURSTS(3),.BASE0(32'h10000),.BASE1(32'h20000)) pa(
      .clk(core_clk),.rst_n(core_rst_n),.start(start_a),.pause(pause),.busy(ab),
      .source_quiescent(aq),.a0_arvalid(a0v),.a0_arready(a0r),.a0_araddr(a0a),
      .a0_arlen(a0l),.a0_arsize(a0s),.a0_arburst(a0b),.a1_arvalid(a1v),
      .a1_arready(a1r),.a1_araddr(a1a),.a1_arlen(a1l),.a1_arsize(a1s),
      .a1_arburst(a1b),.a0_rvalid(av0),.a0_rready(car0),.a0_rlast(arl0),
      .a1_rvalid(av1),.a1_rready(car1),.a1_rlast(arl1));
    hap_v4_contract_producer #(.BURSTS(6),.BASE0(32'h30000),.BASE1(32'h40000)) pm(
      .clk(core_clk),.rst_n(core_rst_n),.start(start_m),.pause(pause),.busy(mb),
      .source_quiescent(mq),.a0_arvalid(m0v),.a0_arready(m0r),.a0_araddr(m0a),
      .a0_arlen(m0l),.a0_arsize(m0s),.a0_arburst(m0b),.a1_arvalid(m1v),
      .a1_arready(m1r),.a1_araddr(m1a),.a1_arlen(m1l),.a1_arsize(m1s),
      .a1_arburst(m1b),.a0_rvalid(am0),.a0_rready(cmr0),.a0_rlast(mrl0),
      .a1_rvalid(am1),.a1_rready(cmr1),.a1_rlast(mrl1));

    hap_axi512_paired_2client_read_wrr dut(
      .core_clk(core_clk),.core_rst_n(core_rst_n),.core_clear(core_clear),
      .core_enable(1'b1),.attn_source_quiescent(aq),.mlp_source_quiescent(mq),
      .maintenance_pause_sources(pause),.maintenance_drain_active(drain),
      .maintenance_soft_clear_pulse(soft_clear),.ddr0_clk(d0_clk),
      .ddr0_rst_n(d0_rst_n),.ddr0_enable(1'b1),.ddr1_clk(d1_clk),
      .ddr1_rst_n(d1_rst_n),.ddr1_enable(1'b1),
      .a0_arvalid(a0v),.a0_arready(a0r),.a0_araddr(a0a),.a0_arlen(a0l),
      .a0_arsize(a0s),.a0_arburst(a0b),.a0_rvalid(av0),.a0_rready(car0),
      .a0_rdata(dummy0),.a0_rresp(),.a0_rlast(arl0),
      .m0_arvalid(m0v),.m0_arready(m0r),.m0_araddr(m0a),.m0_arlen(m0l),
      .m0_arsize(m0s),.m0_arburst(m0b),.m0_rvalid(am0),.m0_rready(cmr0),
      .m0_rdata(),.m0_rresp(),.m0_rlast(mrl0),
      .a1_arvalid(a1v),.a1_arready(a1r),.a1_araddr(a1a),.a1_arlen(a1l),
      .a1_arsize(a1s),.a1_arburst(a1b),.a1_rvalid(av1),.a1_rready(car1),
      .a1_rdata(dummy1),.a1_rresp(),.a1_rlast(arl1),
      .m1_arvalid(m1v),.m1_arready(m1r),.m1_araddr(m1a),.m1_arlen(m1l),
      .m1_arsize(m1s),.m1_arburst(m1b),.m1_rvalid(am1),.m1_rready(cmr1),
      .m1_rdata(),.m1_rresp(),.m1_rlast(mrl1),
      .p0_arvalid(ar0v),.p0_arready(ar0r),.p0_araddr(ar0a),.p0_arlen(ar0l),
      .p0_arsize(ar0s),.p0_arburst(ar0b),.p0_rvalid(rv0),.p0_rready(rr0),
      .p0_rdata(rd0),.p0_rresp(rp0),.p0_rlast(rl0),
      .p1_arvalid(ar1v),.p1_arready(ar1r),.p1_araddr(ar1a),.p1_arlen(ar1l),
      .p1_arsize(ar1s),.p1_arburst(ar1b),.p1_rvalid(rv1),.p1_rready(rr1),
      .p1_rdata(rd1),.p1_rresp(rp1),.p1_rlast(rl1),
      .core_quiescent(leaf_q),.error(error),.accepted_attn_bursts(),
      .accepted_mlp_bursts(),.both_eligible_cycles(),.p0_hol_cycles(),
      .p1_hol_cycles(),.p0_tag_high_watermark(),.p1_tag_high_watermark());
    always @(posedge core_clk)begin
      if(soft_clear)clear_count<=clear_count+1;
      if(pause&&(ab||mb))saw_pause_busy<=1;
      if(pause&&(a0v||a1v||m0v||m1v))saw_held_valid<=1;
    end
    always @(posedge d0_clk)begin
      d0_cycle<=d0_cycle+1;
      if(ar0v&&ar0r)begin q0_addr[q0_wr]<=ar0a;q0_len[q0_wr]<=ar0l;
        q0_wr<=q0_wr+1;end
      if(!rv0&&q0_rd<q0_wr&&(d0_cycle%3)!=0)begin
        rv0<=1;beat0<=0;rd0<={16{q0_addr[q0_rd]}};rl0<=q0_len[q0_rd]==0;
      end else if(rv0&&rr0)begin
        if(rl0)begin rv0<=0;rl0<=0;q0_rd<=q0_rd+1;beat0<=0;end
        else begin beat0<=beat0+1;rd0<={16{q0_addr[q0_rd]}};
          rl0<=beat0+1==q0_len[q0_rd];end end
    end
    assign ar0r=(d0_cycle%5)!=1;
    always @(posedge d1_clk)begin
      d1_cycle<=d1_cycle+1;
      if(ar1v&&ar1r)begin q1_addr[q1_wr]<=ar1a;q1_len[q1_wr]<=ar1l;
        q1_wr<=q1_wr+1;end
      if(!rv1&&q1_rd<q1_wr&&(d1_cycle%4)!=0)begin
        rv1<=1;beat1<=0;rd1<={16{q1_addr[q1_rd]}};rl1<=q1_len[q1_rd]==0;
      end else if(rv1&&rr1)begin
        if(rl1)begin rv1<=0;rl1<=0;q1_rd<=q1_rd+1;beat1<=0;end
        else begin beat1<=beat1+1;rd1<={16{q1_addr[q1_rd]}};
          rl1<=beat1+1==q1_len[q1_rd];end end
    end
    // Deliberately asymmetric AR acceptance.
    assign ar1r=(d1_cycle%7)!=2;
    task tick;begin @(posedge core_clk);#1;end endtask
    task check(input c,input[8*96-1:0]m);begin checks=checks+1;
      if(!c)begin $display("FAIL %0s",m);$fatal(1);end end endtask
    initial begin
      repeat(6)tick();core_rst_n=1;d0_rst_n=1;d1_rst_n=1;
      repeat(20)tick();start_a=1;start_m=1;tick();start_a=0;start_m=0;
      repeat(8)tick();core_clear=1;
      wait(pause);check(ab||mb,"maintenance did not overlap active command");
      repeat(4)tick();core_clear=0;
      wait(soft_clear);tick();check(clear_count==1,"soft clear count");
      check(saw_pause_busy,"pause never observed busy producer");
      check(saw_held_valid,"pause retracted all in-flight ARVALID");
      check(!error,"paired leaf error");check(!ab&&!mb,"producer not drained");
      repeat(12)tick();check(clear_count==1,"extra soft clear pulse");
      $display("PASS hap_v4_production_maintenance_contract checks=%0d",checks);
      $finish;
    end
    initial begin #2000000;
      $display("DBG pause=%b drain=%b clear=%b aq=%b mq=%b ab=%b mb=%b leafq=%b err=%b q=%0d/%0d %0d/%0d issuedA=%0d/%0d doneA=%0d/%0d issuedM=%0d/%0d doneM=%0d/%0d",
        pause,drain,soft_clear,aq,mq,ab,mb,leaf_q,error,q0_rd,q0_wr,q1_rd,q1_wr,
        pa.issued0_r,pa.issued1_r,pa.done0_r,pa.done1_r,
        pm.issued0_r,pm.issued1_r,pm.done0_r,pm.done1_r);
      $fatal(1,"timeout");end
endmodule
