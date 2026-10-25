# V5 board-owned physical constraints.  MIG and XDMA generated XDCs remain
# authoritative for their IP.  Project-owned false paths and datapath-only
# delays are intentionally absent.
set pcie_refclk_p_port [get_ports -quiet pcie_refclk_p]
set pcie_refclk_n_port [get_ports -quiet pcie_refclk_n]
set pcie_perstn_port [get_ports -quiet pcie_perstn]
set_property BOARD_PART_PIN {pcie_mgt_clkp} $pcie_refclk_p_port
set_property BOARD_PART_PIN {pcie_mgt_clkn} $pcie_refclk_n_port
set_property BOARD_PART_PIN {pcie_perstn_rst} $pcie_perstn_port
create_clock -period 10.000 -name pcie_refclk $pcie_refclk_p_port
