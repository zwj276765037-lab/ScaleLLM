`timescale 1ns / 1ps

// Scheme-A tensor boundary over a dedicated 256-bit AXI data master.
// Input is 128 contiguous cohort16 group32 records (48 beats/record); output
// is 256 contiguous cohort16 tile16 records (32 beats/record).
module hap_mlp_tensor_dma_bridge #(
    parameter integer INPUT_GROUPS = 128,
    parameter integer OUTPUT_TILES = 256,
    parameter integer PRODUCTION_SHAPE = 1
) (
    input wire clk,input wire rst_n,input wire clear,
    input wire load_valid,output wire load_ready,input wire load_bank,
    input wire [31:0] input_base_addr,
    input wire store_valid,output wire store_ready,
    input wire [31:0] output_base_addr,
    output wire mlp_input_valid,input wire mlp_input_ready,
    output wire mlp_input_bank,output wire [6:0] mlp_input_group,
    output wire [12287:0] mlp_input_s24x16x32,
    input wire mlp_out_valid,output wire mlp_out_ready,
    input wire [7:0] mlp_out_tile,input wire [8191:0] mlp_out_s32x16x16,
    output wire busy,output reg done,output reg load_done,
    output reg store_done,output wire store_armed,output wire axi_active,
    output reg error,
    output wire [2:0] phase,output reg [31:0] input_beat_count,
    output reg [31:0] input_group_count,
    output reg [31:0] output_beat_count,
    output reg [31:0] output_tile_count,

    output wire m_axi_arvalid,input wire m_axi_arready,
    output wire [31:0] m_axi_araddr,output wire [7:0] m_axi_arlen,
    output wire [2:0] m_axi_arsize,output wire [1:0] m_axi_arburst,
    input wire m_axi_rvalid,output wire m_axi_rready,
    input wire [255:0] m_axi_rdata,input wire [1:0] m_axi_rresp,
    input wire m_axi_rlast,output wire m_axi_awvalid,
    input wire m_axi_awready,output wire [31:0] m_axi_awaddr,
    output wire [7:0] m_axi_awlen,output wire [2:0] m_axi_awsize,
    output wire [1:0] m_axi_awburst,output wire m_axi_wvalid,
    input wire m_axi_wready,output wire [255:0] m_axi_wdata,
    output wire [31:0] m_axi_wstrb,output wire m_axi_wlast,
    input wire m_axi_bvalid,output wire m_axi_bready,
    input wire [1:0] m_axi_bresp
);
    localparam [2:0] P_IDLE=0,P_LOAD=1,P_LOAD_DRAIN=2,P_STORE_ARM=3,
        P_STORE=4;
    reg [2:0] state_r;
    reg active_bank_r;
    reg [6:0] input_group_r;
    reg [5:0] input_beat_r;
    // A 12288-bit shift register made rd_fire a 12288-load CE and Vivado
    // promoted that data/control net onto a BUFGCE in the full V5 place.
    // Store each AXI beat directly in its final 256-bit bank instead.  The
    // bank decode has only 48 sinks and each local enable owns 256 FFs; the
    // flattened tensor order at the MLP boundary is unchanged.
    (* DONT_TOUCH = "yes" *) reg [255:0] input_group_beat_r [0:47];
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [47:0] input_beat_write_enable;
    reg input_group_valid_r;
    reg [7:0] expected_output_tile_r;
    reg [4:0] output_beat_r;
    // Likewise, shifting a complete 8192-bit output tile on every accepted
    // AXI beat created a second global data predicate.  Capture the 32 final
    // words into protected banks and advance only a 256-bit registered stream
    // word.  The per-bank hold bits are physical control copies; bit zero of
    // output_tile_valid_r remains the sole architectural protocol owner.
    (* DONT_TOUCH = "yes" *) reg [255:0] output_tile_beat_r [0:31];
    (* DONT_TOUCH = "yes" *) reg [31:0] output_tile_hold_r;
    // A stallable two-stage 32-to-1 read pipeline keeps the beat selector and
    // data mux local.  It adds two startup cycles per tile but still retires
    // one AXI beat per cycle once full.
    reg [5:0] output_issue_count_r;
    (* DONT_TOUCH = "yes" *) reg [255:0]
        output_mux_group_data_r [0:7];
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [7:0] output_mux_group_write_enable;
    (* DONT_TOUCH = "yes" *) reg [2:0] output_mux_group_r;
    (* DONT_TOUCH = "yes" *) reg output_mux_stage0_valid_r;
    (* DONT_TOUCH = "yes" *) reg [255:0] output_stream_data_r;
    (* DONT_TOUCH = "yes" *) reg output_stream_valid_r;
    reg output_tile_valid_r;

    wire dma_cmd_valid=(state_r==P_IDLE&&load_valid)||
        (state_r==P_STORE_ARM&&mlp_out_valid);
    wire dma_cmd_ready,dma_busy,dma_done,dma_error;
    wire start_load=state_r==P_IDLE&&load_valid&&load_ready;
    wire arm_store=state_r==P_IDLE&&!load_valid&&store_valid&&store_ready;
    wire start_store_dma=state_r==P_STORE_ARM&&mlp_out_valid&&dma_cmd_ready;
    wire dma_cmd_write=state_r==P_STORE_ARM;
    wire [31:0] dma_cmd_base=state_r==P_IDLE?input_base_addr:output_base_addr;
    wire [31:0] dma_cmd_beats=state_r==P_IDLE?INPUT_GROUPS*48:OUTPUT_TILES*32;
    wire dma_rd_valid,dma_rd_ready,dma_rd_last;
    wire [255:0] dma_rd_data;
    wire dma_wr_valid,dma_wr_ready;
    wire [255:0] dma_wr_data;
    wire rd_fire=dma_rd_valid&&dma_rd_ready;
    wire wr_fire=dma_wr_valid&&dma_wr_ready;
    wire input_fire=input_group_valid_r&&mlp_input_ready;
    wire output_fire=mlp_out_valid&&mlp_out_ready;

    assign load_ready=rst_n&&!clear&&state_r==P_IDLE&&dma_cmd_ready;
    assign store_ready=rst_n&&!clear&&state_r==P_IDLE&&!load_valid;
    assign busy=state_r!=P_IDLE;
    assign store_armed=state_r==P_STORE_ARM||state_r==P_STORE;
    assign axi_active=state_r==P_LOAD||state_r==P_LOAD_DRAIN||state_r==P_STORE;
    assign phase=state_r;
    assign dma_rd_ready=state_r==P_LOAD&&!input_group_valid_r;
    assign mlp_input_valid=input_group_valid_r;
    assign mlp_input_bank=active_bank_r;
    assign mlp_input_group=input_group_r;
    assign mlp_out_ready=state_r==P_STORE&&!output_tile_valid_r;
    wire output_stream_ready = !output_stream_valid_r || dma_wr_ready;
    wire output_mux_stage0_ready = !output_mux_stage0_valid_r ||
        output_stream_ready;
    wire output_issue_valid = state_r==P_STORE&&output_tile_valid_r&&
        output_issue_count_r<32;
    wire output_issue_fire = output_issue_valid&&output_mux_stage0_ready;

    assign dma_wr_valid=state_r==P_STORE&&output_tile_valid_r&&
        output_stream_valid_r;
    assign dma_wr_data=output_stream_data_r;

    genvar input_bank;
    generate
      for(input_bank=0;input_bank<48;input_bank=input_bank+1)begin:
          g_input_beat_bank
        assign mlp_input_s24x16x32[input_bank*256+:256]=
          input_group_beat_r[input_bank];
        // Keep bank 47's payload CEs separate from the logically equivalent
        // input_group_valid update.
        (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
        u_input_beat_write_enable (
          .I0(rd_fire&&(input_beat_r==input_bank)),
          .O(input_beat_write_enable[input_bank])
        );
        always @(posedge clk)begin
          if(input_beat_write_enable[input_bank])
            input_group_beat_r[input_bank]<=dma_rd_data;
        end
      end
    endgenerate

    genvar output_bank;
    generate
      for(output_bank=0;output_bank<32;output_bank=output_bank+1)begin:
          g_output_beat_bank
        // While empty, every bank tracks the current source tile.  On the
        // output_fire edge the old hold value is still zero, so all 32 words
        // capture the handshaken payload; the replicated hold bits then
        // freeze only their local 256-bit banks until the final AXI beat.
        always @(posedge clk)begin
          if(!output_tile_hold_r[output_bank])
            output_tile_beat_r[output_bank]<=
              mlp_out_s32x16x16[output_bank*256+:256];
        end
      end
    endgenerate

    // Payload registers have no architectural reset value; their valid bits
    // are reset in the control block below.  Keeping payload writes in a
    // clock-only process prevents Vivado from inferring ambiguous FDCP cells
    // with simultaneous asynchronous set/reset behavior.
    always @(posedge clk) begin
      if(output_stream_ready&&output_mux_stage0_valid_r)begin
        case(output_mux_group_r)
          3'd0:output_stream_data_r<=output_mux_group_data_r[0];
          3'd1:output_stream_data_r<=output_mux_group_data_r[1];
          3'd2:output_stream_data_r<=output_mux_group_data_r[2];
          3'd3:output_stream_data_r<=output_mux_group_data_r[3];
          3'd4:output_stream_data_r<=output_mux_group_data_r[4];
          3'd5:output_stream_data_r<=output_mux_group_data_r[5];
          3'd6:output_stream_data_r<=output_mux_group_data_r[6];
          default:output_stream_data_r<=output_mux_group_data_r[7];
        endcase
      end
    end

    genvar output_mux_group;
    generate
      for(output_mux_group=0;output_mux_group<8;
          output_mux_group=output_mux_group+1)begin:
          g_output_mux_group
        // Keep the eight 256-load payload enables physically independent.  A
        // shared 2048-load CE is otherwise eligible for data-BUFG promotion.
        (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
        u_output_mux_group_write_enable (
          .I0(output_issue_fire),
          .O(output_mux_group_write_enable[output_mux_group])
        );
        always @(posedge clk)begin
          if(output_mux_group_write_enable[output_mux_group])
          case(output_issue_count_r[1:0])
            2'd0:output_mux_group_data_r[output_mux_group]<=
              output_tile_beat_r[output_mux_group*4];
            2'd1:output_mux_group_data_r[output_mux_group]<=
              output_tile_beat_r[output_mux_group*4+1];
            2'd2:output_mux_group_data_r[output_mux_group]<=
              output_tile_beat_r[output_mux_group*4+2];
            default:output_mux_group_data_r[output_mux_group]<=
              output_tile_beat_r[output_mux_group*4+3];
          endcase
        end
      end
    endgenerate

    hap_axi256_dma u_dma(
      .clk(clk),.rst_n(rst_n),.clear(clear),.cmd_valid(dma_cmd_valid),
      .cmd_ready(dma_cmd_ready),.cmd_write(dma_cmd_write),
      .cmd_base_addr(dma_cmd_base),.cmd_beat_count(dma_cmd_beats),
      .busy(dma_busy),.done(dma_done),.error(dma_error),
      .rd_valid(dma_rd_valid),.rd_ready(dma_rd_ready),.rd_data(dma_rd_data),
      .rd_last(dma_rd_last),.wr_valid(dma_wr_valid),.wr_ready(dma_wr_ready),
      .wr_data(dma_wr_data),.m_axi_arvalid(m_axi_arvalid),
      .m_axi_arready(m_axi_arready),.m_axi_araddr(m_axi_araddr),
      .m_axi_arlen(m_axi_arlen),.m_axi_arsize(m_axi_arsize),
      .m_axi_arburst(m_axi_arburst),.m_axi_rvalid(m_axi_rvalid),
      .m_axi_rready(m_axi_rready),.m_axi_rdata(m_axi_rdata),
      .m_axi_rresp(m_axi_rresp),.m_axi_rlast(m_axi_rlast),
      .m_axi_awvalid(m_axi_awvalid),.m_axi_awready(m_axi_awready),
      .m_axi_awaddr(m_axi_awaddr),.m_axi_awlen(m_axi_awlen),
      .m_axi_awsize(m_axi_awsize),.m_axi_awburst(m_axi_awburst),
      .m_axi_wvalid(m_axi_wvalid),.m_axi_wready(m_axi_wready),
      .m_axi_wdata(m_axi_wdata),.m_axi_wstrb(m_axi_wstrb),
      .m_axi_wlast(m_axi_wlast),.m_axi_bvalid(m_axi_bvalid),
      .m_axi_bready(m_axi_bready),.m_axi_bresp(m_axi_bresp),
      .command_count(),.read_beat_count(),.write_beat_count(),
      .burst_count(),.protocol_error_count());

    always @(posedge clk or negedge rst_n) begin
      if(!rst_n)begin state_r<=P_IDLE;active_bank_r<=0;input_group_r<=0;
        input_beat_r<=0;input_group_valid_r<=0;expected_output_tile_r<=0;
        output_beat_r<=0;output_tile_valid_r<=0;done<=0;load_done<=0;
        store_done<=0;error<=0;
        output_issue_count_r<=0;output_mux_group_r<=0;
        output_mux_stage0_valid_r<=0;output_stream_valid_r<=0;
        output_tile_hold_r<=32'd0;
        input_beat_count<=0;input_group_count<=0;output_beat_count<=0;
        output_tile_count<=0;end
      else if(clear)begin state_r<=P_IDLE;input_group_valid_r<=0;
        output_tile_valid_r<=0;done<=0;load_done<=0;store_done<=0;
        output_issue_count_r<=0;output_mux_stage0_valid_r<=0;
        output_stream_valid_r<=0;
        output_tile_hold_r<=32'd0;
        error<=0;input_beat_count<=0;
        input_group_count<=0;output_beat_count<=0;output_tile_count<=0;end
      else begin done<=0;load_done<=0;store_done<=0;if(dma_error)error<=1;
        if(start_load)begin state_r<=P_LOAD;active_bank_r<=load_bank;
          input_group_r<=0;input_beat_r<=0;input_group_valid_r<=0;
          input_beat_count<=0;input_group_count<=0;end
        if(arm_store)begin state_r<=P_STORE_ARM;expected_output_tile_r<=0;
          output_beat_r<=0;output_tile_valid_r<=0;
          output_issue_count_r<=0;output_mux_stage0_valid_r<=0;
          output_stream_valid_r<=0;
          output_tile_hold_r<=32'd0;output_beat_count<=0;
          output_tile_count<=0;end
        if(start_store_dma)state_r<=P_STORE;
        if(rd_fire)begin
          input_beat_count<=input_beat_count+1;
          if(input_beat_r==47)begin input_beat_r<=0;input_group_valid_r<=1;end
          else input_beat_r<=input_beat_r+1;end
        if(input_fire)begin input_group_valid_r<=0;
          input_group_count<=input_group_count+1;
          if(input_group_r+1==INPUT_GROUPS)begin
            if(dma_done)begin state_r<=P_IDLE;done<=1;load_done<=1;end
            else state_r<=P_LOAD_DRAIN;end
          else input_group_r<=input_group_r+1;end
        // input_fire owns the completion decision when the final consumer
        // handshake and DMA done pulse coincide.  Without this priority, the
        // drain assignment below can overwrite the IDLE transition above.
        if(state_r==P_LOAD&&dma_done&&!input_fire)begin
          if(input_group_valid_r||input_group_count<INPUT_GROUPS)state_r<=P_LOAD_DRAIN;
          else begin state_r<=P_IDLE;done<=1;load_done<=1;end end
        if(state_r==P_LOAD_DRAIN&&input_fire&&input_group_r+1==INPUT_GROUPS)begin
          state_r<=P_IDLE;done<=1;load_done<=1;end
        if(output_fire)begin
          if(mlp_out_tile!=expected_output_tile_r)error<=1;
          output_tile_valid_r<=1;
          output_tile_hold_r<={32{1'b1}};
          output_beat_r<=0;output_issue_count_r<=0;
          output_mux_stage0_valid_r<=0;output_stream_valid_r<=0;end
        if(output_stream_ready)begin
          output_stream_valid_r<=output_mux_stage0_valid_r;
        end
        if(output_mux_stage0_ready)begin
          output_mux_stage0_valid_r<=output_issue_valid;
          if(output_issue_valid)begin
            output_mux_group_r<=output_issue_count_r[4:2];
          end
        end
        if(output_issue_fire)
          output_issue_count_r<=output_issue_count_r+1'b1;
        if(wr_fire)begin output_beat_count<=output_beat_count+1;
          if(output_beat_r==31)begin output_beat_r<=0;output_tile_valid_r<=0;
            output_issue_count_r<=0;
            output_tile_hold_r<=32'd0;
            output_tile_count<=output_tile_count+1;
            expected_output_tile_r<=expected_output_tile_r+1;end
          else output_beat_r<=output_beat_r+1;end
        if(state_r==P_STORE&&dma_done)begin
          if(output_tile_count!=OUTPUT_TILES||output_tile_valid_r)error<=1;
          state_r<=P_IDLE;done<=1;store_done<=1;end
      end
    end
    initial if(PRODUCTION_SHAPE&&(INPUT_GROUPS!=128||OUTPUT_TILES!=256))
      $error("hap_mlp_tensor_dma_bridge production shape required");
endmodule
