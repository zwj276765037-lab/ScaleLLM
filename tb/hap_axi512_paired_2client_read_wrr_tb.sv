`timescale 1ns / 1ps

module hap_axi512_paired_2client_read_wrr_tb;
  reg core_clk=0,ddr0_clk=0,ddr1_clk=0;
  reg core_rst_n=0,ddr0_rst_n=0,ddr1_rst_n=0;
  reg core_clear=0,core_enable=1,ddr0_enable=1,ddr1_enable=1;
  always #3.333 core_clk=~core_clk;
  always #1.667 ddr0_clk=~ddr0_clk;
  always #1.923 ddr1_clk=~ddr1_clk;

  reg a0_arvalid=0,m0_arvalid=0,a1_arvalid=0,m1_arvalid=0;
  wire a0_arready,m0_arready,a1_arready,m1_arready;
  reg[31:0]a0_araddr=32'hA000_0000,m0_araddr=32'hB000_0000;
  reg[31:0]a1_araddr=32'hA100_0000,m1_araddr=32'hB100_0000;
  wire a0_rvalid,m0_rvalid,a1_rvalid,m1_rvalid;
  reg a0_rready=0,m0_rready=0,a1_rready=0,m1_rready=0;
  wire[511:0]a0_rdata,m0_rdata,a1_rdata,m1_rdata;
  wire[1:0]a0_rresp,m0_rresp,a1_rresp,m1_rresp;
  wire a0_rlast,m0_rlast,a1_rlast,m1_rlast;
  wire p0_arvalid,p1_arvalid;reg p0_arready=0,p1_arready=0;
  wire[31:0]p0_araddr,p1_araddr;wire[7:0]p0_arlen,p1_arlen;
  wire[2:0]p0_arsize,p1_arsize;wire[1:0]p0_arburst,p1_arburst;
  reg p0_rvalid=0,p1_rvalid=0;wire p0_rready,p1_rready;
  reg[511:0]p0_rdata=0,p1_rdata=0;reg[1:0]p0_rresp=0,p1_rresp=0;
  reg p0_rlast=0,p1_rlast=0;
  wire core_quiescent,error;
  wire[31:0]accepted_attn_bursts,accepted_mlp_bursts,both_eligible_cycles;
  wire[31:0]p0_hol_cycles,p1_hol_cycles,p0_tag_high_watermark,p1_tag_high_watermark;

  integer target_attn=8,target_mlp=16,failures=0;
  integer a0_sent=0,a1_sent=0,m0_sent=0,m1_sent=0;
  integer a0_beats=0,a1_beats=0,m0_beats=0,m1_beats=0;
  integer ddr0_cycle=0,ddr1_cycle=0,checks=0;
  integer q0_wr=0,q0_rd=0,q1_wr=0,q1_rd=0;
  reg[31:0]q0_addr[0:63],q1_addr[0:63];
  reg[7:0]q0_len[0:63],q1_len[0:63];
  reg q0_owner_log[0:63],q1_owner_log[0:63];
  integer p0_beat=0,p1_beat=0;
  reg inject_bad_p0=0;
  reg p0_both_rvalid_seen=0,p1_both_rvalid_seen=0;
  reg[31:0]p0_stall_addr,p1_stall_addr;reg[7:0]p0_stall_len,p1_stall_len;
  reg p0_was_stalled=0,p1_was_stalled=0;

  function automatic[511:0]make_data;
    input[31:0]addr;input integer beat;input integer channel;
    begin make_data=512'd0;make_data[31:0]=addr;make_data[39:32]=beat[7:0];
      make_data[40]=channel[0];make_data[41]=(addr[31:28]==4'hB);end
  endfunction
  task automatic check;input condition;input[8*100-1:0]message;
    begin checks=checks+1;if(!condition)begin failures=failures+1;
      $display("FAIL check=%0d %0s",checks,message);end end
  endtask

  hap_axi512_paired_2client_read_wrr dut(
    .core_clk(core_clk),.core_rst_n(core_rst_n),.core_clear(core_clear),
    .core_enable(core_enable),.attn_source_quiescent(1'b1),
    .mlp_source_quiescent(1'b1),.maintenance_pause_sources(),
    .maintenance_drain_active(),.maintenance_soft_clear_pulse(),
    .ddr0_clk(ddr0_clk),.ddr0_rst_n(ddr0_rst_n),
    .ddr0_enable(ddr0_enable),.ddr1_clk(ddr1_clk),.ddr1_rst_n(ddr1_rst_n),
    .ddr1_enable(ddr1_enable),
    .a0_arvalid(a0_arvalid),.a0_arready(a0_arready),.a0_araddr(a0_araddr),
    .a0_arlen(8'd15),.a0_arsize(3'd6),.a0_arburst(2'b01),
    .a0_rvalid(a0_rvalid),.a0_rready(a0_rready),.a0_rdata(a0_rdata),
    .a0_rresp(a0_rresp),.a0_rlast(a0_rlast),
    .m0_arvalid(m0_arvalid),.m0_arready(m0_arready),.m0_araddr(m0_araddr),
    .m0_arlen(8'd15),.m0_arsize(3'd6),.m0_arburst(2'b01),
    .m0_rvalid(m0_rvalid),.m0_rready(m0_rready),.m0_rdata(m0_rdata),
    .m0_rresp(m0_rresp),.m0_rlast(m0_rlast),
    .a1_arvalid(a1_arvalid),.a1_arready(a1_arready),.a1_araddr(a1_araddr),
    .a1_arlen(8'd15),.a1_arsize(3'd6),.a1_arburst(2'b01),
    .a1_rvalid(a1_rvalid),.a1_rready(a1_rready),.a1_rdata(a1_rdata),
    .a1_rresp(a1_rresp),.a1_rlast(a1_rlast),
    .m1_arvalid(m1_arvalid),.m1_arready(m1_arready),.m1_araddr(m1_araddr),
    .m1_arlen(8'd15),.m1_arsize(3'd6),.m1_arburst(2'b01),
    .m1_rvalid(m1_rvalid),.m1_rready(m1_rready),.m1_rdata(m1_rdata),
    .m1_rresp(m1_rresp),.m1_rlast(m1_rlast),
    .p0_arvalid(p0_arvalid),.p0_arready(p0_arready),.p0_araddr(p0_araddr),
    .p0_arlen(p0_arlen),.p0_arsize(p0_arsize),.p0_arburst(p0_arburst),
    .p0_rvalid(p0_rvalid),.p0_rready(p0_rready),.p0_rdata(p0_rdata),
    .p0_rresp(p0_rresp),.p0_rlast(p0_rlast),
    .p1_arvalid(p1_arvalid),.p1_arready(p1_arready),.p1_araddr(p1_araddr),
    .p1_arlen(p1_arlen),.p1_arsize(p1_arsize),.p1_arburst(p1_arburst),
    .p1_rvalid(p1_rvalid),.p1_rready(p1_rready),.p1_rdata(p1_rdata),
    .p1_rresp(p1_rresp),.p1_rlast(p1_rlast),
    .core_quiescent(core_quiescent),.error(error),
    .accepted_attn_bursts(accepted_attn_bursts),
    .accepted_mlp_bursts(accepted_mlp_bursts),
    .both_eligible_cycles(both_eligible_cycles),
    .p0_hol_cycles(p0_hol_cycles),.p1_hol_cycles(p1_hol_cycles),
    .p0_tag_high_watermark(p0_tag_high_watermark),
    .p1_tag_high_watermark(p1_tag_high_watermark));

  // Four independent reader-side AR streams.  Each holds payload stable until
  // the arbiter ingress FIFO accepts it.
  always @(posedge ddr0_clk)begin
    if(!ddr0_rst_n)begin a0_arvalid<=0;m0_arvalid<=0;a0_sent<=0;m0_sent<=0;
      a0_araddr<=32'hA000_0000;m0_araddr<=32'hB000_0000;end
    else begin
      if(a0_arvalid&&a0_arready)begin a0_sent<=a0_sent+1;a0_araddr<=a0_araddr+1024;
        if(a0_sent+1>=target_attn)a0_arvalid<=0;end
      else if(!a0_arvalid&&a0_sent<target_attn)a0_arvalid<=1;
      if(m0_arvalid&&m0_arready)begin m0_sent<=m0_sent+1;m0_araddr<=m0_araddr+1024;
        if(m0_sent+1>=target_mlp)m0_arvalid<=0;end
      else if(!m0_arvalid&&m0_sent<target_mlp)m0_arvalid<=1;
    end
  end
  always @(posedge ddr1_clk)begin
    if(!ddr1_rst_n)begin a1_arvalid<=0;m1_arvalid<=0;a1_sent<=0;m1_sent<=0;
      a1_araddr<=32'hA100_0000;m1_araddr<=32'hB100_0000;end
    else begin
      if(a1_arvalid&&a1_arready)begin a1_sent<=a1_sent+1;a1_araddr<=a1_araddr+1024;
        if(a1_sent+1>=target_attn)a1_arvalid<=0;end
      else if(!a1_arvalid&&a1_sent<target_attn)a1_arvalid<=1;
      if(m1_arvalid&&m1_arready)begin m1_sent<=m1_sent+1;m1_araddr<=m1_araddr+1024;
        if(m1_sent+1>=target_mlp)m1_arvalid<=0;end
      else if(!m1_arvalid&&m1_sent<target_mlp)m1_arvalid<=1;
    end
  end

  // MIG0 ordered responder plus AR-stability assertion.
  always @(posedge ddr0_clk)begin
    if(!ddr0_rst_n)begin ddr0_cycle<=0;p0_arready<=0;q0_wr<=0;q0_rd<=0;
      p0_rvalid<=0;p0_rlast<=0;p0_rdata<=0;p0_beat<=0;p0_was_stalled<=0;
      a0_rready<=0;m0_rready<=0;end
    else begin
      ddr0_cycle<=ddr0_cycle+1;
      p0_arready<=(ddr0_cycle%5)!=1;
      // Retain the last beat of the first Attention burst until the following
      // MLP burst reaches its independent FIFO.  This directly covers both
      // owner FIFOs being non-empty without blocking completion of the
      // physical Attention burst.
      a0_rready<=((a0_beats<14)||p0_both_rvalid_seen)&&
        ((ddr0_cycle%7)!=0);
      m0_rready<=(ddr0_cycle%11)!=0;
      if(p0_was_stalled)begin
        if(!p0_arvalid||p0_araddr!=p0_stall_addr||p0_arlen!=p0_stall_len)
          $fatal(1,"MIG0 AR payload changed while stalled");
      end
      p0_was_stalled<=p0_arvalid&&!p0_arready;
      if(p0_arvalid&&!p0_arready)begin p0_stall_addr<=p0_araddr;p0_stall_len<=p0_arlen;end
      if(p0_arvalid&&p0_arready)begin
        q0_addr[q0_wr]<=p0_araddr;q0_len[q0_wr]<=p0_arlen;
        q0_owner_log[q0_wr]<=p0_araddr[31:28]==4'hB;q0_wr<=q0_wr+1;
      end
      if(!p0_rvalid&&q0_rd<q0_wr&&(ddr0_cycle%3)!=0)begin
        p0_rvalid<=1;p0_beat<=0;p0_rdata<=make_data(q0_addr[q0_rd],0,0);
        p0_rlast<=inject_bad_p0?1'b0:(q0_len[q0_rd]==0);
      end else if(p0_rvalid&&p0_rready)begin
        if(p0_rlast)begin p0_rvalid<=0;p0_rlast<=0;q0_rd<=q0_rd+1;p0_beat<=0;end
        else begin
          p0_beat<=p0_beat+1;
          p0_rdata<=make_data(q0_addr[q0_rd],p0_beat+1,0);
          p0_rlast<=inject_bad_p0?(p0_beat==1):(p0_beat+1==q0_len[q0_rd]);
        end
      end
      if(a0_rvalid&&a0_rready)begin
        if(a0_rdata[41]||a0_rdata[40])$fatal(1,"MIG0 Attention R misroute");
        a0_beats<=a0_beats+1;end
      if(m0_rvalid&&m0_rready)begin
        if(!m0_rdata[41]||m0_rdata[40])$fatal(1,"MIG0 MLP R misroute");
        m0_beats<=m0_beats+1;end
      // Independent response FIFOs may both be non-empty; simultaneous
      // client RVALID is legal even though each physical MIG beat has one owner.
      if(a0_rvalid&&m0_rvalid)p0_both_rvalid_seen<=1;
    end
  end

  // MIG1 has different stalls/latency to exercise paired logical order with
  // independent physical timing.
  always @(posedge ddr1_clk)begin
    if(!ddr1_rst_n)begin ddr1_cycle<=0;p1_arready<=0;q1_wr<=0;q1_rd<=0;
      p1_rvalid<=0;p1_rlast<=0;p1_rdata<=0;p1_beat<=0;p1_was_stalled<=0;
      a1_rready<=0;m1_rready<=0;end
    else begin
      ddr1_cycle<=ddr1_cycle+1;
      p1_arready<=(ddr1_cycle%7)!=2;
      a1_rready<=((a1_beats<14)||p1_both_rvalid_seen)&&
        ((ddr1_cycle%5)!=0);
      m1_rready<=(ddr1_cycle%13)!=0;
      if(p1_was_stalled)begin
        if(!p1_arvalid||p1_araddr!=p1_stall_addr||p1_arlen!=p1_stall_len)
          $fatal(1,"MIG1 AR payload changed while stalled");
      end
      p1_was_stalled<=p1_arvalid&&!p1_arready;
      if(p1_arvalid&&!p1_arready)begin p1_stall_addr<=p1_araddr;p1_stall_len<=p1_arlen;end
      if(p1_arvalid&&p1_arready)begin
        q1_addr[q1_wr]<=p1_araddr;q1_len[q1_wr]<=p1_arlen;
        q1_owner_log[q1_wr]<=p1_araddr[31:28]==4'hB;q1_wr<=q1_wr+1;
      end
      if(!p1_rvalid&&q1_rd<q1_wr&&(ddr1_cycle%4)!=0)begin
        p1_rvalid<=1;p1_beat<=0;p1_rdata<=make_data(q1_addr[q1_rd],0,1);
        p1_rlast<=q1_len[q1_rd]==0;
      end else if(p1_rvalid&&p1_rready)begin
        if(p1_rlast)begin p1_rvalid<=0;p1_rlast<=0;q1_rd<=q1_rd+1;p1_beat<=0;end
        else begin p1_beat<=p1_beat+1;
          p1_rdata<=make_data(q1_addr[q1_rd],p1_beat+1,1);
          p1_rlast<=p1_beat+1==q1_len[q1_rd];end
      end
      if(a1_rvalid&&a1_rready)begin
        if(a1_rdata[41]||!a1_rdata[40])$fatal(1,"MIG1 Attention R misroute");
        a1_beats<=a1_beats+1;end
      if(m1_rvalid&&m1_rready)begin
        if(!m1_rdata[41]||!m1_rdata[40])$fatal(1,"MIG1 MLP R misroute");
        m1_beats<=m1_beats+1;end
      if(a1_rvalid&&m1_rvalid)p1_both_rvalid_seen<=1;
    end
  end

  integer i,timeout;
  initial begin
    repeat(8)@(posedge core_clk);
    core_rst_n=1;ddr0_rst_n=1;ddr1_rst_n=1;
    repeat(20)@(posedge core_clk);
    timeout=0;
    while((a0_beats<target_attn*16||a1_beats<target_attn*16||
           m0_beats<target_mlp*16||m1_beats<target_mlp*16||!core_quiescent)&&
          timeout<20000)begin @(posedge core_clk);timeout=timeout+1;end
    check(timeout<20000,"paired WRR good-flow timeout");
    check(!error,"paired WRR raised error on good flow");
    check(accepted_attn_bursts==target_attn,"Attention accepted burst count");
    check(accepted_mlp_bursts==target_mlp,"MLP accepted burst count");
    check(q0_wr==target_attn+target_mlp&&q1_wr==target_attn+target_mlp,
      "physical AR burst counts");
    for(i=0;i<target_attn+target_mlp;i=i+1)begin
      check(q0_owner_log[i]==q1_owner_log[i],"paired MIG owner order mismatch");
      check(q0_addr[i][23:0]==q1_addr[i][23:0],"paired MIG address sequence mismatch");
    end
    check(a0_beats==target_attn*16&&a1_beats==target_attn*16,
      "Attention R beat counts");
    check(m0_beats==target_mlp*16&&m1_beats==target_mlp*16,
      "MLP R beat counts");
    check(both_eligible_cycles!=0,"both-eligible coverage missing");
    check(p0_tag_high_watermark!=0&&p1_tag_high_watermark!=0,
      "response tag FIFO was not exercised");
    check(p0_both_rvalid_seen,
      "MIG0 owner response FIFOs were not simultaneously non-empty");
    check(p1_both_rvalid_seen,
      "MIG1 owner response FIFOs were not simultaneously non-empty");
    if(failures!=0)begin
      $display("FAIL hap_axi512_paired_2client_read_wrr failures=%0d checks=%0d",failures,checks);
      $finish;
    end
    $display("PASS hap_axi512_paired_2client_read_wrr checks=%0d A/M=%0d/%0d beats=%0d/%0d/%0d/%0d HOL=%0d/%0d tag_hwm=%0d/%0d",
      checks,accepted_attn_bursts,accepted_mlp_bursts,a0_beats,a1_beats,
      m0_beats,m1_beats,p0_hol_cycles,p1_hol_cycles,
      p0_tag_high_watermark,p1_tag_high_watermark);
    $finish;
  end
endmodule
