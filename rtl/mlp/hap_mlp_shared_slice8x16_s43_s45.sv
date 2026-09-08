`timescale 1ns / 1ps

// One physical A8W4 8x16 kernel shared by gate/up and down phases.  Mode/tags
// are queued with each kernel input.  S36 output fans only to local S43/S45
// accumulators in the same hierarchy; the selected valid/ready path is gated.
module hap_mlp_shared_slice8x16_s43_s45 #(
    parameter integer DOWN_TILES=256,
    parameter integer DOWN_GROUPS=448,
    parameter integer TILE_W=(DOWN_TILES<=2)?1:$clog2(DOWN_TILES),
    parameter integer INGRESS_DEPTH=2
) (
    input wire clk,input wire rst_n,input wire clear,
    input wire in_valid,output wire in_ready,input wire in_down,
    input wire in_first,input wire in_last,input wire [TILE_W-1:0] in_tile,
    input wire signed [2303:0] activation_s9x8x32,
    input wire signed [2047:0] weights_s4x16x32,
    input wire [63:0] activation_code_u8x8,
    input wire [47:0] activation_shift_u6x8,
    input wire [127:0] weight_code_u8x16,
    input wire [95:0] weight_shift_u6x16,
    output wire gate_valid,input wire gate_ready,
    output wire signed [3071:0] gate_s24x8x16,
    output wire down_valid,input wire down_ready,
    output wire [TILE_W-1:0] down_tile,
    output wire signed [3071:0] down_s24x8x16,
    output wire [31:0] gate_saturation,output wire [31:0] down_saturation,
    output wire error
);
    // A local two-entry payload FIFO is the physical SLR timing boundary.
    // Its ready depends only on registered local occupancy, never on the
    // kernel/recover/dot ready chain.  The dual-slice parent atomically pushes
    // both local FIFOs, so the two halves cannot lose alignment.
    reg clear_local_r;
    reg ingress_down [0:INGRESS_DEPTH-1];
    reg ingress_first [0:INGRESS_DEPTH-1];
    reg ingress_last [0:INGRESS_DEPTH-1];
    reg [TILE_W-1:0] ingress_tile [0:INGRESS_DEPTH-1];
    reg signed [2303:0] ingress_activation [0:INGRESS_DEPTH-1];
    reg signed [2047:0] ingress_weights [0:INGRESS_DEPTH-1];
    reg [63:0] ingress_activation_code [0:INGRESS_DEPTH-1];
    reg [47:0] ingress_activation_shift [0:INGRESS_DEPTH-1];
    reg [127:0] ingress_weight_code [0:INGRESS_DEPTH-1];
    reg [95:0] ingress_weight_shift [0:INGRESS_DEPTH-1];
    reg ingress_wr_r,ingress_rd_r;
    reg [1:0] ingress_count_r;

    reg tag_mode[0:31],tag_first[0:31],tag_last[0:31];
    reg [TILE_W-1:0] tag_tile[0:31];
    reg [4:0] wr_r,rd_r;reg [5:0] count_r;
    wire full=count_r==32,empty=count_r==0;
    wire ingress_full=ingress_count_r==INGRESS_DEPTH;
    wire ingress_empty=ingress_count_r==0;
    wire kernel_ready,kernel_valid;
    wire signed [4607:0] guard;
    wire gate_acc_ready,down_acc_ready;
    wire selected_ready=tag_mode[rd_r]?down_acc_ready:gate_acc_ready;
    wire kernel_fire=kernel_valid&&!empty&&selected_ready;
    wire input_fire=in_valid&&in_ready;
    wire dispatch_valid=!ingress_empty&&!full;
    wire dispatch_fire=dispatch_valid&&kernel_ready;
    wire kernel_error,gate_error,down_error;
    assign in_ready=rst_n&&!clear_local_r&&!ingress_full;

    hap_a8w4_slice8x16_group_s36 u_kernel(
      .clk(clk),.rst_n(rst_n),.clear(clear_local_r),
      .in_valid(dispatch_valid),.in_ready(kernel_ready),
      .activation_s9x8x32(ingress_activation[ingress_rd_r]),
      .weights_s4x16x32(ingress_weights[ingress_rd_r]),
      .activation_code_u8x8(ingress_activation_code[ingress_rd_r]),
      .activation_shift_u6x8(ingress_activation_shift[ingress_rd_r]),
      .weight_code_u8x16(ingress_weight_code[ingress_rd_r]),
      .weight_shift_u6x16(ingress_weight_shift[ingress_rd_r]),
      .out_valid(kernel_valid),.out_ready(!empty&&selected_ready),
      .guard_s36x8x16(guard),.input_group_count(),.output_group_count(),
      .error(kernel_error));

    hap_mlp_tile_accum_s36 #(.LANES(128),.ACC_W(43),.GROUPS(128))
    u_gate_accum(
      .clk(clk),.rst_n(rst_n),.clear(clear_local_r),
      .in_valid(kernel_valid&&!empty&&!tag_mode[rd_r]),
      .in_ready(gate_acc_ready),.in_first_group(tag_first[rd_r]),
      .in_last_group(tag_last[rd_r]),.in_guard_s36(guard),
      .out_valid(gate_valid),.out_ready(gate_ready),
      .out_projection_s24(gate_s24x8x16),.input_group_count(),
      .output_tile_count(),.saturation_count(gate_saturation),
      .error(gate_error));

    hap_mlp_down_group_major_accum_s45 #(
      .LANES(128),.TILES(DOWN_TILES),.GROUPS(DOWN_GROUPS),.TILE_W(TILE_W))
    u_down_accum(
      .clk(clk),.rst_n(rst_n),.clear(clear_local_r),
      .in_valid(kernel_valid&&!empty&&tag_mode[rd_r]),
      .in_ready(down_acc_ready),.in_first_group(tag_first[rd_r]),
      .in_last_group(tag_last[rd_r]),.in_tile_index(tag_tile[rd_r]),
      .in_guard_s36(guard),.out_valid(down_valid),.out_ready(down_ready),
      .out_tile_index(down_tile),.out_projection_s24(down_s24x8x16),
      .input_tile_count(),.input_group_count(),.output_tile_count(),
      .saturation_count(down_saturation),.error(down_error));

    assign error=kernel_error||gate_error||down_error;
    always @(posedge clk or negedge rst_n) begin
      if(!rst_n) clear_local_r<=1'b1;
      else clear_local_r<=clear;
    end
    always @(posedge clk) begin
      if(!rst_n||clear_local_r)begin
        ingress_wr_r<=0;ingress_rd_r<=0;ingress_count_r<=0;
        wr_r<=0;rd_r<=0;count_r<=0;
      end else begin
        if(input_fire)begin
          ingress_down[ingress_wr_r]<=in_down;
          ingress_first[ingress_wr_r]<=in_first;
          ingress_last[ingress_wr_r]<=in_last;
          ingress_tile[ingress_wr_r]<=in_tile;
          ingress_activation[ingress_wr_r]<=activation_s9x8x32;
          ingress_weights[ingress_wr_r]<=weights_s4x16x32;
          ingress_activation_code[ingress_wr_r]<=activation_code_u8x8;
          ingress_activation_shift[ingress_wr_r]<=activation_shift_u6x8;
          ingress_weight_code[ingress_wr_r]<=weight_code_u8x16;
          ingress_weight_shift[ingress_wr_r]<=weight_shift_u6x16;
          ingress_wr_r<=ingress_wr_r+1'b1;
        end
        if(dispatch_fire)begin
          tag_mode[wr_r]<=ingress_down[ingress_rd_r];
          tag_first[wr_r]<=ingress_first[ingress_rd_r];
          tag_last[wr_r]<=ingress_last[ingress_rd_r];
          tag_tile[wr_r]<=ingress_tile[ingress_rd_r];
          wr_r<=wr_r+1'b1;
          ingress_rd_r<=ingress_rd_r+1'b1;
        end
        case({input_fire,dispatch_fire})
          2'b10:ingress_count_r<=ingress_count_r+1'b1;
          2'b01:ingress_count_r<=ingress_count_r-1'b1;
          default:ingress_count_r<=ingress_count_r;
        endcase
        if(kernel_fire)rd_r<=rd_r+1;
        case({dispatch_fire,kernel_fire})2'b10:count_r<=count_r+1;
          2'b01:count_r<=count_r-1;default:count_r<=count_r;endcase
      end
    end
    initial begin
      if(INGRESS_DEPTH!=2)
        $error("shared slice SLR ingress FIFO must have depth 2");
    end
endmodule
