`timescale 1ns / 1ps
// Single-command A8 ownership. Payload is never reset; validity is the owner.
module hap_mlp_gu_cache16 (
 input wire clk, input wire rst_n, input wire job_clear,
 input wire begin_valid, output wire begin_ready, input wire [1:0] begin_opcode,
 input wire wr_valid, output wire wr_ready, input wire [8:0] wr_group,
 input wire [4095:0] wr_u8x16x32, input wire [383:0] wr_meta_u24x16,
 input wire seal_valid, output wire seal_ready, output reg sealed,
 input wire rd_req_valid, output wire rd_req_ready, input wire [8:0] rd_req_group,
 output wire rd_rsp_valid, input wire rd_rsp_ready, output reg [8:0] rd_rsp_group,
 output wire [4095:0] rd_rsp_u8x16x32, output wire [383:0] rd_rsp_meta_u24x16,
 output reg [8:0] write_count, output reg [8:0] expected_groups,
 output reg owned, output wire quiescent, output reg error, output reg [31:0] error_code
);
 localparam [31:0] E_OPCODE=32'h1010, E_GROUP=32'h2010, E_SEAL=32'h2011;
 wire [279:0] bank_data[0:15];
 reg pending;
 reg rsp_valid;
 reg [8:0] pending_group;
 (* DONT_TOUCH="yes" *) reg [15:0] capture_pending;
 wire wr_fire=wr_valid&&wr_ready;
 wire wr_legal=wr_group<128 && wr_group==write_count && write_count<128;
 wire read_fire=rd_req_valid&&rd_req_ready;
 wire read_legal=rd_req_group<128;
 assign begin_ready=rst_n&&!job_clear&&!owned&&!pending&&!rsp_valid&&!error;
 assign wr_ready=rst_n&&!job_clear&&owned&&!sealed&&!error&&!seal_valid;
 // Accept a premature seal and report its error instead of hanging the sender.
 assign seal_ready=rst_n&&!job_clear&&owned&&!sealed&&!error&&!wr_valid;
 assign rd_req_ready=rst_n&&!job_clear&&owned&&sealed&&!error&&!pending&&(!rsp_valid||rd_rsp_ready);
 assign rd_rsp_valid=rst_n&&!job_clear&&rsp_valid;
 assign quiescent=!pending&&!rsp_valid;
 genvar row;
 generate for(row=0;row<16;row=row+1)begin:gen_row
  (* ram_style="block" *) reg [279:0] memory[0:127];
  reg [279:0] read_data;
  reg [279:0] response_data;
  always @(posedge clk)begin
   if(wr_fire&&wr_legal)memory[wr_group[6:0]]<={wr_meta_u24x16[row*24+:24],wr_u8x16x32[row*256+:256]};
   if(read_fire&&read_legal)read_data<=memory[rd_req_group[6:0]];
   if(capture_pending[row])response_data<=read_data;
  end
  assign bank_data[row]=response_data;
  assign rd_rsp_u8x16x32[row*256+:256]=bank_data[row][255:0];
  assign rd_rsp_meta_u24x16[row*24+:24]=bank_data[row][279:256];
 end endgenerate
 always @(posedge clk)begin
  if(!rst_n||job_clear)begin
   sealed<=0; owned<=0; pending<=0; rsp_valid<=0; capture_pending<=0;
   rd_rsp_group<=0; pending_group<=0; write_count<=0; expected_groups<=0; error<=0;error_code<=0;
  end else begin
   capture_pending<={16{read_fire&&read_legal}};
   if(rd_rsp_valid&&rd_rsp_ready)rsp_valid<=0;
   if(pending)begin rsp_valid<=1;rd_rsp_group<=pending_group;pending<=0;end
   if(begin_valid&&begin_ready)begin
    if(begin_opcode==1)begin
     owned<=1;expected_groups<=9'd128;
    end else begin error<=1;error_code<=E_OPCODE;end
   end
   if(wr_fire)begin
    if(wr_legal)write_count<=write_count+1'b1;
    else begin error<=1;error_code<=E_GROUP;end
   end
   if(seal_valid&&seal_ready)begin
    if(write_count==expected_groups)sealed<=1;
    else begin error<=1;error_code<=E_SEAL;end
   end
   if(read_fire)begin
    if(read_legal)begin pending<=1;pending_group<=rd_req_group;end
    else begin error<=1;error_code<=32'h2012;end
   end
  end
 end
`ifndef SYNTHESIS
 always @(posedge clk)if(rst_n&&job_clear&&!quiescent)$error("cache job_clear before response drain");
`endif
endmodule
