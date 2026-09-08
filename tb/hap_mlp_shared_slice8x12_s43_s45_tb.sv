`timescale 1ns / 1ps

module hap_mlp_shared_slice8x12_s43_s45_tb;
    localparam integer GATE_GROUPS=128;
    localparam integer DOWN_GROUPS=448;
    localparam integer TOTAL=GATE_GROUPS+DOWN_GROUPS;
    reg clk=0; always #3.333 clk=~clk;
    reg rst_n=0,clear=0,out_ready=1;
    integer send_index=0,cycle_count=0,mismatch_count=0;
    integer gate_received=0,down_received=0,last_accept=-1,max_ii=0;
    wire in_valid=send_index<TOTAL;
    wire in_ready;
    wire [9:0] source_index=send_index<TOTAL?send_index:TOTAL-1;
    reg [2303:0] activation_mem[0:TOTAL-1];
    reg [1535:0] weight_mem[0:TOTAL-1];
    reg [111:0] activation_meta_mem[0:TOTAL-1];
    reg [167:0] weight_meta_mem[0:TOTAL-1];
    reg [2:0] tag_mem[0:TOTAL-1];
    reg [11:0] mask_mem[0:TOTAL-1];
    reg [2303:0] expected_gate_mem[0:0],expected_down_mem[0:0];
    wire gate_valid,down_valid,error;
    wire [2303:0] gate_projection,down_projection;

    hap_mlp_shared_slice8x12_s43_s45 dut(
      .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(in_valid),
      .in_ready(in_ready),.in_down(tag_mem[source_index][2]),
      .in_first(tag_mem[source_index][1]),.in_last(tag_mem[source_index][0]),
      .activation_s9x8x32(activation_mem[source_index]),
      .weights_s4x12x32(weight_mem[source_index]),
      .activation_code_u8x8(activation_meta_mem[source_index][63:0]),
      .activation_shift_u6x8(activation_meta_mem[source_index][111:64]),
      .weight_code_u8x12(weight_meta_mem[source_index][95:0]),
      .weight_shift_u6x12(weight_meta_mem[source_index][167:96]),
      .column_valid_u12(mask_mem[source_index]),
      .gate_valid(gate_valid),.gate_ready(out_ready),
      .gate_s24x8x12(gate_projection),
      .down_valid(down_valid),.down_ready(out_ready),
      .down_s24x8x12(down_projection),
      .gate_saturation(),.down_saturation(),.error(error));

    initial begin
      $readmemh("data/mlp_shared_slice8x12/activation_s9x8x32.mem",activation_mem);
      $readmemh("data/mlp_shared_slice8x12/weights_s4x12x32.mem",weight_mem);
      $readmemh("data/mlp_shared_slice8x12/activation_meta_u112.mem",activation_meta_mem);
      $readmemh("data/mlp_shared_slice8x12/weight_meta_u168.mem",weight_meta_mem);
      $readmemh("data/mlp_shared_slice8x12/tags_u3.mem",tag_mem);
      $readmemh("data/mlp_shared_slice8x12/column_valid_u12.mem",mask_mem);
      $readmemh("data/mlp_shared_slice8x12/expected_gate_s24x8x12.mem",expected_gate_mem);
      $readmemh("data/mlp_shared_slice8x12/expected_down_s24x8x12.mem",expected_down_mem);
      repeat(5)@(posedge clk);rst_n<=1;
    end

    always @(posedge clk) begin
      if(rst_n)begin
        cycle_count<=cycle_count+1;
        out_ready<=((cycle_count%13)!=4&&(cycle_count%17)!=9);
        if(in_valid&&in_ready)begin
          send_index<=send_index+1;
          if(send_index<64&&last_accept>=0&&cycle_count-last_accept>max_ii)
            max_ii<=cycle_count-last_accept;
          last_accept<=cycle_count;
        end
        if(gate_valid&&out_ready)begin
          if(gate_projection!==expected_gate_mem[0])begin
            $display("MISMATCH gate");mismatch_count<=mismatch_count+1;end
          gate_received<=gate_received+1;
        end
        if(down_valid&&out_ready)begin
          if(down_projection!==expected_down_mem[0])begin
            $display("MISMATCH down");mismatch_count<=mismatch_count+1;end
          down_received<=down_received+1;
          if(down_received+1==1)begin
            if(mismatch_count==0&&!error&&gate_received==1&&max_ii<=1)
              begin $display("PASS: hap_mlp_shared_slice8x12 S43/S45 transactions=%0d cycles=%0d mismatches=0 row_major_index=12 unstalled_ii=%0d",TOTAL,cycle_count,max_ii);$finish;end
            else $fatal(1,"FAIL mismatch=%0d error=%0d gate=%0d down=%0d ii=%0d",mismatch_count,error,gate_received,down_received+1,max_ii);
          end
        end
        if(cycle_count>1600)$fatal(1,"FAIL timeout send=%0d gate=%0d down=%0d error=%0d",send_index,gate_received,down_received,error);
      end
    end
endmodule

