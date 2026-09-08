`timescale 1ns/1ps
module hap_attention_axil_launch_guard_tb;
 reg clk=0,rst_n=0;reg[11:0]awaddr=0,araddr=0;reg awvalid=0,wvalid=0,bready=0;
 reg[31:0]wdata=0;reg[3:0]wstrb=0;wire awready,wready;wire[1:0]bresp,rresp;
 wire bvalid,arready,rvalid;wire[31:0]rdata;reg arvalid=0,rready=0;
 reg engine_busy=0,launch_granted=0,engine_done=0,engine_error=0;
 reg maintenance_busy=0;wire start_pulse;
 wire clear_pulse,reload_metadata,reload_rope,preserve_historical_kv;
 wire[31:0]command_id,layer_id,run_format_id,input_base,output_base,weight_c0_base,
  weight_c1_base,weight_meta_base,rope_base;wire[6:0]query_start;wire[7:0]valid_key_count,query_count;
 wire irq,done_sticky,error_sticky;integer starts=0,checks=0;always #3.333 clk=~clk;
 hap_attention_axil_control dut(.clk(clk),.rst_n(rst_n),.s_axil_awaddr(awaddr),
  .s_axil_awvalid(awvalid),.s_axil_awready(awready),.s_axil_wdata(wdata),
  .s_axil_wstrb(wstrb),.s_axil_wvalid(wvalid),.s_axil_wready(wready),
  .s_axil_bresp(bresp),.s_axil_bvalid(bvalid),.s_axil_bready(bready),
  .s_axil_araddr(araddr),.s_axil_arvalid(arvalid),.s_axil_arready(arready),
  .s_axil_rdata(rdata),.s_axil_rresp(rresp),.s_axil_rvalid(rvalid),
  .s_axil_rready(rready),.engine_busy(engine_busy),.launch_enable(launch_granted),
  .maintenance_busy(maintenance_busy),
  .engine_done(engine_done),.engine_error(engine_error),.engine_error_code(0),
  .metadata_loaded(1'b1),.rope_loaded(1'b1),.cycle_count(0),.weight_group_count(0),
  .projection_tile_count(0),.attention_row_count(0),.wo_tile_count(0),
  .input_frontend_cycle_count(0),.qkv_projection_cycle_count(0),.rope_cycle_count(0),
  .kv12_cycle_count(0),.attention_cycle_count(0),.context_frontend_cycle_count(0),
  .wo_projection_cycle_count(0),.control_overhead_cycle_count(0),.start_pulse(start_pulse),
  .clear_pulse(clear_pulse),.reload_metadata(reload_metadata),.reload_rope(reload_rope),
  .preserve_historical_kv(preserve_historical_kv),.command_id(command_id),.layer_id(layer_id),
  .query_start(query_start),.valid_key_count(valid_key_count),.query_count(query_count),
  .run_format_id(run_format_id),.input_base(input_base),.output_base(output_base),
  .weight_c0_base(weight_c0_base),.weight_c1_base(weight_c1_base),
  .weight_meta_base(weight_meta_base),.rope_base(rope_base),.irq(irq),
  .done_sticky(done_sticky),.error_sticky(error_sticky));
 task tick;begin @(posedge clk);#1;end endtask
 task wr;
  input [11:0] a;
  input [31:0] v;
  input [1:0] exp;
  begin
   while (!awready || !wready) tick();
   awaddr=a;wdata=v;wstrb=4'hf;awvalid=1;wvalid=1;tick();awvalid=0;wvalid=0;
   while (!bvalid) tick();
   if (bresp != exp) begin
    $display("FAIL bresp");
    $fatal(1);
   end
   checks=checks+1;bready=1;tick();bready=0;
  end
 endtask
 always @(posedge clk)if(start_pulse)starts<=starts+1;
 initial begin
  repeat(4) tick();
  rst_n=1;
  tick();
  wr(12'h018,32'h00080100,0);
  wr(12'h020,32'h2000,0);
  wr(12'h024,32'h4000,0);
  wr(12'h028,32'h10000000,0);
  wr(12'h02c,32'h20000000,0);
  wr(12'h030,32'h30000000,0);
  wr(12'h034,32'h40000000,0);
  wr(12'h008,1,2);
  if(starts!=0) begin
   $display("FAIL launch guard");
   $fatal(1);
  end
  wr(12'h008,2,0);
  launch_granted=1;
  maintenance_busy=1;wr(12'h008,1,2);
  if(starts!=0)$fatal(1,"maintenance launch guard");
  maintenance_busy=0;
  wr(12'h008,1,0);
  if(starts!=1) begin
   $display("FAIL enabled start");
   $fatal(1);
  end
  $display("PASS hap_attention_axil_launch_guard checks=%0d",checks);
  $finish;
 end
endmodule
