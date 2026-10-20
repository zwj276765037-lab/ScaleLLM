`timescale 1ns/1ps
// Complete selected production top, reset/CSR/maintenance smoke only; no force.
module hap_m003_selected_production_smoke_tb;
reg clk=0,d0=0,d1=0;always #5 clk=~clk;always #2.5 d0=~d0;initial begin #1.25;forever #2.5 d1=~d1;end
reg rst=0,clear=0,valid=0,ready=0;reg[11:0]addr=0;
wire arready,rvalid,error;wire[31:0]rdata;wire[1:0]rresp;integer checks=0;
hap_attention_mlp_production_core dut (
.core_clk(clk),
.core_rst_n(rst),
.core_clear(clear),
.ddr0_clk(d0),
.ddr0_rst_n(rst),
.ddr1_clk(d1),
.ddr1_rst_n(rst),
.ctrl_awaddr('0),
.ctrl_awvalid('0),
.ctrl_wdata('0),
.ctrl_wstrb('0),
.ctrl_wvalid('0),
.ctrl_bready('0),
.ctrl_araddr(addr),
.ctrl_arvalid(valid),
.ctrl_rready(ready),
.data_axi_arready('0),
.data_axi_rvalid('0),
.data_axi_rdata('0),
.data_axi_rresp('0),
.data_axi_rlast('0),
.data_axi_awready('0),
.data_axi_wready('0),
.data_axi_bvalid('0),
.data_axi_bresp('0),
.mlp_data_axi_arready('0),
.mlp_data_axi_rvalid('0),
.mlp_data_axi_rdata('0),
.mlp_data_axi_rresp('0),
.mlp_data_axi_rlast('0),
.mlp_data_axi_awready('0),
.mlp_data_axi_wready('0),
.mlp_data_axi_bvalid('0),
.mlp_data_axi_bresp('0),
.ddr0_axi_arready('0),
.ddr0_axi_rvalid('0),
.ddr0_axi_rdata('0),
.ddr0_axi_rresp('0),
.ddr0_axi_rlast('0),
.ddr1_axi_arready('0),
.ddr1_axi_rvalid('0),
.ddr1_axi_rdata('0),
.ddr1_axi_rresp('0),
.ddr1_axi_rlast('0),
.ctrl_arready(arready),
.ctrl_rdata(rdata),
.ctrl_rresp(rresp),
.ctrl_rvalid(rvalid),
.integration_error(error));
task automatic read_csr(input [11:0] a,input [31:0] expected);
integer n;reg[31:0]held;begin
 @(negedge clk);addr=a;valid=1;ready=0;n=0;
 do begin @(posedge clk);n=n+1;if(n>100)$fatal(1,"AR timeout");end while(!arready);
 @(negedge clk);valid=0;n=0;
 while(!rvalid)begin @(negedge clk);n=n+1;if(n>100)$fatal(1,"R timeout");end
 held=rdata;
 repeat(3)begin @(negedge clk);if(!rvalid||rdata!==held||rresp!==0)$fatal(1,"CSR response stability");end
 if(rdata!==expected)$fatal(1,"CSR identity mismatch %h %h",a,rdata);
 ready=1;@(negedge clk);ready=0;checks=checks+1;
end endtask
initial begin
 repeat(5)@(negedge clk);rst=1;repeat(30)@(negedge clk);
 if(dut.u_compute.u_attention.u_meta.LOCAL_ADDR_COPIES!=1)$fatal(1,"A3 production mode absent");
 if(dut.u_compute.u_mlp.u_serial_command.u_shared_compute.TILE_W!=9)$fatal(1,"M2 production width absent");
 read_csr(12'h000,32'h48384103);read_csr(12'h004,32'h00020000);
 read_csr(12'h100,32'h48384605);read_csr(12'h104,32'h00050000);
 @(negedge clk);clear=1;@(negedge clk);clear=0;
 repeat(100)@(negedge clk);
 if(error!==0)$fatal(1,"post maintenance production health");
 read_csr(12'h000,32'h48384103);read_csr(12'h100,32'h48384605);
 if(checks!=6)$fatal(1,"smoke scope missing");
 $display("M003_PRODUCTION_SMOKE checks=%0d A3_mode1 M2_TILE9 asynchronous_DDR_clocks maintenance",checks);
 $display("HARDWARE_AGENT_SIM_PASS");$finish;
end
endmodule
