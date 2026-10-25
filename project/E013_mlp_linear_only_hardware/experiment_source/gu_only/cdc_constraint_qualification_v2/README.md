# Same-routed-copy constraint qualification

This entry follows `hardware/source/mlp_linear/design.md` section 12. It opens only the historically bound R008/AT001 routed checkpoint. The already delivered AT003 engineering-validation bitstream must exist with its successful native result and delivery receipt. No synthesis, optimization, placement, routing, bitstream regeneration, FPGA configuration, or board execution occurs here.

The initial version was frozen in R008/AT004. Its CPU preparation completed 19 helper, rejection, JSON, and syntax checks; those checks do not prove Vivado object or timing behavior. Native results are separate.

The native flow exports the complete effective XDC and all valid/invalid timing constraints from the actual routed design. An unchanged timing replay must preserve the exported timing bytes, native clock identity, all twelve formal timing summary metrics, and each clock's setup/hold extrema. Full endpoint details are retained; equal-slack tie ordering is not treated as a timing change.

The candidate changes exactly one user three-domain clock-group command. DDR0-to-DDR1 isolation and every vendor constraint remain. Each directed PCIe-derived-to-DDR cut uses the complete primitive incoming-pin through superset, with explicit CE and INOUT handling, minus exactly 68 Attention and 70 GU dynamic D pins. Reverse cuts retain their original clock direction. Native inclusion assertions cover register data/async/CE, BUFG/BUFH/BUFR gating CE, and INOUT categories. Clock direction clamps preserve multi-clock RAM/DSP associations.

Each exposed D must be a real FDRE pin, directly driven by its corresponding XPM source FF Q, without an intermediate primitive. The source/capture clock-pin classification, Q/D direction, exact D exclusions, and absence of launch Q from external-output drivers prove an empty intersection with the complete through set. This proof is specific to the fixed 138 direct connections; it is not applied to SMC paths containing combinational logic. Both SMC exceptions remain unchanged in this first candidate.

All 138 corrected max paths must have finite, nonnegative slack under the actual 10 ns datapath-only constraint. Four bus-skew reports, full active setup/hold/pulse summaries, clock interaction, CDC, and check_timing are saved. A new checkpoint is written to a new path. The runner requires identical SHA256 values for the original and candidate EDIF, net-name, device, route, placement, and shape database members before issuing its scoped qualification manifest. It binds the existing bitstream; it does not regenerate one by default.

External reset timing/board requirements and final review of raw CDC/DRC findings remain independent acceptance boundaries. Historical FAIL results and the original routed DCP are never overwritten or upgraded.
