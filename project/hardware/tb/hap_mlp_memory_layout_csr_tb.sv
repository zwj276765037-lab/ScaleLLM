`timescale 1ns / 1ps
module hap_mlp_memory_layout_csr_tb;
 reg clk=0,rst_n=0;always #5 clk=~clk;
 reg[11:0]awaddr=0,araddr=0;reg[31:0]wdata=0;
 reg[3:0]wstrb=0;reg awvalid=0,wvalid=0,arvalid=0,bready=0,rready=0;
 wire awready,wready,arready,bvalid,rvalid;wire[1:0]bresp,rresp;wire[31:0]rdata;
 integer checks=0;
 hap_mlp_axil_control dut(
 .clk(clk),
 .rst_n(rst_n),
 .s_axil_awaddr(awaddr),
 .s_axil_awvalid(awvalid),
 .s_axil_awready(awready),
 .s_axil_wdata(wdata),
 .s_axil_wstrb(wstrb),
 .s_axil_wvalid(wvalid),
 .s_axil_wready(wready),
 .s_axil_bresp(bresp),
 .s_axil_bvalid(bvalid),
 .s_axil_bready(bready),
 .s_axil_araddr(araddr),
 .s_axil_arvalid(arvalid),
 .s_axil_arready(arready),
 .s_axil_rdata(rdata),
 .s_axil_rresp(rresp),
 .s_axil_rvalid(rvalid),
 .s_axil_rready(rready),
 .owner_request_valid(),
 .owner_request_ready('0),
 .admission_pause('0),
 .owner_request(),
 .owner_request_done('0),
 .active_owner('0),
 .owner_switch_pending('0),
 .attention_launch_enable('0),
 .mlp_launch_enable('0),
 .owner_protocol_error('0),
 .ddr0_outstanding('0),
 .ddr1_outstanding('0),
 .maintenance_busy('0),
 .maintenance_request_pending('0),
 .mlp_abort_complete('0),
 .paired_quiescent('0),
 .paired_attn_bursts('0),
 .paired_mlp_bursts('0),
 .paired_both_cycles('0),
 .paired_hol0('0),
 .paired_hol1('0),
 .paired_hwm0('0),
 .paired_hwm1('0),
 .mlp_command_valid(),
 .mlp_command_ready('0),
 .mlp_clear_pulse(),
 .mlp_abort_pending(),
 .mlp_command_bank(),
 .mlp_gate_ddr0_base_addr(),
 .mlp_gate_ddr1_base_addr(),
 .mlp_down_ddr0_base_addr(),
 .mlp_down_ddr1_base_addr(),
 .mlp_input_base_addr(),
 .mlp_output_base_addr(),
 .mlp_command_id(),
 .mlp_layer_id(),
 .mlp_input_bank_ready('0),
 .mlp_busy('0),
 .mlp_done('0),
 .mlp_error('0),
 .mlp_phase('0),
 .mlp_telemetry('0),
 .mlp_down_output_saturation_count('0),
 .mlp_total_shift_format_count('0),
 .mlp_numeric_status('0),
 .tensor_load_valid(),
 .tensor_load_ready('0),
 .tensor_store_valid(),
 .tensor_store_ready('0),
 .tensor_store_armed('0),
 .tensor_dma_busy('0),
 .tensor_dma_done('0),
 .tensor_dma_error('0),
 .tensor_dma_phase('0),
 .tensor_input_beat_count('0),
 .tensor_input_group_count('0),
 .tensor_output_beat_count('0),
 .tensor_output_tile_count('0),
 .meta_gate_base_addr(),
 .meta_down_base_addr(),
 .meta_dma_busy('0),
 .meta_dma_done('0),
 .meta_dma_error('0),
 .meta_dma_phase('0),
 .meta_dma_gate_record_count('0),
 .meta_dma_down_record_count('0),
 .meta_dma_physical_bytes('0),
 .meta_load_begin_valid(),
 .meta_load_begin_ready('0),
 .meta_load_bank(),
 .meta_commit_valid(),
 .meta_commit_ready('0),
 .meta_commit_bank(),
 .meta_commit_generation(),
 .meta_active_bank('0),
 .meta_active_generation('0),
 .meta_bank_valid('0),
 .meta_bank_loading('0),
 .meta_gate_write_count_bank0('0),
 .meta_gate_write_count_bank1('0),
 .meta_down_write_count_bank0('0),
 .meta_down_write_count_bank1('0),
 .meta_error('0),
 .irq(),
 .done_sticky(),
 .error_sticky());
 task automatic rd(input[11:0]a,input[31:0]expected);
 begin
 @(negedge clk);araddr=a;arvalid=1;
 do @(posedge clk);while(!arready);
 @(negedge clk);arvalid=0;
 while(!rvalid)@(negedge clk);
 // Exercise a stalled read response and ensure payload remains stable.
 repeat(5)begin @(negedge clk);
 if(!rvalid||rdata!==expected||rresp!==0)$fatal(1,"CSR read/stability addr=%h got=%h expected=%h",a,rdata,expected);end
 rready=1;@(negedge clk);rready=0;checks=checks+1;
 end endtask
 task automatic reject_write(input[3:0]strobes);
 begin
 @(negedge clk);awaddr=12'h2b8;wdata=32'hdeadbeef;wstrb=strobes;awvalid=1;
 do @(posedge clk);while(!awready);
 @(negedge clk);awvalid=0;
 repeat(3)@(negedge clk);wvalid=1;
 do @(posedge clk);while(!wready);
 @(negedge clk);wvalid=0;
 while(!bvalid)@(negedge clk);
 repeat(3)begin @(negedge clk);if(!bvalid||bresp!==2)$fatal(1,"layout CSR write accepted");end
 bready=1;@(negedge clk);bready=0;checks=checks+1;
 end endtask
 initial begin
 repeat(5)@(negedge clk);rst_n=1;
 rd(12'h100,32'h48384605);rd(12'h104,32'h00050000);
 rd(12'h2b8,32'h4d303032);
 reject_write(4'hf);rd(12'h2b8,32'h4d303032);
 reject_write(4'h1);rd(12'h2b8,32'h4d303032);
 reject_write(4'h0);rd(12'h2b8,32'h4d303032);
 rst_n=0;repeat(5)@(negedge clk);rst_n=1;rd(12'h2b8,32'h4d303032);
 $display("PASS hap_mlp_memory_layout_csr checks=%0d",checks);
 $display("HARDWARE_AGENT_SIM_PASS");$finish;
 end
 initial begin #100000;$fatal(1,"layout CSR global timeout");end
endmodule
