`timescale 1ns / 1ps

// Small, non-fall-through asynchronous FIFO used only for narrow AXI read
// descriptors.  The XPM owns pointer CDC; no wide weight payload crosses this
// FIFO.  FWFT makes the descriptor stable until rd_ready accepts it.
module hap_v4_async_fifo #(
    parameter integer WIDTH = 45,
    parameter integer DEPTH = 16,
    parameter integer COUNT_W = $clog2(DEPTH+1)
) (
    input  wire                 wr_rst,
    input  wire                 rd_rst,
    input  wire                 wr_clk,
    input  wire                 wr_valid,
    output wire                 wr_ready,
    input  wire [WIDTH-1:0]     wr_data,
    input  wire                 rd_clk,
    output wire                 rd_valid,
    input  wire                 rd_ready,
    output wire [WIDTH-1:0]     rd_data,
    output wire                 wr_empty,
    output wire                 error
);
    wire full,empty,overflow,underflow,wr_rst_busy,rd_rst_busy;
    wire [COUNT_W-1:0]wr_data_count;
    reg overflow_sticky_r,underflow_sticky_r;
    wire overflow_sticky_rd;

    assign wr_ready=!wr_rst&&!full&&!wr_rst_busy;
    assign rd_valid=!rd_rst&&!empty&&!rd_rst_busy;
    assign wr_empty=!wr_rst&&!wr_rst_busy&&(wr_data_count==0);
    assign error=overflow_sticky_rd||underflow_sticky_r;

    always @(posedge wr_clk)begin
      if(wr_rst)overflow_sticky_r<=1'b0;
      else if(overflow)overflow_sticky_r<=1'b1;
    end
    always @(posedge rd_clk)begin
      if(rd_rst)underflow_sticky_r<=1'b0;
      else if(underflow)underflow_sticky_r<=1'b1;
    end
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(0))u_overflow_cdc(.src_clk(wr_clk),
      .src_in(overflow_sticky_r),.dest_clk(rd_clk),
      .dest_out(overflow_sticky_rd));

    xpm_fifo_async #(
      .FIFO_MEMORY_TYPE("distributed"),.ECC_MODE("no_ecc"),
      .RELATED_CLOCKS(0),.SIM_ASSERT_CHK(1),.FIFO_WRITE_DEPTH(DEPTH),
      .WRITE_DATA_WIDTH(WIDTH),.WR_DATA_COUNT_WIDTH(COUNT_W),
      .PROG_FULL_THRESH(DEPTH-3),.FULL_RESET_VALUE(0),
      .USE_ADV_FEATURES("0404"),.READ_MODE("fwft"),
      .FIFO_READ_LATENCY(0),.READ_DATA_WIDTH(WIDTH),
      .RD_DATA_COUNT_WIDTH(COUNT_W),.PROG_EMPTY_THRESH(3),
      .DOUT_RESET_VALUE("0"),.CDC_SYNC_STAGES(2),.WAKEUP_TIME(0)
    )u_fifo(
      .sleep(1'b0),.rst(wr_rst),.wr_clk(wr_clk),
      .wr_en(!wr_rst&&wr_valid&&wr_ready),.din(wr_data),.full(full),
      .prog_full(),.wr_data_count(wr_data_count),.overflow(overflow),
      .wr_rst_busy(wr_rst_busy),.almost_full(),.wr_ack(),
      .rd_clk(rd_clk),.rd_en(!rd_rst&&rd_valid&&rd_ready),.dout(rd_data),
      .empty(empty),.prog_empty(),.rd_data_count(),.underflow(underflow),
      .rd_rst_busy(rd_rst_busy),.almost_empty(),.data_valid(),
      .dbiterr(),.sbiterr(),.injectdbiterr(1'b0),.injectsbiterr(1'b0));

    initial begin
      if(DEPTH<16||(DEPTH&(DEPTH-1))!=0)
        $error("V4 descriptor FIFO depth must be a power of two >=16");
    end
endmodule

// One MIG-local ordered issue/response unit.  A descriptor has already been
// paired with the other MIG by the core scheduler.  Physical AR acceptance
// appends {owner,sequence,ARLEN}; ordered R beats are returned only to that
// owner until the exact expected RLAST.  A malformed response freezes this
// unit until hard reset so no later beat can be delivered to the wrong client.
module hap_axi512_ordered_local_issue #(
    parameter integer AXI_ADDR_W = 32,
    parameter integer SEQ_W = 16,
    parameter integer TAG_DEPTH = 32,
    parameter integer TAG_PTR_W = $clog2(TAG_DEPTH)
) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     hard_reset,
    input  wire                     soft_reset,
    input  wire                     enable,
    input  wire                     freeze,
    input  wire                     desc_valid,
    output wire                     desc_ready,
    input  wire [AXI_ADDR_W+13+SEQ_W:0] desc_data,

    output wire                     m_axi_arvalid,
    input  wire                     m_axi_arready,
    output wire [AXI_ADDR_W-1:0]    m_axi_araddr,
    output wire [7:0]               m_axi_arlen,
    output wire [2:0]               m_axi_arsize,
    output wire [1:0]               m_axi_arburst,
    input  wire                     m_axi_rvalid,
    output wire                     m_axi_rready,
    input  wire [511:0]             m_axi_rdata,
    input  wire [1:0]               m_axi_rresp,
    input  wire                     m_axi_rlast,

    output wire                     attn_rvalid,
    input  wire                     attn_rready,
    output wire [511:0]             attn_rdata,
    output wire [1:0]               attn_rresp,
    output wire                     attn_rlast,
    output wire                     mlp_rvalid,
    input  wire                     mlp_rready,
    output wire [511:0]             mlp_rdata,
    output wire [1:0]               mlp_rresp,
    output wire                     mlp_rlast,

    output wire                     quiescent,
    output wire                     protocol_error,
    output reg  [31:0]              physical_ar_count,
    output reg  [31:0]              physical_r_count,
    output reg  [31:0]              attn_burst_count,
    output reg  [31:0]              mlp_burst_count,
    output reg  [31:0]              hol_cycle_count,
    output wire [31:0]              tag_high_watermark
);
    localparam integer DESC_W=AXI_ADDR_W+13;
    localparam integer INGRESS_W=SEQ_W+DESC_W;
    localparam integer EGRESS_W=1+SEQ_W+DESC_W;
    localparam integer TAG_W=1+SEQ_W+8;
    localparam integer TAG_COUNT_W=$clog2(TAG_DEPTH+1);

    reg issue_valid_r;
    reg [EGRESS_W-1:0]issue_data_r;
    reg [SEQ_W-1:0]next_issue_seq_r;
    // The tag payload is deliberately not reset.  Validity is owned by
    // tag_count_r/pointers, so clearing every RAM bit only prevents LUTRAM
    // inference and creates an unnecessary high-fanout reset network.
    (* ram_style = "distributed" *) reg [TAG_W-1:0]tag_mem[0:TAG_DEPTH-1];
    reg [TAG_PTR_W-1:0]tag_wr_r,tag_rd_r;
    reg [TAG_COUNT_W-1:0]tag_count_r;
    reg [TAG_COUNT_W-1:0]tag_high_watermark_r;
    reg active_valid_r,active_owner_r;
    reg next_tag_valid_r,next_tag_owner_r;
    reg [SEQ_W-1:0]next_tag_seq_r;
    reg [7:0]next_tag_len_r;
    reg [SEQ_W-1:0]active_seq_r;
    reg [7:0]active_len_r;
    reg [7:0]response_beat_r;
    reg protocol_error_r;

    // Two non-fall-through MIG-local elastic entries per client.  The
    // physical R channel only sees registered occupancy; client RREADY never
    // participates in m_axi_rready, including on a full-FIFO pop cycle.
    reg [514:0]attn_head_r,attn_tail_r,mlp_head_r,mlp_tail_r;
    reg [1:0]attn_count_r,mlp_count_r;

    wire issue_owner=issue_data_r[EGRESS_W-1];
    wire [SEQ_W-1:0]issue_seq=issue_data_r[DESC_W+SEQ_W-1:DESC_W];
    wire [DESC_W-1:0]issue_desc=issue_data_r[DESC_W-1:0];
    wire [AXI_ADDR_W-1:0]issue_addr=issue_desc[DESC_W-1:13];
    wire [7:0]issue_len=issue_desc[12:5];
    wire [2:0]issue_size=issue_desc[4:2];
    wire [1:0]issue_burst=issue_desc[1:0];
    // tag_count_r counts the active tag, the prefetched next tag and every
    // tag still resident in tag_mem.  The prefetched entry removes the LUTRAM
    // read and tag-pointer controls from the final R-beat critical path.
    wire tag_full=tag_count_r==TAG_DEPTH;
    wire expected_last=response_beat_r==active_len_r;
    wire ar_fire=m_axi_arvalid&&m_axi_arready;
    wire selected_buffer_full=active_owner_r?(mlp_count_r==2):(attn_count_r==2);
    wire r_fire=m_axi_rvalid&&m_axi_rready;
    wire malformed=r_fire&&(m_axi_rresp!=2'b00||m_axi_rlast!=expected_last);
    wire good_r_push=r_fire&&!malformed;
    wire response_last_good=good_r_push&&expected_last&&m_axi_rlast;
    wire attn_push=good_r_push&&!active_owner_r;
    wire mlp_push=good_r_push&&active_owner_r;
    wire attn_pop=attn_rvalid&&attn_rready;
    wire mlp_pop=mlp_rvalid&&mlp_rready;
    wire [514:0]incoming_payload={m_axi_rlast,m_axi_rresp,m_axi_rdata};
    wire ar_load_active=ar_fire&&(tag_count_r==0||
        (response_last_good&&tag_count_r==1));
    wire ar_load_next=ar_fire&&!ar_load_active&&(!next_tag_valid_r||
        (response_last_good&&tag_count_r==2));
    wire tag_write=ar_fire&&!ar_load_active&&!ar_load_next;
    wire [TAG_W-1:0]tag_head=tag_mem[tag_rd_r];
    wire refill_next_from_mem=response_last_good&&next_tag_valid_r&&
        (tag_count_r>2);

    assign desc_ready=enable&&!freeze&&!soft_reset&&!protocol_error_r&&
        !issue_valid_r&&!tag_full;
    // Once VALID is presented, AXI requires it and its payload to remain
    // asserted through READY.  Freeze blocks new descriptors but cannot
    // retract an already committed AR transfer.
    assign m_axi_arvalid=issue_valid_r;
    assign m_axi_araddr=issue_addr;
    assign m_axi_arlen=issue_len;
    assign m_axi_arsize=issue_size;
    assign m_axi_arburst=issue_burst;
    assign attn_rvalid=!freeze&&!soft_reset&&!protocol_error_r&&
        (attn_count_r!=0);
    assign mlp_rvalid=!freeze&&!soft_reset&&!protocol_error_r&&
        (mlp_count_r!=0);
    assign attn_rdata=attn_head_r[511:0];
    assign mlp_rdata=mlp_head_r[511:0];
    assign attn_rresp=attn_head_r[513:512];
    assign mlp_rresp=mlp_head_r[513:512];
    assign attn_rlast=attn_head_r[514];
    assign mlp_rlast=mlp_head_r[514];
    assign m_axi_rready=!freeze&&!soft_reset&&!protocol_error_r&&active_valid_r&&
        !selected_buffer_full;
    assign quiescent=!desc_valid&&!issue_valid_r&&!active_valid_r&&
        tag_count_r==0&&attn_count_r==0&&mlp_count_r==0&&!protocol_error_r;
    assign protocol_error=protocol_error_r;
    assign tag_high_watermark={{(32-TAG_COUNT_W){1'b0}},tag_high_watermark_r};

    // A resetless single-write/asynchronous-read array maps to LUTRAM on
    // UltraScale+.  The old write inside the async-reset process forced this
    // 32-entry queue into registers and a variable 32:1 read mux.
    always @(posedge clk)begin
      if(tag_write)tag_mem[tag_wr_r]<={issue_owner,issue_seq,issue_len};
    end

    // Payload state deliberately has no reset.  The narrow valid/count state
    // below is the sole authority for visibility, so reset values here would
    // create four 515-bit reset/control sets and prevent local retiming.
    always @(posedge clk)begin
      if(desc_valid&&desc_ready&&
         desc_data[DESC_W+SEQ_W-1:DESC_W]==next_issue_seq_r)
        issue_data_r<=desc_data;
      case({attn_push,attn_pop})
        2'b10:begin
          if(attn_count_r==0)attn_head_r<=incoming_payload;
          else attn_tail_r<=incoming_payload;
        end
        2'b01:if(attn_count_r==2)attn_head_r<=attn_tail_r;
        2'b11:if(attn_count_r==1)attn_head_r<=incoming_payload;
        default:begin end
      endcase
      case({mlp_push,mlp_pop})
        2'b10:begin
          if(mlp_count_r==0)mlp_head_r<=incoming_payload;
          else mlp_tail_r<=incoming_payload;
        end
        2'b01:if(mlp_count_r==2)mlp_head_r<=mlp_tail_r;
        2'b11:if(mlp_count_r==1)mlp_head_r<=incoming_payload;
        default:begin end
      endcase
    end

    always @(posedge clk or negedge rst_n)begin
      if(!rst_n)begin
        issue_valid_r<=0;next_issue_seq_r<='0;
        tag_wr_r<='0;tag_rd_r<='0;tag_count_r<='0;response_beat_r<=0;
        active_valid_r<=0;active_owner_r<=0;active_seq_r<='0;active_len_r<=0;
        next_tag_valid_r<=0;next_tag_owner_r<=0;next_tag_seq_r<='0;
        next_tag_len_r<=0;
        attn_count_r<=0;mlp_count_r<=0;
        protocol_error_r<=0;physical_ar_count<=0;physical_r_count<=0;
        attn_burst_count<=0;mlp_burst_count<=0;hol_cycle_count<=0;
        tag_high_watermark_r<=0;
      end else if(hard_reset)begin
        issue_valid_r<=0;next_issue_seq_r<='0;
        tag_wr_r<='0;tag_rd_r<='0;tag_count_r<='0;response_beat_r<=0;
        active_valid_r<=0;active_owner_r<=0;active_seq_r<='0;active_len_r<=0;
        next_tag_valid_r<=0;next_tag_owner_r<=0;next_tag_seq_r<='0;
        next_tag_len_r<=0;
        attn_count_r<=0;mlp_count_r<=0;
        protocol_error_r<=0;physical_ar_count<=0;physical_r_count<=0;
        attn_burst_count<=0;mlp_burst_count<=0;hol_cycle_count<=0;
        tag_high_watermark_r<=0;
      end else if(soft_reset)begin
        // A maintenance clear is legal only before fatal state.  Once burst
        // framing is lost, only rst_n/hard_reset may clear the sticky error.
        if(protocol_error_r)begin
          protocol_error_r<=1;
        end else if(desc_valid||issue_valid_r||active_valid_r||tag_count_r!=0||
                    attn_count_r!=0||mlp_count_r!=0)begin
          protocol_error_r<=1;
        end else begin
          issue_valid_r<=0;next_issue_seq_r<='0;
          tag_wr_r<='0;tag_rd_r<='0;tag_count_r<='0;response_beat_r<=0;
          active_valid_r<=0;active_owner_r<=0;active_seq_r<='0;active_len_r<=0;
          next_tag_valid_r<=0;next_tag_owner_r<=0;next_tag_seq_r<='0;
          next_tag_len_r<=0;
          attn_count_r<=0;mlp_count_r<=0;
          physical_ar_count<=0;physical_r_count<=0;
          attn_burst_count<=0;mlp_burst_count<=0;hol_cycle_count<=0;
          tag_high_watermark_r<=0;
        end
      end else begin
        if(desc_valid&&desc_ready)begin
          if(desc_data[DESC_W+SEQ_W-1:DESC_W]!=next_issue_seq_r)begin
            protocol_error_r<=1;
          end else begin
            issue_valid_r<=1;
            next_issue_seq_r<=next_issue_seq_r+1'b1;
          end
        end
        if(ar_fire)begin
          issue_valid_r<=0;
          if(ar_load_active)begin
            active_valid_r<=1;
            active_owner_r<=issue_owner;
            active_seq_r<=issue_seq;
            active_len_r<=issue_len;
          end else if(ar_load_next)begin
            next_tag_valid_r<=1;
            next_tag_owner_r<=issue_owner;
            next_tag_seq_r<=issue_seq;
            next_tag_len_r<=issue_len;
          end else begin
            tag_wr_r<=tag_wr_r+1'b1;
          end
          physical_ar_count<=physical_ar_count+1'b1;
          if(issue_owner)mlp_burst_count<=mlp_burst_count+1'b1;
          else attn_burst_count<=attn_burst_count+1'b1;
        end
        // HWM is a narrow observer of registered occupancy only.  Every
        // count peak exists for at least one cycle, so this cannot miss a
        // peak and no response/final-beat control enters the metric CE.
        if(tag_count_r>tag_high_watermark_r)
          tag_high_watermark_r<=tag_count_r;
        if(m_axi_rvalid&&active_valid_r&&selected_buffer_full&&!protocol_error_r)
          hol_cycle_count<=hol_cycle_count+1'b1;
        if(m_axi_rvalid&&!active_valid_r&&!ar_fire&&!protocol_error_r)
          protocol_error_r<=1;
        if(r_fire)begin
          physical_r_count<=physical_r_count+1'b1;
          if(malformed)begin
            protocol_error_r<=1;
          end else if(response_last_good)begin
            response_beat_r<=0;
            if(next_tag_valid_r)begin
              active_owner_r<=next_tag_owner_r;
              active_seq_r<=next_tag_seq_r;
              active_len_r<=next_tag_len_r;
              if(ar_load_next)begin
                // The simultaneous AR write above fills the slot vacated by
                // the promoted tag when no older RAM-resident tag exists.
                next_tag_valid_r<=1;
              end else if(refill_next_from_mem)begin
                next_tag_valid_r<=1;
                next_tag_owner_r<=tag_head[TAG_W-1];
                next_tag_seq_r<=tag_head[TAG_W-2:8];
                next_tag_len_r<=tag_head[7:0];
                tag_rd_r<=tag_rd_r+1'b1;
              end else next_tag_valid_r<=0;
            end else if(ar_load_active)begin
              // ar_load_active already installed the simultaneous new tag.
              active_valid_r<=1;
            end else begin
              active_valid_r<=0;
            end
          end else begin
            response_beat_r<=response_beat_r+1'b1;
          end
        end
        case({ar_fire,response_last_good})
          2'b10:tag_count_r<=tag_count_r+1'b1;
          2'b01:tag_count_r<=tag_count_r-1'b1;
          default:tag_count_r<=tag_count_r;
        endcase

        case({attn_push,attn_pop})
          2'b10:begin
            attn_count_r<=attn_count_r+1'b1;
          end
          2'b01:begin
            attn_count_r<=attn_count_r-1'b1;
          end
          2'b11:begin
            if(attn_count_r!=1)begin
              // Count 2 cannot push because m_axi_rready deliberately omits
              // pop look-ahead; count 0 cannot pop.
              protocol_error_r<=1;
            end
          end
          default:attn_count_r<=attn_count_r;
        endcase
        case({mlp_push,mlp_pop})
          2'b10:begin
            mlp_count_r<=mlp_count_r+1'b1;
          end
          2'b01:begin
            mlp_count_r<=mlp_count_r-1'b1;
          end
          2'b11:begin
            if(mlp_count_r!=1)protocol_error_r<=1;
          end
          default:mlp_count_r<=mlp_count_r;
        endcase
        if(ar_fire&&tag_full)protocol_error_r<=1;
      end
    end

    initial begin
      if(TAG_DEPTH<16||(TAG_DEPTH&(TAG_DEPTH-1))!=0)
        $error("V4 response tag depth must be a power of two >=16");
      if(EGRESS_W!=AXI_ADDR_W+SEQ_W+14)
        $error("V4 local issue descriptor width mismatch");
    end
endmodule

// Three-clock paired two-client AXI512 read arbiter.  Four narrow AR streams
// cross to the 150-MHz core scheduler.  The scheduler accepts only a complete
// DDR0+DDR1 pair and writes the same owner/sequence into both MIG egress FIFOs.
// Each 300-MHz local unit then issues independently while retaining identical
// logical order.  Existing client payload/halfgroup FIFOs remain the wide-data
// timing and CDC boundary.
module hap_axi512_paired_2client_read_wrr #(
    parameter integer AXI_ADDR_W=32,
    parameter integer FIFO_DEPTH=16,
    parameter integer TAG_DEPTH=32,
    parameter integer SEQ_W=16
) (
    input wire core_clk,input wire core_rst_n,input wire core_clear,
    input wire core_enable,
    // Producers acknowledge this pause only after they can no longer create
    // new paired AR requests and all already-presented AR have handshaken.
    input wire attn_source_quiescent,input wire mlp_source_quiescent,
    output wire maintenance_pause_sources,
    output wire maintenance_drain_active,
    output wire maintenance_soft_clear_pulse,
    // Both enables are committed core_clk levels.  This leaf owns their
    // synchronization before either level is consumed in a DDR clock domain.
    input wire ddr0_clk,input wire ddr0_rst_n,input wire ddr0_enable,
    input wire ddr1_clk,input wire ddr1_rst_n,input wire ddr1_enable,

    input wire a0_arvalid,output wire a0_arready,input wire[AXI_ADDR_W-1:0]a0_araddr,
    input wire[7:0]a0_arlen,input wire[2:0]a0_arsize,input wire[1:0]a0_arburst,
    output wire a0_rvalid,input wire a0_rready,output wire[511:0]a0_rdata,
    output wire[1:0]a0_rresp,output wire a0_rlast,
    input wire m0_arvalid,output wire m0_arready,input wire[AXI_ADDR_W-1:0]m0_araddr,
    input wire[7:0]m0_arlen,input wire[2:0]m0_arsize,input wire[1:0]m0_arburst,
    output wire m0_rvalid,input wire m0_rready,output wire[511:0]m0_rdata,
    output wire[1:0]m0_rresp,output wire m0_rlast,

    input wire a1_arvalid,output wire a1_arready,input wire[AXI_ADDR_W-1:0]a1_araddr,
    input wire[7:0]a1_arlen,input wire[2:0]a1_arsize,input wire[1:0]a1_arburst,
    output wire a1_rvalid,input wire a1_rready,output wire[511:0]a1_rdata,
    output wire[1:0]a1_rresp,output wire a1_rlast,
    input wire m1_arvalid,output wire m1_arready,input wire[AXI_ADDR_W-1:0]m1_araddr,
    input wire[7:0]m1_arlen,input wire[2:0]m1_arsize,input wire[1:0]m1_arburst,
    output wire m1_rvalid,input wire m1_rready,output wire[511:0]m1_rdata,
    output wire[1:0]m1_rresp,output wire m1_rlast,

    output wire p0_arvalid,input wire p0_arready,output wire[AXI_ADDR_W-1:0]p0_araddr,
    output wire[7:0]p0_arlen,output wire[2:0]p0_arsize,output wire[1:0]p0_arburst,
    input wire p0_rvalid,output wire p0_rready,input wire[511:0]p0_rdata,
    input wire[1:0]p0_rresp,input wire p0_rlast,
    output wire p1_arvalid,input wire p1_arready,output wire[AXI_ADDR_W-1:0]p1_araddr,
    output wire[7:0]p1_arlen,output wire[2:0]p1_arsize,output wire[1:0]p1_arburst,
    input wire p1_rvalid,output wire p1_rready,input wire[511:0]p1_rdata,
    input wire[1:0]p1_rresp,input wire p1_rlast,

    output wire core_quiescent,output wire error,
    output reg[31:0]accepted_attn_bursts,output reg[31:0]accepted_mlp_bursts,
    output reg[31:0]both_eligible_cycles,
    output wire[31:0]p0_hol_cycles,output wire[31:0]p1_hol_cycles,
    output wire[31:0]p0_tag_high_watermark,output wire[31:0]p1_tag_high_watermark
);
    localparam integer DESC_W=AXI_ADDR_W+13;
    localparam integer INGRESS_W=SEQ_W+DESC_W;
    localparam integer EGRESS_W=1+SEQ_W+DESC_W;
    wire global_reset_request=!core_rst_n||!ddr0_rst_n||!ddr1_rst_n;
    reg[4:0]reset_shift_r;
    reg[2:0]source_closed_stable_r;
    reg[2:0]clear_stable_r;
    reg maintenance_req_r;
    reg maintenance_stop_req_r;
    reg maintenance_soft_clear_pulse_r;
    reg clear_armed_r;
    reg fifo_reset_request_r;
    // core_rst_n asserts this registered request asynchronously.  Remote DDR
    // resets reach the manager through hard_rst_core and assert it on a core
    // edge.  Its Q, not a combinational reset OR, is the only source presented
    // to the three destination reset synchronizers.
    wire fifo_reset_source=fifo_reset_request_r;
    wire fifo_rst_core,fifo_rst_ddr0,fifo_rst_ddr1;
    wire hard_rst_core,hard_rst_ddr0,hard_rst_ddr1;

    reg[SEQ_W-1:0]a0_src_seq_r,a1_src_seq_r,m0_src_seq_r,m1_src_seq_r;
    reg a0_skid_valid_r,a1_skid_valid_r,m0_skid_valid_r,m1_skid_valid_r;
    reg[INGRESS_W-1:0]a0_skid_data_r,a1_skid_data_r;
    reg[INGRESS_W-1:0]m0_skid_data_r,m1_skid_data_r;
    wire a0_wr_ready,a1_wr_ready,m0_wr_ready,m1_wr_ready;
    wire a0_wr_empty,a1_wr_empty,m0_wr_empty,m1_wr_empty;
    wire a0_in_error,a1_in_error,m0_in_error,m1_in_error;
    wire a0_q_valid,a1_q_valid,m0_q_valid,m1_q_valid;
    wire a0_q_ready,a1_q_ready,m0_q_ready,m1_q_ready;
    wire[INGRESS_W-1:0]a0_q,a1_q,m0_q,m1_q;

    wire o0_wr_ready,o1_wr_ready,o0_wr_empty,o1_wr_empty;
    wire o0_q_valid,o1_q_valid,o0_q_ready,o1_q_ready;
    wire[EGRESS_W-1:0]o0_q,o1_q;
    wire o0_error,o1_error;
    reg[1:0]wrr_phase_r;
    reg[SEQ_W-1:0]sequence_r;
    reg core_error_r;
    wire a_pair_present=a0_q_valid&&a1_q_valid;
    wire m_pair_present=m0_q_valid&&m1_q_valid;
    wire a_pair_match=a0_q[INGRESS_W-1:DESC_W]==a1_q[INGRESS_W-1:DESC_W]&&
        a0_q[12:0]==a1_q[12:0];
    wire m_pair_match=m0_q[INGRESS_W-1:DESC_W]==m1_q[INGRESS_W-1:DESC_W]&&
        m0_q[12:0]==m1_q[12:0];
    wire outputs_ready=o0_wr_ready&&o1_wr_ready;
    wire scheduler_run=core_enable||maintenance_req_r;
    wire a_eligible=scheduler_run&&a_pair_present&&a_pair_match&&outputs_ready;
    wire m_eligible=scheduler_run&&m_pair_present&&m_pair_match&&outputs_ready;
    wire prefer_attn=wrr_phase_r==0;
    wire grant_attn;
    wire grant_mlp;
    wire pair_fire=grant_attn||grant_mlp;
    wire selected_owner=grant_mlp;
    wire[DESC_W-1:0]selected0=grant_mlp?m0_q[DESC_W-1:0]:a0_q[DESC_W-1:0];
    wire[DESC_W-1:0]selected1=grant_mlp?m1_q[DESC_W-1:0]:a1_q[DESC_W-1:0];
    wire[EGRESS_W-1:0]o0_in={selected_owner,sequence_r,selected0};
    wire[EGRESS_W-1:0]o1_in={selected_owner,sequence_r,selected1};

    wire local0_quiescent,local1_quiescent,local0_error,local1_error;
    wire local0_q_core,local1_q_core,local0_error_core,local1_error_core;
    wire o0_error_core,o1_error_core;
    reg maintenance_violation0_r,maintenance_violation1_r;
    wire maintenance_violation0_core,maintenance_violation1_core;
    wire global_freeze_core=core_error_r||local0_error_core||local1_error_core||
        a0_in_error||a1_in_error||m0_in_error||m1_in_error||
        o0_error_core||o1_error_core||maintenance_violation0_core||
        maintenance_violation1_core;
    wire global_freeze_ddr0,global_freeze_ddr1;
    wire maintenance_active_ddr0,maintenance_active_ddr1;
    wire maintenance_stop_ddr0,maintenance_stop_ddr1;
    wire maintenance_ack0_core,maintenance_ack1_core;
    wire a0_skid_push=a0_skid_valid_r&&!local0_error&&
        !global_freeze_ddr0&&a0_wr_ready;
    wire m0_skid_push=m0_skid_valid_r&&!local0_error&&
        !global_freeze_ddr0&&m0_wr_ready;
    wire a1_skid_push=a1_skid_valid_r&&!local1_error&&
        !global_freeze_ddr1&&a1_wr_ready;
    wire m1_skid_push=m1_skid_valid_r&&!local1_error&&
        !global_freeze_ddr1&&m1_wr_ready;
    wire a0_source_empty_ddr0=!a0_skid_valid_r&&a0_wr_empty;
    wire m0_source_empty_ddr0=!m0_skid_valid_r&&m0_wr_empty;
    wire a1_source_empty_ddr1=!a1_skid_valid_r&&a1_wr_empty;
    wire m1_source_empty_ddr1=!m1_skid_valid_r&&m1_wr_empty;
    wire a0_source_empty_core,m0_source_empty_core;
    wire a1_source_empty_core,m1_source_empty_core;
    // The mode controller changes both enables only after the core-domain
    // quiescence contract has drained every producer, FIFO and local issuer.
    // They nevertheless originate in core_clk and must not directly control
    // the 300-MHz admission/issue state.  Synchronize the committed level once
    // at each DDR boundary; every local consumer below uses only this copy.
    // The synchronizer latency is paid only on a quiescent mode transition,
    // never between steady-state requests, so normal request II is unchanged.
    wire ddr0_enable_sync,ddr1_enable_sync;
    wire ddr0_run=ddr0_enable_sync||maintenance_active_ddr0;
    wire ddr1_run=ddr1_enable_sync||maintenance_active_ddr1;
    wire sources_closed_level=maintenance_req_r&&attn_source_quiescent&&
        mlp_source_quiescent;
    wire sources_closed_seen=sources_closed_level&&
        (source_closed_stable_r==3'b111);
    wire clear_drain_level=maintenance_req_r&&maintenance_ack0_core&&
        maintenance_ack1_core&&core_quiescent;
    wire clear_drain_seen=clear_drain_level&&(clear_stable_r==3'b111);
    wire unsafe_clear=core_clear&&global_freeze_core;
    assign maintenance_pause_sources=maintenance_req_r;
    assign maintenance_drain_active=maintenance_req_r;
    assign maintenance_soft_clear_pulse=maintenance_soft_clear_pulse_r;
    assign grant_attn=!global_freeze_core&&a_eligible&&
        (prefer_attn||!m_eligible);
    assign grant_mlp=!global_freeze_core&&m_eligible&&
        (!prefer_attn||!a_eligible);
    assign core_quiescent=!fifo_rst_core&&!global_freeze_core&&
        a0_source_empty_core&&a1_source_empty_core&&
        m0_source_empty_core&&m1_source_empty_core&&
        !a0_q_valid&&!a1_q_valid&&!m0_q_valid&&!m1_q_valid&&
        o0_wr_empty&&o1_wr_empty&&local0_q_core&&local1_q_core;
    assign error=global_freeze_core;

    assign a0_arready=ddr0_run&&!fifo_rst_ddr0&&!local0_error&&
        !global_freeze_ddr0&&!maintenance_stop_ddr0&&!a0_skid_valid_r;
    assign m0_arready=ddr0_run&&!fifo_rst_ddr0&&!local0_error&&
        !global_freeze_ddr0&&!maintenance_stop_ddr0&&!m0_skid_valid_r;
    assign a1_arready=ddr1_run&&!fifo_rst_ddr1&&!local1_error&&
        !global_freeze_ddr1&&!maintenance_stop_ddr1&&!a1_skid_valid_r;
    assign m1_arready=ddr1_run&&!fifo_rst_ddr1&&!local1_error&&
        !global_freeze_ddr1&&!maintenance_stop_ddr1&&!m1_skid_valid_r;
    assign a0_q_ready=grant_attn;assign a1_q_ready=grant_attn;
    assign m0_q_ready=grant_mlp;assign m1_q_ready=grant_mlp;

    // Descriptor payloads are resetless; skid valid bits below own their
    // visibility.  Keeping data in a separate process removes wide reset
    // control sets from both 300-MHz source domains.
    always @(posedge ddr0_clk)begin
      if(a0_arvalid&&a0_arready)
        a0_skid_data_r<={a0_src_seq_r,a0_araddr,a0_arlen,a0_arsize,a0_arburst};
      if(m0_arvalid&&m0_arready)
        m0_skid_data_r<={m0_src_seq_r,m0_araddr,m0_arlen,m0_arsize,m0_arburst};
    end
    always @(posedge ddr1_clk)begin
      if(a1_arvalid&&a1_arready)
        a1_skid_data_r<={a1_src_seq_r,a1_araddr,a1_arlen,a1_arsize,a1_arburst};
      if(m1_arvalid&&m1_arready)
        m1_skid_data_r<={m1_src_seq_r,m1_araddr,m1_arlen,m1_arsize,m1_arburst};
    end

    hap_v4_async_fifo #(.WIDTH(INGRESS_W),.DEPTH(FIFO_DEPTH))u_a0_in(
      .wr_rst(fifo_rst_ddr0),.rd_rst(fifo_rst_core),.wr_clk(ddr0_clk),
      .wr_valid(a0_skid_valid_r&&!local0_error&&!global_freeze_ddr0),
      .wr_ready(a0_wr_ready),.wr_data(a0_skid_data_r),.rd_clk(core_clk),
      .rd_valid(a0_q_valid),.rd_ready(a0_q_ready),.rd_data(a0_q),
      .wr_empty(a0_wr_empty),.error(a0_in_error));
    hap_v4_async_fifo #(.WIDTH(INGRESS_W),.DEPTH(FIFO_DEPTH))u_a1_in(
      .wr_rst(fifo_rst_ddr1),.rd_rst(fifo_rst_core),.wr_clk(ddr1_clk),
      .wr_valid(a1_skid_valid_r&&!local1_error&&!global_freeze_ddr1),
      .wr_ready(a1_wr_ready),.wr_data(a1_skid_data_r),.rd_clk(core_clk),
      .rd_valid(a1_q_valid),.rd_ready(a1_q_ready),.rd_data(a1_q),
      .wr_empty(a1_wr_empty),.error(a1_in_error));
    hap_v4_async_fifo #(.WIDTH(INGRESS_W),.DEPTH(FIFO_DEPTH))u_m0_in(
      .wr_rst(fifo_rst_ddr0),.rd_rst(fifo_rst_core),.wr_clk(ddr0_clk),
      .wr_valid(m0_skid_valid_r&&!local0_error&&!global_freeze_ddr0),
      .wr_ready(m0_wr_ready),.wr_data(m0_skid_data_r),.rd_clk(core_clk),
      .rd_valid(m0_q_valid),.rd_ready(m0_q_ready),.rd_data(m0_q),
      .wr_empty(m0_wr_empty),.error(m0_in_error));
    hap_v4_async_fifo #(.WIDTH(INGRESS_W),.DEPTH(FIFO_DEPTH))u_m1_in(
      .wr_rst(fifo_rst_ddr1),.rd_rst(fifo_rst_core),.wr_clk(ddr1_clk),
      .wr_valid(m1_skid_valid_r&&!local1_error&&!global_freeze_ddr1),
      .wr_ready(m1_wr_ready),.wr_data(m1_skid_data_r),.rd_clk(core_clk),
      .rd_valid(m1_q_valid),.rd_ready(m1_q_ready),.rd_data(m1_q),
      .wr_empty(m1_wr_empty),.error(m1_in_error));
    hap_v4_async_fifo #(.WIDTH(EGRESS_W),.DEPTH(FIFO_DEPTH))u_o0(
      .wr_rst(fifo_rst_core),.rd_rst(fifo_rst_ddr0),.wr_clk(core_clk),
      .wr_valid(pair_fire),
      .wr_ready(o0_wr_ready),.wr_data(o0_in),.rd_clk(ddr0_clk),
      .rd_valid(o0_q_valid),.rd_ready(o0_q_ready),.rd_data(o0_q),
      .wr_empty(o0_wr_empty),.error(o0_error));
    hap_v4_async_fifo #(.WIDTH(EGRESS_W),.DEPTH(FIFO_DEPTH))u_o1(
      .wr_rst(fifo_rst_core),.rd_rst(fifo_rst_ddr1),.wr_clk(core_clk),
      .wr_valid(pair_fire),
      .wr_ready(o1_wr_ready),.wr_data(o1_in),.rd_clk(ddr1_clk),
      .rd_valid(o1_q_valid),.rd_ready(o1_q_ready),.rd_data(o1_q),
      .wr_empty(o1_wr_empty),.error(o1_error));

    always @(posedge core_clk or negedge core_rst_n)begin
      if(!core_rst_n||hard_rst_core)begin
        reset_shift_r<=5'b11111;fifo_reset_request_r<=1;
        maintenance_soft_clear_pulse_r<=0;
      end else begin
        maintenance_soft_clear_pulse_r<=0;
        fifo_reset_request_r<=|reset_shift_r;
        if(|reset_shift_r)reset_shift_r<={1'b0,reset_shift_r[4:1]};
        else if(clear_drain_seen)begin
          reset_shift_r<=5'b11111;fifo_reset_request_r<=1;
          maintenance_soft_clear_pulse_r<=1;
        end
      end
    end
    always @(posedge core_clk or negedge core_rst_n)begin
      if(!core_rst_n)begin maintenance_req_r<=0;clear_armed_r<=1;end
      else if(hard_rst_core)begin maintenance_req_r<=0;clear_armed_r<=1;end
      else begin
        if(!core_clear)clear_armed_r<=1;
        if(|reset_shift_r)maintenance_req_r<=0;
        else if(core_clear&&clear_armed_r&&!global_freeze_core)begin
          maintenance_req_r<=1;clear_armed_r<=0;end
      end
    end
    always @(posedge core_clk or negedge core_rst_n)begin
      if(!core_rst_n)begin
        source_closed_stable_r<=0;maintenance_stop_req_r<=0;
      end else if(hard_rst_core||fifo_rst_core||!maintenance_req_r)begin
        source_closed_stable_r<=0;maintenance_stop_req_r<=0;
      end else begin
        if(!sources_closed_level)source_closed_stable_r<=0;
        else if(!(&source_closed_stable_r))source_closed_stable_r<=
          {source_closed_stable_r[1:0],1'b1};
        if(sources_closed_seen)maintenance_stop_req_r<=1;
      end
    end
    always @(posedge core_clk or negedge core_rst_n)begin
      if(!core_rst_n)clear_stable_r<=0;
      else if(hard_rst_core||!clear_drain_level)clear_stable_r<=0;
      else if(!(&clear_stable_r))clear_stable_r<=
        {clear_stable_r[1:0],1'b1};
    end
    always @(posedge ddr0_clk or negedge ddr0_rst_n)begin
      if(!ddr0_rst_n)begin a0_src_seq_r<=0;m0_src_seq_r<=0;
        a0_skid_valid_r<=0;m0_skid_valid_r<=0;
        maintenance_violation0_r<=0;end
      else if(hard_rst_ddr0)begin a0_src_seq_r<=0;m0_src_seq_r<=0;
        a0_skid_valid_r<=0;m0_skid_valid_r<=0;
        maintenance_violation0_r<=0;end
      else if(fifo_rst_ddr0&&!hard_rst_ddr0)begin
        a0_src_seq_r<=0;m0_src_seq_r<=0;
        a0_skid_valid_r<=0;m0_skid_valid_r<=0;
      end
      else begin
        if(maintenance_stop_ddr0&&(a0_arvalid||m0_arvalid))
          maintenance_violation0_r<=1;
        if(a0_skid_push)a0_skid_valid_r<=0;
        if(m0_skid_push)m0_skid_valid_r<=0;
        if(a0_arvalid&&a0_arready)begin
          a0_skid_valid_r<=1;
          a0_src_seq_r<=a0_src_seq_r+1'b1;end
        if(m0_arvalid&&m0_arready)begin
          m0_skid_valid_r<=1;
          m0_src_seq_r<=m0_src_seq_r+1'b1;end
      end
    end
    always @(posedge ddr1_clk or negedge ddr1_rst_n)begin
      if(!ddr1_rst_n)begin a1_src_seq_r<=0;m1_src_seq_r<=0;
        a1_skid_valid_r<=0;m1_skid_valid_r<=0;
        maintenance_violation1_r<=0;end
      else if(hard_rst_ddr1)begin a1_src_seq_r<=0;m1_src_seq_r<=0;
        a1_skid_valid_r<=0;m1_skid_valid_r<=0;
        maintenance_violation1_r<=0;end
      else if(fifo_rst_ddr1&&!hard_rst_ddr1)begin
        a1_src_seq_r<=0;m1_src_seq_r<=0;
        a1_skid_valid_r<=0;m1_skid_valid_r<=0;
      end
      else begin
        if(maintenance_stop_ddr1&&(a1_arvalid||m1_arvalid))
          maintenance_violation1_r<=1;
        if(a1_skid_push)a1_skid_valid_r<=0;
        if(m1_skid_push)m1_skid_valid_r<=0;
        if(a1_arvalid&&a1_arready)begin
          a1_skid_valid_r<=1;
          a1_src_seq_r<=a1_src_seq_r+1'b1;end
        if(m1_arvalid&&m1_arready)begin
          m1_skid_valid_r<=1;
          m1_src_seq_r<=m1_src_seq_r+1'b1;end
      end
    end
    always @(posedge core_clk or negedge core_rst_n)begin
      if(!core_rst_n)begin wrr_phase_r<=0;sequence_r<=0;core_error_r<=0;
        accepted_attn_bursts<=0;accepted_mlp_bursts<=0;both_eligible_cycles<=0;end
      else if(hard_rst_core)begin wrr_phase_r<=0;sequence_r<=0;core_error_r<=0;
        accepted_attn_bursts<=0;accepted_mlp_bursts<=0;both_eligible_cycles<=0;end
      else if(fifo_rst_core)begin wrr_phase_r<=0;sequence_r<=0;
        accepted_attn_bursts<=0;accepted_mlp_bursts<=0;both_eligible_cycles<=0;end
      else begin
        if(unsafe_clear)core_error_r<=1;
        if(local0_error_core||local1_error_core||a0_in_error||a1_in_error||
           m0_in_error||m1_in_error||o0_error_core||o1_error_core||
           maintenance_violation0_core||maintenance_violation1_core)
          core_error_r<=1;
        if((a_pair_present&&!a_pair_match)||(m_pair_present&&!m_pair_match))
          core_error_r<=1;
        if(a_eligible&&m_eligible)both_eligible_cycles<=both_eligible_cycles+1'b1;
        if(pair_fire)begin
          sequence_r<=sequence_r+1'b1;
          if(grant_attn)accepted_attn_bursts<=accepted_attn_bursts+1'b1;
          else accepted_mlp_bursts<=accepted_mlp_bursts+1'b1;
          if((prefer_attn&&grant_attn)||(!prefer_attn&&grant_mlp))begin
            if(wrr_phase_r==2)wrr_phase_r<=0;
            else wrr_phase_r<=wrr_phase_r+1'b1;
          end
        end
      end
    end

    hap_axi512_ordered_local_issue #(.AXI_ADDR_W(AXI_ADDR_W),.SEQ_W(SEQ_W),
      .TAG_DEPTH(TAG_DEPTH))u_local0(
      .clk(ddr0_clk),.rst_n(ddr0_rst_n),.hard_reset(hard_rst_ddr0),
      .soft_reset(fifo_rst_ddr0&&!hard_rst_ddr0),.enable(ddr0_run),
      .freeze(global_freeze_ddr0),
      .desc_valid(o0_q_valid),.desc_ready(o0_q_ready),.desc_data(o0_q),
      .m_axi_arvalid(p0_arvalid),.m_axi_arready(p0_arready),.m_axi_araddr(p0_araddr),
      .m_axi_arlen(p0_arlen),.m_axi_arsize(p0_arsize),.m_axi_arburst(p0_arburst),
      .m_axi_rvalid(p0_rvalid),.m_axi_rready(p0_rready),.m_axi_rdata(p0_rdata),
      .m_axi_rresp(p0_rresp),.m_axi_rlast(p0_rlast),
      .attn_rvalid(a0_rvalid),.attn_rready(a0_rready),.attn_rdata(a0_rdata),
      .attn_rresp(a0_rresp),.attn_rlast(a0_rlast),.mlp_rvalid(m0_rvalid),
      .mlp_rready(m0_rready),.mlp_rdata(m0_rdata),.mlp_rresp(m0_rresp),
      .mlp_rlast(m0_rlast),.quiescent(local0_quiescent),
      .protocol_error(local0_error),.physical_ar_count(),.physical_r_count(),
      .attn_burst_count(),.mlp_burst_count(),.hol_cycle_count(p0_hol_cycles),
      .tag_high_watermark(p0_tag_high_watermark));
    hap_axi512_ordered_local_issue #(.AXI_ADDR_W(AXI_ADDR_W),.SEQ_W(SEQ_W),
      .TAG_DEPTH(TAG_DEPTH))u_local1(
      .clk(ddr1_clk),.rst_n(ddr1_rst_n),.hard_reset(hard_rst_ddr1),
      .soft_reset(fifo_rst_ddr1&&!hard_rst_ddr1),.enable(ddr1_run),
      .freeze(global_freeze_ddr1),
      .desc_valid(o1_q_valid),.desc_ready(o1_q_ready),.desc_data(o1_q),
      .m_axi_arvalid(p1_arvalid),.m_axi_arready(p1_arready),.m_axi_araddr(p1_araddr),
      .m_axi_arlen(p1_arlen),.m_axi_arsize(p1_arsize),.m_axi_arburst(p1_arburst),
      .m_axi_rvalid(p1_rvalid),.m_axi_rready(p1_rready),.m_axi_rdata(p1_rdata),
      .m_axi_rresp(p1_rresp),.m_axi_rlast(p1_rlast),
      .attn_rvalid(a1_rvalid),.attn_rready(a1_rready),.attn_rdata(a1_rdata),
      .attn_rresp(a1_rresp),.attn_rlast(a1_rlast),.mlp_rvalid(m1_rvalid),
      .mlp_rready(m1_rready),.mlp_rdata(m1_rdata),.mlp_rresp(m1_rresp),
      .mlp_rlast(m1_rlast),.quiescent(local1_quiescent),
      .protocol_error(local1_error),.physical_ar_count(),.physical_r_count(),
      .attn_burst_count(),.mlp_burst_count(),.hol_cycle_count(p1_hol_cycles),
      .tag_high_watermark(p1_tag_high_watermark));

    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_q0_cdc(.src_clk(ddr0_clk),.src_in(local0_quiescent),
      .dest_clk(core_clk),.dest_out(local0_q_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_q1_cdc(.src_clk(ddr1_clk),.src_in(local1_quiescent),
      .dest_clk(core_clk),.dest_out(local1_q_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_e0_cdc(.src_clk(ddr0_clk),.src_in(local0_error),
      .dest_clk(core_clk),.dest_out(local0_error_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_e1_cdc(.src_clk(ddr1_clk),.src_in(local1_error),
      .dest_clk(core_clk),.dest_out(local1_error_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_oe0_cdc(.src_clk(ddr0_clk),.src_in(o0_error),
      .dest_clk(core_clk),.dest_out(o0_error_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_oe1_cdc(.src_clk(ddr1_clk),.src_in(o1_error),
      .dest_clk(core_clk),.dest_out(o1_error_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_mv0_cdc(.src_clk(ddr0_clk),
      .src_in(maintenance_violation0_r),.dest_clk(core_clk),
      .dest_out(maintenance_violation0_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_mv1_cdc(.src_clk(ddr1_clk),
      .src_in(maintenance_violation1_r),.dest_clk(core_clk),
      .dest_out(maintenance_violation1_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_freeze0_cdc(.src_clk(core_clk),.src_in(global_freeze_core),
      .dest_clk(ddr0_clk),.dest_out(global_freeze_ddr0));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_freeze1_cdc(.src_clk(core_clk),.src_in(global_freeze_core),
      .dest_clk(ddr1_clk),.dest_out(global_freeze_ddr1));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_maint_stop0_cdc(.src_clk(core_clk),
      .src_in(maintenance_stop_req_r),.dest_clk(ddr0_clk),
      .dest_out(maintenance_stop_ddr0));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_maint_stop1_cdc(.src_clk(core_clk),
      .src_in(maintenance_stop_req_r),.dest_clk(ddr1_clk),
      .dest_out(maintenance_stop_ddr1));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_maint_active0_cdc(.src_clk(core_clk),
      .src_in(maintenance_req_r),.dest_clk(ddr0_clk),
      .dest_out(maintenance_active_ddr0));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_maint_active1_cdc(.src_clk(core_clk),
      .src_in(maintenance_req_r),.dest_clk(ddr1_clk),
      .dest_out(maintenance_active_ddr1));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_enable0_cdc(.src_clk(core_clk),
      .src_in(ddr0_enable),.dest_clk(ddr0_clk),.dest_out(ddr0_enable_sync));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_enable1_cdc(.src_clk(core_clk),
      .src_in(ddr1_enable),.dest_clk(ddr1_clk),.dest_out(ddr1_enable_sync));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_maint_ack0_cdc(.src_clk(ddr0_clk),
      .src_in(maintenance_stop_ddr0),.dest_clk(core_clk),
      .dest_out(maintenance_ack0_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_maint_ack1_cdc(.src_clk(ddr1_clk),
      .src_in(maintenance_stop_ddr1),.dest_clk(core_clk),
      .dest_out(maintenance_ack1_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_a0_empty_cdc(.src_clk(ddr0_clk),
      .src_in(a0_source_empty_ddr0),.dest_clk(core_clk),
      .dest_out(a0_source_empty_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_m0_empty_cdc(.src_clk(ddr0_clk),
      .src_in(m0_source_empty_ddr0),.dest_clk(core_clk),
      .dest_out(m0_source_empty_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_a1_empty_cdc(.src_clk(ddr1_clk),
      .src_in(a1_source_empty_ddr1),.dest_clk(core_clk),
      .dest_out(a1_source_empty_core));
    xpm_cdc_single #(.DEST_SYNC_FF(2),.INIT_SYNC_FF(1),.SIM_ASSERT_CHK(0),
      .SRC_INPUT_REG(1))u_m1_empty_cdc(.src_clk(ddr1_clk),
      .src_in(m1_source_empty_ddr1),.dest_clk(core_clk),
      .dest_out(m1_source_empty_core));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_reset_core(.src_rst(fifo_reset_source),
      .dest_clk(core_clk),.dest_rst(fifo_rst_core));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_reset_ddr0(.src_rst(fifo_reset_source),
      .dest_clk(ddr0_clk),.dest_rst(fifo_rst_ddr0));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_reset_ddr1(.src_rst(fifo_reset_source),
      .dest_clk(ddr1_clk),.dest_rst(fifo_rst_ddr1));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_hard_reset_core(.src_rst(global_reset_request),
      .dest_clk(core_clk),.dest_rst(hard_rst_core));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_hard_reset_ddr0(.src_rst(global_reset_request),
      .dest_clk(ddr0_clk),.dest_rst(hard_rst_ddr0));
    xpm_cdc_sync_rst #(.DEST_SYNC_FF(2),.INIT(1),.INIT_SYNC_FF(1),
      .SIM_ASSERT_CHK(0))u_hard_reset_ddr1(.src_rst(global_reset_request),
      .dest_clk(ddr1_clk),.dest_rst(hard_rst_ddr1));

    initial begin
      if(FIFO_DEPTH<16||TAG_DEPTH<16)
        $error("V4 paired arbiter FIFO/tag depths must be >=16");
    end
endmodule
