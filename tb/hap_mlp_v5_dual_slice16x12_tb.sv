`timescale 1ns / 1ps

module hap_mlp_v5_dual_slice16x12_tb;
    localparam integer GATE_GROUPS=128;
    localparam integer DOWN_GROUPS=5;
    localparam integer DOWN_TILES=4;
    localparam integer DOWN_TOTAL=DOWN_GROUPS*DOWN_TILES;
    reg clk=0; always #3.333 clk=~clk;
    reg rst_n=0, clear=0;
    integer cycle_count=0, gate_send=0, gate_receive=0, down_send=0, down_receive=0;
    integer mismatch_count=0, stall_count=0, stable_count=0;
    integer down_last_accept=-1, down_max_accept_interval=0;
    integer down_ii_samples=0;
    reg gate_out_ready=0, down_out_ready=0;

    reg [4607:0] gate_activation[0:GATE_GROUPS-1];
    reg [1535:0] gate_weight[0:GATE_GROUPS-1];
    reg [223:0] gate_ameta[0:GATE_GROUPS-1];
    reg [167:0] gate_wmeta[0:GATE_GROUPS-1];
    reg [11:0] gate_mask[0:GATE_GROUPS-1];
    reg [4607:0] gate_expected[0:0];
    reg [6911:0] gate_guard_expected[0:GATE_GROUPS-1];
    reg [4607:0] down_activation[0:DOWN_TOTAL-1];
    reg [1535:0] down_weight[0:DOWN_TOTAL-1];
    reg [223:0] down_ameta[0:DOWN_TOTAL-1];
    reg [167:0] down_wmeta[0:DOWN_TOTAL-1];
    reg [11:0] down_mask[0:DOWN_TOTAL-1];
    reg [4607:0] down_expected[0:DOWN_TILES-1];

    wire gate_in_valid=gate_send<GATE_GROUPS;
    wire gate_in_ready,gate_out_valid,gate_error;
    wire [4607:0] gate_projection;
    wire [31:0] gate_input_count,gate_output_count,gate_saturation;
    wire [6:0] gate_source=gate_send<GATE_GROUPS?gate_send:GATE_GROUPS-1;

    hap_mlp_gate_up_dual_slice16x12_s43 gate_dut(
      .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(gate_in_valid),.in_ready(gate_in_ready),
      .in_first_group(gate_send==0),.in_last_group(gate_send==GATE_GROUPS-1),
      .activation_s9x16x32(gate_activation[gate_source]),.weights_s4x12x32(gate_weight[gate_source]),
      .activation_code_u8x16(gate_ameta[gate_source][127:0]),.activation_shift_u6x16(gate_ameta[gate_source][223:128]),
      .weight_code_u8x12(gate_wmeta[gate_source][95:0]),.weight_shift_u6x12(gate_wmeta[gate_source][167:96]),
      .column_valid_u12(gate_mask[gate_source]),.out_valid(gate_out_valid),.out_ready(gate_out_ready),
      .projection_s24x16x12(gate_projection),.input_group_count(gate_input_count),
      .output_pass_count(gate_output_count),.saturation_count(gate_saturation),.error(gate_error));

    wire down_in_valid=down_send<DOWN_TOTAL;
    wire down_in_ready,down_out_valid,down_error;
    wire [1:0] down_tile;
    wire [4607:0] down_projection;
    wire [31:0] down_input_count,down_output_count,down_saturation;
    wire [4:0] down_source=down_send<DOWN_TOTAL?down_send:DOWN_TOTAL-1;
    wire [1:0] down_tile_in=down_send%DOWN_TILES;
    hap_mlp_down_group_major_dual_slice16x12_s45 #(.TILES(DOWN_TILES),.GROUPS(DOWN_GROUPS)) down_dut(
      .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(down_in_valid),.in_ready(down_in_ready),
      .in_first_group(down_send/DOWN_TILES==0),.in_last_group(down_send/DOWN_TILES==DOWN_GROUPS-1),
      .in_tile_index(down_tile_in),.activation_s9x16x32(down_activation[down_source]),
      .weights_s4x12x32(down_weight[down_source]),.activation_code_u8x16(down_ameta[down_source][127:0]),
      .activation_shift_u6x16(down_ameta[down_source][223:128]),.weight_code_u8x12(down_wmeta[down_source][95:0]),
      .weight_shift_u6x12(down_wmeta[down_source][167:96]),.column_valid_u12(down_mask[down_source]),
      .out_valid(down_out_valid),.out_ready(down_out_ready),.out_tile_index(down_tile),
      .projection_s24x16x12(down_projection),.input_tile_count(down_input_count),
      .output_pass_count(down_output_count),.saturation_count(down_saturation),.error(down_error));

    reg gate_stalled=0,down_stalled=0;
    integer gate_forced_stall=0, down_forced_stall=0;
    integer gate_stall_remaining=4, down_stall_remaining=4;
    reg [4607:0] gate_hold,down_hold; reg [1:0] down_tile_hold;
    reg signed [42:0] observed_guard_sum0=0;
    reg signed [42:0] source_model_sum0=0;
    integer guard_debug_index=0;
    integer stage_debug_index=0;
    initial begin
      $readmemh("data/mlp_v5_dual_slice16x12/gate_activation_s9x16x32.mem",gate_activation);
      $readmemh("data/mlp_v5_dual_slice16x12/gate_weights_s4x12x32.mem",gate_weight);
      $readmemh("data/mlp_v5_dual_slice16x12/gate_activation_meta_u224.mem",gate_ameta);
      $readmemh("data/mlp_v5_dual_slice16x12/gate_weight_meta_u168.mem",gate_wmeta);
      $readmemh("data/mlp_v5_dual_slice16x12/gate_column_valid_u12.mem",gate_mask);
      $readmemh("data/mlp_v5_dual_slice16x12/gate_expected_s24x16x12.mem",gate_expected);
      $readmemh("data/mlp_v5_dual_slice16x12/gate_expected_s36x16x12.mem",gate_guard_expected);
      $readmemh("data/mlp_v5_dual_slice16x12/down_activation_s9x16x32.mem",down_activation);
      $readmemh("data/mlp_v5_dual_slice16x12/down_weights_s4x12x32.mem",down_weight);
      $readmemh("data/mlp_v5_dual_slice16x12/down_activation_meta_u224.mem",down_ameta);
      $readmemh("data/mlp_v5_dual_slice16x12/down_weight_meta_u168.mem",down_wmeta);
      $readmemh("data/mlp_v5_dual_slice16x12/down_column_valid_u12.mem",down_mask);
      $readmemh("data/mlp_v5_dual_slice16x12/down_expected_s24x16x12.mem",down_expected);
      repeat(6)@(posedge clk);rst_n<=1;
    end

    always @(posedge clk) if(rst_n) begin
      cycle_count<=cycle_count+1;
      if(gate_receive==0&&gate_stall_remaining>0)begin
        gate_out_ready<=0;
        if(gate_out_valid) gate_stall_remaining=gate_stall_remaining-1;
      end else gate_out_ready<=cycle_count%7!=2;
      if(down_receive==0&&down_stall_remaining>0)begin
        down_out_ready<=0;
        if(down_out_valid) down_stall_remaining=down_stall_remaining-1;
      end else down_out_ready<=cycle_count%11!=4&&cycle_count%13!=7;
      if(gate_in_valid&&gate_in_ready)begin
        gate_send<=gate_send+1;
        source_model_sum0<=source_model_sum0+$signed(gate_dut.u_slice0.guard_s36x8x12[35:0]);
      end
      if(down_in_valid&&down_in_ready)begin
        down_send<=down_send+1;
        if(down_last_accept>=0&&cycle_count-down_last_accept>down_max_accept_interval)
          down_max_accept_interval<=cycle_count-down_last_accept;
        if(down_last_accept>=0) down_ii_samples<=down_ii_samples+1;
        down_last_accept<=cycle_count;
      end
      if(gate_dut.guard_fire) begin
        if(gate_dut.joined_guard!==gate_guard_expected[guard_debug_index])begin
          $display("MISMATCH gate guard index=%0d lane0 got=%h expected=%h",
            guard_debug_index,gate_dut.joined_guard[35:0],
            gate_guard_expected[guard_debug_index][35:0]);
          mismatch_count<=mismatch_count+1;
        end
        observed_guard_sum0<=observed_guard_sum0+$signed(gate_dut.joined_guard[35:0]);
        guard_debug_index<=guard_debug_index+1;
      end
      if(gate_dut.slice0_accept) stage_debug_index<=stage_debug_index+1;
      if(gate_stalled)begin stable_count<=stable_count+1;if(!gate_out_valid||gate_projection!==gate_hold)begin $display("MISMATCH gate stall");mismatch_count<=mismatch_count+1;end end
      if(down_stalled)begin stable_count<=stable_count+1;if(!down_out_valid||down_projection!==down_hold||down_tile!==down_tile_hold)begin $display("MISMATCH down stall");mismatch_count<=mismatch_count+1;end end
      gate_stalled<=gate_out_valid&&!gate_out_ready;down_stalled<=down_out_valid&&!down_out_ready;
      if(gate_out_valid&&!gate_out_ready)begin gate_hold<=gate_projection;stall_count=stall_count+1;end
      if(down_out_valid&&!down_out_ready)begin down_hold<=down_projection;down_tile_hold<=down_tile;stall_count=stall_count+1;end
      if(gate_out_valid&&gate_out_ready)begin
        gate_receive<=gate_receive+1;
        if(gate_projection!==gate_expected[0])begin
          $display("MISMATCH gate result");
          mismatch_count<=mismatch_count+1;end
      end
      if(down_out_valid&&down_out_ready)begin
        if(down_tile!==down_receive||down_projection!==down_expected[down_receive])begin $display("MISMATCH down result tile=%0d got=%0d",down_receive,down_tile);mismatch_count<=mismatch_count+1;end
        down_receive<=down_receive+1;
        if(down_receive+1==DOWN_TILES)begin
          // Down can finish before the independent gate test.  Completion is
          // checked below only after both streams have drained.
        end
      end
      if(cycle_count>2000)$fatal(1,"FAIL timeout gate=%0d down=%0d output=%0d err=%0d/%0d",gate_send,down_send,down_receive,gate_error,down_error);
      if(gate_error)begin
        $display("DEBUG gate error cycle=%0d kernel=%0d/%0d accum=%0d",
          cycle_count,gate_dut.kernel_error0,gate_dut.kernel_error1,
          gate_dut.accum_error);
        $fatal(1,"gate debug stop");
      end
      if(down_receive==DOWN_TILES && gate_receive==1)begin
        if(mismatch_count==0&&!gate_error&&!down_error&&gate_input_count==GATE_GROUPS&&
           down_input_count==DOWN_TOTAL&&down_output_count==DOWN_TILES&&stall_count>0&&stable_count>0&&
           down_max_accept_interval<=1&&down_ii_samples==DOWN_TOTAL-1)
          begin $display("PASS: V5 dual 16x12 gate/down bit-exact gate=%0d down=%0d cycles=%0d stalls=%0d stable=%0d down_ii=%0d",gate_input_count,down_input_count,cycle_count,stall_count,stable_count,down_max_accept_interval);$finish;end
        else $fatal(1,"FAIL mismatch=%0d gate_err=%0d down_err=%0d counts=%0d/%0d/%0d/%0d stalls=%0d stable=%0d",mismatch_count,gate_error,down_error,gate_input_count,gate_output_count,down_input_count,down_output_count,stall_count,stable_count);
      end
    end
endmodule
