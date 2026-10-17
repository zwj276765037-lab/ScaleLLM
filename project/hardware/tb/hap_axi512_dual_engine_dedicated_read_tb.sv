`timescale 1ns / 1ps
// Independent per-engine source, physical DDR model and full-width scoreboard.
// Expected logical response data is derived from the submitted stream index,
// not the DUT's owner tags, sequence state or returned physical AR address.
module hap_m002_weight_engine_bfm #(parameter integer ENGINE=0)(
 input wire clk,input wire rst_n,input integer target,input wire block_ar,
 input wire[1:0] fault,
 output reg[1:0] s_arvalid=0,input wire[1:0] s_arready,
 output wire[1:0][31:0] s_araddr,output wire[1:0][7:0] s_arlen,
 input wire[1:0] s_rvalid,output reg[1:0] s_rready=0,
 input wire[1:0][511:0] s_rdata,input wire[1:0][1:0] s_rresp,
 input wire[1:0] s_rlast,
 input wire p_arvalid,output reg p_arready=0,input wire[31:0] p_araddr,
 input wire[7:0] p_arlen,input wire[2:0] p_arsize,input wire[1:0] p_arburst,
 output reg p_rvalid=0,input wire p_rready,output reg[511:0] p_rdata=0,
 output reg[1:0] p_rresp=0,output reg p_rlast=0,
 output wire complete,output integer physical_bursts=0,
 output integer checked_beats=0,output integer ar_stalls=0,
 output integer r_stalls=0);
 wire groups_complete;
 hap_m002_group_join_scoreboard #(.ENGINE(ENGINE)) group_score(
   .clk(clk),.rst_n(rst_n),.target(target),.rvalid(s_rvalid),
   .rready(s_rready),.rdata(s_rdata),.complete(groups_complete));
 integer sent[0:1],received[0:1],rx_beat[0:1];
 integer qrd=0,tx_beat=0,i;
 reg[31:0] qaddr[0:511];reg[7:0] qlen[0:511];
 reg[31:0] random_r=32'h391ac623+ENGINE;
 reg ar_stalled=0;reg[44:0] ar_hold;
 reg[1:0] r_stalled=0;reg[1:0][514:0] r_hold;
 reg physical_stalled=0;reg[514:0] physical_hold;
 function automatic[31:0] address(input integer stream,input integer burst);
   address=32'h00100000+ENGINE*32'h04000000+stream*32'h01000000+burst*1024;
 endfunction
 function automatic[7:0] length(input integer burst);
   case(burst%4)0:length=0;1:length=1;2:length=3;default:length=15;endcase
 endfunction
 function automatic[511:0] payload(input[31:0] addr,input integer beat);
   integer w;begin for(w=0;w<16;w=w+1)
     payload[32*w+:32]=(addr+beat*64+w*4)^32'h5ac31f07^(w*32'h01010101);
   end
 endfunction
 assign s_araddr[0]=address(0,sent[0]);assign s_araddr[1]=address(1,sent[1]);
 assign s_arlen[0]=length(sent[0]);assign s_arlen[1]=length(sent[1]);
 assign complete=received[0]==target&&received[1]==target&&
   sent[0]==target&&sent[1]==target&&s_arvalid==0&&groups_complete;
 always @(posedge clk or negedge rst_n)begin
   if(!rst_n)begin
     s_arvalid<=0;s_rready<=0;p_arready<=0;p_rvalid<=0;p_rlast<=0;
     p_rresp<=0;physical_bursts<=0;qrd<=0;tx_beat<=0;checked_beats<=0;
     ar_stalls<=0;r_stalls<=0;ar_stalled<=0;r_stalled<=0;
     physical_stalled<=0;random_r<=32'h391ac623+ENGINE;
     for(i=0;i<2;i=i+1)begin sent[i]<=0;received[i]<=0;rx_beat[i]<=0;end
   end else begin
     random_r<={random_r[30:0],random_r[31]^random_r[21]^random_r[1]^random_r[0]};
     p_arready<=!block_ar&&(random_r[2:0]!=0);
     for(i=0;i<2;i=i+1)begin
       s_rready[i]<=random_r[3+i]||random_r[9+i];
       if(s_arvalid[i]&&s_arready[i])begin
         sent[i]<=sent[i]+1;s_arvalid[i]<=0;
       end else if(!s_arvalid[i]&&sent[i]<target&&random_r[12+i])s_arvalid[i]<=1;
       if(r_stalled[i]&&(!s_rvalid[i]||
         {s_rlast[i],s_rresp[i],s_rdata[i]}!==r_hold[i]))
         $fatal(1,"engine%0d stream%0d R payload changed under backpressure",ENGINE,i);
       r_stalled[i]<=s_rvalid[i]&&!s_rready[i];
       r_hold[i]<={s_rlast[i],s_rresp[i],s_rdata[i]};
       if(s_rvalid[i]&&!s_rready[i])r_stalls<=r_stalls+1;
       if(s_rvalid[i]&&s_rready[i])begin
         if(s_rdata[i]!==payload(address(i,received[i]),rx_beat[i])||
            s_rresp[i]!==0||s_rlast[i]!== (rx_beat[i]==length(received[i])))
           $fatal(1,"engine%0d stream%0d response mismatch burst%0d beat%0d got=%h expected=%h",ENGINE,i,received[i],rx_beat[i],s_rdata[i],payload(address(i,received[i]),rx_beat[i]));
         if(rx_beat[i]==length(received[i]))begin
           received[i]<=received[i]+1;rx_beat[i]<=0;
         end else rx_beat[i]<=rx_beat[i]+1;
       end
     end
     checked_beats<=checked_beats+(s_rvalid[0]&&s_rready[0])+(s_rvalid[1]&&s_rready[1]);
     if(ar_stalled&&(!p_arvalid||{p_araddr,p_arlen,p_arsize,p_arburst}!==ar_hold))
       $fatal(1,"engine%0d physical AR unstable",ENGINE);
     ar_stalled<=p_arvalid&&!p_arready;ar_hold<={p_araddr,p_arlen,p_arsize,p_arburst};
     if(p_arvalid&&!p_arready)ar_stalls<=ar_stalls+1;
     if(p_arvalid&&p_arready)begin
       if(p_araddr!==address(physical_bursts%2,physical_bursts/2)||
          p_arlen!==length(physical_bursts/2)||p_arsize!==6||p_arburst!==1)
         $fatal(1,"engine%0d physical target/order/length mismatch burst%0d addr=%h",ENGINE,physical_bursts,p_araddr);
       qaddr[physical_bursts]<=p_araddr;qlen[physical_bursts]<=p_arlen;
       physical_bursts<=physical_bursts+1;
     end
     if(physical_stalled&&(!p_rvalid||{p_rlast,p_rresp,p_rdata}!==physical_hold))
       $fatal(1,"physical responder changed stalled R payload");
     physical_stalled<=p_rvalid&&!p_rready;
     physical_hold<={p_rlast,p_rresp,p_rdata};
     if(!p_rvalid&&qrd<physical_bursts&&random_r[17])begin
       p_rvalid<=1;tx_beat<=0;p_rdata<=payload(qaddr[qrd],0);
       p_rresp<=fault==1?2'b10:0;
       p_rlast<=fault==2?1'b1:qlen[qrd]==0;
     end else if(p_rvalid&&p_rready)begin
       if(p_rlast)begin p_rvalid<=0;qrd<=qrd+1;tx_beat<=0;end
       else begin
         tx_beat<=tx_beat+1;p_rdata<=payload(qaddr[qrd],tx_beat+1);
         p_rlast<=fault==2?1'b1:tx_beat+1==qlen[qrd];
       end
     end
   end
 end
endmodule


// Accepted logical beats are packed into real engine halfgroups, then passed
// through the unmodified production assembler/join. This separately checks
// complete group concatenation, ScaleCode metadata association and column order.
module hap_m002_group_join_scoreboard #(parameter integer ENGINE=0)(
 input wire clk,input wire rst_n,input integer target,
 input wire[1:0]rvalid,input wire[1:0]rready,
 input wire[1:0][511:0]rdata,output wire complete);
 localparam integer HALF_BEATS=ENGINE==0?4:2;
 localparam integer HALF_BITS=HALF_BEATS*512;
 reg[HALF_BITS-1:0] halfmem[0:1][0:511];
 reg[HALF_BITS-1:0] pack[0:1];
 integer fill[0:1],written[0:1],consumed=0,checked_groups=0;
 integer i,k,j;reg[31:0]random_r=32'h76ab91c3+ENGINE;
 wire[1:0]half_valid={written[1]>consumed,written[0]>consumed};
 wire[1:0]half_ready;wire meta_ready,out_valid,join_error;
 wire out_ready=random_r[11]||random_r[18];
 wire[HALF_BITS*2-1:0]group_data;
 wire[255:0]group_meta;wire[9:0]out_tile;wire[6:0]out_group;
 wire[31:0]meta_word=32'hc0200000+consumed;
 reg[HALF_BITS*2-1:0]expected;
 wire[31:0]expected_meta_word=32'hc0200000+checked_groups;
 wire[255:0]expected_meta=ENGINE==0?{8{expected_meta_word}}:{32'd0,{7{expected_meta_word}}};
 reg was_stalled=0;reg[HALF_BITS*2+255:0]hold_data;
 function automatic integer length(input integer n);
 case(n%4)0:length=1;1:length=2;2:length=4;default:length=16;endcase
 endfunction
 function automatic integer expected_groups(input integer bursts);
 integer b,n;begin n=0;for(b=0;b<bursts;b=b+1)n=n+length(b);
 expected_groups=n/HALF_BEATS;end endfunction
 function automatic[511:0]reference_beat(input integer stream,input integer global_beat);
 integer b,n,w;reg[31:0]addr;
 begin b=0;n=global_beat;while(n>=length(b))begin n=n-length(b);b=b+1;end
 addr=32'h00100000+ENGINE*32'h04000000+stream*32'h01000000+b*1024;
 for(w=0;w<16;w=w+1)reference_beat[w*32+:32]=
 (addr+n*64+w*4)^32'h5ac31f07^(w*32'h01010101);
 end endfunction
 assign complete=checked_groups==expected_groups(target);
 generate if(ENGINE==0)begin:g_attention
 wire[31:0]groups;
 hap_dual_ddr_weight_group_assembler u_join(
 .clk(clk),.rst_n(rst_n),.clear(1'b0),
 .ddr0_valid(half_valid[0]),.ddr0_ready(half_ready[0]),.ddr0_half(halfmem[0][consumed]),
 .ddr1_valid(half_valid[1]),.ddr1_ready(half_ready[1]),.ddr1_half(halfmem[1][consumed]),
 .meta_valid(1'b1),.meta_ready(meta_ready),.meta_tile(10'(consumed/128)),
 .meta_group(7'(consumed%128)),.meta16({8{meta_word}}),
 .out_valid(out_valid),.out_ready(out_ready),.out_tile(out_tile),.out_group(out_group),
 .out_weight_s8(group_data),.out_meta16(group_meta),.assembled_group_count(groups),.error(join_error));
 end else begin:g_mlp
 wire[31:0]groups;wire[63:0]bytes;wire[223:0]meta;
 assign group_meta={32'd0,meta};assign out_tile=0;assign out_group=0;
 hap_mlp_w4_dual_channel_join u_join(
 .clk(clk),.rst_n(rst_n),.clear(1'b0),
 .half0_valid(half_valid[0]),.half0_ready(half_ready[0]),.half0_data(halfmem[0][consumed]),
 .half1_valid(half_valid[1]),.half1_ready(half_ready[1]),.half1_data(halfmem[1][consumed]),
 .meta_valid(1'b1),.meta_ready(meta_ready),.meta_u224({7{meta_word}}),
 .out_valid(out_valid),.out_ready(out_ready),.weights_s4x16x32(group_data),
 .weight_meta_u224(meta),.useful_group_count(groups),.useful_weight_byte_count(bytes),.error(join_error));
 end endgenerate
 always_comb begin
 for(integer st=0;st<2;st=st+1)
 for(integer b=0;b<HALF_BEATS;b=b+1)
 expected[st*HALF_BITS+b*512+:512]=reference_beat(st,checked_groups*HALF_BEATS+b);
 end
 always @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin
 consumed<=0;checked_groups<=0;was_stalled<=0;random_r<=32'h76ab91c3+ENGINE;
 for(i=0;i<2;i=i+1)begin fill[i]<=0;written[i]<=0;end
 end else begin
 random_r<={random_r[30:0],random_r[31]^random_r[21]^random_r[1]^random_r[0]};
 for(i=0;i<2;i=i+1)if(rvalid[i]&&rready[i])begin
 pack[i][fill[i]*512+:512]<=rdata[i];
 if(fill[i]==HALF_BEATS-1)begin
 halfmem[i][written[i]]<={rdata[i],pack[i][HALF_BITS-513:0]};
 written[i]<=written[i]+1;fill[i]<=0;
 end else fill[i]<=fill[i]+1;
 end
 if(half_ready[0]&&half_valid[0])begin
 if(!half_ready[1]||!half_valid[1]||!meta_ready)$fatal(1,"partial logical group consume");
 consumed<=consumed+1;end
 if(join_error)$fatal(1,"real assembler/join error");
 if(was_stalled&&(!out_valid||{group_data,group_meta}!==hold_data))$fatal(1,"assembled group unstable");
 was_stalled<=out_valid&&!out_ready;hold_data<={group_data,group_meta};
 if(out_valid&&out_ready)begin
 if($isunknown(expected)||$isunknown(expected_meta))$fatal(1,"uninitialized independent group oracle");
 if(group_data!==expected||group_meta!==expected_meta)begin
 $display("GROUP_DIAGNOSTIC engine=%0d group=%0d expected_unknown=%b got=%h expected=%h got_meta=%h expected_meta=%h",ENGINE,checked_groups,$isunknown(expected),group_data,expected,group_meta,expected_meta);
 $fatal(1,"engine%0d full group/metadata/column order mismatch group%0d",ENGINE,checked_groups);end
 if(ENGINE==0&&(out_tile!==10'(checked_groups/128)||out_group!==7'(checked_groups%128)))
 $fatal(1,"Attention group identity mismatch");
 checked_groups<=checked_groups+1;
 end
 end end
endmodule

module hap_axi512_dual_engine_dedicated_read_tb;
 reg core_clk=0,ddr0_clk=0,ddr1_clk=0;
 always #5 core_clk=~core_clk;
 always #2.5 ddr0_clk=~ddr0_clk;
 initial begin #0.625;forever #2.5 ddr1_clk=~ddr1_clk;end
 reg core_rst_n=0,ddr0_rst_n=0,ddr1_rst_n=0;
 wire bfm_rst_n=core_rst_n&&ddr0_rst_n&&ddr1_rst_n;
 reg core_clear=0,core_enable=1,ddr0_enable=1,ddr1_enable=1;
 integer target_a=0,target_m=0,soft_clears=0,checks=0,second_stalls=0;
 reg block0=0,block1=0;reg[1:0]fault0=0,fault1=0;
 wire complete_a,complete_m,core_quiescent,error;
 wire maintenance_pause_sources,maintenance_drain_active,maintenance_soft_clear_pulse;
 wire[31:0]accepted_attn_bursts,accepted_mlp_bursts,both_eligible_cycles;
 wire[31:0]p0_hol_cycles,p1_hol_cycles,p0_tag_high_watermark,p1_tag_high_watermark;
 wire[1:0]a_arvalid,a_arready,a_rvalid,a_rready,a_rlast;
 wire[1:0][31:0]a_araddr;wire[1:0][7:0]a_arlen;
 wire[1:0][511:0]a_rdata;wire[1:0][1:0]a_rresp;
 wire[1:0]m_arvalid,m_arready,m_rvalid,m_rready,m_rlast;
 wire[1:0][31:0]m_araddr;wire[1:0][7:0]m_arlen;
 wire[1:0][511:0]m_rdata;wire[1:0][1:0]m_rresp;
 wire p0_arvalid,p0_arready,p0_rvalid,p0_rready,p0_rlast;
 wire[31:0]p0_araddr;wire[7:0]p0_arlen;wire[2:0]p0_arsize;
 wire[1:0]p0_arburst,p0_rresp;wire[511:0]p0_rdata;
 wire signed[31:0]physical0,beats0,ar_stalls0,r_stalls0;
 wire p1_arvalid,p1_arready,p1_rvalid,p1_rready,p1_rlast;
 wire[31:0]p1_araddr;wire[7:0]p1_arlen;wire[2:0]p1_arsize;
 wire[1:0]p1_arburst,p1_rresp;wire[511:0]p1_rdata;
 wire signed[31:0]physical1,beats1,ar_stalls1,r_stalls1;
 hap_axi512_dual_engine_dedicated_read #(.TAG_DEPTH(16)) dut(
 .attn_source_quiescent(complete_a),.mlp_source_quiescent(complete_m),
 .a0_arvalid(a_arvalid[0]),
 .a0_arready(a_arready[0]),
 .a0_araddr(a_araddr[0]),
 .a0_arlen(a_arlen[0]),
 .a0_rvalid(a_rvalid[0]),
 .a0_rready(a_rready[0]),
 .a0_rdata(a_rdata[0]),
 .a0_rresp(a_rresp[0]),
 .a0_rlast(a_rlast[0]),
 .a0_arsize(3'd6),.a0_arburst(2'b01),
 .a1_arvalid(a_arvalid[1]),
 .a1_arready(a_arready[1]),
 .a1_araddr(a_araddr[1]),
 .a1_arlen(a_arlen[1]),
 .a1_rvalid(a_rvalid[1]),
 .a1_rready(a_rready[1]),
 .a1_rdata(a_rdata[1]),
 .a1_rresp(a_rresp[1]),
 .a1_rlast(a_rlast[1]),
 .a1_arsize(3'd6),.a1_arburst(2'b01),
 .m0_arvalid(m_arvalid[0]),
 .m0_arready(m_arready[0]),
 .m0_araddr(m_araddr[0]),
 .m0_arlen(m_arlen[0]),
 .m0_rvalid(m_rvalid[0]),
 .m0_rready(m_rready[0]),
 .m0_rdata(m_rdata[0]),
 .m0_rresp(m_rresp[0]),
 .m0_rlast(m_rlast[0]),
 .m0_arsize(3'd6),.m0_arburst(2'b01),
 .m1_arvalid(m_arvalid[1]),
 .m1_arready(m_arready[1]),
 .m1_araddr(m_araddr[1]),
 .m1_arlen(m_arlen[1]),
 .m1_rvalid(m_rvalid[1]),
 .m1_rready(m_rready[1]),
 .m1_rdata(m_rdata[1]),
 .m1_rresp(m_rresp[1]),
 .m1_rlast(m_rlast[1]),
 .m1_arsize(3'd6),.m1_arburst(2'b01),
 .*);
 hap_m002_weight_engine_bfm #(.ENGINE(0)) bfm0(
 .clk(ddr0_clk),.rst_n(bfm_rst_n),.target(target_a),.block_ar(block0),.fault(fault0),
 .s_arvalid(a_arvalid),
 .s_arready(a_arready),
 .s_araddr(a_araddr),
 .s_arlen(a_arlen),
 .s_rvalid(a_rvalid),
 .s_rready(a_rready),
 .s_rdata(a_rdata),
 .s_rresp(a_rresp),
 .s_rlast(a_rlast),
 .p_arvalid(p0_arvalid),
 .p_arready(p0_arready),
 .p_araddr(p0_araddr),
 .p_arlen(p0_arlen),
 .p_arsize(p0_arsize),
 .p_arburst(p0_arburst),
 .p_rvalid(p0_rvalid),
 .p_rready(p0_rready),
 .p_rdata(p0_rdata),
 .p_rresp(p0_rresp),
 .p_rlast(p0_rlast),
 .complete(complete_a),.physical_bursts(physical0),.checked_beats(beats0),.ar_stalls(ar_stalls0),.r_stalls(r_stalls0));
 hap_m002_weight_engine_bfm #(.ENGINE(1)) bfm1(
 .clk(ddr1_clk),.rst_n(bfm_rst_n),.target(target_m),.block_ar(block1),.fault(fault1),
 .s_arvalid(m_arvalid),
 .s_arready(m_arready),
 .s_araddr(m_araddr),
 .s_arlen(m_arlen),
 .s_rvalid(m_rvalid),
 .s_rready(m_rready),
 .s_rdata(m_rdata),
 .s_rresp(m_rresp),
 .s_rlast(m_rlast),
 .p_arvalid(p1_arvalid),
 .p_arready(p1_arready),
 .p_araddr(p1_araddr),
 .p_arlen(p1_arlen),
 .p_arsize(p1_arsize),
 .p_arburst(p1_arburst),
 .p_rvalid(p1_rvalid),
 .p_rready(p1_rready),
 .p_rdata(p1_rdata),
 .p_rresp(p1_rresp),
 .p_rlast(p1_rlast),
 .complete(complete_m),.physical_bursts(physical1),.checked_beats(beats1),.ar_stalls(ar_stalls1),.r_stalls(r_stalls1));
 task automatic check(input condition,input string message);
 begin checks=checks+1;if(condition!==1'b1)$fatal(1,"%s",message);end endtask
 task automatic wait_complete;
 integer t;begin
 // Targets are changed by the sequential scenario. Wait one clock boundary
 // so the continuous complete flags reflect those new inputs before sampling.
 @(negedge core_clk);t=0;
 while(!(complete_a&&complete_m&&core_quiescent)&&t<30000)begin
   @(negedge core_clk);t=t+1;if(error)$fatal(1,"unexpected good-flow error");end
 check(t<30000,"dedicated DDR flow timed out");end endtask
 task automatic restart(input integer kind);
 integer t;begin
 target_a=0;target_m=0;fault0=0;fault1=0;block0=0;block1=0;
 @(negedge core_clk);
 case(kind)0:core_rst_n=0;1:ddr0_rst_n=0;2:ddr1_rst_n=0;
 default:begin core_rst_n=0;ddr0_rst_n=0;ddr1_rst_n=0;end endcase
 repeat(8)@(negedge core_clk);
 core_rst_n=1;ddr0_rst_n=1;ddr1_rst_n=1;
 repeat(60)@(negedge core_clk);
 check(core_quiescent&&!error,"hard reset failed to restart");
 check(accepted_attn_bursts==0&&accepted_mlp_bursts==0,"hard reset counters");
 end endtask
 always @(posedge core_clk)if(core_rst_n&&dut.second0_valid_r&&!dut.o0_wr_ready)
 second_stalls=second_stalls+1;
 always @(posedge core_clk)if(maintenance_soft_clear_pulse)begin
 soft_clears=soft_clears+1;
 check(complete_a&&complete_m,"soft clear preceded accepted command drain");end
 integer t;
 initial begin
 restart(3);
 target_a=12;wait_complete();
 check(physical0==24&&physical1==0,"Attention-only physical target counts");
 check(accepted_attn_bursts==12&&accepted_mlp_bursts==0,"Attention pair counter ABI");
 target_a=24;target_m=18;wait_complete();
 check(accepted_attn_bursts==24&&accepted_mlp_bursts==18,"shared pair counters");
 check(physical0==48&&physical1==36,"both logical halves must be physically read");
 // A blocked DDR0 must not hold DDR1's independent engine or egress FIFO.
 block0=1;repeat(5)@(negedge core_clk);target_a=48;target_m=30;
 @(negedge core_clk);t=0;while(!complete_m&&t<15000)begin @(negedge core_clk);t=t+1;end
 check(complete_m&&!complete_a,"DDR1 cannot progress independently of blocked DDR0");
 block0=0;wait_complete();
 check(second_stalls>0,"pending second descriptor + full egress not covered");
 check(ar_stalls0>0&&ar_stalls1>0&&r_stalls0>0&&r_stalls1>0,"backpressure coverage missing");
 target_a=64;target_m=48;
 repeat(40)@(negedge core_clk);core_clear=1;
 @(negedge core_clk);core_clear=0;
 t=0;while(soft_clears==0&&t<20000)begin @(negedge core_clk);t=t+1;end
 check(soft_clears==1,"maintenance did not emit one delayed soft clear");
 repeat(60)@(negedge core_clk);wait_complete();
 check(accepted_attn_bursts==0&&accepted_mlp_bursts==0,"soft clear pair counters");
 // Post-maintenance traffic must restart physical tag sequences from zero.
 target_a=80;target_m=64;wait_complete();
 check(accepted_attn_bursts==16&&accepted_mlp_bursts==16,"post-maintenance restart");
 $display("COVERAGE assembled attention=%0d mlp=%0d second_pending_full_cycles=%0d",bfm0.group_score.checked_groups,bfm1.group_score.checked_groups,second_stalls);
 $display("COVERAGE good-flow bytes=%0d/%0d physical=%0d/%0d stallsAR=%0d/%0d stallsR=%0d/%0d",beats0*64,beats1*64,physical0,physical1,ar_stalls0,ar_stalls1,r_stalls0,r_stalls1);
 restart(0);target_a=4;target_m=4;wait_complete();
 restart(1);target_a=4;target_m=4;wait_complete();
 restart(2);target_a=4;target_m=4;wait_complete();
 // Protocol failures freeze until a hard reset; software clear cannot hide it.
 restart(3);fault0=1;target_a=2;
 t=0;while(!error&&t<1000)begin @(negedge core_clk);t=t+1;end
 check(error,"bad RRESP was not detected");
 check(beats0==0,"malformed first beat leaked to logical consumer");
 core_clear=1;repeat(20)@(negedge core_clk);core_clear=0;
 check(error,"maintenance improperly recovered fatal response error");
 restart(3);fault1=2;target_m=2;
 // Burst0 is one beat, so early-RLAST injection first faults on burst1.
 t=0;while(!error&&t<1000)begin @(negedge core_clk);t=t+1;end
 check(error,"early RLAST was not detected");
 restart(3);target_a=4;target_m=4;wait_complete();
 $display("PASS hap_axi512_dual_engine_dedicated_read checks=%0d",checks);
 $display("HARDWARE_AGENT_SIM_PASS");$finish;
 end
 initial begin #5000000;$fatal(1,"dedicated read global timeout");end
endmodule
