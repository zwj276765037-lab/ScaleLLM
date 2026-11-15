// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2025 Advanced Micro Devices, Inc. All Rights Reserved.
// --------------------------------------------------------------------------------
// Tool Version: Vivado v.2025.2 (lin64) Build 6299465 Fri Nov 14 12:34:56 MST 2025
// Date        : Sat Nov 14 09:04:45 2026
// Host        : user running 64-bit Ubuntu 24.04.4 LTS
// Command     : write_verilog -force -mode funcsim
//               /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/0_Hardware_supplementation_experiment/experiment/mlp_scalecode_dsp_board/functional/dsp_all/attempts/20261114T010405Z/synth/post_synth_funcsim.v
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
  wire raw0_s33_reg_i_1_n_0;
  wire raw0_s33_reg_i_2_n_0;
  wire raw0_s33_reg_i_3_n_0;
  wire [32:0]raw1_s33;
  wire rst_n;
  wire s0_code_product0_u16_r_reg_n_100;
  wire s0_code_product0_u16_r_reg_n_101;
  wire s0_code_product0_u16_r_reg_n_102;
  wire s0_code_product0_u16_r_reg_n_103;
  wire s0_code_product0_u16_r_reg_n_104;
  wire s0_code_product0_u16_r_reg_n_105;
  wire s0_code_product0_u16_r_reg_n_90;
  wire s0_code_product0_u16_r_reg_n_91;
  wire s0_code_product0_u16_r_reg_n_92;
  wire s0_code_product0_u16_r_reg_n_93;
  wire s0_code_product0_u16_r_reg_n_94;
  wire s0_code_product0_u16_r_reg_n_95;
  wire s0_code_product0_u16_r_reg_n_96;
  wire s0_code_product0_u16_r_reg_n_97;
  wire s0_code_product0_u16_r_reg_n_98;
  wire s0_code_product0_u16_r_reg_n_99;
  wire s0_code_product1_u16_r_reg_n_100;
  wire s0_code_product1_u16_r_reg_n_101;
  wire s0_code_product1_u16_r_reg_n_102;
  wire s0_code_product1_u16_r_reg_n_103;
  wire s0_code_product1_u16_r_reg_n_104;
  wire s0_code_product1_u16_r_reg_n_105;
  wire s0_code_product1_u16_r_reg_n_90;
  wire s0_code_product1_u16_r_reg_n_91;
  wire s0_code_product1_u16_r_reg_n_92;
  wire s0_code_product1_u16_r_reg_n_93;
  wire s0_code_product1_u16_r_reg_n_94;
  wire s0_code_product1_u16_r_reg_n_95;
  wire s0_code_product1_u16_r_reg_n_96;
  wire s0_code_product1_u16_r_reg_n_97;
  wire s0_code_product1_u16_r_reg_n_98;
  wire s0_code_product1_u16_r_reg_n_99;
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
  wire NLW_s0_code_product0_u16_r_reg_CARRYCASCOUT_UNCONNECTED;
  wire NLW_s0_code_product0_u16_r_reg_MULTSIGNOUT_UNCONNECTED;
  wire NLW_s0_code_product0_u16_r_reg_OVERFLOW_UNCONNECTED;
  wire NLW_s0_code_product0_u16_r_reg_PATTERNBDETECT_UNCONNECTED;
  wire NLW_s0_code_product0_u16_r_reg_PATTERNDETECT_UNCONNECTED;
  wire NLW_s0_code_product0_u16_r_reg_UNDERFLOW_UNCONNECTED;
  wire [29:0]NLW_s0_code_product0_u16_r_reg_ACOUT_UNCONNECTED;
  wire [17:0]NLW_s0_code_product0_u16_r_reg_BCOUT_UNCONNECTED;
  wire [3:0]NLW_s0_code_product0_u16_r_reg_CARRYOUT_UNCONNECTED;
  wire [47:16]NLW_s0_code_product0_u16_r_reg_P_UNCONNECTED;
  wire [47:0]NLW_s0_code_product0_u16_r_reg_PCOUT_UNCONNECTED;
  wire [7:0]NLW_s0_code_product0_u16_r_reg_XOROUT_UNCONNECTED;
  wire NLW_s0_code_product1_u16_r_reg_CARRYCASCOUT_UNCONNECTED;
  wire NLW_s0_code_product1_u16_r_reg_MULTSIGNOUT_UNCONNECTED;
  wire NLW_s0_code_product1_u16_r_reg_OVERFLOW_UNCONNECTED;
  wire NLW_s0_code_product1_u16_r_reg_PATTERNBDETECT_UNCONNECTED;
  wire NLW_s0_code_product1_u16_r_reg_PATTERNDETECT_UNCONNECTED;
  wire NLW_s0_code_product1_u16_r_reg_UNDERFLOW_UNCONNECTED;
  wire [29:0]NLW_s0_code_product1_u16_r_reg_ACOUT_UNCONNECTED;
  wire [17:0]NLW_s0_code_product1_u16_r_reg_BCOUT_UNCONNECTED;
  wire [3:0]NLW_s0_code_product1_u16_r_reg_CARRYOUT_UNCONNECTED;
  wire [47:16]NLW_s0_code_product1_u16_r_reg_P_UNCONNECTED;
  wire [47:0]NLW_s0_code_product1_u16_r_reg_PCOUT_UNCONNECTED;
  wire [7:0]NLW_s0_code_product1_u16_r_reg_XOROUT_UNCONNECTED;

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
  (* SOFT_HLUTNM = "soft_lutpair1" *) 
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
  (* KEEP_HIERARCHY = "YES" *) 
  DSP48E2 #(
    .ACASCREG(1),
    .ADREG(1),
    .ALUMODEREG(0),
    .AMULTSEL("A"),
    .AREG(1),
    .AUTORESET_PATDET("NO_RESET"),
    .AUTORESET_PRIORITY("RESET"),
    .A_INPUT("DIRECT"),
    .BCASCREG(0),
    .BMULTSEL("B"),
    .BREG(0),
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
        .B({1'b0,1'b0,s0_code_product0_u16_r_reg_n_90,s0_code_product0_u16_r_reg_n_91,s0_code_product0_u16_r_reg_n_92,s0_code_product0_u16_r_reg_n_93,s0_code_product0_u16_r_reg_n_94,s0_code_product0_u16_r_reg_n_95,s0_code_product0_u16_r_reg_n_96,s0_code_product0_u16_r_reg_n_97,s0_code_product0_u16_r_reg_n_98,s0_code_product0_u16_r_reg_n_99,s0_code_product0_u16_r_reg_n_100,s0_code_product0_u16_r_reg_n_101,s0_code_product0_u16_r_reg_n_102,s0_code_product0_u16_r_reg_n_103,s0_code_product0_u16_r_reg_n_104,s0_code_product0_u16_r_reg_n_105}),
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
        .CEB2(1'b0),
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
        .RSTB(1'b0),
        .RSTC(1'b0),
        .RSTCTRL(1'b0),
        .RSTD(1'b0),
        .RSTINMODE(1'b0),
        .RSTM(RSTP),
        .RSTP(RSTP),
        .UNDERFLOW(NLW_raw0_s33_reg_UNDERFLOW_UNCONNECTED),
        .XOROUT(NLW_raw0_s33_reg_XOROUT_UNCONNECTED[7:0]));
  (* SOFT_HLUTNM = "soft_lutpair2" *) 
  LUT4 #(
    .INIT(16'h0080)) 
    raw0_s33_reg_i_1
       (.I0(in_valid),
        .I1(s0_ready),
        .I2(rst_n),
        .I3(clear),
        .O(raw0_s33_reg_i_1_n_0));
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
  LUT4 #(
    .INIT(16'h008A)) 
    raw0_s33_reg_i_3
       (.I0(s1_valid_r),
        .I1(out_ready),
        .I2(out_valid),
        .I3(clear),
        .O(raw0_s33_reg_i_3_n_0));
  LUT1 #(
    .INIT(2'h1)) 
    raw0_s33_reg_i_4
       (.I0(rst_n),
        .O(RSTP));
  (* SOFT_HLUTNM = "soft_lutpair0" *) 
  LUT4 #(
    .INIT(16'hDFFF)) 
    raw0_s33_reg_i_5
       (.I0(s1_valid_r),
        .I1(out_ready),
        .I2(out_valid),
        .I3(s0_valid_r),
        .O(s0_ready));
  (* KEEP_HIERARCHY = "YES" *) 
  DSP48E2 #(
    .ACASCREG(1),
    .ADREG(1),
    .ALUMODEREG(0),
    .AMULTSEL("A"),
    .AREG(1),
    .AUTORESET_PATDET("NO_RESET"),
    .AUTORESET_PRIORITY("RESET"),
    .A_INPUT("DIRECT"),
    .BCASCREG(0),
    .BMULTSEL("B"),
    .BREG(0),
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
        .B({1'b0,1'b0,s0_code_product1_u16_r_reg_n_90,s0_code_product1_u16_r_reg_n_91,s0_code_product1_u16_r_reg_n_92,s0_code_product1_u16_r_reg_n_93,s0_code_product1_u16_r_reg_n_94,s0_code_product1_u16_r_reg_n_95,s0_code_product1_u16_r_reg_n_96,s0_code_product1_u16_r_reg_n_97,s0_code_product1_u16_r_reg_n_98,s0_code_product1_u16_r_reg_n_99,s0_code_product1_u16_r_reg_n_100,s0_code_product1_u16_r_reg_n_101,s0_code_product1_u16_r_reg_n_102,s0_code_product1_u16_r_reg_n_103,s0_code_product1_u16_r_reg_n_104,s0_code_product1_u16_r_reg_n_105}),
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
        .CEB2(1'b0),
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
        .RSTB(1'b0),
        .RSTC(1'b0),
        .RSTCTRL(1'b0),
        .RSTD(1'b0),
        .RSTINMODE(1'b0),
        .RSTM(RSTP),
        .RSTP(RSTP),
        .UNDERFLOW(NLW_raw1_s33_reg_UNDERFLOW_UNCONNECTED),
        .XOROUT(NLW_raw1_s33_reg_XOROUT_UNCONNECTED[7:0]));
  (* KEEP_HIERARCHY = "YES" *) 
  (* METHODOLOGY_DRC_VIOS = "{SYNTH-12 {cell *THIS*}}" *) 
  DSP48E2 #(
    .ACASCREG(0),
    .ADREG(1),
    .ALUMODEREG(0),
    .AMULTSEL("A"),
    .AREG(0),
    .AUTORESET_PATDET("NO_RESET"),
    .AUTORESET_PRIORITY("RESET"),
    .A_INPUT("DIRECT"),
    .BCASCREG(0),
    .BMULTSEL("B"),
    .BREG(0),
    .B_INPUT("DIRECT"),
    .CARRYINREG(0),
    .CARRYINSELREG(0),
    .CREG(0),
    .DREG(1),
    .INMODEREG(0),
    .MASK(48'h3FFFFFFFFFFF),
    .MREG(0),
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
    s0_code_product0_u16_r_reg
       (.A({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,activation_code_u8}),
        .ACIN({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .ACOUT(NLW_s0_code_product0_u16_r_reg_ACOUT_UNCONNECTED[29:0]),
        .ALUMODE({1'b0,1'b0,1'b0,1'b0}),
        .B({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,weight0_code_u8}),
        .BCIN({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .BCOUT(NLW_s0_code_product0_u16_r_reg_BCOUT_UNCONNECTED[17:0]),
        .C({1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1}),
        .CARRYCASCIN(1'b0),
        .CARRYCASCOUT(NLW_s0_code_product0_u16_r_reg_CARRYCASCOUT_UNCONNECTED),
        .CARRYIN(1'b0),
        .CARRYINSEL({1'b0,1'b0,1'b0}),
        .CARRYOUT(NLW_s0_code_product0_u16_r_reg_CARRYOUT_UNCONNECTED[3:0]),
        .CEA1(1'b0),
        .CEA2(1'b0),
        .CEAD(1'b0),
        .CEALUMODE(1'b0),
        .CEB1(1'b0),
        .CEB2(1'b0),
        .CEC(1'b0),
        .CECARRYIN(1'b0),
        .CECTRL(1'b0),
        .CED(1'b0),
        .CEINMODE(1'b0),
        .CEM(1'b0),
        .CEP(raw0_s33_reg_i_1_n_0),
        .CLK(clk),
        .D({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .INMODE({1'b0,1'b0,1'b0,1'b0,1'b0}),
        .MULTSIGNIN(1'b0),
        .MULTSIGNOUT(NLW_s0_code_product0_u16_r_reg_MULTSIGNOUT_UNCONNECTED),
        .OPMODE({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b1,1'b0,1'b1}),
        .OVERFLOW(NLW_s0_code_product0_u16_r_reg_OVERFLOW_UNCONNECTED),
        .P({NLW_s0_code_product0_u16_r_reg_P_UNCONNECTED[47:16],s0_code_product0_u16_r_reg_n_90,s0_code_product0_u16_r_reg_n_91,s0_code_product0_u16_r_reg_n_92,s0_code_product0_u16_r_reg_n_93,s0_code_product0_u16_r_reg_n_94,s0_code_product0_u16_r_reg_n_95,s0_code_product0_u16_r_reg_n_96,s0_code_product0_u16_r_reg_n_97,s0_code_product0_u16_r_reg_n_98,s0_code_product0_u16_r_reg_n_99,s0_code_product0_u16_r_reg_n_100,s0_code_product0_u16_r_reg_n_101,s0_code_product0_u16_r_reg_n_102,s0_code_product0_u16_r_reg_n_103,s0_code_product0_u16_r_reg_n_104,s0_code_product0_u16_r_reg_n_105}),
        .PATTERNBDETECT(NLW_s0_code_product0_u16_r_reg_PATTERNBDETECT_UNCONNECTED),
        .PATTERNDETECT(NLW_s0_code_product0_u16_r_reg_PATTERNDETECT_UNCONNECTED),
        .PCIN({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .PCOUT(NLW_s0_code_product0_u16_r_reg_PCOUT_UNCONNECTED[47:0]),
        .RSTA(1'b0),
        .RSTALLCARRYIN(1'b0),
        .RSTALUMODE(1'b0),
        .RSTB(1'b0),
        .RSTC(1'b0),
        .RSTCTRL(1'b0),
        .RSTD(1'b0),
        .RSTINMODE(1'b0),
        .RSTM(1'b0),
        .RSTP(RSTP),
        .UNDERFLOW(NLW_s0_code_product0_u16_r_reg_UNDERFLOW_UNCONNECTED),
        .XOROUT(NLW_s0_code_product0_u16_r_reg_XOROUT_UNCONNECTED[7:0]));
  (* KEEP_HIERARCHY = "YES" *) 
  (* METHODOLOGY_DRC_VIOS = "{SYNTH-12 {cell *THIS*}}" *) 
  DSP48E2 #(
    .ACASCREG(0),
    .ADREG(1),
    .ALUMODEREG(0),
    .AMULTSEL("A"),
    .AREG(0),
    .AUTORESET_PATDET("NO_RESET"),
    .AUTORESET_PRIORITY("RESET"),
    .A_INPUT("DIRECT"),
    .BCASCREG(0),
    .BMULTSEL("B"),
    .BREG(0),
    .B_INPUT("DIRECT"),
    .CARRYINREG(0),
    .CARRYINSELREG(0),
    .CREG(0),
    .DREG(1),
    .INMODEREG(0),
    .MASK(48'h3FFFFFFFFFFF),
    .MREG(0),
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
    s0_code_product1_u16_r_reg
       (.A({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,activation_code_u8}),
        .ACIN({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .ACOUT(NLW_s0_code_product1_u16_r_reg_ACOUT_UNCONNECTED[29:0]),
        .ALUMODE({1'b0,1'b0,1'b0,1'b0}),
        .B({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,weight1_code_u8}),
        .BCIN({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .BCOUT(NLW_s0_code_product1_u16_r_reg_BCOUT_UNCONNECTED[17:0]),
        .C({1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1,1'b1}),
        .CARRYCASCIN(1'b0),
        .CARRYCASCOUT(NLW_s0_code_product1_u16_r_reg_CARRYCASCOUT_UNCONNECTED),
        .CARRYIN(1'b0),
        .CARRYINSEL({1'b0,1'b0,1'b0}),
        .CARRYOUT(NLW_s0_code_product1_u16_r_reg_CARRYOUT_UNCONNECTED[3:0]),
        .CEA1(1'b0),
        .CEA2(1'b0),
        .CEAD(1'b0),
        .CEALUMODE(1'b0),
        .CEB1(1'b0),
        .CEB2(1'b0),
        .CEC(1'b0),
        .CECARRYIN(1'b0),
        .CECTRL(1'b0),
        .CED(1'b0),
        .CEINMODE(1'b0),
        .CEM(1'b0),
        .CEP(raw0_s33_reg_i_1_n_0),
        .CLK(clk),
        .D({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .INMODE({1'b0,1'b0,1'b0,1'b0,1'b0}),
        .MULTSIGNIN(1'b0),
        .MULTSIGNOUT(NLW_s0_code_product1_u16_r_reg_MULTSIGNOUT_UNCONNECTED),
        .OPMODE({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b1,1'b0,1'b1}),
        .OVERFLOW(NLW_s0_code_product1_u16_r_reg_OVERFLOW_UNCONNECTED),
        .P({NLW_s0_code_product1_u16_r_reg_P_UNCONNECTED[47:16],s0_code_product1_u16_r_reg_n_90,s0_code_product1_u16_r_reg_n_91,s0_code_product1_u16_r_reg_n_92,s0_code_product1_u16_r_reg_n_93,s0_code_product1_u16_r_reg_n_94,s0_code_product1_u16_r_reg_n_95,s0_code_product1_u16_r_reg_n_96,s0_code_product1_u16_r_reg_n_97,s0_code_product1_u16_r_reg_n_98,s0_code_product1_u16_r_reg_n_99,s0_code_product1_u16_r_reg_n_100,s0_code_product1_u16_r_reg_n_101,s0_code_product1_u16_r_reg_n_102,s0_code_product1_u16_r_reg_n_103,s0_code_product1_u16_r_reg_n_104,s0_code_product1_u16_r_reg_n_105}),
        .PATTERNBDETECT(NLW_s0_code_product1_u16_r_reg_PATTERNBDETECT_UNCONNECTED),
        .PATTERNDETECT(NLW_s0_code_product1_u16_r_reg_PATTERNDETECT_UNCONNECTED),
        .PCIN({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .PCOUT(NLW_s0_code_product1_u16_r_reg_PCOUT_UNCONNECTED[47:0]),
        .RSTA(1'b0),
        .RSTALLCARRYIN(1'b0),
        .RSTALUMODE(1'b0),
        .RSTB(1'b0),
        .RSTC(1'b0),
        .RSTCTRL(1'b0),
        .RSTD(1'b0),
        .RSTINMODE(1'b0),
        .RSTM(1'b0),
        .RSTP(RSTP),
        .UNDERFLOW(NLW_s0_code_product1_u16_r_reg_UNDERFLOW_UNCONNECTED),
        .XOROUT(NLW_s0_code_product1_u16_r_reg_XOROUT_UNCONNECTED[7:0]));
  (* SOFT_HLUTNM = "soft_lutpair2" *) 
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
  (* SOFT_HLUTNM = "soft_lutpair1" *) 
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
