`timescale 1ns/1ps
// Revision3 section9: real production graph, N_GU128/N_DOWN64, complete K128/448.
// No stub/force/internal state writes. Attention is real but idle; no concurrent-attention claim.
// BFM image definitions follow export_scalellm_llama31_artifacts.py pack_w4/pack_mlp_meta.
module hap_attention_mlp_linear_integration_tb;
 reg  core_clk=0;
 reg  core_rst_n=0;
 reg  core_clear=0;
 reg  ddr0_clk=0;
 reg  ddr0_rst_n=0;
 reg  ddr1_clk=0;
 reg  ddr1_rst_n=0;
 reg [11:0] ctrl_awaddr=0;
 reg  ctrl_awvalid=0;
 wire  ctrl_awready;
 reg [31:0] ctrl_wdata=0;
 reg [3:0] ctrl_wstrb=0;
 reg  ctrl_wvalid=0;
 wire  ctrl_wready;
 wire [1:0] ctrl_bresp;
 wire  ctrl_bvalid;
 reg  ctrl_bready=0;
 reg [11:0] ctrl_araddr=0;
 reg  ctrl_arvalid=0;
 wire  ctrl_arready;
 wire [31:0] ctrl_rdata;
 wire [1:0] ctrl_rresp;
 wire  ctrl_rvalid;
 reg  ctrl_rready=0;
 wire  data_axi_arvalid;
 reg  data_axi_arready=0;
 wire [31:0] data_axi_araddr;
 wire [7:0] data_axi_arlen;
 wire [2:0] data_axi_arsize;
 wire [1:0] data_axi_arburst;
 reg  data_axi_rvalid=0;
 wire  data_axi_rready;
 reg [255:0] data_axi_rdata=0;
 reg [1:0] data_axi_rresp=0;
 reg  data_axi_rlast=0;
 wire  data_axi_awvalid;
 reg  data_axi_awready=0;
 wire [31:0] data_axi_awaddr;
 wire [7:0] data_axi_awlen;
 wire [2:0] data_axi_awsize;
 wire [1:0] data_axi_awburst;
 wire  data_axi_wvalid;
 reg  data_axi_wready=0;
 wire [255:0] data_axi_wdata;
 wire [31:0] data_axi_wstrb;
 wire  data_axi_wlast;
 reg  data_axi_bvalid=0;
 wire  data_axi_bready;
 reg [1:0] data_axi_bresp=0;
 wire  mlp_data_axi_arvalid;
 reg  mlp_data_axi_arready=0;
 wire [31:0] mlp_data_axi_araddr;
 wire [7:0] mlp_data_axi_arlen;
 wire [2:0] mlp_data_axi_arsize;
 wire [1:0] mlp_data_axi_arburst;
 reg  mlp_data_axi_rvalid=0;
 wire  mlp_data_axi_rready;
 reg [255:0] mlp_data_axi_rdata=0;
 reg [1:0] mlp_data_axi_rresp=0;
 reg  mlp_data_axi_rlast=0;
 wire  mlp_data_axi_awvalid;
 reg  mlp_data_axi_awready=0;
 wire [31:0] mlp_data_axi_awaddr;
 wire [7:0] mlp_data_axi_awlen;
 wire [2:0] mlp_data_axi_awsize;
 wire [1:0] mlp_data_axi_awburst;
 wire  mlp_data_axi_wvalid;
 reg  mlp_data_axi_wready=0;
 wire [255:0] mlp_data_axi_wdata;
 wire [31:0] mlp_data_axi_wstrb;
 wire  mlp_data_axi_wlast;
 reg  mlp_data_axi_bvalid=0;
 wire  mlp_data_axi_bready;
 reg [1:0] mlp_data_axi_bresp=0;
 wire  ddr0_axi_arvalid;
 reg  ddr0_axi_arready=0;
 wire [31:0] ddr0_axi_araddr;
 wire [7:0] ddr0_axi_arlen;
 wire [2:0] ddr0_axi_arsize;
 wire [1:0] ddr0_axi_arburst;
 reg  ddr0_axi_rvalid=0;
 wire  ddr0_axi_rready;
 reg [511:0] ddr0_axi_rdata=0;
 reg [1:0] ddr0_axi_rresp=0;
 reg  ddr0_axi_rlast=0;
 wire  ddr1_axi_arvalid;
 reg  ddr1_axi_arready=0;
 wire [31:0] ddr1_axi_araddr;
 wire [7:0] ddr1_axi_arlen;
 wire [2:0] ddr1_axi_arsize;
 wire [1:0] ddr1_axi_arburst;
 reg  ddr1_axi_rvalid=0;
 wire  ddr1_axi_rready;
 reg [511:0] ddr1_axi_rdata=0;
 reg [1:0] ddr1_axi_rresp=0;
 reg  ddr1_axi_rlast=0;
 wire  attention_irq;
 wire  mlp_irq;
 wire  integration_error;
 hap_attention_mlp_production_core #(.INTERMEDIATE_COLUMNS(128),.HIDDEN_COLUMNS(64),.ENFORCE_PRODUCTION_SHAPE(0)) dut(.*);
 localparam [31:0] META_G=32'h06800000,META_D=32'h06900000;
 localparam integer JOB_BOUND=2000000,RUN_BOUND=18000000;
 integer cycles=0,checks=0,job_op=1,job_cohort=0,job_id=0;
 integer epoch_number=9,meta_generation=7;
 reg [31:0] input_base=0,output_base=0;
 integer input_size=73728,output_size=12288;
 integer fault_kind=0; // 0 healthy,1 badREC,2 BRESP,3 ABORT,4 physical RLAST
 reg input_bad=0,inject_b_error=0,inject_weight_framing=0,framing_injected=0;
 reg hold_final_b=0,final_b_waiting=0;
 integer read_left=0,write_left=0,weight_left=0;
 reg [31:0] read_address=0,write_address=0,weight_address=0;
 integer data_read_bytes=0,data_write_bytes=0,data_b_bytes=0;
 integer job_aw_count=0,job_b_count=0,weight_beats=0,weight_ar_count=0;
 integer meta_read_bytes=0,job_cache_reads=0,job_compute_starts=0;
 integer job_meta_g_issue=0,job_meta_g_deliver=0,job_meta_d_issue=0,job_meta_d_deliver=0;
 integer job_gu_records=0,job_down_records=0;
 integer clear_pulses=0,soft_clear_pulses=0,job_clear_baseline=0,soft_clear_baseline=0;
 integer b_delay=0,b_bytes=0;
 reg b_pending=0,b_will_error=0,b_is_final=0;
 reg [31:0] last_status=0;
 longint signed gold_gu[0:1][0:1][0:15][0:127];
 longint signed gold_down[0:1][0:15][0:63];
 integer gold_groups_evaluated=0;
 reg [255:0] previous_data_r=0;
 reg [511:0] previous_weight_r=0;
 reg previous_data_r_stall=0,previous_weight_r_stall=0;
 reg previous_data_last=0,previous_weight_last=0;
 integer start_cycle,old_aw,old_soft,old_clear;
 reg [31:0] saved_records,saved_input,saved_output,saved_error;

 always #5 core_clk=~core_clk;
 always #2.5 ddr0_clk=~ddr0_clk;
 initial begin #1;forever #2.5 ddr1_clk=~ddr1_clk;end

 task automatic check(input bit condition,input string message);
 begin checks=checks+1;if(!condition)$fatal(1,"integration: %s cycle=%0d job=%0d",message,cycles,job_id);end
 endtask
 function automatic integer activation(input integer cohort,g,row,lane);
 activation=(g*3+row*5+lane*7+cohort*11)%31-15;
 endfunction
 function automatic integer zero_point(input integer row);zero_point=120+row%9;endfunction
 function automatic integer activation_code(input integer cohort,row);activation_code=1+row%7+cohort;endfunction
 function automatic integer activation_shift(input integer op,g,row);activation_shift=(op==1?10:6)+(g+row)%2;endfunction
 function automatic integer weight_value(input integer g,col,matrix,lane);
 weight_value=(g*7+col*3+matrix*5+lane*11)%16-8;
 endfunction
 function automatic integer weight_code(input integer g,col,matrix);weight_code=1+(col+g+matrix)%7;endfunction
 function automatic integer weight_shift(input integer op,g,col);
 weight_shift=(op==1?10:6)+10*(col%3)+(g%2);
 endfunction

 // Pure mathematical oracle: every full K group/lane is evaluated. S17 dot,
 // code products, arithmetic F24 alignment, exact accumulation, final half-away
 // rounding and saturation. No reader/gather/kernel control state is used.
 // |dot|<=3840, codes<=8/7, total shift12..42: |sum|<2**40,
 // so signed64 preserves every intermediate and the final rounding addition.
 function automatic longint signed oracle(input integer op,cohort,matrix,row,col);
 longint signed dot,raw,guard_value,acc,rounded;integer shift_total;
 begin
  acc=0;
  for(integer g=0;g<(op==1?128:448);g=g+1)begin
   dot=0;
   for(integer k=0;k<32;k=k+1)dot=dot+activation(cohort,g,row,k)*weight_value(g,col,matrix,k);
   raw=dot*activation_code(cohort,row)*weight_code(g,col,matrix);
   shift_total=activation_shift(op,g,row)+weight_shift(op,g,col);
   if(shift_total<=24)guard_value=raw<<<(24-shift_total);
   else guard_value=raw>>>(shift_total-24);
   acc=acc+guard_value;
  end
  if(acc<0)rounded=-((-acc+64'sd128)>>>8);
  else rounded=(acc+64'sd128)>>>8;
  if(op==1)begin
   if(rounded>8388607)rounded=8388607;
   if(rounded< -8388608)rounded= -8388608;
  end else begin
   if(rounded>64'sd2147483647)rounded=64'sd2147483647;
   if(rounded< -64'sd2147483648)rounded= -64'sd2147483648;
  end
  oracle=rounded;
 end endfunction

 function automatic [255:0] metadata_beat(input integer op,record_number);
 integer tile,matrix,g,col;reg [255:0] result;
 begin
  result=0;
  if(op==1)begin tile=record_number/256;matrix=(record_number/128)%2;g=record_number%128;end
  else begin tile=record_number%4;matrix=0;g=record_number/4;end
  for(integer lane=0;lane<16;lane=lane+1)begin
   col=tile*16+lane;
   result[lane*8+:8]=8'(weight_code(g,col,matrix));
   result[128+lane*6+:6]=6'(weight_shift(op,g,col));
  end
  metadata_beat=result;
 end endfunction

 function automatic [7:0] input_byte(input integer offset);
 integer g,position,row,lane,meta_byte;reg [23:0] metadata;
 begin
  g=offset/576;position=offset%576;
  if(position<512)begin row=position/32;lane=position%32;
   input_byte=8'(zero_point(row)+activation(job_cohort,g,row,lane));
  end else if(position<560)begin
   row=(position-512)/3;meta_byte=(position-512)%3;
   metadata=(activation_shift(job_op,g,row)<<16)|(activation_code(job_cohort,row)<<8)|zero_point(row);
   input_byte=8'(metadata>>(meta_byte*8));
  end else input_byte=(input_bad&&g==7&&position==560)?8'd1:8'd0;
 end endfunction
 function automatic [255:0] data_memory(input [31:0] address);
 reg [255:0] result;
 begin
  result=0;
  if(address>=META_G&&address<META_G+65536)result=metadata_beat(1,(address-META_G)/32);
  else if(address>=META_D&&address<META_D+57344)result=metadata_beat(2,(address-META_D)/32);
  else if(address>=input_base&&address<input_base+input_size)begin
   for(integer b=0;b<32;b=b+1)result[b*8+:8]=input_byte(address-input_base+b);
  end else $fatal(1,"unexpected data read address %h",address);
  data_memory=result;
 end endfunction

 function automatic [511:0] weight_memory(input [31:0] address);
 integer op,half_number,source,beat,tile,matrix,g,col,lane;
 reg [31:0] base;reg [511:0] result;
 begin
  if(address<32'h00040000)begin op=1;half_number=0;base=0;end
  else if(address>=32'h01c00000&&address<32'h01c40000)begin op=1;half_number=1;base=32'h01c00000;end
  else if(address>=32'h03800000&&address<32'h03838000)begin op=2;half_number=0;base=32'h03800000;end
  else if(address>=32'h04600000&&address<32'h04638000)begin op=2;half_number=1;base=32'h04600000;end
  else begin $fatal(1,"unexpected DDR1 weight read address %h",address);op=0;half_number=0;base=0;end
  source=(address-base)/128;beat=((address-base)%128)/64;
  if(op==1)begin tile=source/256;matrix=(source/128)%2;g=source%128;end
  else begin tile=source%4;matrix=0;g=source/4;end
  result=0;
  for(integer n=0;n<128;n=n+1)begin
   col=tile*16+half_number*8+beat*4+n/32;lane=n%32;
   result[n*4+:4]=4'(weight_value(g,col,matrix,lane));
  end
  weight_memory=result;
 end endfunction

 function automatic [7:0] expected_output_byte(input integer offset);
 integer record_number,position,element,row,col,matrix,byte_number;
 longint signed value;
 begin
  if(job_op==1)begin
   record_number=offset/768;position=offset%768;element=position/3;byte_number=position%3;
   row=element/16;col=(record_number/2)*16+element%16;matrix=record_number%2;
   value=gold_gu[job_cohort][matrix][row][col];
  end else begin
   record_number=offset/1024;position=offset%1024;element=position/4;byte_number=position%4;
   row=element/16;col=record_number*16+element%16;
   value=gold_down[job_cohort][row][col];
  end
  expected_output_byte=8'(value>>>(byte_number*8));
 end endfunction

 // AXI256 core-domain DDR model. One accepted read and one accepted write
 // burst can progress independently. All valid responses hold their payload
 // until handshake. Stalls are deterministic; there is no guessed rate gold.
 always @(negedge core_clk)begin
  mlp_data_axi_arready=core_rst_n&&read_left==0&&!mlp_data_axi_rvalid&&(cycles%11!=3);
  mlp_data_axi_awready=core_rst_n&&write_left==0&&!b_pending&&!mlp_data_axi_bvalid&&(cycles%13!=4);
  mlp_data_axi_wready=core_rst_n&&write_left>0&&(cycles%17>3);
  if(core_rst_n&&!mlp_data_axi_rvalid&&read_left>0&&cycles%7!=2)begin
   mlp_data_axi_rdata=data_memory(read_address);mlp_data_axi_rresp=0;
   mlp_data_axi_rlast=read_left==1;mlp_data_axi_rvalid=1;
  end
  if(core_rst_n&&b_pending&&!mlp_data_axi_bvalid)begin
   if(b_delay>0)b_delay=b_delay-1;
   else if(!(b_is_final&&hold_final_b))begin
    mlp_data_axi_bvalid=1;mlp_data_axi_bresp=b_will_error?2'b10:2'b00;
   end
  end
 end
 always @(posedge core_clk)begin
  cycles<=cycles+1;
  if(cycles>RUN_BOUND)$fatal(1,"integration global bounded-cycle watchdog");
  if(!core_rst_n)begin
   read_left=0;write_left=0;b_pending=0;mlp_data_axi_rvalid<=0;mlp_data_axi_bvalid<=0;
   previous_data_r_stall<=0;final_b_waiting=0;
  end else begin
   if(data_axi_arvalid||data_axi_awvalid||ddr0_axi_arvalid||attention_irq)
    $fatal(1,"idle real Attention branch produced unexpected traffic/IRQ");
   if(previous_data_r_stall&&(mlp_data_axi_rvalid!==1||mlp_data_axi_rdata!==previous_data_r||mlp_data_axi_rlast!==previous_data_last))
    $fatal(1,"data BFM violated RVALID payload hold");
   previous_data_r_stall<=mlp_data_axi_rvalid&&!mlp_data_axi_rready;
   previous_data_r<=mlp_data_axi_rdata;previous_data_last<=mlp_data_axi_rlast;
   if(mlp_data_axi_arvalid&&mlp_data_axi_arready)begin
    check(mlp_data_axi_arsize==5&&mlp_data_axi_arburst==1,"data AR size/type");
    check((mlp_data_axi_araddr&4095)+(mlp_data_axi_arlen+1)*32<=4096,"data AR does not cross4KiB");
    read_left=mlp_data_axi_arlen+1;read_address=mlp_data_axi_araddr;
   end
   if(mlp_data_axi_rvalid&&mlp_data_axi_rready)begin
    if(read_address>=META_G&&read_address<META_D+57344)meta_read_bytes=meta_read_bytes+32;
    else data_read_bytes=data_read_bytes+32;
    read_left=read_left-1;read_address=read_address+32;mlp_data_axi_rvalid<=0;
   end
   if(mlp_data_axi_awvalid&&mlp_data_axi_awready)begin
    check(mlp_data_axi_awsize==5&&mlp_data_axi_awburst==1,"data AW size/type");
    check((mlp_data_axi_awaddr&4095)+(mlp_data_axi_awlen+1)*32<=4096,"data AW does not cross4KiB");
    check(mlp_data_axi_awaddr==output_base+data_write_bytes,"output AW address/order");
    if(inject_b_error&&job_b_count>0)$fatal(1,"new AW after injected failing BRESP");
    write_left=mlp_data_axi_awlen+1;write_address=mlp_data_axi_awaddr;
    b_bytes=write_left*32;job_aw_count=job_aw_count+1;
   end
   if(mlp_data_axi_wvalid&&mlp_data_axi_wready)begin
    check(write_left>0&&mlp_data_axi_wstrb==32'hffffffff,"W follows accepted AW with full strobe");
    check(mlp_data_axi_wlast==(write_left==1),"WLAST matches burst count");
    for(integer byte_number=0;byte_number<32;byte_number=byte_number+1)
     if(mlp_data_axi_wdata[byte_number*8+:8]!==expected_output_byte(write_address-output_base+byte_number))
      $fatal(1,"output numeric/layout mismatch op%0d cohort%0d offset%0d actual%h expected%h",job_op,job_cohort,write_address-output_base+byte_number,mlp_data_axi_wdata[byte_number*8+:8],expected_output_byte(write_address-output_base+byte_number));
    write_left=write_left-1;write_address=write_address+32;data_write_bytes=data_write_bytes+32;
    if(write_left==0)begin
     b_pending=1;b_delay=9;b_is_final=data_write_bytes==output_size;
     b_will_error=inject_b_error&&job_b_count==0;
     if(b_is_final)final_b_waiting=1;
    end
   end
   if(mlp_data_axi_bvalid&&mlp_data_axi_bready)begin
    if(mlp_data_axi_bresp==0)data_b_bytes=data_b_bytes+b_bytes;
    job_b_count=job_b_count+1;b_pending=0;mlp_data_axi_bvalid<=0;
   end
   if(dut.engine_soft_clear)soft_clear_pulses=soft_clear_pulses+1;
   if(dut.mlp_job_clear)clear_pulses=clear_pulses+1;
   if(dut.u_compute.req_valid&&dut.u_compute.req_ready)begin
    check(dut.u_compute.req_group<(job_op==1?128:448),"cache group range");
    job_cache_reads=job_cache_reads+1;
   end
   if(dut.mlp_command_valid&&dut.mlp_command_ready)job_compute_starts=job_compute_starts+1;
   if(dut.gate_rd_valid&&dut.gate_rd_ready)job_meta_g_issue=job_meta_g_issue+1;
   if(dut.gate_meta_valid&&dut.gate_meta_ready)job_meta_g_deliver=job_meta_g_deliver+1;
   if(dut.down_rd_valid&&dut.down_rd_ready)job_meta_d_issue=job_meta_d_issue+1;
   if(dut.down_meta_valid&&dut.down_meta_ready)job_meta_d_deliver=job_meta_d_deliver+1;
   if(dut.mlp_gu_valid&&dut.mlp_gu_ready)job_gu_records=job_gu_records+1;
   if(dut.mlp_out_valid&&dut.mlp_out_ready)job_down_records=job_down_records+1;
  end
 end

 // Both logical MLP half-streams reach the actual physical DDR1 port.
 // The other physical DDR port remains idle with real Attention instantiated.
 always @(negedge ddr1_clk)begin
  ddr1_axi_arready=ddr1_rst_n&&weight_left==0&&!ddr1_axi_rvalid;
  if(ddr1_rst_n&&!ddr1_axi_rvalid&&weight_left>0)begin
   ddr1_axi_rdata=weight_memory(weight_address);ddr1_axi_rresp=0;
   ddr1_axi_rlast=weight_left==1;
   if(inject_weight_framing&&!framing_injected&&weight_left>1)begin
    ddr1_axi_rlast=1;framing_injected=1;
   end
   ddr1_axi_rvalid=1;
  end
 end
 always @(posedge ddr1_clk)begin
  if(!ddr1_rst_n)begin weight_left=0;ddr1_axi_rvalid<=0;previous_weight_r_stall<=0;end
  else begin
   if(previous_weight_r_stall&&(ddr1_axi_rvalid!==1||ddr1_axi_rdata!==previous_weight_r||ddr1_axi_rlast!==previous_weight_last))
    $fatal(1,"weight BFM violated RVALID payload hold");
   previous_weight_r_stall<=ddr1_axi_rvalid&&!ddr1_axi_rready;
   previous_weight_r<=ddr1_axi_rdata;previous_weight_last<=ddr1_axi_rlast;
   if(ddr1_axi_arvalid&&ddr1_axi_arready)begin
    check(ddr1_axi_arsize==6&&ddr1_axi_arburst==1,"weight AR format");
    check((ddr1_axi_araddr&4095)+(ddr1_axi_arlen+1)*64<=4096,"weight AR does not cross4KiB");
    weight_left=ddr1_axi_arlen+1;weight_address=ddr1_axi_araddr;weight_ar_count=weight_ar_count+1;
   end
   if(ddr1_axi_rvalid&&ddr1_axi_rready)begin
    weight_left=weight_left-1;weight_address=weight_address+64;
    weight_beats=weight_beats+1;ddr1_axi_rvalid<=0;
   end
  end
 end

 task automatic write_csr(input [11:0] address,input [31:0] value,input [1:0] response);
 begin
  @(negedge core_clk);ctrl_awaddr=address;ctrl_awvalid=1;
  ctrl_wdata=value;ctrl_wstrb=15;ctrl_wvalid=1;ctrl_bready=0;
  fork
   begin @(posedge core_clk);while(!ctrl_awready)@(posedge core_clk);@(negedge core_clk);ctrl_awvalid=0;end
   begin @(posedge core_clk);while(!ctrl_wready)@(posedge core_clk);@(negedge core_clk);ctrl_wvalid=0;end
  join
  while(!ctrl_bvalid)@(negedge core_clk);
  check(ctrl_bresp===response,$sformatf("CSR write response address%h actual%0d expected%0d",address,ctrl_bresp,response));
  repeat(2)@(negedge core_clk);ctrl_bready=1;@(negedge core_clk);ctrl_bready=0;
 end endtask
 task automatic read_csr(input [11:0] address,output reg [31:0] value);
 begin
  @(negedge core_clk);ctrl_araddr=address;ctrl_arvalid=1;ctrl_rready=0;
  @(posedge core_clk);while(!ctrl_arready)@(posedge core_clk);
  @(negedge core_clk);ctrl_arvalid=0;
  while(!ctrl_rvalid)@(negedge core_clk);
  check(ctrl_rresp==0,"CSR read OKAY");value=ctrl_rdata;
  ctrl_rready=1;@(negedge core_clk);ctrl_rready=0;
 end endtask
 task automatic expect_csr(input [11:0] address,input [31:0] expected);
 reg [31:0] value;
 begin read_csr(address,value);check(value===expected,$sformatf("CSR%h actual%h expected%h",address,value,expected));end endtask
 task automatic poll_csr(input [11:0] address,input [31:0] mask,expected);
 reg [31:0] value;integer began;
 begin
  began=cycles;value=~expected;
  while((value&mask)!==expected)begin
   read_csr(address,value);check(cycles-began<JOB_BOUND,$sformatf("CSR bounded wait addr%h value%h",address,value));
   if((value&mask)!==expected)repeat(31)@(negedge core_clk);
  end
 end endtask
 task automatic session_reset;
 begin
  @(negedge core_clk);core_rst_n=0;ddr0_rst_n=0;ddr1_rst_n=0;core_clear=0;
  ctrl_awvalid=0;ctrl_wvalid=0;ctrl_bready=0;ctrl_arvalid=0;ctrl_rready=0;
  input_bad=0;inject_b_error=0;inject_weight_framing=0;hold_final_b=0;framing_injected=0;
  repeat(16)@(negedge core_clk);core_rst_n=1;ddr0_rst_n=1;ddr1_rst_n=1;
  repeat(80)@(negedge core_clk);
  expect_csr(12'h104,32'h00060000);expect_csr(12'h300,32'h4d4c0001);
  poll_csr(12'h10c,32'h20,32'h20);write_csr(12'h108,3,0);
  poll_csr(12'h10c,32'h1f,32'h1b);
  check(!integration_error,"new session healthy in SHARED mode");
 end endtask
 task automatic load_metadata_and_epoch;
 integer before_bytes;
 begin
  before_bytes=meta_read_bytes;
  write_csr(12'h150,1,0);write_csr(12'h16c,META_G,0);write_csr(12'h170,META_D,0);
  write_csr(12'h154,1,0);poll_csr(12'h14c,32'h10,32'h10);
  poll_csr(12'h178,32'h14,0);
  expect_csr(12'h160,2048);expect_csr(12'h168,1792);
  check(meta_read_bytes-before_bytes==122880,"all3840 padded metadata records DMA-read");
  write_csr(12'h158,meta_generation,0);write_csr(12'h154,2,0);
  poll_csr(12'h144,32'hffffffff,meta_generation);
  write_csr(12'h11c,2,0);write_csr(12'h12c,0,0);write_csr(12'h130,32'h01c00000,0);
  write_csr(12'h134,32'h03800000,0);write_csr(12'h138,32'h04600000,0);
  write_csr(12'h374,1,0);write_csr(12'h36c,epoch_number,0);
  expect_csr(12'h370,0);expect_csr(12'h368,epoch_number);
 end endtask
 task automatic configure_job(input integer op,cohort,id,kind);
 reg [31:0] base;
 begin
  @(negedge core_clk);
  job_op=op;job_cohort=cohort;job_id=id;fault_kind=kind;
  base=32'h10000000+cohort*3*32'h00800000;
  input_base=base+(op==1?0:32'h00300000);output_base=base+(op==1?32'h00100000:32'h00400000);
  input_size=op==1?73728:258048;output_size=op==1?12288:4096;
  input_bad=kind==1;inject_b_error=kind==2;inject_weight_framing=kind==4;framing_injected=0;
  hold_final_b=kind==0||kind==3;final_b_waiting=0;
  data_read_bytes=0;data_write_bytes=0;data_b_bytes=0;job_aw_count=0;job_b_count=0;
  weight_beats=0;weight_ar_count=0;job_cache_reads=0;job_compute_starts=0;job_gu_records=0;job_down_records=0;
  job_meta_g_issue=0;job_meta_g_deliver=0;job_meta_d_issue=0;job_meta_d_deliver=0;
  job_clear_baseline=clear_pulses;soft_clear_baseline=soft_clear_pulses;
  write_csr(12'h118,id,0);write_csr(12'h280,100+cohort,0);
  write_csr(12'h284,(cohort*3<<16)|cohort,0);write_csr(12'h11c,2,0);
  write_csr(12'h30c,op,0);write_csr(12'h120,32'h48384605,0);
  write_csr(12'h124,input_base,0);write_csr(12'h128,output_base,0);
  write_csr(12'h310,input_size,0);write_csr(12'h314,output_size,0);
  write_csr(12'h318,id+1,0);write_csr(12'h140,meta_generation,0);write_csr(12'h31c,epoch_number,0);
  write_csr(12'h374,1,0);write_csr(12'h320,1,0);expect_csr(12'h370,0);
  start_cycle=cycles;
 end endtask
 task automatic wait_done;
 begin
  while(!dut.job_completion_valid)begin
   @(negedge core_clk);check(cycles-start_cycle<JOB_BOUND,"job completed within finite structural bound");
  end
 end endtask
 task automatic finish_success(input integer abort_expected);
 begin
  while(!final_b_waiting)begin
   @(negedge core_clk);check(cycles-start_cycle<JOB_BOUND,"reached final output B");
   check(!dut.job_completion_valid,"no DONE before full output W");
  end
  repeat(64)begin
   @(negedge core_clk);
   check(!dut.job_completion_valid&&clear_pulses==job_clear_baseline,"final B hold blocks DONE and job_clear");
  end
  hold_final_b=0;wait_done();
  expect_csr(12'h338,job_id);expect_csr(12'h33c,100+job_cohort);
  expect_csr(12'h340,(job_cohort*3<<16)|job_cohort);expect_csr(12'h344,2);
  expect_csr(12'h328,job_op);expect_csr(12'h32c,job_id+1);
  expect_csr(12'h334,meta_generation);expect_csr(12'h330,epoch_number);
  expect_csr(12'h348,input_size);expect_csr(12'h34c,output_size);
  expect_csr(12'h350,abort_expected?32'h2201:0);expect_csr(12'h364,job_op==1?16:4);
  check(data_read_bytes==input_size&&data_write_bytes==output_size&&data_b_bytes==output_size,"exact external input/W/OKAY-B byte counts");
  check(job_compute_starts==1&&job_cache_reads==(job_op==1?2816:448),"completeK cache requests and one compute start");
  check(job_gu_records==(job_op==1?16:0)&&job_down_records==(job_op==2?4:0),"exact GU/Down writer-accepted records");
  check(job_meta_g_issue==(job_op==1?2048:0)&&job_meta_g_deliver==(job_op==1?2048:0)&&job_meta_d_issue==(job_op==2?1792:0)&&job_meta_d_deliver==(job_op==2?1792:0),"all metadata issued and delivered once");
  check(weight_beats==(job_op==1?8192:7168),"both physical weight halves include all records");
  if(!abort_expected)begin
   check(soft_clear_pulses==soft_clear_baseline&&!integration_error,"normal SHARED job never invokes maintenance");
   check(dut.attention_launch_enable,"normal MLP job retains Attention launch permission");
   expect_csr(12'h368,epoch_number);expect_csr(12'h144,meta_generation);
  end
  $display("INTEGRATION_JOB id=%0d op=%0d cohort=%0d cycles=%0d input=%0d output=%0d cache=%0d weights=%0d abort=%0d",job_id,job_op,job_cohort,cycles-start_cycle,data_read_bytes,data_b_bytes,job_cache_reads,weight_beats,abort_expected);
 end endtask
 task automatic ack_job;
 begin
  write_csr(12'h2a0,job_id,0);poll_csr(12'h29c,1,0);
  repeat(8)@(negedge core_clk);
 end endtask

 initial begin : run
  // Everything used by the very first transfer is initialized explicitly;
  // no always-@* time-zero trigger is required for memory image generation.
  // Literal vectors independently recomputed with Python arbitrary integers:
  // acc44916 ->175; acc-576 ->-2; acc-58 ->0; acc-26638336 ->-104056;
  // acc1247232 ->4872; acc-161 ->-1. These detect oracle width/sign mistakes
  // at time0 before any RTL transaction, without adapting gold to the DUT.
  check(oracle(1,0,0,0,0)===64'sd175,"independent GU scalar oracle known vector");
  check(oracle(1,1,1,15,127)===-64'sd2,"independent GU last-column oracle known vector");
  check(oracle(1,0,1,10,125)===64'sd0,"independent GU right-shift negative oracle vector");
  check(oracle(2,0,0,0,0)===-64'sd104056,"independent Down scalar oracle known vector");
  check(oracle(2,1,0,15,63)===64'sd4872,"independent Down last-column oracle known vector");
  check(oracle(2,1,0,10,62)===-64'sd1,"independent Down arithmetic-right-shift oracle vector");
  for(integer cohort=0;cohort<2;cohort=cohort+1)begin
   for(integer row=0;row<16;row=row+1)begin
    for(integer matrix=0;matrix<2;matrix=matrix+1)
     for(integer col=0;col<128;col=col+1)begin
      gold_gu[cohort][matrix][row][col]=oracle(1,cohort,matrix,row,col);
      gold_groups_evaluated=gold_groups_evaluated+128;
     end
    for(integer col=0;col<64;col=col+1)begin
     gold_down[cohort][row][col]=oracle(2,cohort,0,row,col);
     gold_groups_evaluated=gold_groups_evaluated+448;
    end
   end
  end
  $display("INTEGRATION_GOLD full scalar groups=%0d lane_products=%0d",gold_groups_evaluated,gold_groups_evaluated*32);
  session_reset();load_metadata_and_epoch();
  // Same epoch, both cohorts, independent GU and Down inputs (not a complete
  // Host SwiGLU chain because GU outputN is intentionally reduced).
  for(integer cohort=0;cohort<2;cohort=cohort+1)begin
   configure_job(1,cohort,10+cohort*2,0);finish_success(0);ack_job();
   expect_csr(12'h368,epoch_number);expect_csr(12'h144,meta_generation);
   configure_job(2,cohort,11+cohort*2,0);finish_success(0);ack_job();
   expect_csr(12'h368,epoch_number);expect_csr(12'h144,meta_generation);
  end
  // Mid-input format error: group7 padding, prefix exactly seven records;
  // the accepted whole input must still drain without sealing or launching.
  configure_job(1,0,20,1);wait_done();
  expect_csr(12'h350,32'h2001);expect_csr(12'h348,7*576);expect_csr(12'h34c,0);
  check(data_read_bytes==73728&&job_aw_count==0&&job_compute_starts==0&&job_cache_reads==0,"badREC full read drain with no compute/AW");
  check(!dut.mlp_cache_sealed&&!dut.job_reset_required,"recoverable badREC never seals cache");
  ack_job();expect_csr(12'h368,epoch_number);expect_csr(12'h144,meta_generation);
  configure_job(1,0,21,0);finish_success(0);ack_job();

  // Real ABORT while accepted compute is active must allow transport/kernel
  // progress. After full output drain, controlled maintenance preserves DONE.
  configure_job(2,0,22,3);
  while(job_compute_starts==0)@(negedge core_clk);
  repeat(100)@(negedge core_clk);write_csr(12'h320,4,0);
  finish_success(1);
  poll_csr(12'h368,32'hffffffff,0);poll_csr(12'h14c,32'h6,0);
  check(soft_clear_pulses>soft_clear_baseline,"ABORT used real post-drain maintenance");
  expect_csr(12'h350,32'h2201);expect_csr(12'h338,22);ack_job();
  epoch_number=10;meta_generation=8;load_metadata_and_epoch();

  // Framing-correct failing BRESP is a drainable fatal fault, distinct from
  // the physical reader global-freeze test below. No internal signal is forced.
  configure_job(1,0,30,2);wait_done();
  expect_csr(12'h350,32'h2103);expect_csr(12'h338,30);expect_csr(12'h34c,0);
  check(dut.job_reset_required&&job_aw_count==1&&job_b_count==1&&!b_pending&&write_left==0,"BRESP failure retires its accepted burst and prohibits new AW");
  read_csr(12'h364,saved_records);read_csr(12'h348,saved_input);read_csr(12'h34c,saved_output);
  write_csr(12'h2a0,30,2);
  write_csr(12'h320,0,2);expect_csr(12'h370,32'h1001);
  old_soft=soft_clear_pulses;write_csr(12'h110,2,0);
  start_cycle=cycles;
  while(soft_clear_pulses==old_soft)begin @(negedge core_clk);check(cycles-start_cycle<JOB_BOUND,"drainableBRESP reaches actual safe maintenance barrier");end
  repeat(80)@(negedge core_clk);
  check(!dut.job_reset_required&&dut.job_completion_valid,"hard_clear retains unACKed fatal DONE but releases live reset_required");
  expect_csr(12'h350,32'h2103);expect_csr(12'h338,30);
  expect_csr(12'h364,saved_records);expect_csr(12'h348,saved_input);expect_csr(12'h34c,saved_output);
  expect_csr(12'h370,32'h1001);expect_csr(12'h368,0);poll_csr(12'h14c,6,0);
  ack_job();epoch_number=11;meta_generation=9;load_metadata_and_epoch();
  configure_job(2,1,31,0);finish_success(0);ack_job();

  // Corrupt physicalDDR1 RLAST on the first beat of a multi-beat burst. The
  // BFM keeps all subsequent valid data stable; global_freeze may not pretend
  // it drained. Only a true core/reset session can discard that bus history.
  configure_job(1,0,40,4);
  start_cycle=cycles;
  while(!dut.u_paired_weight.global_freeze_core)begin
   @(negedge core_clk);check(cycles-start_cycle<JOB_BOUND,"framing corruption triggers paired global_freeze");
  end
  repeat(80)@(negedge core_clk);
  check(framing_injected&&dut.job_reset_required&&!dut.paired_core_quiescent,"framing failure retains fault and true nonquiescent");
  old_soft=soft_clear_pulses;
  @(negedge core_clk);core_clear=1;@(negedge core_clk);core_clear=0;
  repeat(128)@(negedge core_clk);
  check(dut.u_paired_weight.global_freeze_core&&dut.job_reset_required&&soft_clear_pulses==old_soft,"global_freeze cannot be recovered by soft-clear request");
  session_reset();expect_csr(12'h368,0);expect_csr(12'h370,0);
  epoch_number=12;meta_generation=10;load_metadata_and_epoch();
  configure_job(1,0,41,0);finish_success(0);ack_job();
  check(!integration_error&&weight_left==0&&read_left==0&&write_left==0&&!b_pending,"new session completes and all external transports retire");
  $display("INTEGRATION_SCOPE N_GU=128 N_DOWN=64 K_GU=128 K_DOWN=448 rows=16 same_epoch_jobs=4 badREC_retry=1 ABORT_drain=1 BRESP_maintenance_retry=1 framing_core_reset_retry=1 Attention=real_idle no_fullshape_or_concurrent_Attention_claim");
  $display("INTEGRATION_COUNTERS checks=%0d core_cycles=%0d metadata_bytes=%0d soft_clears=%0d job_clears=%0d",checks,cycles,meta_read_bytes,soft_clear_pulses,clear_pulses);
  $display("HARDWARE_AGENT_SIM_PASS");$finish;
 end
endmodule
