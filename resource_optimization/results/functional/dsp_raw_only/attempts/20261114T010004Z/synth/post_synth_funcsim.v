// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2025 Advanced Micro Devices, Inc. All Rights Reserved.
// --------------------------------------------------------------------------------
// Tool Version: Vivado v.2025.2 (lin64) Build 6299465 Fri Nov 14 12:34:56 MST 2025
// Date        : Sat Nov 14 09:00:44 2026
// Host        : user running 64-bit Ubuntu 24.04.4 LTS
// Command     : write_verilog -force -mode funcsim
//               /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/0_Hardware_supplementation_experiment/experiment/mlp_scalecode_dsp_board/functional/dsp_raw_only/attempts/20261114T010004Z/synth/post_synth_funcsim.v
// Design      : hap_a8w4_scalecode_recover2_lut
// Purpose     : This verilog netlist is a functional simulation representation of the design and should not be modified
//               or synthesized. This netlist cannot be used for SDF annotated simulation.
// Device      : xcvu9p-flga2104-2L-e
// --------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

(* NotValidForBitStream *)
module hap_a8w4_scalecode_recover2_lut
   (clk,
    rst_n,
    clear,
    in_valid,
    in_ready,
    dot0_s17,
    dot1_s17,
    activation_code_u8,
    weight0_code_u8,
    weight1_code_u8,
    out_valid,
    out_ready,
    raw0_s33,
    raw1_s33);
  input clk;
  input rst_n;
  input clear;
  input in_valid;
  output in_ready;
  input [16:0]dot0_s17;
  input [16:0]dot1_s17;
  input [7:0]activation_code_u8;
  input [7:0]weight0_code_u8;
  input [7:0]weight1_code_u8;
  output out_valid;
  input out_ready;
  output [32:0]raw0_s33;
  output [32:0]raw1_s33;

  wire RSTP;
  wire [7:0]activation_code_u8;
  wire clear;
  wire clk;
  wire [16:0]dot0_s17;
  wire [16:0]dot1_s17;
  wire in_ready;
  wire in_valid;
  wire out_ready;
  wire out_valid;
  wire out_valid_i_1_n_0;
  wire out_valid_i_2_n_0;
  wire [32:0]raw0_s33;
  wire raw0_s33_reg_i_100_n_0;
  wire raw0_s33_reg_i_10_n_0;
  wire raw0_s33_reg_i_11_n_0;
  wire raw0_s33_reg_i_12_n_0;
  wire raw0_s33_reg_i_13_n_0;
  wire raw0_s33_reg_i_14_n_0;
  wire raw0_s33_reg_i_15_n_0;
  wire raw0_s33_reg_i_16_n_0;
  wire raw0_s33_reg_i_17_n_0;
  wire raw0_s33_reg_i_18_n_0;
  wire raw0_s33_reg_i_19_n_0;
  wire raw0_s33_reg_i_1_n_0;
  wire raw0_s33_reg_i_20_n_0;
  wire raw0_s33_reg_i_21_n_0;
  wire raw0_s33_reg_i_22_n_0;
  wire raw0_s33_reg_i_23_n_0;
  wire raw0_s33_reg_i_24_n_0;
  wire raw0_s33_reg_i_25_n_0;
  wire raw0_s33_reg_i_26_n_0;
  wire raw0_s33_reg_i_27_n_0;
  wire raw0_s33_reg_i_28_n_0;
  wire raw0_s33_reg_i_29_n_0;
  wire raw0_s33_reg_i_2_n_0;
  wire raw0_s33_reg_i_30_n_0;
  wire raw0_s33_reg_i_31_n_0;
  wire raw0_s33_reg_i_32_n_0;
  wire raw0_s33_reg_i_33_n_0;
  wire raw0_s33_reg_i_34_n_0;
  wire raw0_s33_reg_i_35_n_0;
  wire raw0_s33_reg_i_36_n_0;
  wire raw0_s33_reg_i_37_n_0;
  wire raw0_s33_reg_i_38_n_0;
  wire raw0_s33_reg_i_39_n_0;
  wire raw0_s33_reg_i_3_n_0;
  wire raw0_s33_reg_i_40_n_0;
  wire raw0_s33_reg_i_41_n_0;
  wire raw0_s33_reg_i_42_n_0;
  wire raw0_s33_reg_i_43_n_0;
  wire raw0_s33_reg_i_44_n_0;
  wire raw0_s33_reg_i_45_n_0;
  wire raw0_s33_reg_i_46_n_0;
  wire raw0_s33_reg_i_47_n_14;
  wire raw0_s33_reg_i_47_n_15;
  wire raw0_s33_reg_i_47_n_6;
  wire raw0_s33_reg_i_47_n_7;
  wire raw0_s33_reg_i_48_n_0;
  wire raw0_s33_reg_i_49_n_0;
  wire raw0_s33_reg_i_50_n_0;
  wire raw0_s33_reg_i_51_n_0;
  wire raw0_s33_reg_i_52_n_0;
  wire raw0_s33_reg_i_53_n_0;
  wire raw0_s33_reg_i_54_n_0;
  wire raw0_s33_reg_i_55_n_0;
  wire raw0_s33_reg_i_56_n_0;
  wire raw0_s33_reg_i_57_n_0;
  wire raw0_s33_reg_i_58_n_0;
  wire raw0_s33_reg_i_59_n_0;
  wire raw0_s33_reg_i_5_n_11;
  wire raw0_s33_reg_i_5_n_12;
  wire raw0_s33_reg_i_5_n_13;
  wire raw0_s33_reg_i_5_n_14;
  wire raw0_s33_reg_i_5_n_15;
  wire raw0_s33_reg_i_5_n_4;
  wire raw0_s33_reg_i_5_n_5;
  wire raw0_s33_reg_i_5_n_6;
  wire raw0_s33_reg_i_5_n_7;
  wire raw0_s33_reg_i_60_n_0;
  wire raw0_s33_reg_i_61_n_0;
  wire raw0_s33_reg_i_61_n_1;
  wire raw0_s33_reg_i_61_n_10;
  wire raw0_s33_reg_i_61_n_11;
  wire raw0_s33_reg_i_61_n_12;
  wire raw0_s33_reg_i_61_n_13;
  wire raw0_s33_reg_i_61_n_14;
  wire raw0_s33_reg_i_61_n_15;
  wire raw0_s33_reg_i_61_n_2;
  wire raw0_s33_reg_i_61_n_3;
  wire raw0_s33_reg_i_61_n_4;
  wire raw0_s33_reg_i_61_n_5;
  wire raw0_s33_reg_i_61_n_6;
  wire raw0_s33_reg_i_61_n_7;
  wire raw0_s33_reg_i_61_n_8;
  wire raw0_s33_reg_i_61_n_9;
  wire raw0_s33_reg_i_62_n_0;
  wire raw0_s33_reg_i_63_n_0;
  wire raw0_s33_reg_i_64_n_0;
  wire raw0_s33_reg_i_65_n_0;
  wire raw0_s33_reg_i_66_n_0;
  wire raw0_s33_reg_i_67_n_0;
  wire raw0_s33_reg_i_68_n_0;
  wire raw0_s33_reg_i_69_n_0;
  wire raw0_s33_reg_i_6_n_0;
  wire raw0_s33_reg_i_6_n_1;
  wire raw0_s33_reg_i_6_n_10;
  wire raw0_s33_reg_i_6_n_11;
  wire raw0_s33_reg_i_6_n_12;
  wire raw0_s33_reg_i_6_n_13;
  wire raw0_s33_reg_i_6_n_14;
  wire raw0_s33_reg_i_6_n_15;
  wire raw0_s33_reg_i_6_n_2;
  wire raw0_s33_reg_i_6_n_3;
  wire raw0_s33_reg_i_6_n_4;
  wire raw0_s33_reg_i_6_n_5;
  wire raw0_s33_reg_i_6_n_6;
  wire raw0_s33_reg_i_6_n_7;
  wire raw0_s33_reg_i_6_n_8;
  wire raw0_s33_reg_i_6_n_9;
  wire raw0_s33_reg_i_70_n_0;
  wire raw0_s33_reg_i_71_n_0;
  wire raw0_s33_reg_i_72_n_0;
  wire raw0_s33_reg_i_73_n_0;
  wire raw0_s33_reg_i_74_n_0;
  wire raw0_s33_reg_i_75_n_0;
  wire raw0_s33_reg_i_76_n_14;
  wire raw0_s33_reg_i_76_n_15;
  wire raw0_s33_reg_i_76_n_6;
  wire raw0_s33_reg_i_76_n_7;
  wire raw0_s33_reg_i_77_n_0;
  wire raw0_s33_reg_i_78_n_0;
  wire raw0_s33_reg_i_79_n_0;
  wire raw0_s33_reg_i_7_n_0;
  wire raw0_s33_reg_i_7_n_1;
  wire raw0_s33_reg_i_7_n_10;
  wire raw0_s33_reg_i_7_n_11;
  wire raw0_s33_reg_i_7_n_12;
  wire raw0_s33_reg_i_7_n_13;
  wire raw0_s33_reg_i_7_n_14;
  wire raw0_s33_reg_i_7_n_15;
  wire raw0_s33_reg_i_7_n_2;
  wire raw0_s33_reg_i_7_n_3;
  wire raw0_s33_reg_i_7_n_4;
  wire raw0_s33_reg_i_7_n_5;
  wire raw0_s33_reg_i_7_n_6;
  wire raw0_s33_reg_i_7_n_7;
  wire raw0_s33_reg_i_7_n_8;
  wire raw0_s33_reg_i_7_n_9;
  wire raw0_s33_reg_i_80_n_0;
  wire raw0_s33_reg_i_81_n_0;
  wire raw0_s33_reg_i_82_n_0;
  wire raw0_s33_reg_i_83_n_0;
  wire raw0_s33_reg_i_84_n_0;
  wire raw0_s33_reg_i_85_n_0;
  wire raw0_s33_reg_i_86_n_0;
  wire raw0_s33_reg_i_87_n_0;
  wire raw0_s33_reg_i_88_n_0;
  wire raw0_s33_reg_i_89_n_0;
  wire raw0_s33_reg_i_90_n_0;
  wire raw0_s33_reg_i_91_n_0;
  wire raw0_s33_reg_i_92_n_0;
  wire raw0_s33_reg_i_93_n_0;
  wire raw0_s33_reg_i_94_n_0;
  wire raw0_s33_reg_i_95_n_0;
  wire raw0_s33_reg_i_96_n_0;
  wire raw0_s33_reg_i_97_n_0;
  wire raw0_s33_reg_i_98_n_0;
  wire raw0_s33_reg_i_99_n_0;
  wire raw0_s33_reg_i_9_n_0;
  wire [32:0]raw1_s33;
  wire raw1_s33_reg_i_10_n_0;
  wire raw1_s33_reg_i_11_n_0;
  wire raw1_s33_reg_i_12_n_0;
  wire raw1_s33_reg_i_13_n_0;
  wire raw1_s33_reg_i_14_n_0;
  wire raw1_s33_reg_i_15_n_0;
  wire raw1_s33_reg_i_16_n_0;
  wire raw1_s33_reg_i_17_n_0;
  wire raw1_s33_reg_i_18_n_0;
  wire raw1_s33_reg_i_19_n_0;
  wire raw1_s33_reg_i_1_n_11;
  wire raw1_s33_reg_i_1_n_12;
  wire raw1_s33_reg_i_1_n_13;
  wire raw1_s33_reg_i_1_n_14;
  wire raw1_s33_reg_i_1_n_15;
  wire raw1_s33_reg_i_1_n_4;
  wire raw1_s33_reg_i_1_n_5;
  wire raw1_s33_reg_i_1_n_6;
  wire raw1_s33_reg_i_1_n_7;
  wire raw1_s33_reg_i_20_n_0;
  wire raw1_s33_reg_i_21_n_0;
  wire raw1_s33_reg_i_22_n_0;
  wire raw1_s33_reg_i_23_n_0;
  wire raw1_s33_reg_i_24_n_0;
  wire raw1_s33_reg_i_25_n_0;
  wire raw1_s33_reg_i_26_n_0;
  wire raw1_s33_reg_i_27_n_0;
  wire raw1_s33_reg_i_28_n_0;
  wire raw1_s33_reg_i_29_n_0;
  wire raw1_s33_reg_i_2_n_0;
  wire raw1_s33_reg_i_2_n_1;
  wire raw1_s33_reg_i_2_n_10;
  wire raw1_s33_reg_i_2_n_11;
  wire raw1_s33_reg_i_2_n_12;
  wire raw1_s33_reg_i_2_n_13;
  wire raw1_s33_reg_i_2_n_14;
  wire raw1_s33_reg_i_2_n_15;
  wire raw1_s33_reg_i_2_n_2;
  wire raw1_s33_reg_i_2_n_3;
  wire raw1_s33_reg_i_2_n_4;
  wire raw1_s33_reg_i_2_n_5;
  wire raw1_s33_reg_i_2_n_6;
  wire raw1_s33_reg_i_2_n_7;
  wire raw1_s33_reg_i_2_n_8;
  wire raw1_s33_reg_i_2_n_9;
  wire raw1_s33_reg_i_30_n_0;
  wire raw1_s33_reg_i_31_n_0;
  wire raw1_s33_reg_i_32_n_0;
  wire raw1_s33_reg_i_33_n_0;
  wire raw1_s33_reg_i_34_n_0;
  wire raw1_s33_reg_i_35_n_0;
  wire raw1_s33_reg_i_36_n_0;
  wire raw1_s33_reg_i_37_n_0;
  wire raw1_s33_reg_i_38_n_0;
  wire raw1_s33_reg_i_39_n_0;
  wire raw1_s33_reg_i_3_n_0;
  wire raw1_s33_reg_i_3_n_1;
  wire raw1_s33_reg_i_3_n_10;
  wire raw1_s33_reg_i_3_n_11;
  wire raw1_s33_reg_i_3_n_12;
  wire raw1_s33_reg_i_3_n_13;
  wire raw1_s33_reg_i_3_n_14;
  wire raw1_s33_reg_i_3_n_15;
  wire raw1_s33_reg_i_3_n_2;
  wire raw1_s33_reg_i_3_n_3;
  wire raw1_s33_reg_i_3_n_4;
  wire raw1_s33_reg_i_3_n_5;
  wire raw1_s33_reg_i_3_n_6;
  wire raw1_s33_reg_i_3_n_7;
  wire raw1_s33_reg_i_3_n_8;
  wire raw1_s33_reg_i_3_n_9;
  wire raw1_s33_reg_i_40_n_0;
  wire raw1_s33_reg_i_41_n_0;
  wire raw1_s33_reg_i_42_n_14;
  wire raw1_s33_reg_i_42_n_15;
  wire raw1_s33_reg_i_42_n_6;
  wire raw1_s33_reg_i_42_n_7;
  wire raw1_s33_reg_i_43_n_0;
  wire raw1_s33_reg_i_44_n_0;
  wire raw1_s33_reg_i_45_n_0;
  wire raw1_s33_reg_i_46_n_0;
  wire raw1_s33_reg_i_47_n_0;
  wire raw1_s33_reg_i_48_n_0;
  wire raw1_s33_reg_i_49_n_0;
  wire raw1_s33_reg_i_4_n_0;
  wire raw1_s33_reg_i_50_n_0;
  wire raw1_s33_reg_i_51_n_0;
  wire raw1_s33_reg_i_52_n_0;
  wire raw1_s33_reg_i_53_n_0;
  wire raw1_s33_reg_i_54_n_0;
  wire raw1_s33_reg_i_55_n_0;
  wire raw1_s33_reg_i_56_n_0;
  wire raw1_s33_reg_i_56_n_1;
  wire raw1_s33_reg_i_56_n_10;
  wire raw1_s33_reg_i_56_n_11;
  wire raw1_s33_reg_i_56_n_12;
  wire raw1_s33_reg_i_56_n_13;
  wire raw1_s33_reg_i_56_n_14;
  wire raw1_s33_reg_i_56_n_15;
  wire raw1_s33_reg_i_56_n_2;
  wire raw1_s33_reg_i_56_n_3;
  wire raw1_s33_reg_i_56_n_4;
  wire raw1_s33_reg_i_56_n_5;
  wire raw1_s33_reg_i_56_n_6;
  wire raw1_s33_reg_i_56_n_7;
  wire raw1_s33_reg_i_56_n_8;
  wire raw1_s33_reg_i_56_n_9;
  wire raw1_s33_reg_i_57_n_0;
  wire raw1_s33_reg_i_58_n_0;
  wire raw1_s33_reg_i_59_n_0;
  wire raw1_s33_reg_i_5_n_0;
  wire raw1_s33_reg_i_60_n_0;
  wire raw1_s33_reg_i_61_n_0;
  wire raw1_s33_reg_i_62_n_0;
  wire raw1_s33_reg_i_63_n_0;
  wire raw1_s33_reg_i_64_n_0;
  wire raw1_s33_reg_i_65_n_0;
  wire raw1_s33_reg_i_66_n_0;
  wire raw1_s33_reg_i_67_n_0;
  wire raw1_s33_reg_i_68_n_0;
  wire raw1_s33_reg_i_69_n_0;
  wire raw1_s33_reg_i_6_n_0;
  wire raw1_s33_reg_i_70_n_0;
  wire raw1_s33_reg_i_71_n_14;
  wire raw1_s33_reg_i_71_n_15;
  wire raw1_s33_reg_i_71_n_6;
  wire raw1_s33_reg_i_71_n_7;
  wire raw1_s33_reg_i_72_n_0;
  wire raw1_s33_reg_i_73_n_0;
  wire raw1_s33_reg_i_74_n_0;
  wire raw1_s33_reg_i_75_n_0;
  wire raw1_s33_reg_i_76_n_0;
  wire raw1_s33_reg_i_77_n_0;
  wire raw1_s33_reg_i_78_n_0;
  wire raw1_s33_reg_i_79_n_0;
  wire raw1_s33_reg_i_7_n_0;
  wire raw1_s33_reg_i_80_n_0;
  wire raw1_s33_reg_i_81_n_0;
  wire raw1_s33_reg_i_82_n_0;
  wire raw1_s33_reg_i_83_n_0;
  wire raw1_s33_reg_i_84_n_0;
  wire raw1_s33_reg_i_85_n_0;
  wire raw1_s33_reg_i_86_n_0;
  wire raw1_s33_reg_i_87_n_0;
  wire raw1_s33_reg_i_88_n_0;
  wire raw1_s33_reg_i_89_n_0;
  wire raw1_s33_reg_i_8_n_0;
  wire raw1_s33_reg_i_90_n_0;
  wire raw1_s33_reg_i_91_n_0;
  wire raw1_s33_reg_i_92_n_0;
  wire raw1_s33_reg_i_93_n_0;
  wire raw1_s33_reg_i_94_n_0;
  wire raw1_s33_reg_i_95_n_0;
  wire raw1_s33_reg_i_9_n_0;
  wire rst_n;
  wire s0_ready;
  wire s0_valid_r;
  wire s0_valid_r_i_1_n_0;
  wire s1_valid_r;
  wire s1_valid_r_i_1_n_0;
  wire [7:0]weight0_code_u8;
  wire [7:0]weight1_code_u8;
  wire NLW_raw0_s33_reg_CARRYCASCOUT_UNCONNECTED;
  wire NLW_raw0_s33_reg_MULTSIGNOUT_UNCONNECTED;
  wire NLW_raw0_s33_reg_OVERFLOW_UNCONNECTED;
  wire NLW_raw0_s33_reg_PATTERNBDETECT_UNCONNECTED;
  wire NLW_raw0_s33_reg_PATTERNDETECT_UNCONNECTED;
  wire NLW_raw0_s33_reg_UNDERFLOW_UNCONNECTED;
  wire [29:0]NLW_raw0_s33_reg_ACOUT_UNCONNECTED;
  wire [17:0]NLW_raw0_s33_reg_BCOUT_UNCONNECTED;
  wire [3:0]NLW_raw0_s33_reg_CARRYOUT_UNCONNECTED;
  wire [47:33]NLW_raw0_s33_reg_P_UNCONNECTED;
  wire [47:0]NLW_raw0_s33_reg_PCOUT_UNCONNECTED;
  wire [7:0]NLW_raw0_s33_reg_XOROUT_UNCONNECTED;
  wire [7:2]NLW_raw0_s33_reg_i_47_CO_UNCONNECTED;
  wire [7:2]NLW_raw0_s33_reg_i_47_O_UNCONNECTED;
  wire [7:4]NLW_raw0_s33_reg_i_5_CO_UNCONNECTED;
  wire [7:5]NLW_raw0_s33_reg_i_5_O_UNCONNECTED;
  wire [7:2]NLW_raw0_s33_reg_i_76_CO_UNCONNECTED;
  wire [7:2]NLW_raw0_s33_reg_i_76_O_UNCONNECTED;
  wire NLW_raw1_s33_reg_CARRYCASCOUT_UNCONNECTED;
  wire NLW_raw1_s33_reg_MULTSIGNOUT_UNCONNECTED;
  wire NLW_raw1_s33_reg_OVERFLOW_UNCONNECTED;
  wire NLW_raw1_s33_reg_PATTERNBDETECT_UNCONNECTED;
  wire NLW_raw1_s33_reg_PATTERNDETECT_UNCONNECTED;
  wire NLW_raw1_s33_reg_UNDERFLOW_UNCONNECTED;
  wire [29:0]NLW_raw1_s33_reg_ACOUT_UNCONNECTED;
  wire [17:0]NLW_raw1_s33_reg_BCOUT_UNCONNECTED;
  wire [3:0]NLW_raw1_s33_reg_CARRYOUT_UNCONNECTED;
  wire [47:33]NLW_raw1_s33_reg_P_UNCONNECTED;
  wire [47:0]NLW_raw1_s33_reg_PCOUT_UNCONNECTED;
  wire [7:0]NLW_raw1_s33_reg_XOROUT_UNCONNECTED;
  wire [7:4]NLW_raw1_s33_reg_i_1_CO_UNCONNECTED;
  wire [7:5]NLW_raw1_s33_reg_i_1_O_UNCONNECTED;
  wire [7:2]NLW_raw1_s33_reg_i_42_CO_UNCONNECTED;
  wire [7:2]NLW_raw1_s33_reg_i_42_O_UNCONNECTED;
  wire [7:2]NLW_raw1_s33_reg_i_71_CO_UNCONNECTED;
  wire [7:2]NLW_raw1_s33_reg_i_71_O_UNCONNECTED;

  LUT6 #(
    .INIT(64'h2202222222222222)) 
    in_ready_INST_0
       (.I0(rst_n),
        .I1(clear),
        .I2(s1_valid_r),
        .I3(out_ready),
        .I4(out_valid),
        .I5(s0_valid_r),
        .O(in_ready));
  LUT2 #(
    .INIT(4'hB)) 
    out_valid_i_1
       (.I0(clear),
        .I1(rst_n),
        .O(out_valid_i_1_n_0));
  (* SOFT_HLUTNM = "soft_lutpair11" *) 
  LUT3 #(
    .INIT(8'hBA)) 
    out_valid_i_2
       (.I0(s1_valid_r),
        .I1(out_ready),
        .I2(out_valid),
        .O(out_valid_i_2_n_0));
  FDRE out_valid_reg
       (.C(clk),
        .CE(1'b1),
        .D(out_valid_i_2_n_0),
        .Q(out_valid),
        .R(out_valid_i_1_n_0));
  DSP48E2 #(
    .ACASCREG(1),
    .ADREG(1),
    .ALUMODEREG(0),
    .AMULTSEL("A"),
    .AREG(1),
    .AUTORESET_PATDET("NO_RESET"),
    .AUTORESET_PRIORITY("RESET"),
    .A_INPUT("DIRECT"),
    .BCASCREG(1),
    .BMULTSEL("B"),
    .BREG(1),
    .B_INPUT("DIRECT"),
    .CARRYINREG(0),
    .CARRYINSELREG(0),
    .CREG(1),
    .DREG(1),
    .INMODEREG(0),
    .MASK(48'h3FFFFFFFFFFF),
    .MREG(1),
    .OPMODEREG(0),
    .PATTERN(48'h000000000000),
    .PREADDINSEL("A"),
    .PREG(1),
    .RND(48'h000000000000),
    .SEL_MASK("MASK"),
    .SEL_PATTERN("PATTERN"),
    .USE_MULT("MULTIPLY"),
    .USE_PATTERN_DETECT("NO_PATDET"),
    .USE_SIMD("ONE48"),
    .USE_WIDEXOR("FALSE"),
    .XORSIMD("XOR24_48_96")) 
    raw0_s33_reg
       (.A({dot0_s17[16],dot0_s17[16],dot0_s17[16],dot0_s17[16],dot0_s17[16],dot0_s17[16],dot0_s17[16],dot0_s17[16],dot0_s17[16],dot0_s17[16],dot0_s17[16],dot0_s17[16],dot0_s17[16],dot0_s17}),
        .ACIN({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .ACOUT(NLW_raw0_s33_reg_ACOUT_UNCONNECTED[29:0]),
        .ALUMODE({1'b0,1'b0,1'b0,1'b0}),
        .B({1'b0,1'b0,raw0_s33_reg_i_5_n_11,raw0_s33_reg_i_5_n_12,raw0_s33_reg_i_5_n_13,raw0_s33_reg_i_5_n_14,raw0_s33_reg_i_5_n_15,raw0_s33_reg_i_6_n_8,raw0_s33_reg_i_6_n_9,raw0_s33_reg_i_6_n_10,raw0_s33_reg_i_6_n_11,raw0_s33_reg_i_6_n_12,raw0_s33_reg_i_6_n_13,raw0_s33_reg_i_6_n_14,raw0_s33_reg_i_6_n_15,raw0_s33_reg_i_7_n_13,raw0_s33_reg_i_7_n_14,raw0_s33_reg_i_7_n_15}),
        .BCIN({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .BCOUT(NLW_raw0_s33_reg_BCOUT_UNCONNECTED[17:0]),
        .C({1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1}),
        .CARRYCASCIN(1'b0),
        .CARRYCASCOUT(NLW_raw0_s33_reg_CARRYCASCOUT_UNCONNECTED),
        .CARRYIN(1'b0),
        .CARRYINSEL({1'b0,1'b0,1'b0}),
        .CARRYOUT(NLW_raw0_s33_reg_CARRYOUT_UNCONNECTED[3:0]),
        .CEA1(1'b0),
        .CEA2(raw0_s33_reg_i_1_n_0),
        .CEAD(1'b0),
        .CEALUMODE(1'b0),
        .CEB1(1'b0),
        .CEB2(raw0_s33_reg_i_1_n_0),
        .CEC(1'b0),
        .CECARRYIN(1'b0),
        .CECTRL(1'b0),
        .CED(1'b0),
        .CEINMODE(1'b0),
        .CEM(raw0_s33_reg_i_2_n_0),
        .CEP(raw0_s33_reg_i_3_n_0),
        .CLK(clk),
        .D({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .INMODE({1'b0,1'b0,1'b0,1'b0,1'b0}),
        .MULTSIGNIN(1'b0),
        .MULTSIGNOUT(NLW_raw0_s33_reg_MULTSIGNOUT_UNCONNECTED),
        .OPMODE({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b1,1'b0,1'b1}),
        .OVERFLOW(NLW_raw0_s33_reg_OVERFLOW_UNCONNECTED),
        .P({NLW_raw0_s33_reg_P_UNCONNECTED[47:33],raw0_s33}),
        .PATTERNBDETECT(NLW_raw0_s33_reg_PATTERNBDETECT_UNCONNECTED),
        .PATTERNDETECT(NLW_raw0_s33_reg_PATTERNDETECT_UNCONNECTED),
        .PCIN({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .PCOUT(NLW_raw0_s33_reg_PCOUT_UNCONNECTED[47:0]),
        .RSTA(RSTP),
        .RSTALLCARRYIN(1'b0),
        .RSTALUMODE(1'b0),
        .RSTB(RSTP),
        .RSTC(1'b0),
        .RSTCTRL(1'b0),
        .RSTD(1'b0),
        .RSTINMODE(1'b0),
        .RSTM(RSTP),
        .RSTP(RSTP),
        .UNDERFLOW(NLW_raw0_s33_reg_UNDERFLOW_UNCONNECTED),
        .XOROUT(NLW_raw0_s33_reg_XOROUT_UNCONNECTED[7:0]));
  (* SOFT_HLUTNM = "soft_lutpair12" *) 
  LUT4 #(
    .INIT(16'h0080)) 
    raw0_s33_reg_i_1
       (.I0(in_valid),
        .I1(s0_ready),
        .I2(rst_n),
        .I3(clear),
        .O(raw0_s33_reg_i_1_n_0));
  LUT6 #(
    .INIT(64'h7D44144414441444)) 
    raw0_s33_reg_i_10
       (.I0(raw0_s33_reg_i_48_n_0),
        .I1(raw0_s33_reg_i_47_n_14),
        .I2(activation_code_u8[5]),
        .I3(weight0_code_u8[7]),
        .I4(raw0_s33_reg_i_47_n_15),
        .I5(activation_code_u8[4]),
        .O(raw0_s33_reg_i_10_n_0));
  (* SOFT_HLUTNM = "soft_lutpair21" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_100
       (.I0(activation_code_u8[3]),
        .I1(weight0_code_u8[3]),
        .O(raw0_s33_reg_i_100_n_0));
  LUT6 #(
    .INIT(64'h8FF8F8F808808080)) 
    raw0_s33_reg_i_11
       (.I0(weight0_code_u8[6]),
        .I1(activation_code_u8[5]),
        .I2(raw0_s33_reg_i_47_n_15),
        .I3(activation_code_u8[4]),
        .I4(weight0_code_u8[7]),
        .I5(raw0_s33_reg_i_49_n_0),
        .O(raw0_s33_reg_i_11_n_0));
  LUT4 #(
    .INIT(16'h8F08)) 
    raw0_s33_reg_i_12
       (.I0(weight0_code_u8[6]),
        .I1(activation_code_u8[4]),
        .I2(raw0_s33_reg_i_50_n_0),
        .I3(raw0_s33_reg_i_51_n_0),
        .O(raw0_s33_reg_i_12_n_0));
  LUT4 #(
    .INIT(16'h8000)) 
    raw0_s33_reg_i_13
       (.I0(activation_code_u8[7]),
        .I1(raw0_s33_reg_i_47_n_6),
        .I2(activation_code_u8[6]),
        .I3(weight0_code_u8[7]),
        .O(raw0_s33_reg_i_13_n_0));
  LUT6 #(
    .INIT(64'h4FD525D52540B040)) 
    raw0_s33_reg_i_14
       (.I0(raw0_s33_reg_i_52_n_0),
        .I1(weight0_code_u8[6]),
        .I2(activation_code_u8[7]),
        .I3(weight0_code_u8[7]),
        .I4(activation_code_u8[6]),
        .I5(raw0_s33_reg_i_47_n_6),
        .O(raw0_s33_reg_i_14_n_0));
  LUT5 #(
    .INIT(32'h69999666)) 
    raw0_s33_reg_i_15
       (.I0(raw0_s33_reg_i_10_n_0),
        .I1(raw0_s33_reg_i_53_n_0),
        .I2(weight0_code_u8[6]),
        .I3(activation_code_u8[7]),
        .I4(raw0_s33_reg_i_52_n_0),
        .O(raw0_s33_reg_i_15_n_0));
  LUT6 #(
    .INIT(64'hD2B4B4B4B42D2D2D)) 
    raw0_s33_reg_i_16
       (.I0(raw0_s33_reg_i_49_n_0),
        .I1(raw0_s33_reg_i_54_n_0),
        .I2(raw0_s33_reg_i_55_n_0),
        .I3(weight0_code_u8[7]),
        .I4(activation_code_u8[4]),
        .I5(raw0_s33_reg_i_47_n_15),
        .O(raw0_s33_reg_i_16_n_0));
  LUT6 #(
    .INIT(64'hD42B2BD42BD4D42B)) 
    raw0_s33_reg_i_17
       (.I0(raw0_s33_reg_i_51_n_0),
        .I1(raw0_s33_reg_i_50_n_0),
        .I2(raw0_s33_reg_i_56_n_0),
        .I3(raw0_s33_reg_i_57_n_0),
        .I4(raw0_s33_reg_i_54_n_0),
        .I5(raw0_s33_reg_i_49_n_0),
        .O(raw0_s33_reg_i_17_n_0));
  LUT4 #(
    .INIT(16'h8F08)) 
    raw0_s33_reg_i_18
       (.I0(weight0_code_u8[6]),
        .I1(activation_code_u8[3]),
        .I2(raw0_s33_reg_i_58_n_0),
        .I3(raw0_s33_reg_i_59_n_0),
        .O(raw0_s33_reg_i_18_n_0));
  LUT6 #(
    .INIT(64'h8A08080808080808)) 
    raw0_s33_reg_i_19
       (.I0(weight0_code_u8[6]),
        .I1(activation_code_u8[2]),
        .I2(raw0_s33_reg_i_60_n_0),
        .I3(activation_code_u8[1]),
        .I4(raw0_s33_reg_i_61_n_12),
        .I5(raw0_s33_reg_i_7_n_9),
        .O(raw0_s33_reg_i_19_n_0));
  (* SOFT_HLUTNM = "soft_lutpair0" *) 
  LUT5 #(
    .INIT(32'h0000A2AA)) 
    raw0_s33_reg_i_2
       (.I0(s0_valid_r),
        .I1(out_valid),
        .I2(out_ready),
        .I3(s1_valid_r),
        .I4(clear),
        .O(raw0_s33_reg_i_2_n_0));
  LUT6 #(
    .INIT(64'h5995959595959595)) 
    raw0_s33_reg_i_20
       (.I0(raw0_s33_reg_i_60_n_0),
        .I1(weight0_code_u8[6]),
        .I2(activation_code_u8[2]),
        .I3(raw0_s33_reg_i_7_n_9),
        .I4(raw0_s33_reg_i_61_n_12),
        .I5(activation_code_u8[1]),
        .O(raw0_s33_reg_i_20_n_0));
  LUT4 #(
    .INIT(16'h9666)) 
    raw0_s33_reg_i_21
       (.I0(raw0_s33_reg_i_7_n_8),
        .I1(raw0_s33_reg_i_61_n_11),
        .I2(activation_code_u8[0]),
        .I3(weight0_code_u8[7]),
        .O(raw0_s33_reg_i_21_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    raw0_s33_reg_i_22
       (.I0(raw0_s33_reg_i_7_n_9),
        .I1(raw0_s33_reg_i_61_n_12),
        .O(raw0_s33_reg_i_22_n_0));
  LUT6 #(
    .INIT(64'hD42B2BD42BD4D42B)) 
    raw0_s33_reg_i_23
       (.I0(raw0_s33_reg_i_59_n_0),
        .I1(raw0_s33_reg_i_58_n_0),
        .I2(raw0_s33_reg_i_62_n_0),
        .I3(raw0_s33_reg_i_50_n_0),
        .I4(raw0_s33_reg_i_56_n_0),
        .I5(raw0_s33_reg_i_51_n_0),
        .O(raw0_s33_reg_i_23_n_0));
  LUT6 #(
    .INIT(64'hD42B2BD42BD4D42B)) 
    raw0_s33_reg_i_24
       (.I0(raw0_s33_reg_i_63_n_0),
        .I1(raw0_s33_reg_i_60_n_0),
        .I2(raw0_s33_reg_i_64_n_0),
        .I3(raw0_s33_reg_i_58_n_0),
        .I4(raw0_s33_reg_i_62_n_0),
        .I5(raw0_s33_reg_i_59_n_0),
        .O(raw0_s33_reg_i_24_n_0));
  LUT6 #(
    .INIT(64'h6969966996699696)) 
    raw0_s33_reg_i_25
       (.I0(raw0_s33_reg_i_60_n_0),
        .I1(raw0_s33_reg_i_64_n_0),
        .I2(raw0_s33_reg_i_63_n_0),
        .I3(raw0_s33_reg_i_65_n_0),
        .I4(raw0_s33_reg_i_7_n_8),
        .I5(raw0_s33_reg_i_61_n_11),
        .O(raw0_s33_reg_i_25_n_0));
  LUT5 #(
    .INIT(32'h6A959595)) 
    raw0_s33_reg_i_26
       (.I0(raw0_s33_reg_i_66_n_0),
        .I1(activation_code_u8[1]),
        .I2(weight0_code_u8[6]),
        .I3(raw0_s33_reg_i_61_n_12),
        .I4(raw0_s33_reg_i_7_n_9),
        .O(raw0_s33_reg_i_26_n_0));
  LUT4 #(
    .INIT(16'h9666)) 
    raw0_s33_reg_i_27
       (.I0(raw0_s33_reg_i_61_n_12),
        .I1(raw0_s33_reg_i_7_n_9),
        .I2(weight0_code_u8[6]),
        .I3(activation_code_u8[0]),
        .O(raw0_s33_reg_i_27_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    raw0_s33_reg_i_28
       (.I0(raw0_s33_reg_i_7_n_10),
        .I1(raw0_s33_reg_i_61_n_13),
        .O(raw0_s33_reg_i_28_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    raw0_s33_reg_i_29
       (.I0(raw0_s33_reg_i_7_n_11),
        .I1(raw0_s33_reg_i_61_n_14),
        .O(raw0_s33_reg_i_29_n_0));
  LUT4 #(
    .INIT(16'h008A)) 
    raw0_s33_reg_i_3
       (.I0(s1_valid_r),
        .I1(out_ready),
        .I2(out_valid),
        .I3(clear),
        .O(raw0_s33_reg_i_3_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    raw0_s33_reg_i_30
       (.I0(raw0_s33_reg_i_7_n_12),
        .I1(raw0_s33_reg_i_61_n_15),
        .O(raw0_s33_reg_i_30_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw0_s33_reg_i_31
       (.I0(weight0_code_u8[2]),
        .I1(activation_code_u8[4]),
        .I2(weight0_code_u8[1]),
        .I3(activation_code_u8[5]),
        .I4(weight0_code_u8[0]),
        .I5(activation_code_u8[6]),
        .O(raw0_s33_reg_i_31_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw0_s33_reg_i_32
       (.I0(weight0_code_u8[2]),
        .I1(activation_code_u8[3]),
        .I2(weight0_code_u8[1]),
        .I3(activation_code_u8[4]),
        .I4(weight0_code_u8[0]),
        .I5(activation_code_u8[5]),
        .O(raw0_s33_reg_i_32_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw0_s33_reg_i_33
       (.I0(weight0_code_u8[2]),
        .I1(activation_code_u8[2]),
        .I2(weight0_code_u8[1]),
        .I3(activation_code_u8[3]),
        .I4(weight0_code_u8[0]),
        .I5(activation_code_u8[4]),
        .O(raw0_s33_reg_i_33_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw0_s33_reg_i_34
       (.I0(weight0_code_u8[2]),
        .I1(activation_code_u8[1]),
        .I2(weight0_code_u8[1]),
        .I3(activation_code_u8[2]),
        .I4(weight0_code_u8[0]),
        .I5(activation_code_u8[3]),
        .O(raw0_s33_reg_i_34_n_0));
  LUT6 #(
    .INIT(64'h8777788878887888)) 
    raw0_s33_reg_i_35
       (.I0(weight0_code_u8[1]),
        .I1(activation_code_u8[2]),
        .I2(weight0_code_u8[2]),
        .I3(activation_code_u8[1]),
        .I4(activation_code_u8[3]),
        .I5(weight0_code_u8[0]),
        .O(raw0_s33_reg_i_35_n_0));
  LUT4 #(
    .INIT(16'h7888)) 
    raw0_s33_reg_i_36
       (.I0(weight0_code_u8[1]),
        .I1(activation_code_u8[1]),
        .I2(weight0_code_u8[2]),
        .I3(activation_code_u8[0]),
        .O(raw0_s33_reg_i_36_n_0));
  LUT2 #(
    .INIT(4'h8)) 
    raw0_s33_reg_i_37
       (.I0(weight0_code_u8[0]),
        .I1(activation_code_u8[1]),
        .O(raw0_s33_reg_i_37_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw0_s33_reg_i_38
       (.I0(raw0_s33_reg_i_31_n_0),
        .I1(weight0_code_u8[1]),
        .I2(activation_code_u8[6]),
        .I3(raw0_s33_reg_i_67_n_0),
        .I4(activation_code_u8[7]),
        .I5(weight0_code_u8[0]),
        .O(raw0_s33_reg_i_38_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw0_s33_reg_i_39
       (.I0(raw0_s33_reg_i_32_n_0),
        .I1(weight0_code_u8[1]),
        .I2(activation_code_u8[5]),
        .I3(raw0_s33_reg_i_68_n_0),
        .I4(activation_code_u8[6]),
        .I5(weight0_code_u8[0]),
        .O(raw0_s33_reg_i_39_n_0));
  LUT1 #(
    .INIT(2'h1)) 
    raw0_s33_reg_i_4
       (.I0(rst_n),
        .O(RSTP));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw0_s33_reg_i_40
       (.I0(raw0_s33_reg_i_33_n_0),
        .I1(weight0_code_u8[1]),
        .I2(activation_code_u8[4]),
        .I3(raw0_s33_reg_i_69_n_0),
        .I4(activation_code_u8[5]),
        .I5(weight0_code_u8[0]),
        .O(raw0_s33_reg_i_40_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw0_s33_reg_i_41
       (.I0(raw0_s33_reg_i_34_n_0),
        .I1(weight0_code_u8[1]),
        .I2(activation_code_u8[3]),
        .I3(raw0_s33_reg_i_70_n_0),
        .I4(activation_code_u8[4]),
        .I5(weight0_code_u8[0]),
        .O(raw0_s33_reg_i_41_n_0));
  LUT6 #(
    .INIT(64'h99C369C399339933)) 
    raw0_s33_reg_i_42
       (.I0(activation_code_u8[2]),
        .I1(raw0_s33_reg_i_71_n_0),
        .I2(activation_code_u8[1]),
        .I3(weight0_code_u8[1]),
        .I4(activation_code_u8[0]),
        .I5(weight0_code_u8[2]),
        .O(raw0_s33_reg_i_42_n_0));
  LUT6 #(
    .INIT(64'h8777788878887888)) 
    raw0_s33_reg_i_43
       (.I0(activation_code_u8[0]),
        .I1(weight0_code_u8[2]),
        .I2(activation_code_u8[1]),
        .I3(weight0_code_u8[1]),
        .I4(weight0_code_u8[0]),
        .I5(activation_code_u8[2]),
        .O(raw0_s33_reg_i_43_n_0));
  LUT4 #(
    .INIT(16'h7888)) 
    raw0_s33_reg_i_44
       (.I0(weight0_code_u8[0]),
        .I1(activation_code_u8[1]),
        .I2(weight0_code_u8[1]),
        .I3(activation_code_u8[0]),
        .O(raw0_s33_reg_i_44_n_0));
  LUT2 #(
    .INIT(4'h8)) 
    raw0_s33_reg_i_45
       (.I0(activation_code_u8[0]),
        .I1(weight0_code_u8[0]),
        .O(raw0_s33_reg_i_45_n_0));
  (* SOFT_HLUTNM = "soft_lutpair26" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_46
       (.I0(activation_code_u8[7]),
        .I1(weight0_code_u8[6]),
        .O(raw0_s33_reg_i_46_n_0));
  CARRY8 raw0_s33_reg_i_47
       (.CI(raw0_s33_reg_i_61_n_0),
        .CI_TOP(1'b0),
        .CO({NLW_raw0_s33_reg_i_47_CO_UNCONNECTED[7:2],raw0_s33_reg_i_47_n_6,raw0_s33_reg_i_47_n_7}),
        .DI({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,raw0_s33_reg_i_72_n_0,raw0_s33_reg_i_73_n_0}),
        .O({NLW_raw0_s33_reg_i_47_O_UNCONNECTED[7:2],raw0_s33_reg_i_47_n_14,raw0_s33_reg_i_47_n_15}),
        .S({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,raw0_s33_reg_i_74_n_0,raw0_s33_reg_i_75_n_0}));
  (* SOFT_HLUTNM = "soft_lutpair25" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_48
       (.I0(activation_code_u8[6]),
        .I1(weight0_code_u8[6]),
        .O(raw0_s33_reg_i_48_n_0));
  (* SOFT_HLUTNM = "soft_lutpair6" *) 
  LUT4 #(
    .INIT(16'hE888)) 
    raw0_s33_reg_i_49
       (.I0(raw0_s33_reg_i_61_n_8),
        .I1(raw0_s33_reg_i_76_n_6),
        .I2(weight0_code_u8[7]),
        .I3(activation_code_u8[3]),
        .O(raw0_s33_reg_i_49_n_0));
  (* ADDER_THRESHOLD = "35" *) 
  CARRY8 raw0_s33_reg_i_5
       (.CI(raw0_s33_reg_i_6_n_0),
        .CI_TOP(1'b0),
        .CO({NLW_raw0_s33_reg_i_5_CO_UNCONNECTED[7:4],raw0_s33_reg_i_5_n_4,raw0_s33_reg_i_5_n_5,raw0_s33_reg_i_5_n_6,raw0_s33_reg_i_5_n_7}),
        .DI({1'b0,1'b0,1'b0,1'b0,raw0_s33_reg_i_9_n_0,raw0_s33_reg_i_10_n_0,raw0_s33_reg_i_11_n_0,raw0_s33_reg_i_12_n_0}),
        .O({NLW_raw0_s33_reg_i_5_O_UNCONNECTED[7:5],raw0_s33_reg_i_5_n_11,raw0_s33_reg_i_5_n_12,raw0_s33_reg_i_5_n_13,raw0_s33_reg_i_5_n_14,raw0_s33_reg_i_5_n_15}),
        .S({1'b0,1'b0,1'b0,raw0_s33_reg_i_13_n_0,raw0_s33_reg_i_14_n_0,raw0_s33_reg_i_15_n_0,raw0_s33_reg_i_16_n_0,raw0_s33_reg_i_17_n_0}));
  (* SOFT_HLUTNM = "soft_lutpair6" *) 
  LUT4 #(
    .INIT(16'h7887)) 
    raw0_s33_reg_i_50
       (.I0(weight0_code_u8[7]),
        .I1(activation_code_u8[3]),
        .I2(raw0_s33_reg_i_61_n_8),
        .I3(raw0_s33_reg_i_76_n_6),
        .O(raw0_s33_reg_i_50_n_0));
  (* SOFT_HLUTNM = "soft_lutpair5" *) 
  LUT4 #(
    .INIT(16'hE888)) 
    raw0_s33_reg_i_51
       (.I0(raw0_s33_reg_i_61_n_9),
        .I1(raw0_s33_reg_i_76_n_14),
        .I2(weight0_code_u8[7]),
        .I3(activation_code_u8[2]),
        .O(raw0_s33_reg_i_51_n_0));
  (* SOFT_HLUTNM = "soft_lutpair1" *) 
  LUT3 #(
    .INIT(8'h7F)) 
    raw0_s33_reg_i_52
       (.I0(weight0_code_u8[7]),
        .I1(activation_code_u8[5]),
        .I2(raw0_s33_reg_i_47_n_14),
        .O(raw0_s33_reg_i_52_n_0));
  (* SOFT_HLUTNM = "soft_lutpair15" *) 
  LUT3 #(
    .INIT(8'h87)) 
    raw0_s33_reg_i_53
       (.I0(weight0_code_u8[7]),
        .I1(activation_code_u8[6]),
        .I2(raw0_s33_reg_i_47_n_6),
        .O(raw0_s33_reg_i_53_n_0));
  (* SOFT_HLUTNM = "soft_lutpair24" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_54
       (.I0(activation_code_u8[5]),
        .I1(weight0_code_u8[6]),
        .O(raw0_s33_reg_i_54_n_0));
  (* SOFT_HLUTNM = "soft_lutpair1" *) 
  LUT5 #(
    .INIT(32'h6A959595)) 
    raw0_s33_reg_i_55
       (.I0(raw0_s33_reg_i_47_n_14),
        .I1(activation_code_u8[5]),
        .I2(weight0_code_u8[7]),
        .I3(weight0_code_u8[6]),
        .I4(activation_code_u8[6]),
        .O(raw0_s33_reg_i_55_n_0));
  (* SOFT_HLUTNM = "soft_lutpair23" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_56
       (.I0(activation_code_u8[4]),
        .I1(weight0_code_u8[6]),
        .O(raw0_s33_reg_i_56_n_0));
  (* SOFT_HLUTNM = "soft_lutpair15" *) 
  LUT3 #(
    .INIT(8'h87)) 
    raw0_s33_reg_i_57
       (.I0(weight0_code_u8[7]),
        .I1(activation_code_u8[4]),
        .I2(raw0_s33_reg_i_47_n_15),
        .O(raw0_s33_reg_i_57_n_0));
  (* SOFT_HLUTNM = "soft_lutpair5" *) 
  LUT4 #(
    .INIT(16'h7887)) 
    raw0_s33_reg_i_58
       (.I0(weight0_code_u8[7]),
        .I1(activation_code_u8[2]),
        .I2(raw0_s33_reg_i_61_n_9),
        .I3(raw0_s33_reg_i_76_n_14),
        .O(raw0_s33_reg_i_58_n_0));
  (* SOFT_HLUTNM = "soft_lutpair4" *) 
  LUT4 #(
    .INIT(16'hE888)) 
    raw0_s33_reg_i_59
       (.I0(raw0_s33_reg_i_61_n_10),
        .I1(raw0_s33_reg_i_76_n_15),
        .I2(weight0_code_u8[7]),
        .I3(activation_code_u8[1]),
        .O(raw0_s33_reg_i_59_n_0));
  (* ADDER_THRESHOLD = "35" *) 
  CARRY8 raw0_s33_reg_i_6
       (.CI(1'b0),
        .CI_TOP(1'b0),
        .CO({raw0_s33_reg_i_6_n_0,raw0_s33_reg_i_6_n_1,raw0_s33_reg_i_6_n_2,raw0_s33_reg_i_6_n_3,raw0_s33_reg_i_6_n_4,raw0_s33_reg_i_6_n_5,raw0_s33_reg_i_6_n_6,raw0_s33_reg_i_6_n_7}),
        .DI({raw0_s33_reg_i_18_n_0,raw0_s33_reg_i_19_n_0,raw0_s33_reg_i_20_n_0,raw0_s33_reg_i_21_n_0,raw0_s33_reg_i_22_n_0,raw0_s33_reg_i_7_n_10,raw0_s33_reg_i_7_n_11,raw0_s33_reg_i_7_n_12}),
        .O({raw0_s33_reg_i_6_n_8,raw0_s33_reg_i_6_n_9,raw0_s33_reg_i_6_n_10,raw0_s33_reg_i_6_n_11,raw0_s33_reg_i_6_n_12,raw0_s33_reg_i_6_n_13,raw0_s33_reg_i_6_n_14,raw0_s33_reg_i_6_n_15}),
        .S({raw0_s33_reg_i_23_n_0,raw0_s33_reg_i_24_n_0,raw0_s33_reg_i_25_n_0,raw0_s33_reg_i_26_n_0,raw0_s33_reg_i_27_n_0,raw0_s33_reg_i_28_n_0,raw0_s33_reg_i_29_n_0,raw0_s33_reg_i_30_n_0}));
  (* SOFT_HLUTNM = "soft_lutpair4" *) 
  LUT4 #(
    .INIT(16'h7887)) 
    raw0_s33_reg_i_60
       (.I0(weight0_code_u8[7]),
        .I1(activation_code_u8[1]),
        .I2(raw0_s33_reg_i_61_n_10),
        .I3(raw0_s33_reg_i_76_n_15),
        .O(raw0_s33_reg_i_60_n_0));
  CARRY8 raw0_s33_reg_i_61
       (.CI(1'b0),
        .CI_TOP(1'b0),
        .CO({raw0_s33_reg_i_61_n_0,raw0_s33_reg_i_61_n_1,raw0_s33_reg_i_61_n_2,raw0_s33_reg_i_61_n_3,raw0_s33_reg_i_61_n_4,raw0_s33_reg_i_61_n_5,raw0_s33_reg_i_61_n_6,raw0_s33_reg_i_61_n_7}),
        .DI({raw0_s33_reg_i_77_n_0,raw0_s33_reg_i_78_n_0,raw0_s33_reg_i_79_n_0,raw0_s33_reg_i_80_n_0,raw0_s33_reg_i_81_n_0,raw0_s33_reg_i_82_n_0,raw0_s33_reg_i_83_n_0,1'b0}),
        .O({raw0_s33_reg_i_61_n_8,raw0_s33_reg_i_61_n_9,raw0_s33_reg_i_61_n_10,raw0_s33_reg_i_61_n_11,raw0_s33_reg_i_61_n_12,raw0_s33_reg_i_61_n_13,raw0_s33_reg_i_61_n_14,raw0_s33_reg_i_61_n_15}),
        .S({raw0_s33_reg_i_84_n_0,raw0_s33_reg_i_85_n_0,raw0_s33_reg_i_86_n_0,raw0_s33_reg_i_87_n_0,raw0_s33_reg_i_88_n_0,raw0_s33_reg_i_89_n_0,raw0_s33_reg_i_90_n_0,raw0_s33_reg_i_91_n_0}));
  (* SOFT_HLUTNM = "soft_lutpair22" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_62
       (.I0(activation_code_u8[3]),
        .I1(weight0_code_u8[6]),
        .O(raw0_s33_reg_i_62_n_0));
  (* SOFT_HLUTNM = "soft_lutpair13" *) 
  LUT4 #(
    .INIT(16'h8000)) 
    raw0_s33_reg_i_63
       (.I0(raw0_s33_reg_i_7_n_9),
        .I1(raw0_s33_reg_i_61_n_12),
        .I2(weight0_code_u8[6]),
        .I3(activation_code_u8[1]),
        .O(raw0_s33_reg_i_63_n_0));
  (* SOFT_HLUTNM = "soft_lutpair13" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_64
       (.I0(activation_code_u8[2]),
        .I1(weight0_code_u8[6]),
        .O(raw0_s33_reg_i_64_n_0));
  (* SOFT_HLUTNM = "soft_lutpair3" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_65
       (.I0(activation_code_u8[0]),
        .I1(weight0_code_u8[7]),
        .O(raw0_s33_reg_i_65_n_0));
  (* SOFT_HLUTNM = "soft_lutpair3" *) 
  LUT4 #(
    .INIT(16'h7887)) 
    raw0_s33_reg_i_66
       (.I0(weight0_code_u8[7]),
        .I1(activation_code_u8[0]),
        .I2(raw0_s33_reg_i_61_n_11),
        .I3(raw0_s33_reg_i_7_n_8),
        .O(raw0_s33_reg_i_66_n_0));
  (* SOFT_HLUTNM = "soft_lutpair20" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_67
       (.I0(activation_code_u8[5]),
        .I1(weight0_code_u8[2]),
        .O(raw0_s33_reg_i_67_n_0));
  (* SOFT_HLUTNM = "soft_lutpair19" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_68
       (.I0(activation_code_u8[4]),
        .I1(weight0_code_u8[2]),
        .O(raw0_s33_reg_i_68_n_0));
  (* SOFT_HLUTNM = "soft_lutpair17" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_69
       (.I0(activation_code_u8[3]),
        .I1(weight0_code_u8[2]),
        .O(raw0_s33_reg_i_69_n_0));
  CARRY8 raw0_s33_reg_i_7
       (.CI(1'b0),
        .CI_TOP(1'b0),
        .CO({raw0_s33_reg_i_7_n_0,raw0_s33_reg_i_7_n_1,raw0_s33_reg_i_7_n_2,raw0_s33_reg_i_7_n_3,raw0_s33_reg_i_7_n_4,raw0_s33_reg_i_7_n_5,raw0_s33_reg_i_7_n_6,raw0_s33_reg_i_7_n_7}),
        .DI({raw0_s33_reg_i_31_n_0,raw0_s33_reg_i_32_n_0,raw0_s33_reg_i_33_n_0,raw0_s33_reg_i_34_n_0,raw0_s33_reg_i_35_n_0,raw0_s33_reg_i_36_n_0,raw0_s33_reg_i_37_n_0,1'b0}),
        .O({raw0_s33_reg_i_7_n_8,raw0_s33_reg_i_7_n_9,raw0_s33_reg_i_7_n_10,raw0_s33_reg_i_7_n_11,raw0_s33_reg_i_7_n_12,raw0_s33_reg_i_7_n_13,raw0_s33_reg_i_7_n_14,raw0_s33_reg_i_7_n_15}),
        .S({raw0_s33_reg_i_38_n_0,raw0_s33_reg_i_39_n_0,raw0_s33_reg_i_40_n_0,raw0_s33_reg_i_41_n_0,raw0_s33_reg_i_42_n_0,raw0_s33_reg_i_43_n_0,raw0_s33_reg_i_44_n_0,raw0_s33_reg_i_45_n_0}));
  (* SOFT_HLUTNM = "soft_lutpair18" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_70
       (.I0(activation_code_u8[2]),
        .I1(weight0_code_u8[2]),
        .O(raw0_s33_reg_i_70_n_0));
  (* SOFT_HLUTNM = "soft_lutpair17" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_71
       (.I0(activation_code_u8[3]),
        .I1(weight0_code_u8[0]),
        .O(raw0_s33_reg_i_71_n_0));
  LUT4 #(
    .INIT(16'h8000)) 
    raw0_s33_reg_i_72
       (.I0(weight0_code_u8[5]),
        .I1(activation_code_u8[6]),
        .I2(weight0_code_u8[4]),
        .I3(activation_code_u8[7]),
        .O(raw0_s33_reg_i_72_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw0_s33_reg_i_73
       (.I0(weight0_code_u8[5]),
        .I1(activation_code_u8[5]),
        .I2(weight0_code_u8[4]),
        .I3(activation_code_u8[6]),
        .I4(weight0_code_u8[3]),
        .I5(activation_code_u8[7]),
        .O(raw0_s33_reg_i_73_n_0));
  LUT4 #(
    .INIT(16'h7000)) 
    raw0_s33_reg_i_74
       (.I0(weight0_code_u8[4]),
        .I1(activation_code_u8[6]),
        .I2(weight0_code_u8[5]),
        .I3(activation_code_u8[7]),
        .O(raw0_s33_reg_i_74_n_0));
  LUT6 #(
    .INIT(64'hE75F30007800F000)) 
    raw0_s33_reg_i_75
       (.I0(weight0_code_u8[3]),
        .I1(activation_code_u8[5]),
        .I2(activation_code_u8[6]),
        .I3(weight0_code_u8[5]),
        .I4(activation_code_u8[7]),
        .I5(weight0_code_u8[4]),
        .O(raw0_s33_reg_i_75_n_0));
  CARRY8 raw0_s33_reg_i_76
       (.CI(raw0_s33_reg_i_7_n_0),
        .CI_TOP(1'b0),
        .CO({NLW_raw0_s33_reg_i_76_CO_UNCONNECTED[7:2],raw0_s33_reg_i_76_n_6,raw0_s33_reg_i_76_n_7}),
        .DI({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,raw0_s33_reg_i_92_n_0,raw0_s33_reg_i_93_n_0}),
        .O({NLW_raw0_s33_reg_i_76_O_UNCONNECTED[7:2],raw0_s33_reg_i_76_n_14,raw0_s33_reg_i_76_n_15}),
        .S({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,raw0_s33_reg_i_94_n_0,raw0_s33_reg_i_95_n_0}));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw0_s33_reg_i_77
       (.I0(weight0_code_u8[5]),
        .I1(activation_code_u8[4]),
        .I2(weight0_code_u8[4]),
        .I3(activation_code_u8[5]),
        .I4(weight0_code_u8[3]),
        .I5(activation_code_u8[6]),
        .O(raw0_s33_reg_i_77_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw0_s33_reg_i_78
       (.I0(weight0_code_u8[5]),
        .I1(activation_code_u8[3]),
        .I2(weight0_code_u8[4]),
        .I3(activation_code_u8[4]),
        .I4(weight0_code_u8[3]),
        .I5(activation_code_u8[5]),
        .O(raw0_s33_reg_i_78_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw0_s33_reg_i_79
       (.I0(weight0_code_u8[5]),
        .I1(activation_code_u8[2]),
        .I2(weight0_code_u8[4]),
        .I3(activation_code_u8[3]),
        .I4(weight0_code_u8[3]),
        .I5(activation_code_u8[4]),
        .O(raw0_s33_reg_i_79_n_0));
  (* SOFT_HLUTNM = "soft_lutpair0" *) 
  LUT4 #(
    .INIT(16'hDFFF)) 
    raw0_s33_reg_i_8
       (.I0(s1_valid_r),
        .I1(out_ready),
        .I2(out_valid),
        .I3(s0_valid_r),
        .O(s0_ready));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw0_s33_reg_i_80
       (.I0(weight0_code_u8[5]),
        .I1(activation_code_u8[1]),
        .I2(weight0_code_u8[4]),
        .I3(activation_code_u8[2]),
        .I4(weight0_code_u8[3]),
        .I5(activation_code_u8[3]),
        .O(raw0_s33_reg_i_80_n_0));
  LUT6 #(
    .INIT(64'h8777788878887888)) 
    raw0_s33_reg_i_81
       (.I0(weight0_code_u8[4]),
        .I1(activation_code_u8[2]),
        .I2(weight0_code_u8[5]),
        .I3(activation_code_u8[1]),
        .I4(activation_code_u8[3]),
        .I5(weight0_code_u8[3]),
        .O(raw0_s33_reg_i_81_n_0));
  LUT4 #(
    .INIT(16'h7888)) 
    raw0_s33_reg_i_82
       (.I0(weight0_code_u8[4]),
        .I1(activation_code_u8[1]),
        .I2(weight0_code_u8[5]),
        .I3(activation_code_u8[0]),
        .O(raw0_s33_reg_i_82_n_0));
  LUT2 #(
    .INIT(4'h8)) 
    raw0_s33_reg_i_83
       (.I0(weight0_code_u8[3]),
        .I1(activation_code_u8[1]),
        .O(raw0_s33_reg_i_83_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw0_s33_reg_i_84
       (.I0(raw0_s33_reg_i_77_n_0),
        .I1(weight0_code_u8[4]),
        .I2(activation_code_u8[6]),
        .I3(raw0_s33_reg_i_96_n_0),
        .I4(activation_code_u8[7]),
        .I5(weight0_code_u8[3]),
        .O(raw0_s33_reg_i_84_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw0_s33_reg_i_85
       (.I0(raw0_s33_reg_i_78_n_0),
        .I1(weight0_code_u8[4]),
        .I2(activation_code_u8[5]),
        .I3(raw0_s33_reg_i_97_n_0),
        .I4(activation_code_u8[6]),
        .I5(weight0_code_u8[3]),
        .O(raw0_s33_reg_i_85_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw0_s33_reg_i_86
       (.I0(raw0_s33_reg_i_79_n_0),
        .I1(weight0_code_u8[4]),
        .I2(activation_code_u8[4]),
        .I3(raw0_s33_reg_i_98_n_0),
        .I4(activation_code_u8[5]),
        .I5(weight0_code_u8[3]),
        .O(raw0_s33_reg_i_86_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw0_s33_reg_i_87
       (.I0(raw0_s33_reg_i_80_n_0),
        .I1(weight0_code_u8[4]),
        .I2(activation_code_u8[3]),
        .I3(raw0_s33_reg_i_99_n_0),
        .I4(activation_code_u8[4]),
        .I5(weight0_code_u8[3]),
        .O(raw0_s33_reg_i_87_n_0));
  LUT6 #(
    .INIT(64'h99C369C399339933)) 
    raw0_s33_reg_i_88
       (.I0(activation_code_u8[2]),
        .I1(raw0_s33_reg_i_100_n_0),
        .I2(activation_code_u8[1]),
        .I3(weight0_code_u8[4]),
        .I4(activation_code_u8[0]),
        .I5(weight0_code_u8[5]),
        .O(raw0_s33_reg_i_88_n_0));
  LUT6 #(
    .INIT(64'h8777788878887888)) 
    raw0_s33_reg_i_89
       (.I0(activation_code_u8[0]),
        .I1(weight0_code_u8[5]),
        .I2(activation_code_u8[1]),
        .I3(weight0_code_u8[4]),
        .I4(weight0_code_u8[3]),
        .I5(activation_code_u8[2]),
        .O(raw0_s33_reg_i_89_n_0));
  LUT6 #(
    .INIT(64'h7D44144414441444)) 
    raw0_s33_reg_i_9
       (.I0(raw0_s33_reg_i_46_n_0),
        .I1(raw0_s33_reg_i_47_n_6),
        .I2(activation_code_u8[6]),
        .I3(weight0_code_u8[7]),
        .I4(raw0_s33_reg_i_47_n_14),
        .I5(activation_code_u8[5]),
        .O(raw0_s33_reg_i_9_n_0));
  LUT4 #(
    .INIT(16'h7888)) 
    raw0_s33_reg_i_90
       (.I0(weight0_code_u8[3]),
        .I1(activation_code_u8[1]),
        .I2(weight0_code_u8[4]),
        .I3(activation_code_u8[0]),
        .O(raw0_s33_reg_i_90_n_0));
  LUT2 #(
    .INIT(4'h8)) 
    raw0_s33_reg_i_91
       (.I0(activation_code_u8[0]),
        .I1(weight0_code_u8[3]),
        .O(raw0_s33_reg_i_91_n_0));
  LUT4 #(
    .INIT(16'h8000)) 
    raw0_s33_reg_i_92
       (.I0(weight0_code_u8[2]),
        .I1(activation_code_u8[6]),
        .I2(weight0_code_u8[1]),
        .I3(activation_code_u8[7]),
        .O(raw0_s33_reg_i_92_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw0_s33_reg_i_93
       (.I0(weight0_code_u8[2]),
        .I1(activation_code_u8[5]),
        .I2(weight0_code_u8[1]),
        .I3(activation_code_u8[6]),
        .I4(weight0_code_u8[0]),
        .I5(activation_code_u8[7]),
        .O(raw0_s33_reg_i_93_n_0));
  LUT4 #(
    .INIT(16'h7000)) 
    raw0_s33_reg_i_94
       (.I0(weight0_code_u8[1]),
        .I1(activation_code_u8[6]),
        .I2(weight0_code_u8[2]),
        .I3(activation_code_u8[7]),
        .O(raw0_s33_reg_i_94_n_0));
  LUT6 #(
    .INIT(64'hE75F30007800F000)) 
    raw0_s33_reg_i_95
       (.I0(weight0_code_u8[0]),
        .I1(activation_code_u8[5]),
        .I2(activation_code_u8[6]),
        .I3(weight0_code_u8[2]),
        .I4(activation_code_u8[7]),
        .I5(weight0_code_u8[1]),
        .O(raw0_s33_reg_i_95_n_0));
  (* SOFT_HLUTNM = "soft_lutpair20" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_96
       (.I0(activation_code_u8[5]),
        .I1(weight0_code_u8[5]),
        .O(raw0_s33_reg_i_96_n_0));
  (* SOFT_HLUTNM = "soft_lutpair19" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_97
       (.I0(activation_code_u8[4]),
        .I1(weight0_code_u8[5]),
        .O(raw0_s33_reg_i_97_n_0));
  (* SOFT_HLUTNM = "soft_lutpair21" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_98
       (.I0(activation_code_u8[3]),
        .I1(weight0_code_u8[5]),
        .O(raw0_s33_reg_i_98_n_0));
  (* SOFT_HLUTNM = "soft_lutpair18" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw0_s33_reg_i_99
       (.I0(activation_code_u8[2]),
        .I1(weight0_code_u8[5]),
        .O(raw0_s33_reg_i_99_n_0));
  DSP48E2 #(
    .ACASCREG(1),
    .ADREG(1),
    .ALUMODEREG(0),
    .AMULTSEL("A"),
    .AREG(1),
    .AUTORESET_PATDET("NO_RESET"),
    .AUTORESET_PRIORITY("RESET"),
    .A_INPUT("DIRECT"),
    .BCASCREG(1),
    .BMULTSEL("B"),
    .BREG(1),
    .B_INPUT("DIRECT"),
    .CARRYINREG(0),
    .CARRYINSELREG(0),
    .CREG(1),
    .DREG(1),
    .INMODEREG(0),
    .MASK(48'h3FFFFFFFFFFF),
    .MREG(1),
    .OPMODEREG(0),
    .PATTERN(48'h000000000000),
    .PREADDINSEL("A"),
    .PREG(1),
    .RND(48'h000000000000),
    .SEL_MASK("MASK"),
    .SEL_PATTERN("PATTERN"),
    .USE_MULT("MULTIPLY"),
    .USE_PATTERN_DETECT("NO_PATDET"),
    .USE_SIMD("ONE48"),
    .USE_WIDEXOR("FALSE"),
    .XORSIMD("XOR24_48_96")) 
    raw1_s33_reg
       (.A({dot1_s17[16],dot1_s17[16],dot1_s17[16],dot1_s17[16],dot1_s17[16],dot1_s17[16],dot1_s17[16],dot1_s17[16],dot1_s17[16],dot1_s17[16],dot1_s17[16],dot1_s17[16],dot1_s17[16],dot1_s17}),
        .ACIN({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .ACOUT(NLW_raw1_s33_reg_ACOUT_UNCONNECTED[29:0]),
        .ALUMODE({1'b0,1'b0,1'b0,1'b0}),
        .B({1'b0,1'b0,raw1_s33_reg_i_1_n_11,raw1_s33_reg_i_1_n_12,raw1_s33_reg_i_1_n_13,raw1_s33_reg_i_1_n_14,raw1_s33_reg_i_1_n_15,raw1_s33_reg_i_2_n_8,raw1_s33_reg_i_2_n_9,raw1_s33_reg_i_2_n_10,raw1_s33_reg_i_2_n_11,raw1_s33_reg_i_2_n_12,raw1_s33_reg_i_2_n_13,raw1_s33_reg_i_2_n_14,raw1_s33_reg_i_2_n_15,raw1_s33_reg_i_3_n_13,raw1_s33_reg_i_3_n_14,raw1_s33_reg_i_3_n_15}),
        .BCIN({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .BCOUT(NLW_raw1_s33_reg_BCOUT_UNCONNECTED[17:0]),
        .C({1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1}),
        .CARRYCASCIN(1'b0),
        .CARRYCASCOUT(NLW_raw1_s33_reg_CARRYCASCOUT_UNCONNECTED),
        .CARRYIN(1'b0),
        .CARRYINSEL({1'b0,1'b0,1'b0}),
        .CARRYOUT(NLW_raw1_s33_reg_CARRYOUT_UNCONNECTED[3:0]),
        .CEA1(1'b0),
        .CEA2(raw0_s33_reg_i_1_n_0),
        .CEAD(1'b0),
        .CEALUMODE(1'b0),
        .CEB1(1'b0),
        .CEB2(raw0_s33_reg_i_1_n_0),
        .CEC(1'b0),
        .CECARRYIN(1'b0),
        .CECTRL(1'b0),
        .CED(1'b0),
        .CEINMODE(1'b0),
        .CEM(raw0_s33_reg_i_2_n_0),
        .CEP(raw0_s33_reg_i_3_n_0),
        .CLK(clk),
        .D({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .INMODE({1'b0,1'b0,1'b0,1'b0,1'b0}),
        .MULTSIGNIN(1'b0),
        .MULTSIGNOUT(NLW_raw1_s33_reg_MULTSIGNOUT_UNCONNECTED),
        .OPMODE({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b1,1'b0,1'b1}),
        .OVERFLOW(NLW_raw1_s33_reg_OVERFLOW_UNCONNECTED),
        .P({NLW_raw1_s33_reg_P_UNCONNECTED[47:33],raw1_s33}),
        .PATTERNBDETECT(NLW_raw1_s33_reg_PATTERNBDETECT_UNCONNECTED),
        .PATTERNDETECT(NLW_raw1_s33_reg_PATTERNDETECT_UNCONNECTED),
        .PCIN({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .PCOUT(NLW_raw1_s33_reg_PCOUT_UNCONNECTED[47:0]),
        .RSTA(RSTP),
        .RSTALLCARRYIN(1'b0),
        .RSTALUMODE(1'b0),
        .RSTB(RSTP),
        .RSTC(1'b0),
        .RSTCTRL(1'b0),
        .RSTD(1'b0),
        .RSTINMODE(1'b0),
        .RSTM(RSTP),
        .RSTP(RSTP),
        .UNDERFLOW(NLW_raw1_s33_reg_UNDERFLOW_UNCONNECTED),
        .XOROUT(NLW_raw1_s33_reg_XOROUT_UNCONNECTED[7:0]));
  (* ADDER_THRESHOLD = "35" *) 
  CARRY8 raw1_s33_reg_i_1
       (.CI(raw1_s33_reg_i_2_n_0),
        .CI_TOP(1'b0),
        .CO({NLW_raw1_s33_reg_i_1_CO_UNCONNECTED[7:4],raw1_s33_reg_i_1_n_4,raw1_s33_reg_i_1_n_5,raw1_s33_reg_i_1_n_6,raw1_s33_reg_i_1_n_7}),
        .DI({1'b0,1'b0,1'b0,1'b0,raw1_s33_reg_i_4_n_0,raw1_s33_reg_i_5_n_0,raw1_s33_reg_i_6_n_0,raw1_s33_reg_i_7_n_0}),
        .O({NLW_raw1_s33_reg_i_1_O_UNCONNECTED[7:5],raw1_s33_reg_i_1_n_11,raw1_s33_reg_i_1_n_12,raw1_s33_reg_i_1_n_13,raw1_s33_reg_i_1_n_14,raw1_s33_reg_i_1_n_15}),
        .S({1'b0,1'b0,1'b0,raw1_s33_reg_i_8_n_0,raw1_s33_reg_i_9_n_0,raw1_s33_reg_i_10_n_0,raw1_s33_reg_i_11_n_0,raw1_s33_reg_i_12_n_0}));
  LUT5 #(
    .INIT(32'h69999666)) 
    raw1_s33_reg_i_10
       (.I0(raw1_s33_reg_i_5_n_0),
        .I1(raw1_s33_reg_i_48_n_0),
        .I2(weight1_code_u8[6]),
        .I3(activation_code_u8[7]),
        .I4(raw1_s33_reg_i_47_n_0),
        .O(raw1_s33_reg_i_10_n_0));
  LUT6 #(
    .INIT(64'hD2B4B4B4B42D2D2D)) 
    raw1_s33_reg_i_11
       (.I0(raw1_s33_reg_i_44_n_0),
        .I1(raw1_s33_reg_i_49_n_0),
        .I2(raw1_s33_reg_i_50_n_0),
        .I3(weight1_code_u8[7]),
        .I4(activation_code_u8[4]),
        .I5(raw1_s33_reg_i_42_n_15),
        .O(raw1_s33_reg_i_11_n_0));
  LUT6 #(
    .INIT(64'hD42B2BD42BD4D42B)) 
    raw1_s33_reg_i_12
       (.I0(raw1_s33_reg_i_46_n_0),
        .I1(raw1_s33_reg_i_45_n_0),
        .I2(raw1_s33_reg_i_51_n_0),
        .I3(raw1_s33_reg_i_52_n_0),
        .I4(raw1_s33_reg_i_49_n_0),
        .I5(raw1_s33_reg_i_44_n_0),
        .O(raw1_s33_reg_i_12_n_0));
  LUT4 #(
    .INIT(16'h8F08)) 
    raw1_s33_reg_i_13
       (.I0(weight1_code_u8[6]),
        .I1(activation_code_u8[3]),
        .I2(raw1_s33_reg_i_53_n_0),
        .I3(raw1_s33_reg_i_54_n_0),
        .O(raw1_s33_reg_i_13_n_0));
  LUT6 #(
    .INIT(64'h8A08080808080808)) 
    raw1_s33_reg_i_14
       (.I0(weight1_code_u8[6]),
        .I1(activation_code_u8[2]),
        .I2(raw1_s33_reg_i_55_n_0),
        .I3(activation_code_u8[1]),
        .I4(raw1_s33_reg_i_56_n_12),
        .I5(raw1_s33_reg_i_3_n_9),
        .O(raw1_s33_reg_i_14_n_0));
  LUT6 #(
    .INIT(64'h5995959595959595)) 
    raw1_s33_reg_i_15
       (.I0(raw1_s33_reg_i_55_n_0),
        .I1(weight1_code_u8[6]),
        .I2(activation_code_u8[2]),
        .I3(raw1_s33_reg_i_3_n_9),
        .I4(raw1_s33_reg_i_56_n_12),
        .I5(activation_code_u8[1]),
        .O(raw1_s33_reg_i_15_n_0));
  LUT4 #(
    .INIT(16'h9666)) 
    raw1_s33_reg_i_16
       (.I0(raw1_s33_reg_i_3_n_8),
        .I1(raw1_s33_reg_i_56_n_11),
        .I2(activation_code_u8[0]),
        .I3(weight1_code_u8[7]),
        .O(raw1_s33_reg_i_16_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    raw1_s33_reg_i_17
       (.I0(raw1_s33_reg_i_3_n_9),
        .I1(raw1_s33_reg_i_56_n_12),
        .O(raw1_s33_reg_i_17_n_0));
  LUT6 #(
    .INIT(64'hD42B2BD42BD4D42B)) 
    raw1_s33_reg_i_18
       (.I0(raw1_s33_reg_i_54_n_0),
        .I1(raw1_s33_reg_i_53_n_0),
        .I2(raw1_s33_reg_i_57_n_0),
        .I3(raw1_s33_reg_i_45_n_0),
        .I4(raw1_s33_reg_i_51_n_0),
        .I5(raw1_s33_reg_i_46_n_0),
        .O(raw1_s33_reg_i_18_n_0));
  LUT6 #(
    .INIT(64'hD42B2BD42BD4D42B)) 
    raw1_s33_reg_i_19
       (.I0(raw1_s33_reg_i_58_n_0),
        .I1(raw1_s33_reg_i_55_n_0),
        .I2(raw1_s33_reg_i_59_n_0),
        .I3(raw1_s33_reg_i_53_n_0),
        .I4(raw1_s33_reg_i_57_n_0),
        .I5(raw1_s33_reg_i_54_n_0),
        .O(raw1_s33_reg_i_19_n_0));
  (* ADDER_THRESHOLD = "35" *) 
  CARRY8 raw1_s33_reg_i_2
       (.CI(1'b0),
        .CI_TOP(1'b0),
        .CO({raw1_s33_reg_i_2_n_0,raw1_s33_reg_i_2_n_1,raw1_s33_reg_i_2_n_2,raw1_s33_reg_i_2_n_3,raw1_s33_reg_i_2_n_4,raw1_s33_reg_i_2_n_5,raw1_s33_reg_i_2_n_6,raw1_s33_reg_i_2_n_7}),
        .DI({raw1_s33_reg_i_13_n_0,raw1_s33_reg_i_14_n_0,raw1_s33_reg_i_15_n_0,raw1_s33_reg_i_16_n_0,raw1_s33_reg_i_17_n_0,raw1_s33_reg_i_3_n_10,raw1_s33_reg_i_3_n_11,raw1_s33_reg_i_3_n_12}),
        .O({raw1_s33_reg_i_2_n_8,raw1_s33_reg_i_2_n_9,raw1_s33_reg_i_2_n_10,raw1_s33_reg_i_2_n_11,raw1_s33_reg_i_2_n_12,raw1_s33_reg_i_2_n_13,raw1_s33_reg_i_2_n_14,raw1_s33_reg_i_2_n_15}),
        .S({raw1_s33_reg_i_18_n_0,raw1_s33_reg_i_19_n_0,raw1_s33_reg_i_20_n_0,raw1_s33_reg_i_21_n_0,raw1_s33_reg_i_22_n_0,raw1_s33_reg_i_23_n_0,raw1_s33_reg_i_24_n_0,raw1_s33_reg_i_25_n_0}));
  LUT6 #(
    .INIT(64'h6969966996699696)) 
    raw1_s33_reg_i_20
       (.I0(raw1_s33_reg_i_55_n_0),
        .I1(raw1_s33_reg_i_59_n_0),
        .I2(raw1_s33_reg_i_58_n_0),
        .I3(raw1_s33_reg_i_60_n_0),
        .I4(raw1_s33_reg_i_3_n_8),
        .I5(raw1_s33_reg_i_56_n_11),
        .O(raw1_s33_reg_i_20_n_0));
  LUT5 #(
    .INIT(32'h6A959595)) 
    raw1_s33_reg_i_21
       (.I0(raw1_s33_reg_i_61_n_0),
        .I1(activation_code_u8[1]),
        .I2(weight1_code_u8[6]),
        .I3(raw1_s33_reg_i_56_n_12),
        .I4(raw1_s33_reg_i_3_n_9),
        .O(raw1_s33_reg_i_21_n_0));
  LUT4 #(
    .INIT(16'h9666)) 
    raw1_s33_reg_i_22
       (.I0(raw1_s33_reg_i_56_n_12),
        .I1(raw1_s33_reg_i_3_n_9),
        .I2(weight1_code_u8[6]),
        .I3(activation_code_u8[0]),
        .O(raw1_s33_reg_i_22_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    raw1_s33_reg_i_23
       (.I0(raw1_s33_reg_i_3_n_10),
        .I1(raw1_s33_reg_i_56_n_13),
        .O(raw1_s33_reg_i_23_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    raw1_s33_reg_i_24
       (.I0(raw1_s33_reg_i_3_n_11),
        .I1(raw1_s33_reg_i_56_n_14),
        .O(raw1_s33_reg_i_24_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    raw1_s33_reg_i_25
       (.I0(raw1_s33_reg_i_3_n_12),
        .I1(raw1_s33_reg_i_56_n_15),
        .O(raw1_s33_reg_i_25_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw1_s33_reg_i_26
       (.I0(weight1_code_u8[2]),
        .I1(activation_code_u8[4]),
        .I2(weight1_code_u8[1]),
        .I3(activation_code_u8[5]),
        .I4(weight1_code_u8[0]),
        .I5(activation_code_u8[6]),
        .O(raw1_s33_reg_i_26_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw1_s33_reg_i_27
       (.I0(weight1_code_u8[2]),
        .I1(activation_code_u8[3]),
        .I2(weight1_code_u8[1]),
        .I3(activation_code_u8[4]),
        .I4(weight1_code_u8[0]),
        .I5(activation_code_u8[5]),
        .O(raw1_s33_reg_i_27_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw1_s33_reg_i_28
       (.I0(weight1_code_u8[2]),
        .I1(activation_code_u8[2]),
        .I2(weight1_code_u8[1]),
        .I3(activation_code_u8[3]),
        .I4(weight1_code_u8[0]),
        .I5(activation_code_u8[4]),
        .O(raw1_s33_reg_i_28_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw1_s33_reg_i_29
       (.I0(weight1_code_u8[2]),
        .I1(activation_code_u8[1]),
        .I2(weight1_code_u8[1]),
        .I3(activation_code_u8[2]),
        .I4(weight1_code_u8[0]),
        .I5(activation_code_u8[3]),
        .O(raw1_s33_reg_i_29_n_0));
  CARRY8 raw1_s33_reg_i_3
       (.CI(1'b0),
        .CI_TOP(1'b0),
        .CO({raw1_s33_reg_i_3_n_0,raw1_s33_reg_i_3_n_1,raw1_s33_reg_i_3_n_2,raw1_s33_reg_i_3_n_3,raw1_s33_reg_i_3_n_4,raw1_s33_reg_i_3_n_5,raw1_s33_reg_i_3_n_6,raw1_s33_reg_i_3_n_7}),
        .DI({raw1_s33_reg_i_26_n_0,raw1_s33_reg_i_27_n_0,raw1_s33_reg_i_28_n_0,raw1_s33_reg_i_29_n_0,raw1_s33_reg_i_30_n_0,raw1_s33_reg_i_31_n_0,raw1_s33_reg_i_32_n_0,1'b0}),
        .O({raw1_s33_reg_i_3_n_8,raw1_s33_reg_i_3_n_9,raw1_s33_reg_i_3_n_10,raw1_s33_reg_i_3_n_11,raw1_s33_reg_i_3_n_12,raw1_s33_reg_i_3_n_13,raw1_s33_reg_i_3_n_14,raw1_s33_reg_i_3_n_15}),
        .S({raw1_s33_reg_i_33_n_0,raw1_s33_reg_i_34_n_0,raw1_s33_reg_i_35_n_0,raw1_s33_reg_i_36_n_0,raw1_s33_reg_i_37_n_0,raw1_s33_reg_i_38_n_0,raw1_s33_reg_i_39_n_0,raw1_s33_reg_i_40_n_0}));
  LUT6 #(
    .INIT(64'h8777788878887888)) 
    raw1_s33_reg_i_30
       (.I0(weight1_code_u8[1]),
        .I1(activation_code_u8[2]),
        .I2(weight1_code_u8[2]),
        .I3(activation_code_u8[1]),
        .I4(activation_code_u8[3]),
        .I5(weight1_code_u8[0]),
        .O(raw1_s33_reg_i_30_n_0));
  LUT4 #(
    .INIT(16'h7888)) 
    raw1_s33_reg_i_31
       (.I0(weight1_code_u8[1]),
        .I1(activation_code_u8[1]),
        .I2(weight1_code_u8[2]),
        .I3(activation_code_u8[0]),
        .O(raw1_s33_reg_i_31_n_0));
  LUT2 #(
    .INIT(4'h8)) 
    raw1_s33_reg_i_32
       (.I0(weight1_code_u8[0]),
        .I1(activation_code_u8[1]),
        .O(raw1_s33_reg_i_32_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw1_s33_reg_i_33
       (.I0(raw1_s33_reg_i_26_n_0),
        .I1(weight1_code_u8[1]),
        .I2(activation_code_u8[6]),
        .I3(raw1_s33_reg_i_62_n_0),
        .I4(activation_code_u8[7]),
        .I5(weight1_code_u8[0]),
        .O(raw1_s33_reg_i_33_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw1_s33_reg_i_34
       (.I0(raw1_s33_reg_i_27_n_0),
        .I1(weight1_code_u8[1]),
        .I2(activation_code_u8[5]),
        .I3(raw1_s33_reg_i_63_n_0),
        .I4(activation_code_u8[6]),
        .I5(weight1_code_u8[0]),
        .O(raw1_s33_reg_i_34_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw1_s33_reg_i_35
       (.I0(raw1_s33_reg_i_28_n_0),
        .I1(weight1_code_u8[1]),
        .I2(activation_code_u8[4]),
        .I3(raw1_s33_reg_i_64_n_0),
        .I4(activation_code_u8[5]),
        .I5(weight1_code_u8[0]),
        .O(raw1_s33_reg_i_35_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw1_s33_reg_i_36
       (.I0(raw1_s33_reg_i_29_n_0),
        .I1(weight1_code_u8[1]),
        .I2(activation_code_u8[3]),
        .I3(raw1_s33_reg_i_65_n_0),
        .I4(activation_code_u8[4]),
        .I5(weight1_code_u8[0]),
        .O(raw1_s33_reg_i_36_n_0));
  LUT6 #(
    .INIT(64'h99C369C399339933)) 
    raw1_s33_reg_i_37
       (.I0(activation_code_u8[2]),
        .I1(raw1_s33_reg_i_66_n_0),
        .I2(activation_code_u8[1]),
        .I3(weight1_code_u8[1]),
        .I4(activation_code_u8[0]),
        .I5(weight1_code_u8[2]),
        .O(raw1_s33_reg_i_37_n_0));
  LUT6 #(
    .INIT(64'h8777788878887888)) 
    raw1_s33_reg_i_38
       (.I0(activation_code_u8[0]),
        .I1(weight1_code_u8[2]),
        .I2(activation_code_u8[1]),
        .I3(weight1_code_u8[1]),
        .I4(weight1_code_u8[0]),
        .I5(activation_code_u8[2]),
        .O(raw1_s33_reg_i_38_n_0));
  LUT4 #(
    .INIT(16'h7888)) 
    raw1_s33_reg_i_39
       (.I0(weight1_code_u8[0]),
        .I1(activation_code_u8[1]),
        .I2(weight1_code_u8[1]),
        .I3(activation_code_u8[0]),
        .O(raw1_s33_reg_i_39_n_0));
  LUT6 #(
    .INIT(64'h7D44144414441444)) 
    raw1_s33_reg_i_4
       (.I0(raw1_s33_reg_i_41_n_0),
        .I1(raw1_s33_reg_i_42_n_6),
        .I2(activation_code_u8[6]),
        .I3(weight1_code_u8[7]),
        .I4(raw1_s33_reg_i_42_n_14),
        .I5(activation_code_u8[5]),
        .O(raw1_s33_reg_i_4_n_0));
  LUT2 #(
    .INIT(4'h8)) 
    raw1_s33_reg_i_40
       (.I0(activation_code_u8[0]),
        .I1(weight1_code_u8[0]),
        .O(raw1_s33_reg_i_40_n_0));
  (* SOFT_HLUTNM = "soft_lutpair26" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_41
       (.I0(activation_code_u8[7]),
        .I1(weight1_code_u8[6]),
        .O(raw1_s33_reg_i_41_n_0));
  CARRY8 raw1_s33_reg_i_42
       (.CI(raw1_s33_reg_i_56_n_0),
        .CI_TOP(1'b0),
        .CO({NLW_raw1_s33_reg_i_42_CO_UNCONNECTED[7:2],raw1_s33_reg_i_42_n_6,raw1_s33_reg_i_42_n_7}),
        .DI({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,raw1_s33_reg_i_67_n_0,raw1_s33_reg_i_68_n_0}),
        .O({NLW_raw1_s33_reg_i_42_O_UNCONNECTED[7:2],raw1_s33_reg_i_42_n_14,raw1_s33_reg_i_42_n_15}),
        .S({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,raw1_s33_reg_i_69_n_0,raw1_s33_reg_i_70_n_0}));
  (* SOFT_HLUTNM = "soft_lutpair25" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_43
       (.I0(activation_code_u8[6]),
        .I1(weight1_code_u8[6]),
        .O(raw1_s33_reg_i_43_n_0));
  (* SOFT_HLUTNM = "soft_lutpair10" *) 
  LUT4 #(
    .INIT(16'hE888)) 
    raw1_s33_reg_i_44
       (.I0(raw1_s33_reg_i_56_n_8),
        .I1(raw1_s33_reg_i_71_n_6),
        .I2(weight1_code_u8[7]),
        .I3(activation_code_u8[3]),
        .O(raw1_s33_reg_i_44_n_0));
  (* SOFT_HLUTNM = "soft_lutpair10" *) 
  LUT4 #(
    .INIT(16'h7887)) 
    raw1_s33_reg_i_45
       (.I0(weight1_code_u8[7]),
        .I1(activation_code_u8[3]),
        .I2(raw1_s33_reg_i_56_n_8),
        .I3(raw1_s33_reg_i_71_n_6),
        .O(raw1_s33_reg_i_45_n_0));
  (* SOFT_HLUTNM = "soft_lutpair9" *) 
  LUT4 #(
    .INIT(16'hE888)) 
    raw1_s33_reg_i_46
       (.I0(raw1_s33_reg_i_56_n_9),
        .I1(raw1_s33_reg_i_71_n_14),
        .I2(weight1_code_u8[7]),
        .I3(activation_code_u8[2]),
        .O(raw1_s33_reg_i_46_n_0));
  (* SOFT_HLUTNM = "soft_lutpair2" *) 
  LUT3 #(
    .INIT(8'h7F)) 
    raw1_s33_reg_i_47
       (.I0(weight1_code_u8[7]),
        .I1(activation_code_u8[5]),
        .I2(raw1_s33_reg_i_42_n_14),
        .O(raw1_s33_reg_i_47_n_0));
  (* SOFT_HLUTNM = "soft_lutpair16" *) 
  LUT3 #(
    .INIT(8'h87)) 
    raw1_s33_reg_i_48
       (.I0(weight1_code_u8[7]),
        .I1(activation_code_u8[6]),
        .I2(raw1_s33_reg_i_42_n_6),
        .O(raw1_s33_reg_i_48_n_0));
  (* SOFT_HLUTNM = "soft_lutpair31" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_49
       (.I0(activation_code_u8[5]),
        .I1(weight1_code_u8[6]),
        .O(raw1_s33_reg_i_49_n_0));
  LUT6 #(
    .INIT(64'h7D44144414441444)) 
    raw1_s33_reg_i_5
       (.I0(raw1_s33_reg_i_43_n_0),
        .I1(raw1_s33_reg_i_42_n_14),
        .I2(activation_code_u8[5]),
        .I3(weight1_code_u8[7]),
        .I4(raw1_s33_reg_i_42_n_15),
        .I5(activation_code_u8[4]),
        .O(raw1_s33_reg_i_5_n_0));
  (* SOFT_HLUTNM = "soft_lutpair2" *) 
  LUT5 #(
    .INIT(32'h6A959595)) 
    raw1_s33_reg_i_50
       (.I0(raw1_s33_reg_i_42_n_14),
        .I1(activation_code_u8[5]),
        .I2(weight1_code_u8[7]),
        .I3(weight1_code_u8[6]),
        .I4(activation_code_u8[6]),
        .O(raw1_s33_reg_i_50_n_0));
  (* SOFT_HLUTNM = "soft_lutpair30" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_51
       (.I0(activation_code_u8[4]),
        .I1(weight1_code_u8[6]),
        .O(raw1_s33_reg_i_51_n_0));
  (* SOFT_HLUTNM = "soft_lutpair16" *) 
  LUT3 #(
    .INIT(8'h87)) 
    raw1_s33_reg_i_52
       (.I0(weight1_code_u8[7]),
        .I1(activation_code_u8[4]),
        .I2(raw1_s33_reg_i_42_n_15),
        .O(raw1_s33_reg_i_52_n_0));
  (* SOFT_HLUTNM = "soft_lutpair9" *) 
  LUT4 #(
    .INIT(16'h7887)) 
    raw1_s33_reg_i_53
       (.I0(weight1_code_u8[7]),
        .I1(activation_code_u8[2]),
        .I2(raw1_s33_reg_i_56_n_9),
        .I3(raw1_s33_reg_i_71_n_14),
        .O(raw1_s33_reg_i_53_n_0));
  (* SOFT_HLUTNM = "soft_lutpair8" *) 
  LUT4 #(
    .INIT(16'hE888)) 
    raw1_s33_reg_i_54
       (.I0(raw1_s33_reg_i_56_n_10),
        .I1(raw1_s33_reg_i_71_n_15),
        .I2(weight1_code_u8[7]),
        .I3(activation_code_u8[1]),
        .O(raw1_s33_reg_i_54_n_0));
  (* SOFT_HLUTNM = "soft_lutpair8" *) 
  LUT4 #(
    .INIT(16'h7887)) 
    raw1_s33_reg_i_55
       (.I0(weight1_code_u8[7]),
        .I1(activation_code_u8[1]),
        .I2(raw1_s33_reg_i_56_n_10),
        .I3(raw1_s33_reg_i_71_n_15),
        .O(raw1_s33_reg_i_55_n_0));
  CARRY8 raw1_s33_reg_i_56
       (.CI(1'b0),
        .CI_TOP(1'b0),
        .CO({raw1_s33_reg_i_56_n_0,raw1_s33_reg_i_56_n_1,raw1_s33_reg_i_56_n_2,raw1_s33_reg_i_56_n_3,raw1_s33_reg_i_56_n_4,raw1_s33_reg_i_56_n_5,raw1_s33_reg_i_56_n_6,raw1_s33_reg_i_56_n_7}),
        .DI({raw1_s33_reg_i_72_n_0,raw1_s33_reg_i_73_n_0,raw1_s33_reg_i_74_n_0,raw1_s33_reg_i_75_n_0,raw1_s33_reg_i_76_n_0,raw1_s33_reg_i_77_n_0,raw1_s33_reg_i_78_n_0,1'b0}),
        .O({raw1_s33_reg_i_56_n_8,raw1_s33_reg_i_56_n_9,raw1_s33_reg_i_56_n_10,raw1_s33_reg_i_56_n_11,raw1_s33_reg_i_56_n_12,raw1_s33_reg_i_56_n_13,raw1_s33_reg_i_56_n_14,raw1_s33_reg_i_56_n_15}),
        .S({raw1_s33_reg_i_79_n_0,raw1_s33_reg_i_80_n_0,raw1_s33_reg_i_81_n_0,raw1_s33_reg_i_82_n_0,raw1_s33_reg_i_83_n_0,raw1_s33_reg_i_84_n_0,raw1_s33_reg_i_85_n_0,raw1_s33_reg_i_86_n_0}));
  (* SOFT_HLUTNM = "soft_lutpair29" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_57
       (.I0(activation_code_u8[3]),
        .I1(weight1_code_u8[6]),
        .O(raw1_s33_reg_i_57_n_0));
  (* SOFT_HLUTNM = "soft_lutpair14" *) 
  LUT4 #(
    .INIT(16'h8000)) 
    raw1_s33_reg_i_58
       (.I0(raw1_s33_reg_i_3_n_9),
        .I1(raw1_s33_reg_i_56_n_12),
        .I2(weight1_code_u8[6]),
        .I3(activation_code_u8[1]),
        .O(raw1_s33_reg_i_58_n_0));
  (* SOFT_HLUTNM = "soft_lutpair14" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_59
       (.I0(activation_code_u8[2]),
        .I1(weight1_code_u8[6]),
        .O(raw1_s33_reg_i_59_n_0));
  LUT6 #(
    .INIT(64'h8FF8F8F808808080)) 
    raw1_s33_reg_i_6
       (.I0(weight1_code_u8[6]),
        .I1(activation_code_u8[5]),
        .I2(raw1_s33_reg_i_42_n_15),
        .I3(activation_code_u8[4]),
        .I4(weight1_code_u8[7]),
        .I5(raw1_s33_reg_i_44_n_0),
        .O(raw1_s33_reg_i_6_n_0));
  (* SOFT_HLUTNM = "soft_lutpair7" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_60
       (.I0(activation_code_u8[0]),
        .I1(weight1_code_u8[7]),
        .O(raw1_s33_reg_i_60_n_0));
  (* SOFT_HLUTNM = "soft_lutpair7" *) 
  LUT4 #(
    .INIT(16'h7887)) 
    raw1_s33_reg_i_61
       (.I0(weight1_code_u8[7]),
        .I1(activation_code_u8[0]),
        .I2(raw1_s33_reg_i_56_n_11),
        .I3(raw1_s33_reg_i_3_n_8),
        .O(raw1_s33_reg_i_61_n_0));
  (* SOFT_HLUTNM = "soft_lutpair24" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_62
       (.I0(activation_code_u8[5]),
        .I1(weight1_code_u8[2]),
        .O(raw1_s33_reg_i_62_n_0));
  (* SOFT_HLUTNM = "soft_lutpair23" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_63
       (.I0(activation_code_u8[4]),
        .I1(weight1_code_u8[2]),
        .O(raw1_s33_reg_i_63_n_0));
  (* SOFT_HLUTNM = "soft_lutpair28" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_64
       (.I0(activation_code_u8[3]),
        .I1(weight1_code_u8[2]),
        .O(raw1_s33_reg_i_64_n_0));
  (* SOFT_HLUTNM = "soft_lutpair27" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_65
       (.I0(activation_code_u8[2]),
        .I1(weight1_code_u8[2]),
        .O(raw1_s33_reg_i_65_n_0));
  (* SOFT_HLUTNM = "soft_lutpair22" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_66
       (.I0(activation_code_u8[3]),
        .I1(weight1_code_u8[0]),
        .O(raw1_s33_reg_i_66_n_0));
  LUT4 #(
    .INIT(16'h8000)) 
    raw1_s33_reg_i_67
       (.I0(weight1_code_u8[5]),
        .I1(activation_code_u8[6]),
        .I2(weight1_code_u8[4]),
        .I3(activation_code_u8[7]),
        .O(raw1_s33_reg_i_67_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw1_s33_reg_i_68
       (.I0(weight1_code_u8[5]),
        .I1(activation_code_u8[5]),
        .I2(weight1_code_u8[4]),
        .I3(activation_code_u8[6]),
        .I4(weight1_code_u8[3]),
        .I5(activation_code_u8[7]),
        .O(raw1_s33_reg_i_68_n_0));
  LUT4 #(
    .INIT(16'h7000)) 
    raw1_s33_reg_i_69
       (.I0(weight1_code_u8[4]),
        .I1(activation_code_u8[6]),
        .I2(weight1_code_u8[5]),
        .I3(activation_code_u8[7]),
        .O(raw1_s33_reg_i_69_n_0));
  LUT4 #(
    .INIT(16'h8F08)) 
    raw1_s33_reg_i_7
       (.I0(weight1_code_u8[6]),
        .I1(activation_code_u8[4]),
        .I2(raw1_s33_reg_i_45_n_0),
        .I3(raw1_s33_reg_i_46_n_0),
        .O(raw1_s33_reg_i_7_n_0));
  LUT6 #(
    .INIT(64'hE75F30007800F000)) 
    raw1_s33_reg_i_70
       (.I0(weight1_code_u8[3]),
        .I1(activation_code_u8[5]),
        .I2(activation_code_u8[6]),
        .I3(weight1_code_u8[5]),
        .I4(activation_code_u8[7]),
        .I5(weight1_code_u8[4]),
        .O(raw1_s33_reg_i_70_n_0));
  CARRY8 raw1_s33_reg_i_71
       (.CI(raw1_s33_reg_i_3_n_0),
        .CI_TOP(1'b0),
        .CO({NLW_raw1_s33_reg_i_71_CO_UNCONNECTED[7:2],raw1_s33_reg_i_71_n_6,raw1_s33_reg_i_71_n_7}),
        .DI({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,raw1_s33_reg_i_87_n_0,raw1_s33_reg_i_88_n_0}),
        .O({NLW_raw1_s33_reg_i_71_O_UNCONNECTED[7:2],raw1_s33_reg_i_71_n_14,raw1_s33_reg_i_71_n_15}),
        .S({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,raw1_s33_reg_i_89_n_0,raw1_s33_reg_i_90_n_0}));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw1_s33_reg_i_72
       (.I0(weight1_code_u8[5]),
        .I1(activation_code_u8[4]),
        .I2(weight1_code_u8[4]),
        .I3(activation_code_u8[5]),
        .I4(weight1_code_u8[3]),
        .I5(activation_code_u8[6]),
        .O(raw1_s33_reg_i_72_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw1_s33_reg_i_73
       (.I0(weight1_code_u8[5]),
        .I1(activation_code_u8[3]),
        .I2(weight1_code_u8[4]),
        .I3(activation_code_u8[4]),
        .I4(weight1_code_u8[3]),
        .I5(activation_code_u8[5]),
        .O(raw1_s33_reg_i_73_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw1_s33_reg_i_74
       (.I0(weight1_code_u8[5]),
        .I1(activation_code_u8[2]),
        .I2(weight1_code_u8[4]),
        .I3(activation_code_u8[3]),
        .I4(weight1_code_u8[3]),
        .I5(activation_code_u8[4]),
        .O(raw1_s33_reg_i_74_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw1_s33_reg_i_75
       (.I0(weight1_code_u8[5]),
        .I1(activation_code_u8[1]),
        .I2(weight1_code_u8[4]),
        .I3(activation_code_u8[2]),
        .I4(weight1_code_u8[3]),
        .I5(activation_code_u8[3]),
        .O(raw1_s33_reg_i_75_n_0));
  LUT6 #(
    .INIT(64'h8777788878887888)) 
    raw1_s33_reg_i_76
       (.I0(weight1_code_u8[4]),
        .I1(activation_code_u8[2]),
        .I2(weight1_code_u8[5]),
        .I3(activation_code_u8[1]),
        .I4(activation_code_u8[3]),
        .I5(weight1_code_u8[3]),
        .O(raw1_s33_reg_i_76_n_0));
  LUT4 #(
    .INIT(16'h7888)) 
    raw1_s33_reg_i_77
       (.I0(weight1_code_u8[4]),
        .I1(activation_code_u8[1]),
        .I2(weight1_code_u8[5]),
        .I3(activation_code_u8[0]),
        .O(raw1_s33_reg_i_77_n_0));
  LUT2 #(
    .INIT(4'h8)) 
    raw1_s33_reg_i_78
       (.I0(weight1_code_u8[3]),
        .I1(activation_code_u8[1]),
        .O(raw1_s33_reg_i_78_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw1_s33_reg_i_79
       (.I0(raw1_s33_reg_i_72_n_0),
        .I1(weight1_code_u8[4]),
        .I2(activation_code_u8[6]),
        .I3(raw1_s33_reg_i_91_n_0),
        .I4(activation_code_u8[7]),
        .I5(weight1_code_u8[3]),
        .O(raw1_s33_reg_i_79_n_0));
  LUT4 #(
    .INIT(16'h8000)) 
    raw1_s33_reg_i_8
       (.I0(activation_code_u8[7]),
        .I1(raw1_s33_reg_i_42_n_6),
        .I2(activation_code_u8[6]),
        .I3(weight1_code_u8[7]),
        .O(raw1_s33_reg_i_8_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw1_s33_reg_i_80
       (.I0(raw1_s33_reg_i_73_n_0),
        .I1(weight1_code_u8[4]),
        .I2(activation_code_u8[5]),
        .I3(raw1_s33_reg_i_92_n_0),
        .I4(activation_code_u8[6]),
        .I5(weight1_code_u8[3]),
        .O(raw1_s33_reg_i_80_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw1_s33_reg_i_81
       (.I0(raw1_s33_reg_i_74_n_0),
        .I1(weight1_code_u8[4]),
        .I2(activation_code_u8[4]),
        .I3(raw1_s33_reg_i_93_n_0),
        .I4(activation_code_u8[5]),
        .I5(weight1_code_u8[3]),
        .O(raw1_s33_reg_i_81_n_0));
  LUT6 #(
    .INIT(64'h956A6A956A956A95)) 
    raw1_s33_reg_i_82
       (.I0(raw1_s33_reg_i_75_n_0),
        .I1(weight1_code_u8[4]),
        .I2(activation_code_u8[3]),
        .I3(raw1_s33_reg_i_94_n_0),
        .I4(activation_code_u8[4]),
        .I5(weight1_code_u8[3]),
        .O(raw1_s33_reg_i_82_n_0));
  LUT6 #(
    .INIT(64'h99C369C399339933)) 
    raw1_s33_reg_i_83
       (.I0(activation_code_u8[2]),
        .I1(raw1_s33_reg_i_95_n_0),
        .I2(activation_code_u8[1]),
        .I3(weight1_code_u8[4]),
        .I4(activation_code_u8[0]),
        .I5(weight1_code_u8[5]),
        .O(raw1_s33_reg_i_83_n_0));
  LUT6 #(
    .INIT(64'h8777788878887888)) 
    raw1_s33_reg_i_84
       (.I0(activation_code_u8[0]),
        .I1(weight1_code_u8[5]),
        .I2(activation_code_u8[1]),
        .I3(weight1_code_u8[4]),
        .I4(weight1_code_u8[3]),
        .I5(activation_code_u8[2]),
        .O(raw1_s33_reg_i_84_n_0));
  LUT4 #(
    .INIT(16'h7888)) 
    raw1_s33_reg_i_85
       (.I0(weight1_code_u8[3]),
        .I1(activation_code_u8[1]),
        .I2(weight1_code_u8[4]),
        .I3(activation_code_u8[0]),
        .O(raw1_s33_reg_i_85_n_0));
  LUT2 #(
    .INIT(4'h8)) 
    raw1_s33_reg_i_86
       (.I0(activation_code_u8[0]),
        .I1(weight1_code_u8[3]),
        .O(raw1_s33_reg_i_86_n_0));
  LUT4 #(
    .INIT(16'h8000)) 
    raw1_s33_reg_i_87
       (.I0(weight1_code_u8[2]),
        .I1(activation_code_u8[6]),
        .I2(weight1_code_u8[1]),
        .I3(activation_code_u8[7]),
        .O(raw1_s33_reg_i_87_n_0));
  LUT6 #(
    .INIT(64'hF888800080008000)) 
    raw1_s33_reg_i_88
       (.I0(weight1_code_u8[2]),
        .I1(activation_code_u8[5]),
        .I2(weight1_code_u8[1]),
        .I3(activation_code_u8[6]),
        .I4(weight1_code_u8[0]),
        .I5(activation_code_u8[7]),
        .O(raw1_s33_reg_i_88_n_0));
  LUT4 #(
    .INIT(16'h7000)) 
    raw1_s33_reg_i_89
       (.I0(weight1_code_u8[1]),
        .I1(activation_code_u8[6]),
        .I2(weight1_code_u8[2]),
        .I3(activation_code_u8[7]),
        .O(raw1_s33_reg_i_89_n_0));
  LUT6 #(
    .INIT(64'h4FD525D52540B040)) 
    raw1_s33_reg_i_9
       (.I0(raw1_s33_reg_i_47_n_0),
        .I1(weight1_code_u8[6]),
        .I2(activation_code_u8[7]),
        .I3(weight1_code_u8[7]),
        .I4(activation_code_u8[6]),
        .I5(raw1_s33_reg_i_42_n_6),
        .O(raw1_s33_reg_i_9_n_0));
  LUT6 #(
    .INIT(64'hE75F30007800F000)) 
    raw1_s33_reg_i_90
       (.I0(weight1_code_u8[0]),
        .I1(activation_code_u8[5]),
        .I2(activation_code_u8[6]),
        .I3(weight1_code_u8[2]),
        .I4(activation_code_u8[7]),
        .I5(weight1_code_u8[1]),
        .O(raw1_s33_reg_i_90_n_0));
  (* SOFT_HLUTNM = "soft_lutpair31" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_91
       (.I0(activation_code_u8[5]),
        .I1(weight1_code_u8[5]),
        .O(raw1_s33_reg_i_91_n_0));
  (* SOFT_HLUTNM = "soft_lutpair30" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_92
       (.I0(activation_code_u8[4]),
        .I1(weight1_code_u8[5]),
        .O(raw1_s33_reg_i_92_n_0));
  (* SOFT_HLUTNM = "soft_lutpair29" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_93
       (.I0(activation_code_u8[3]),
        .I1(weight1_code_u8[5]),
        .O(raw1_s33_reg_i_93_n_0));
  (* SOFT_HLUTNM = "soft_lutpair27" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_94
       (.I0(activation_code_u8[2]),
        .I1(weight1_code_u8[5]),
        .O(raw1_s33_reg_i_94_n_0));
  (* SOFT_HLUTNM = "soft_lutpair28" *) 
  LUT2 #(
    .INIT(4'h7)) 
    raw1_s33_reg_i_95
       (.I0(activation_code_u8[3]),
        .I1(weight1_code_u8[3]),
        .O(raw1_s33_reg_i_95_n_0));
  (* SOFT_HLUTNM = "soft_lutpair12" *) 
  LUT3 #(
    .INIT(8'hB8)) 
    s0_valid_r_i_1
       (.I0(in_valid),
        .I1(s0_ready),
        .I2(s0_valid_r),
        .O(s0_valid_r_i_1_n_0));
  FDRE s0_valid_r_reg
       (.C(clk),
        .CE(1'b1),
        .D(s0_valid_r_i_1_n_0),
        .Q(s0_valid_r),
        .R(out_valid_i_1_n_0));
  (* SOFT_HLUTNM = "soft_lutpair11" *) 
  LUT4 #(
    .INIT(16'hAEAA)) 
    s1_valid_r_i_1
       (.I0(s0_valid_r),
        .I1(out_valid),
        .I2(out_ready),
        .I3(s1_valid_r),
        .O(s1_valid_r_i_1_n_0));
  FDRE s1_valid_r_reg
       (.C(clk),
        .CE(1'b1),
        .D(s1_valid_r_i_1_n_0),
        .Q(s1_valid_r),
        .R(out_valid_i_1_n_0));
endmodule
`ifndef GLBL
`define GLBL
`timescale  1 ps / 1 ps

module glbl ();

    parameter ROC_WIDTH = 100000;
    parameter TOC_WIDTH = 0;
    parameter GRES_WIDTH = 10000;
    parameter GRES_START = 10000;

//--------   STARTUP Globals --------------
    wire GSR;
    wire GTS;
    wire GWE;
    wire PRLD;
    wire GRESTORE;
    tri1 p_up_tmp;
    tri (weak1, strong0) PLL_LOCKG = p_up_tmp;

    wire PROGB_GLBL;
    wire CCLKO_GLBL;
    wire FCSBO_GLBL;
    wire [3:0] DO_GLBL;
    wire [3:0] DI_GLBL;
   
    reg GSR_int;
    reg GTS_int;
    reg PRLD_int;
    reg GRESTORE_int;

//--------   JTAG Globals --------------
    wire JTAG_TDO_GLBL;
    wire JTAG_TCK_GLBL;
    wire JTAG_TDI_GLBL;
    wire JTAG_TMS_GLBL;
    wire JTAG_TRST_GLBL;

    reg JTAG_CAPTURE_GLBL;
    reg JTAG_RESET_GLBL;
    reg JTAG_SHIFT_GLBL;
    reg JTAG_UPDATE_GLBL;
    reg JTAG_RUNTEST_GLBL;

    reg JTAG_SEL1_GLBL = 0;
    reg JTAG_SEL2_GLBL = 0 ;
    reg JTAG_SEL3_GLBL = 0;
    reg JTAG_SEL4_GLBL = 0;

    reg JTAG_USER_TDO1_GLBL = 1'bz;
    reg JTAG_USER_TDO2_GLBL = 1'bz;
    reg JTAG_USER_TDO3_GLBL = 1'bz;
    reg JTAG_USER_TDO4_GLBL = 1'bz;

    assign (strong1, weak0) GSR = GSR_int;
    assign (strong1, weak0) GTS = GTS_int;
    assign (weak1, weak0) PRLD = PRLD_int;
    assign (strong1, weak0) GRESTORE = GRESTORE_int;

    initial begin
	GSR_int = 1'b1;
	PRLD_int = 1'b1;
	#(ROC_WIDTH)
	GSR_int = 1'b0;
	PRLD_int = 1'b0;
    end

    initial begin
	GTS_int = 1'b1;
	#(TOC_WIDTH)
	GTS_int = 1'b0;
    end

    initial begin 
	GRESTORE_int = 1'b0;
	#(GRES_START);
	GRESTORE_int = 1'b1;
	#(GRES_WIDTH);
	GRESTORE_int = 1'b0;
    end

endmodule
`endif
