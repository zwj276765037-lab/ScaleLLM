`timescale 1ns/1ps
module vcu118_pcie_refclk_ibuf(
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 pcie_refclk_p CLK",X_INTERFACE_PARAMETER="FREQ_HZ 100000000" *) input wire pcie_refclk_p,
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 pcie_refclk_n CLK",X_INTERFACE_PARAMETER="FREQ_HZ 100000000" *) input wire pcie_refclk_n,
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 sys_clk_gt CLK",X_INTERFACE_PARAMETER="FREQ_HZ 100000000" *) output wire sys_clk_gt,
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 sys_clk CLK",X_INTERFACE_PARAMETER="FREQ_HZ 100000000" *) output wire sys_clk);
 IBUFDS_GTE4 #(.REFCLK_EN_TX_PATH(1'b0),.REFCLK_HROW_CK_SEL(2'b00),.REFCLK_ICNTL_RX(2'b00))
 u_refclk(.I(pcie_refclk_p),.IB(pcie_refclk_n),.CEB(1'b0),.O(sys_clk_gt),.ODIV2(sys_clk));
endmodule
