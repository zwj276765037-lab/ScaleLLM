`timescale 1ns / 1ps

// Preserve the native 72/72/72/8-bit URAM width domains. Only narrow address
// and enable replicas are added; each write payload bit still has one capture.
(* KEEP_HIERARCHY = "yes" *)
module hap_mlp_gu_weight_meta_uram_width_local #(
    parameter integer DEPTH = 229376,
    parameter integer ADDR_W = 18,
    parameter integer WIDTH = 72
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  wr_fire,
    input  wire [ADDR_W-1:0]     wr_addr,
    input  wire [WIDTH-1:0]      wr_data,
    output wire                  write_pending,
    input  wire                  rd_fire,
    input  wire [ADDR_W-1:0]     rd_addr,
    output wire                  read_landing,
    output reg  [WIDTH-1:0]      rd_data
);
    (* ram_style = "ultra" *) reg [WIDTH-1:0] mem [0:DEPTH-1];
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg wr_en_local_r,rd_en_local_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [ADDR_W-1:0] wr_addr_local_r,rd_addr_local_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [WIDTH-1:0] wr_data_local_r;
    assign write_pending=wr_en_local_r;
    assign read_landing=rd_en_local_r;

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            wr_en_local_r<=1'b0;
            rd_en_local_r<=1'b0;
        end else if(clear) begin
            wr_en_local_r<=1'b0;
            rd_en_local_r<=1'b0;
        end else begin
            wr_en_local_r<=wr_fire;
            rd_en_local_r<=rd_fire;
        end
    end
    always @(posedge clk) begin
        if(wr_fire) begin
            wr_addr_local_r<=wr_addr;
            wr_data_local_r<=wr_data;
        end
        if(rd_fire)
            rd_addr_local_r<=rd_addr;
        if(wr_en_local_r && rst_n && !clear)
            mem[wr_addr_local_r]<=wr_data_local_r;
        if(rd_en_local_r && rst_n && !clear)
            rd_data<=mem[rd_addr_local_r];
    end
endmodule

// Four aligned width domains share one ordered response owner. Four credits
// hide the added request stage without a consumer-ready-to-URAM bypass.
module hap_mlp_gu_weight_meta_uram_leaf #(
    parameter integer DEPTH = 229376,
    parameter integer ADDR_W = 18,
    parameter integer BANK_ID = 0
) (
    input  wire                   clk,
    input  wire                   wr_valid,
    input  wire                   wr_bank,
    input  wire [ADDR_W-1:0]      wr_addr,
    input  wire [223:0]           wr_data,
    input  wire                   rst_n,
    input  wire                   clear,
    input  wire                   rd_valid,
    output wire                   rd_ready,
    input  wire [ADDR_W-1:0]      rd_addr,
    output wire                   rsp_valid,
    input  wire                   rsp_ready,
    output wire [223:0]           rsp_data,
    output wire                   response_idle,
    output wire                   write_idle
);
    wire [223:0] rd_data_uram_r;
    wire [3:0] width_write_pending,width_read_landing;
    (* ram_style = "registers", shreg_extract = "no" *)
    reg [223:0] rsp_fifo_slot0_r,rsp_fifo_slot1_r,rsp_fifo_slot2_r;
    reg [1:0] rsp_fifo_wr_ptr_r,rsp_fifo_rd_ptr_r;
    reg [1:0] rsp_fifo_count_r;
    reg rd_pending_r;
    reg [2:0] outstanding_count_r;

    wire wr_fire = rst_n && !clear && wr_valid && (wr_bank == BANK_ID[0]);
    wire rd_fire = rd_valid && rd_ready;
    wire rsp_fire = rsp_valid && rsp_ready;
    wire capture_ready = rsp_fifo_count_r < 3 || rsp_fire;
    wire capture_fire = rd_pending_r && capture_ready;
    wire read_landing = width_read_landing[0];

    assign rd_ready = rst_n && !clear && outstanding_count_r < 4;
    assign rsp_valid = rst_n && !clear && rsp_fifo_count_r != 0;
    assign rsp_data = rsp_fifo_rd_ptr_r == 0 ? rsp_fifo_slot0_r :
        rsp_fifo_rd_ptr_r == 1 ? rsp_fifo_slot1_r : rsp_fifo_slot2_r;
    assign response_idle = outstanding_count_r == 0 &&
        rsp_fifo_count_r == 0 && !rd_pending_r && !(|width_read_landing);
    assign write_idle = !(|width_write_pending);

    genvar width_index;
    generate for(width_index=0;width_index<4;width_index=width_index+1) begin : g_width
        localparam integer WIDTH = width_index==3 ? 8 : 72;
        (* KEEP_HIERARCHY = "yes" *)
        hap_mlp_gu_weight_meta_uram_width_local #(
            .DEPTH(DEPTH),.ADDR_W(ADDR_W),.WIDTH(WIDTH)
        ) u_width_local (
            .clk(clk),.rst_n(rst_n),.clear(clear),.wr_fire(wr_fire),
            .wr_addr(wr_addr),.wr_data(wr_data[width_index*72+:WIDTH]),
            .write_pending(width_write_pending[width_index]),
            .rd_fire(rd_fire),.rd_addr(rd_addr),
            .read_landing(width_read_landing[width_index]),
            .rd_data(rd_data_uram_r[width_index*72+:WIDTH])
        );
    end endgenerate

    // Payload slots intentionally have no reset.  Reset/clear invalidate the
    // registered occupancy before any slot can be observed, and every visible
    // slot is written before its count increments.
    always @(posedge clk) begin
        if (capture_fire) begin
            case(rsp_fifo_wr_ptr_r)
                0: rsp_fifo_slot0_r <= rd_data_uram_r;
                1: rsp_fifo_slot1_r <= rd_data_uram_r;
                2: rsp_fifo_slot2_r <= rd_data_uram_r;
            endcase
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rsp_fifo_wr_ptr_r <= 2'd0;
            rsp_fifo_rd_ptr_r <= 2'd0;
            rsp_fifo_count_r <= 2'd0;
            rd_pending_r <= 1'b0;
            outstanding_count_r <= 3'd0;
        end else if (clear) begin
            rsp_fifo_wr_ptr_r <= 2'd0;
            rsp_fifo_rd_ptr_r <= 2'd0;
            rsp_fifo_count_r <= 2'd0;
            rd_pending_r <= 1'b0;
            outstanding_count_r <= 3'd0;
        end else begin
            if (capture_fire)
                rsp_fifo_wr_ptr_r <= rsp_fifo_wr_ptr_r==2 ? 2'd0 : rsp_fifo_wr_ptr_r+1'b1;
            if (rsp_fire)
                rsp_fifo_rd_ptr_r <= rsp_fifo_rd_ptr_r==2 ? 2'd0 : rsp_fifo_rd_ptr_r+1'b1;
            case ({capture_fire,rsp_fire})
                2'b10: rsp_fifo_count_r <= rsp_fifo_count_r + 1'b1;
                2'b01: rsp_fifo_count_r <= rsp_fifo_count_r - 1'b1;
                default: rsp_fifo_count_r <= rsp_fifo_count_r;
            endcase

            // A blocked result plus three full slots exhausts all four
            // credits, so no forward request can overwrite that result.
            if (capture_fire)
                rd_pending_r <= 1'b0;
            if (read_landing)
                rd_pending_r <= 1'b1;

            case ({rd_fire,rsp_fire})
                2'b10: outstanding_count_r <= outstanding_count_r + 1'b1;
                2'b01: outstanding_count_r <= outstanding_count_r - 1'b1;
                default: outstanding_count_r <= outstanding_count_r;
            endcase
        end
    end
`ifndef SYNTHESIS
    always @(posedge clk) if(rst_n && !clear) begin
        if(width_write_pending !== {4{width_write_pending[0]}} ||
           width_read_landing !== {4{width_read_landing[0]}})
            $error("metadata width-domain control misalignment");
        if(read_landing && rd_pending_r && !capture_fire)
            $error("metadata reserved-credit result overwrite");
        if(outstanding_count_r != rsp_fifo_count_r + rd_pending_r + read_landing)
            $error("metadata read credit conservation failure");
    end
`endif
endmodule

// Two resident MLP metadata images.  Gate/up and down have independent read
// ports because their physical schedules and address widths differ.  The
// inactive bank can be loaded through the two write ports while the active
// bank serves the current layer.  A bank becomes selectable only after both
// exact write counts have been observed and software commits its generation.
module hap_mlp_gu_weight_meta_resident_ab #(
    parameter integer GATE_DEPTH = 229376,
    parameter integer GATE_ADDR_W = 18,
    parameter integer PRODUCTION_SHAPE = 1
) (
    input  wire                       clk,
    input  wire                       rst_n,
    input  wire                       clear,
    input wire load_fault_valid,input wire load_fault_bank,

    input  wire                       load_begin_valid,
    output wire                       load_begin_ready,
    input  wire                       load_begin_bank,

    input  wire                       gate_wr_valid,
    output wire                       gate_wr_ready,
    input  wire                       gate_wr_bank,
    input  wire [GATE_ADDR_W-1:0]     gate_wr_addr,
    input  wire [223:0]               gate_wr_meta_u224,

    input  wire                       commit_valid,
    output wire                       commit_ready,
    input  wire                       commit_bank,
    input  wire [31:0]                commit_generation,
    input  wire                       consumer_quiescent,
    output reg                        active_bank,
    output reg  [31:0]                active_generation,
    output reg  [1:0]                 bank_valid,
    output reg  [1:0]                 bank_loading,

    input  wire                       gate_rd_valid,
    output wire                       gate_rd_ready,
    input  wire [GATE_ADDR_W-1:0]     gate_rd_addr,
    output wire                       gate_rsp_valid,
    input  wire                       gate_rsp_ready,
    output wire [223:0]               gate_rsp_meta_u224,

    output reg  [31:0]                gate_write_count_bank0,
    output reg  [31:0]                gate_write_count_bank1,
    output reg  [31:0]                gate_read_count,
    output wire                       quiescent,
    output reg                        error
);
 wire[223:0]gate_bank0_rsp_data,gate_bank1_rsp_data;
 wire gate_bank0_rd_ready,gate_bank1_rd_ready,gate_bank0_rsp_valid,gate_bank1_rsp_valid;
 wire gate_bank0_idle,gate_bank1_idle,gate_bank0_write_idle,gate_bank1_write_idle;
 assign quiescent=gate_bank0_idle&&gate_bank1_idle&&gate_bank0_write_idle&&gate_bank1_write_idle;
 wire gate_read_allowed=rst_n&&!clear&&bank_valid[active_bank]&&gate_rd_addr<GATE_DEPTH;
 wire gate_wr_fire=gate_wr_valid&&gate_wr_ready;
 wire gate_rsp_fire=gate_rsp_valid&&gate_rsp_ready;
 wire load_begin_fire=load_begin_valid&&load_begin_ready;
 wire commit_fire=commit_valid&&commit_ready;
 wire[31:0]selected_gate_write_count=commit_bank?gate_write_count_bank1:gate_write_count_bank0;
 wire[31:0]gate_target_write_count=gate_wr_bank?gate_write_count_bank1:gate_write_count_bank0;
 assign load_begin_ready=rst_n&&!clear&&!error&&!load_fault_valid&&
   load_begin_bank!=active_bank&&!bank_loading[load_begin_bank];
 assign gate_wr_ready=rst_n&&!clear&&!error&&!load_fault_valid&&gate_wr_bank!=active_bank&&
   bank_loading[gate_wr_bank]&&gate_target_write_count<GATE_DEPTH&&gate_wr_addr<GATE_DEPTH&&
   gate_wr_addr==gate_target_write_count[GATE_ADDR_W-1:0];
 assign commit_ready=rst_n&&!clear&&!error&&!load_fault_valid&&commit_bank!=active_bank&&
   bank_loading[commit_bank]&&selected_gate_write_count==GATE_DEPTH&&consumer_quiescent&&
   !gate_rd_valid&&gate_bank0_idle&&gate_bank1_idle&&
   (commit_bank?gate_bank1_write_idle:gate_bank0_write_idle);
 assign gate_rd_ready=gate_read_allowed&&(active_bank?gate_bank1_rd_ready:gate_bank0_rd_ready);
 assign gate_rsp_valid=rst_n&&!clear&&(active_bank?gate_bank1_rsp_valid:gate_bank0_rsp_valid);
 assign gate_rsp_meta_u224=active_bank?gate_bank1_rsp_data:gate_bank0_rsp_data;
 hap_mlp_gu_weight_meta_uram_leaf #(.DEPTH(GATE_DEPTH),.ADDR_W(GATE_ADDR_W),.BANK_ID(0)) u_gate_bank0(
 .clk(clk),.wr_valid(gate_wr_fire),.wr_bank(gate_wr_bank),.wr_addr(gate_wr_addr),.wr_data(gate_wr_meta_u224),
 .rst_n(rst_n),.clear(clear),.rd_valid(gate_rd_valid&&gate_read_allowed&&active_bank==1'b0),
 .rd_ready(gate_bank0_rd_ready),.rd_addr(gate_rd_addr),.rsp_valid(gate_bank0_rsp_valid),
 .rsp_ready(gate_rsp_ready&&active_bank==1'b0),.rsp_data(gate_bank0_rsp_data),
 .response_idle(gate_bank0_idle),.write_idle(gate_bank0_write_idle));
 hap_mlp_gu_weight_meta_uram_leaf #(.DEPTH(GATE_DEPTH),.ADDR_W(GATE_ADDR_W),.BANK_ID(1)) u_gate_bank1(
 .clk(clk),.wr_valid(gate_wr_fire),.wr_bank(gate_wr_bank),.wr_addr(gate_wr_addr),.wr_data(gate_wr_meta_u224),
 .rst_n(rst_n),.clear(clear),.rd_valid(gate_rd_valid&&gate_read_allowed&&active_bank==1'b1),
 .rd_ready(gate_bank1_rd_ready),.rd_addr(gate_rd_addr),.rsp_valid(gate_bank1_rsp_valid),
 .rsp_ready(gate_rsp_ready&&active_bank==1'b1),.rsp_data(gate_bank1_rsp_data),
 .response_idle(gate_bank1_idle),.write_idle(gate_bank1_write_idle));

 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   active_bank<=0;active_generation<=0;bank_valid<=0;bank_loading<=0;
   gate_write_count_bank0<=0;gate_write_count_bank1<=0;gate_read_count<=0;error<=0;
  end else if(clear)begin
   active_bank<=0;active_generation<=0;bank_valid<=0;bank_loading<=0;
   gate_write_count_bank0<=0;gate_write_count_bank1<=0;gate_read_count<=0;error<=0;
  end else begin
   if(load_begin_fire)begin
    bank_valid[load_begin_bank]<=0;bank_loading[load_begin_bank]<=1;
    if(load_begin_bank)gate_write_count_bank1<=0;else gate_write_count_bank0<=0;
   end
   if(gate_wr_fire)begin
    bank_valid[gate_wr_bank]<=0;
    if(gate_wr_bank)gate_write_count_bank1<=gate_write_count_bank1+1'b1;
    else gate_write_count_bank0<=gate_write_count_bank0+1'b1;
   end
   if(gate_rsp_fire)gate_read_count<=gate_read_count+1'b1;
   if(commit_fire)begin
    active_bank<=commit_bank;active_generation<=commit_generation;
    bank_valid[commit_bank]<=1;bank_loading[commit_bank]<=0;
   end
   // A failed inactive load cannot corrupt or activate the existing bank.
   // The global metadata fault revokes epoch eligibility in job_control.
   if(load_fault_valid)begin
    error<=1;
    if(load_fault_bank!=active_bank)begin
     bank_valid[load_fault_bank]<=0;bank_loading[load_fault_bank]<=0;
    end
   end
   if((gate_wr_valid&&gate_wr_bank==active_bank)||(gate_wr_valid&&gate_wr_addr>=GATE_DEPTH)||
      (gate_wr_valid&&bank_loading[gate_wr_bank]&&gate_wr_addr!=gate_target_write_count[GATE_ADDR_W-1:0])||
      (gate_rd_valid&&gate_rd_addr>=GATE_DEPTH)||(load_begin_valid&&load_begin_bank==active_bank))error<=1;
  end
 end
 initial begin
  if(PRODUCTION_SHAPE&&(GATE_DEPTH!=229376||GATE_ADDR_W!=18))$error("GU metadata resident production shape");
  if(GATE_DEPTH<=0||GATE_DEPTH>229376||GATE_ADDR_W!=18)$error("GU metadata resident structural shape");
 end
endmodule
