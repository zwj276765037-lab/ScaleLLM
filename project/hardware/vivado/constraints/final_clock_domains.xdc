# Actual 80 MHz core is generated from XDMA by clk_core. Its domain remains
# related to the PCIe reference. MIG UI clocks retain separate 200 MHz domains.
# Native XPM/IP scoped constraints own
# individual CDC protocols. Whole-domain cuts would override their datapath
# max-delay bounds, so unknown crossings remain visible for native review.
# Primary/generated clock existence is checked in ordinary native audit Tcl.
# Keep this XDC free of non-SDC foreach/assertion commands (Designutils20-1307).
# No top-level false paths, clock groups, reset or synchronizer-stage exceptions.
