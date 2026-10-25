`timescale 1ns/1ps
// Real loader + inactive/active URAM bank controller + ordered scheduler.
module hap_mlp_gu_metadata_tb;
 localparam integer RECORDS=32;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,clear=0,start_valid=0,target_bank=1;
 wire start_ready,bank_load_begin_valid,bank_load_begin_ready,bank_load_begin_bank;
 wire gate_wr_valid,gate_wr_ready,gate_wr_bank;wire[17:0]gate_wr_addr;wire[223:0]gate_wr_meta;
 wire busy,done,error;wire[2:0]phase;wire[31:0]gate_record_count,error_code;wire[63:0]physical_bytes;
 wire load_fault_valid,load_fault_bank;
 reg[31:0]gate_base_addr=32'h70000fc0;
 wire m_axi_arvalid;reg m_axi_arready=0;wire[31:0]m_axi_araddr;wire[7:0]m_axi_arlen;wire[2:0]m_axi_arsize;wire[1:0]m_axi_arburst;
 reg m_axi_rvalid=0;wire m_axi_rready;reg[255:0]m_axi_rdata=0;reg[1:0]m_axi_rresp=0;reg m_axi_rlast=0;
 wire m_axi_awvalid;wire[31:0]m_axi_awaddr;wire[7:0]m_axi_awlen;wire[2:0]m_axi_awsize;wire[1:0]m_axi_awburst;
 wire m_axi_wvalid;wire[255:0]m_axi_wdata;wire[31:0]m_axi_wstrb;wire m_axi_wlast,m_axi_bready;
 reg commit_valid=0,commit_bank=1,consumer_quiescent=1;wire commit_ready;
 reg[31:0]commit_generation=7;wire active_bank;wire[31:0]active_generation;wire[1:0]bank_valid,bank_loading;
 wire gate_rd_valid,gate_rd_ready,gate_rsp_valid,gate_rsp_ready;wire[17:0]gate_rd_addr;wire[223:0]gate_rsp_meta;
 wire[31:0]gate_write_count_bank0,gate_write_count_bank1,gate_read_count;wire resident_quiescent,resident_error;
 reg command_start=0,command_done=0,gate_enable=0;reg[1:0]command_opcode=1;
 wire drained,gate_meta_valid,active,scheduler_done,scheduler_error;reg gate_meta_ready=0;wire[223:0]gate_meta;
 wire[31:0]gate_issue_count,gate_delivery_count;
 integer cycles=0,left=0,read_index=0,accepted=0,ars=0,delivered=0,faults=0,image=0,bad_record=-1,readback_image=0;
 reg[31:0]address;
 function automatic[223:0]payload(input integer im,rec);
  for(integer b=0;b<28;b=b+1)payload[b*8+:8]=(im*73+rec*17+b*11)&255;
 endfunction
 hap_mlp_gu_meta_dma_loader #(.GATE_RECORDS(RECORDS),.PRODUCTION_SHAPE(0))u_load(.*,
 .m_axi_awready(1'b1),.m_axi_wready(1'b1),.m_axi_bvalid(1'b0),.m_axi_bresp(2'b0));
 hap_mlp_gu_weight_meta_resident_ab #(.GATE_DEPTH(RECORDS),.PRODUCTION_SHAPE(0))u_bank(
 .clk(clk),.rst_n(rst_n),.clear(clear),.load_fault_valid(load_fault_valid),.load_fault_bank(load_fault_bank),
 .load_begin_valid(bank_load_begin_valid),.load_begin_ready(bank_load_begin_ready),.load_begin_bank(bank_load_begin_bank),
 .gate_wr_valid(gate_wr_valid),.gate_wr_ready(gate_wr_ready),.gate_wr_bank(gate_wr_bank),.gate_wr_addr(gate_wr_addr),.gate_wr_meta_u224(gate_wr_meta),
 .commit_valid(commit_valid),.commit_ready(commit_ready),.commit_bank(commit_bank),.commit_generation(commit_generation),.consumer_quiescent(consumer_quiescent),
 .active_bank(active_bank),.active_generation(active_generation),.bank_valid(bank_valid),.bank_loading(bank_loading),
 .gate_rd_valid(gate_rd_valid),.gate_rd_ready(gate_rd_ready),.gate_rd_addr(gate_rd_addr),.gate_rsp_valid(gate_rsp_valid),.gate_rsp_ready(gate_rsp_ready),.gate_rsp_meta_u224(gate_rsp_meta),
 .gate_write_count_bank0(gate_write_count_bank0),.gate_write_count_bank1(gate_write_count_bank1),.gate_read_count(gate_read_count),.quiescent(resident_quiescent),.error(resident_error));
 hap_mlp_gu_metadata_scheduler #(.GATE_RECORDS(RECORDS),.PRODUCTION_SHAPE(0))u_sched(
 .clk(clk),.rst_n(rst_n),.clear(clear),.command_start(command_start),.command_done(command_done),.command_opcode(command_opcode),.drained(drained),.gate_enable(gate_enable),
 .gate_rd_valid(gate_rd_valid),.gate_rd_ready(gate_rd_ready),.gate_rd_addr(gate_rd_addr),.gate_rsp_valid(gate_rsp_valid),.gate_rsp_ready(gate_rsp_ready),.gate_rsp_meta(gate_rsp_meta),
 .gate_meta_valid(gate_meta_valid),.gate_meta_ready(gate_meta_ready),.gate_meta(gate_meta),.active(active),.gate_issue_count(gate_issue_count),.gate_delivery_count(gate_delivery_count),.done(scheduler_done),.error(scheduler_error));
 always @(negedge clk)begin
  m_axi_arready=cycles%7!=0;gate_meta_ready=cycles%11>5;
  if(rst_n&&!clear&&!m_axi_rvalid&&left>0&&cycles%5!=0)begin
   m_axi_rvalid=1;m_axi_rdata={32'd0,payload(image,read_index)};
   if(read_index==bad_record)m_axi_rdata[255:224]=32'h80000001;
   m_axi_rlast=left==1;
  end
 end
 always @(posedge clk)begin
  cycles<=cycles+1;if(cycles>10000)$fatal(1,"watchdog");
  if(m_axi_awvalid||m_axi_wvalid)$fatal(1,"metadata loader wrote AXI");
  if(m_axi_arvalid&&m_axi_arready)begin
   if(left||m_axi_arlen>=16||m_axi_araddr!=gate_base_addr+accepted*32||m_axi_araddr[11:0]+(m_axi_arlen+1)*32>4096)$fatal(1,"metadata AR");
   left=m_axi_arlen+1;ars=ars+1;
  end
  if(m_axi_rvalid&&m_axi_rready)begin left=left-1;accepted=accepted+1;read_index=read_index+1;m_axi_rvalid<=0;end
  if(load_fault_valid)faults=faults+1;
  if(gate_meta_valid&&gate_meta_ready)begin
   if(gate_meta!==payload(readback_image,delivered))$fatal(1,"metadata value image%0d record%0d",readback_image,delivered);
   delivered=delivered+1;
  end
 end
 task load_image(input integer im,bad,bank);
 begin
  @(negedge clk);image=im;bad_record=bad;target_bank=bank;accepted=0;read_index=0;ars=0;start_valid=1;
  while(!start_ready)@(negedge clk);
  @(posedge clk);@(negedge clk);start_valid=0;
  wait(done);@(negedge clk);
  if(busy||accepted!=RECORDS||physical_bytes!=RECORDS*32||left||m_axi_rvalid)$fatal(1,"metadata exact physical drain");
 end endtask
 task read_image(input integer im);
 begin
  @(negedge clk);delivered=0;readback_image=im;gate_enable=1;command_start=1;
  @(negedge clk);command_start=0;
  wait(delivered==RECORDS);@(negedge clk);
  if(!drained||gate_issue_count!=RECORDS||gate_delivery_count!=RECORDS)$fatal(1,"metadata scheduled counts");
  command_done=1;@(negedge clk);command_done=0;gate_enable=0;
  if(scheduler_error||!resident_quiescent||active)$fatal(1,"metadata completion/drain");
 end endtask
 initial begin
  repeat(4)@(negedge clk);rst_n=1;
  if(!drained)$fatal(1,"metadata initial quiescence");
  load_image(1,-1,1);
  if(error||resident_error||gate_record_count!=RECORDS||gate_write_count_bank1!=RECORDS)$fatal(1,"good metadata count");
  consumer_quiescent=0;commit_valid=1;
  repeat(13)begin @(negedge clk);if(commit_ready||active_bank!=0||active_generation!=0)$fatal(1,"commit crossed busy consumer");end
  consumer_quiescent=1;while(!commit_ready)@(negedge clk);
  @(posedge clk);@(negedge clk);commit_valid=0;
  if(active_bank!=1||active_generation!=7||bank_valid!=2'b10||bank_loading)$fatal(1,"metadata first commit");
  read_image(1);
  // Invalid inactive load consumes every 32B record, commits only valid28B prefix.
  load_image(2,7,0);repeat(3)@(negedge clk);
  if(!error||error_code!=32'h2120||!resident_error||faults!=1||gate_record_count!=7||gate_write_count_bank0!=7||bank_valid!=2'b10||bank_loading||active_bank!=1||active_generation!=7)$fatal(1,"padding fault changed active identity or failed invalidation");
  commit_bank=0;commit_generation=8;commit_valid=1;
  repeat(17)begin @(negedge clk);if(commit_ready||start_ready||active_bank!=1||active_generation!=7)$fatal(1,"fault admitted load/commit");end
  commit_valid=0;
  // Existing accepted work can still consume unchanged active bytes after fatal.
  read_image(1);
  @(negedge clk);clear=1;@(negedge clk);clear=0;
  if(error||resident_error||bank_valid||bank_loading||active_generation||active||!drained)$fatal(1,"safe metadata clear");
  $display("GU metadata32B/28B: 32 good records, inactive padding7 full drain/prefix7, active-bank identity+bytes retained, blocked commit, 64 scheduled reads under backpressure");
  $display("HARDWARE_AGENT_SIM_PASS");$finish;
 end
endmodule
