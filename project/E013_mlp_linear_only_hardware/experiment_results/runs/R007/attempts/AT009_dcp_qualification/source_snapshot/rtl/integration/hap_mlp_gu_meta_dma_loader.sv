`timescale 1ns/1ps
// GU-only padded32B metadata reader, validated28B contents and full drain on padding fault.
module hap_mlp_gu_meta_dma_loader #(
    parameter integer GATE_RECORDS=229376,
    parameter integer GATE_ADDR_W=18,
    parameter integer PRODUCTION_SHAPE=1
) (
    input wire clk,input wire rst_n,input wire clear,
    input wire start_valid,output wire start_ready,input wire target_bank,
    input wire [31:0] gate_base_addr,
    output wire bank_load_begin_valid,input wire bank_load_begin_ready,
    output wire bank_load_begin_bank,
    output wire gate_wr_valid,input wire gate_wr_ready,output wire gate_wr_bank,
    output wire [GATE_ADDR_W-1:0] gate_wr_addr,output wire [223:0] gate_wr_meta,
    output wire busy,output reg done,output reg error,output wire [2:0] phase,
    output reg [31:0] gate_record_count,
    output reg [63:0] physical_bytes,
    output reg load_fault_valid,output wire load_fault_bank,output wire [31:0] error_code,
    output wire m_axi_arvalid,input wire m_axi_arready,
    output wire [31:0] m_axi_araddr,output wire [7:0] m_axi_arlen,
    output wire [2:0] m_axi_arsize,output wire [1:0] m_axi_arburst,
    input wire m_axi_rvalid,output wire m_axi_rready,input wire [255:0] m_axi_rdata,
    input wire [1:0] m_axi_rresp,input wire m_axi_rlast,
    output wire m_axi_awvalid,input wire m_axi_awready,output wire [31:0]m_axi_awaddr,
    output wire [7:0]m_axi_awlen,output wire [2:0]m_axi_awsize,
    output wire [1:0]m_axi_awburst,output wire m_axi_wvalid,input wire m_axi_wready,
    output wire [255:0]m_axi_wdata,output wire [31:0]m_axi_wstrb,
    output wire m_axi_wlast,input wire m_axi_bvalid,output wire m_axi_bready,
    input wire [1:0]m_axi_bresp
);
 localparam[2:0]P_IDLE=0,P_BEGIN=1,P_GATE_CMD=2,P_GATE=3;
 reg[2:0]state_r;reg target_bank_r;reg[31:0]gate_base_r;
 wire dma_cmd_valid=state_r==P_GATE_CMD;
 wire dma_cmd_ready,dma_busy,dma_done,dma_error;
 wire dma_rd_valid,dma_rd_ready,dma_rd_last;wire[255:0]dma_rd_data;
 wire dma_wr_ready;
 wire padding_ok=dma_rd_data[255:224]==0;
 wire read_fire=dma_rd_valid&&dma_rd_ready;
 wire write_fire=gate_wr_valid&&gate_wr_ready;
 assign start_ready=rst_n&&!clear&&!error&&state_r==P_IDLE;
 assign busy=state_r!=P_IDLE||dma_busy;
 assign phase=state_r;
 assign load_fault_bank=target_bank_r;
 assign error_code=error?32'h2120:0;
 assign bank_load_begin_valid=state_r==P_BEGIN;
 assign bank_load_begin_bank=target_bank_r;
 assign gate_wr_valid=state_r==P_GATE&&dma_rd_valid&&!error&&!dma_error&&padding_ok;
 assign dma_rd_ready=state_r==P_GATE&&((error||dma_error||!padding_ok)?1'b1:gate_wr_ready);
 assign gate_wr_bank=target_bank_r;
 assign gate_wr_addr=gate_record_count[GATE_ADDR_W-1:0];
 assign gate_wr_meta=dma_rd_data[223:0];
 hap_axi256_dma u_dma(.clk(clk),.rst_n(rst_n),.clear(clear),.cmd_valid(dma_cmd_valid),
  .cmd_ready(dma_cmd_ready),.cmd_write(1'b0),
  .cmd_base_addr(gate_base_r),
  .cmd_beat_count(GATE_RECORDS),
  .busy(dma_busy),.done(dma_done),.error(dma_error),.rd_valid(dma_rd_valid),
  .rd_ready(dma_rd_ready),.rd_data(dma_rd_data),.rd_last(dma_rd_last),
  .wr_valid(1'b0),.wr_ready(dma_wr_ready),.wr_data(256'd0),
  .m_axi_arvalid(m_axi_arvalid),.m_axi_arready(m_axi_arready),.m_axi_araddr(m_axi_araddr),
  .m_axi_arlen(m_axi_arlen),.m_axi_arsize(m_axi_arsize),.m_axi_arburst(m_axi_arburst),
  .m_axi_rvalid(m_axi_rvalid),.m_axi_rready(m_axi_rready),.m_axi_rdata(m_axi_rdata),
  .m_axi_rresp(m_axi_rresp),.m_axi_rlast(m_axi_rlast),.m_axi_awvalid(m_axi_awvalid),
  .m_axi_awready(m_axi_awready),.m_axi_awaddr(m_axi_awaddr),.m_axi_awlen(m_axi_awlen),
  .m_axi_awsize(m_axi_awsize),.m_axi_awburst(m_axi_awburst),.m_axi_wvalid(m_axi_wvalid),
  .m_axi_wready(m_axi_wready),.m_axi_wdata(m_axi_wdata),.m_axi_wstrb(m_axi_wstrb),
  .m_axi_wlast(m_axi_wlast),.m_axi_bvalid(m_axi_bvalid),.m_axi_bready(m_axi_bready),
  .m_axi_bresp(m_axi_bresp),.command_count(),.read_beat_count(),.write_beat_count(),
  .burst_count(),.protocol_error_count());
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   state_r<=P_IDLE;target_bank_r<=0;gate_base_r<=0;gate_record_count<=0;
   physical_bytes<=0;done<=0;error<=0;load_fault_valid<=0;
  end else if(clear)begin
   state_r<=P_IDLE;gate_record_count<=0;physical_bytes<=0;done<=0;error<=0;load_fault_valid<=0;
  end else begin
   done<=0;load_fault_valid<=0;
   if(dma_error)begin error<=1;if(!error)load_fault_valid<=1;end
   if(read_fire)begin
    physical_bytes<=physical_bytes+32;
    if(!padding_ok&&!error)begin error<=1;load_fault_valid<=1;end
   end
   if(write_fire)gate_record_count<=gate_record_count+1'b1;
   case(state_r)
    P_IDLE:if(start_valid&&start_ready)begin
     target_bank_r<=target_bank;gate_base_r<=gate_base_addr;gate_record_count<=0;
     physical_bytes<=0;state_r<=P_BEGIN;
    end
    P_BEGIN:if(bank_load_begin_valid&&bank_load_begin_ready)state_r<=P_GATE_CMD;
    P_GATE_CMD:if(dma_cmd_valid&&dma_cmd_ready)state_r<=P_GATE;
    P_GATE:if(dma_done)begin
     if(gate_record_count!=GATE_RECORDS&&!error)begin error<=1;load_fault_valid<=1;end
     state_r<=P_IDLE;done<=1;
    end
    default:begin state_r<=P_IDLE;error<=1;load_fault_valid<=1;end
   endcase
  end
 end
 initial begin
  if(PRODUCTION_SHAPE&&(GATE_RECORDS!=229376||GATE_ADDR_W!=18))$error("GU metadata loader production shape");
  if(GATE_RECORDS<=0||GATE_RECORDS>229376||GATE_ADDR_W!=18)$error("GU metadata loader structural shape");
 end
endmodule
