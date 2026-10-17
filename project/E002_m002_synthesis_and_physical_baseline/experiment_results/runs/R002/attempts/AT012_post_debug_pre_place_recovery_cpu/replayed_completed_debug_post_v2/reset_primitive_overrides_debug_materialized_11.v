// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2025 Advanced Micro Devices, Inc. All Rights Reserved.
// --------------------------------------------------------------------------------
// Tool Version: Vivado v.2025.2 (lin64) Build 6299465 Fri Nov 14 12:34:56 MST 2025
// Date        : Thu Oct 15 15:49:20 2026
// Host        : user running 64-bit Ubuntu 24.04.4 LTS
// Command     : write_verilog -cell [get_cells -quiet -hier -filter {NAME ==
//               "scalellm_vcu118_f05_bd_i/host_split/inst/clk_map/psr_aclk1/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX"}] -mode
//               funcsim -write_all_overrides true -force
//               /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/reset_primitive_overrides_debug_materialized_11.v
// Design      : scalellm_vcu118_f05_bd_host_split_0_xpm_cdc_single__4
// Purpose     : This verilog netlist is a functional simulation representation of the design and should not be modified
//               or synthesized. This netlist cannot be used for SDF annotated simulation.
// Device      : xcvu9p-flga2104-2L-e
// --------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

(* DEST_SYNC_FF = "4" *) (* INIT_SYNC_FF = "0" *) (* ORIG_REF_NAME = "xpm_cdc_single" *) 
(* SIM_ASSERT_CHK = "0" *) (* SRC_INPUT_REG = "0" *) (* VERSION = "0" *) 
(* XPM_MODULE = "TRUE" *) (* keep_hierarchy = "soft" *) (* xpm_cdc = "SINGLE" *) 
(* NotValidForBitStream *)
(* \DesignAttr:BMM_INFO_DESIGN  = "<?xml version=\"1.0\" encoding=\"UTF-8\"?> <AddressMap Version=\"1\" Minor=\"0\" ProcessorElementCount=\"2\"> <Processor Name=\"scalellm_vcu118_f05_bd_i_ddr4_1_inst_u_ddr4_mem_intfc_u_ddr_cal_riu_mcs0_inst_microblaze_I\" Type=\"MICROBLAZE-LE\" Id=\"100\" Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/microblaze_I\" SpaceElementCount=\"1\"> <AddressSpace Name=\"scalellm_vcu118_f05_bd_i_ddr4_1_inst_u_ddr4_mem_intfc_u_ddr_cal_riu_mcs0_inst_dlmb_cntlr\" Style=\"byte\" StartAddress=\"0x0000000000000000\" EndAddress=\"0x0000000000017FFF\" Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/dlmb_cntlr\" RangeElementCount=\"2\"> <Range Type=\"RAMB32\" BusBlockElementCount=\"1\"> <Block DeviceElementCount=\"16\"> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[15].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"31:30\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[14].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"29:28\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[13].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"27:26\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[12].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"25:24\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[11].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"23:22\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[10].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"21:20\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[9].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"19:18\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[8].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"17:16\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[7].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"15:14\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[6].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"13:12\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[5].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"11:10\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[4].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"9:8\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[3].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"7:6\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[2].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"5:4\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[1].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"3:2\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[0].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"1:0\"> </Device> </Block> </Range> <Range Type=\"RAMB32\" BusBlockElementCount=\"1\"> <Block DeviceElementCount=\"8\"> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[7].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"31:28\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[6].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"27:24\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[5].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"23:20\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[4].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"19:16\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[3].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"15:12\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[2].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"11:8\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[1].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"7:4\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[0].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"3:0\"> </Device> </Block> </Range> </AddressSpace> </Processor> <Processor Name=\"scalellm_vcu118_f05_bd_i_ddr4_0_inst_u_ddr4_mem_intfc_u_ddr_cal_riu_mcs0_inst_microblaze_I\" Type=\"MICROBLAZE-LE\" Id=\"100\" Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/microblaze_I\" SpaceElementCount=\"1\"> <AddressSpace Name=\"scalellm_vcu118_f05_bd_i_ddr4_0_inst_u_ddr4_mem_intfc_u_ddr_cal_riu_mcs0_inst_dlmb_cntlr\" Style=\"byte\" StartAddress=\"0x0000000000000000\" EndAddress=\"0x0000000000017FFF\" Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/dlmb_cntlr\" RangeElementCount=\"2\"> <Range Type=\"RAMB32\" BusBlockElementCount=\"1\"> <Block DeviceElementCount=\"16\"> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[15].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"31:30\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[14].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"29:28\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[13].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"27:26\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[12].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"25:24\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[11].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"23:22\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[10].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"21:20\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[9].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"19:18\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[8].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"17:16\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[7].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"15:14\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[6].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"13:12\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[5].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"11:10\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[4].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"9:8\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[3].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"7:6\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[2].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"5:4\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[1].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"3:2\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[0].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"1:0\"> </Device> </Block> </Range> <Range Type=\"RAMB32\" BusBlockElementCount=\"1\"> <Block DeviceElementCount=\"8\"> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[7].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"31:28\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[6].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"27:24\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[5].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"23:20\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[4].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"19:16\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[3].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"15:12\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[2].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"11:8\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[1].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"7:4\"> </Device> <Device Instance=\"scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_riu/mcs0/inst/second_lmb_bram_I/U0/inst_blk_mem_gen/gnbram.gnative_mem_map_bmg.native_mem_map_blk_mem_gen/valid.cstr/ramloop[0].ram.r/prim_noinit.ram/DEVICE_8SERIES.WITH_BMM_INFO.TRUE_DP.SIMPLE_PRIM36.SERIES8_TDP_SP36_NO_ECC_ATTR.ram\" Type=\"RAMB32\" Width=\"3:0\"> </Device> </Block> </Range> </AddressSpace> </Processor> </AddressMap>" *) 
(* \DesignAttr:ENABLE_NOC_NETLIST_VIEW  *) 
(* \DesignAttr:ENABLE_AIE_NETLIST_VIEW  *) 
module scalellm_vcu118_f05_bd_host_split_0_xpm_cdc_single__4
   (src_clk,
    src_in,
    dest_clk,
    dest_out);
  input src_clk;
  input src_in;
  input dest_clk;
  output dest_out;

  wire dest_clk;
  wire src_in;
  (* RTL_KEEP = "true" *) (* async_reg = "true" *) (* xpm_cdc = "SINGLE" *) wire [3:0]syncstages_ff;

  assign dest_out = syncstages_ff[3];
  (* ASYNC_REG *) 
  (* KEEP = "true" *) 
  (* XPM_CDC = "SINGLE" *) 
  FDRE #(
    .INIT(1'b0)) 
    \syncstages_ff_reg[0] 
       (.C(dest_clk),
        .CE(1'b1),
        .D(src_in),
        .Q(syncstages_ff[0]),
        .R(1'b0));
  (* ASYNC_REG *) 
  (* KEEP = "true" *) 
  (* XPM_CDC = "SINGLE" *) 
  FDRE #(
    .INIT(1'b0)) 
    \syncstages_ff_reg[1] 
       (.C(dest_clk),
        .CE(1'b1),
        .D(syncstages_ff[0]),
        .Q(syncstages_ff[1]),
        .R(1'b0));
  (* ASYNC_REG *) 
  (* KEEP = "true" *) 
  (* XPM_CDC = "SINGLE" *) 
  FDRE #(
    .INIT(1'b0)) 
    \syncstages_ff_reg[2] 
       (.C(dest_clk),
        .CE(1'b1),
        .D(syncstages_ff[1]),
        .Q(syncstages_ff[2]),
        .R(1'b0));
  (* ASYNC_REG *) 
  (* KEEP = "true" *) 
  (* XPM_CDC = "SINGLE" *) 
  FDRE #(
    .INIT(1'b0)) 
    \syncstages_ff_reg[3] 
       (.C(dest_clk),
        .CE(1'b1),
        .D(syncstages_ff[2]),
        .Q(syncstages_ff[3]),
        .R(1'b0));
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
