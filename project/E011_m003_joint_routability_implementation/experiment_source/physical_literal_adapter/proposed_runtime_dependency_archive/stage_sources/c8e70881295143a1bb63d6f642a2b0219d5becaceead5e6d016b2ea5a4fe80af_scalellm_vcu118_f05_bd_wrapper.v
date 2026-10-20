//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//Copyright 2022-2025 Advanced Micro Devices, Inc. All Rights Reserved.
//--------------------------------------------------------------------------------
//Tool Version: Vivado v.2025.2 (lin64) Build 6299465 Fri Nov 14 12:34:56 MST 2025
//Date        : Sun Oct 18 12:28:24 2026
//Host        : user running 64-bit Ubuntu 24.04.4 LTS
//Command     : generate_target scalellm_vcu118_f05_bd_wrapper.bd
//Design      : scalellm_vcu118_f05_bd_wrapper
//Purpose     : IP block netlist
//--------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

module scalellm_vcu118_f05_bd_wrapper
   (ddr4_sdram_c1_act_n,
    ddr4_sdram_c1_adr,
    ddr4_sdram_c1_ba,
    ddr4_sdram_c1_bg,
    ddr4_sdram_c1_ck_c,
    ddr4_sdram_c1_ck_t,
    ddr4_sdram_c1_cke,
    ddr4_sdram_c1_cs_n,
    ddr4_sdram_c1_dm_n,
    ddr4_sdram_c1_dq,
    ddr4_sdram_c1_dqs_c,
    ddr4_sdram_c1_dqs_t,
    ddr4_sdram_c1_odt,
    ddr4_sdram_c1_reset_n,
    ddr4_sdram_c2_act_n,
    ddr4_sdram_c2_adr,
    ddr4_sdram_c2_ba,
    ddr4_sdram_c2_bg,
    ddr4_sdram_c2_ck_c,
    ddr4_sdram_c2_ck_t,
    ddr4_sdram_c2_cke,
    ddr4_sdram_c2_cs_n,
    ddr4_sdram_c2_dm_n,
    ddr4_sdram_c2_dq,
    ddr4_sdram_c2_dqs_c,
    ddr4_sdram_c2_dqs_t,
    ddr4_sdram_c2_odt,
    ddr4_sdram_c2_reset_n,
    default_250mhz_clk1_clk_n,
    default_250mhz_clk1_clk_p,
    default_250mhz_clk2_clk_n,
    default_250mhz_clk2_clk_p,
    pci_express_x8_rxn,
    pci_express_x8_rxp,
    pci_express_x8_txn,
    pci_express_x8_txp,
    pcie_perstn,
    pcie_refclk_n,
    pcie_refclk_p);
  output ddr4_sdram_c1_act_n;
  output [16:0]ddr4_sdram_c1_adr;
  output [1:0]ddr4_sdram_c1_ba;
  output [0:0]ddr4_sdram_c1_bg;
  output [0:0]ddr4_sdram_c1_ck_c;
  output [0:0]ddr4_sdram_c1_ck_t;
  output [0:0]ddr4_sdram_c1_cke;
  output [0:0]ddr4_sdram_c1_cs_n;
  inout [7:0]ddr4_sdram_c1_dm_n;
  inout [63:0]ddr4_sdram_c1_dq;
  inout [7:0]ddr4_sdram_c1_dqs_c;
  inout [7:0]ddr4_sdram_c1_dqs_t;
  output [0:0]ddr4_sdram_c1_odt;
  output ddr4_sdram_c1_reset_n;
  output ddr4_sdram_c2_act_n;
  output [16:0]ddr4_sdram_c2_adr;
  output [1:0]ddr4_sdram_c2_ba;
  output [0:0]ddr4_sdram_c2_bg;
  output [0:0]ddr4_sdram_c2_ck_c;
  output [0:0]ddr4_sdram_c2_ck_t;
  output [0:0]ddr4_sdram_c2_cke;
  output [0:0]ddr4_sdram_c2_cs_n;
  inout [7:0]ddr4_sdram_c2_dm_n;
  inout [63:0]ddr4_sdram_c2_dq;
  inout [7:0]ddr4_sdram_c2_dqs_c;
  inout [7:0]ddr4_sdram_c2_dqs_t;
  output [0:0]ddr4_sdram_c2_odt;
  output ddr4_sdram_c2_reset_n;
  input default_250mhz_clk1_clk_n;
  input default_250mhz_clk1_clk_p;
  input default_250mhz_clk2_clk_n;
  input default_250mhz_clk2_clk_p;
  input [7:0]pci_express_x8_rxn;
  input [7:0]pci_express_x8_rxp;
  output [7:0]pci_express_x8_txn;
  output [7:0]pci_express_x8_txp;
  input pcie_perstn;
  input pcie_refclk_n;
  input pcie_refclk_p;

  wire ddr4_sdram_c1_act_n;
  wire [16:0]ddr4_sdram_c1_adr;
  wire [1:0]ddr4_sdram_c1_ba;
  wire [0:0]ddr4_sdram_c1_bg;
  wire [0:0]ddr4_sdram_c1_ck_c;
  wire [0:0]ddr4_sdram_c1_ck_t;
  wire [0:0]ddr4_sdram_c1_cke;
  wire [0:0]ddr4_sdram_c1_cs_n;
  wire [7:0]ddr4_sdram_c1_dm_n;
  wire [63:0]ddr4_sdram_c1_dq;
  wire [7:0]ddr4_sdram_c1_dqs_c;
  wire [7:0]ddr4_sdram_c1_dqs_t;
  wire [0:0]ddr4_sdram_c1_odt;
  wire ddr4_sdram_c1_reset_n;
  wire ddr4_sdram_c2_act_n;
  wire [16:0]ddr4_sdram_c2_adr;
  wire [1:0]ddr4_sdram_c2_ba;
  wire [0:0]ddr4_sdram_c2_bg;
  wire [0:0]ddr4_sdram_c2_ck_c;
  wire [0:0]ddr4_sdram_c2_ck_t;
  wire [0:0]ddr4_sdram_c2_cke;
  wire [0:0]ddr4_sdram_c2_cs_n;
  wire [7:0]ddr4_sdram_c2_dm_n;
  wire [63:0]ddr4_sdram_c2_dq;
  wire [7:0]ddr4_sdram_c2_dqs_c;
  wire [7:0]ddr4_sdram_c2_dqs_t;
  wire [0:0]ddr4_sdram_c2_odt;
  wire ddr4_sdram_c2_reset_n;
  wire default_250mhz_clk1_clk_n;
  wire default_250mhz_clk1_clk_p;
  wire default_250mhz_clk2_clk_n;
  wire default_250mhz_clk2_clk_p;
  wire [7:0]pci_express_x8_rxn;
  wire [7:0]pci_express_x8_rxp;
  wire [7:0]pci_express_x8_txn;
  wire [7:0]pci_express_x8_txp;
  wire pcie_perstn;
  wire pcie_refclk_n;
  wire pcie_refclk_p;

  scalellm_vcu118_f05_bd scalellm_vcu118_f05_bd_i
       (.ddr4_sdram_c1_act_n(ddr4_sdram_c1_act_n),
        .ddr4_sdram_c1_adr(ddr4_sdram_c1_adr),
        .ddr4_sdram_c1_ba(ddr4_sdram_c1_ba),
        .ddr4_sdram_c1_bg(ddr4_sdram_c1_bg),
        .ddr4_sdram_c1_ck_c(ddr4_sdram_c1_ck_c),
        .ddr4_sdram_c1_ck_t(ddr4_sdram_c1_ck_t),
        .ddr4_sdram_c1_cke(ddr4_sdram_c1_cke),
        .ddr4_sdram_c1_cs_n(ddr4_sdram_c1_cs_n),
        .ddr4_sdram_c1_dm_n(ddr4_sdram_c1_dm_n),
        .ddr4_sdram_c1_dq(ddr4_sdram_c1_dq),
        .ddr4_sdram_c1_dqs_c(ddr4_sdram_c1_dqs_c),
        .ddr4_sdram_c1_dqs_t(ddr4_sdram_c1_dqs_t),
        .ddr4_sdram_c1_odt(ddr4_sdram_c1_odt),
        .ddr4_sdram_c1_reset_n(ddr4_sdram_c1_reset_n),
        .ddr4_sdram_c2_act_n(ddr4_sdram_c2_act_n),
        .ddr4_sdram_c2_adr(ddr4_sdram_c2_adr),
        .ddr4_sdram_c2_ba(ddr4_sdram_c2_ba),
        .ddr4_sdram_c2_bg(ddr4_sdram_c2_bg),
        .ddr4_sdram_c2_ck_c(ddr4_sdram_c2_ck_c),
        .ddr4_sdram_c2_ck_t(ddr4_sdram_c2_ck_t),
        .ddr4_sdram_c2_cke(ddr4_sdram_c2_cke),
        .ddr4_sdram_c2_cs_n(ddr4_sdram_c2_cs_n),
        .ddr4_sdram_c2_dm_n(ddr4_sdram_c2_dm_n),
        .ddr4_sdram_c2_dq(ddr4_sdram_c2_dq),
        .ddr4_sdram_c2_dqs_c(ddr4_sdram_c2_dqs_c),
        .ddr4_sdram_c2_dqs_t(ddr4_sdram_c2_dqs_t),
        .ddr4_sdram_c2_odt(ddr4_sdram_c2_odt),
        .ddr4_sdram_c2_reset_n(ddr4_sdram_c2_reset_n),
        .default_250mhz_clk1_clk_n(default_250mhz_clk1_clk_n),
        .default_250mhz_clk1_clk_p(default_250mhz_clk1_clk_p),
        .default_250mhz_clk2_clk_n(default_250mhz_clk2_clk_n),
        .default_250mhz_clk2_clk_p(default_250mhz_clk2_clk_p),
        .pci_express_x8_rxn(pci_express_x8_rxn),
        .pci_express_x8_rxp(pci_express_x8_rxp),
        .pci_express_x8_txn(pci_express_x8_txn),
        .pci_express_x8_txp(pci_express_x8_txp),
        .pcie_perstn(pcie_perstn),
        .pcie_refclk_n(pcie_refclk_n),
        .pcie_refclk_p(pcie_refclk_p));
endmodule
