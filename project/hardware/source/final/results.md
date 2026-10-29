# Current final hardware results

Synthesis: 730,715 LUTs, 971,057 FFs, 709 BRAM36 equivalents, 304 URAM, 5,389 DSPs.
Placement: 701,775 LUTs, 954,554 FFs, 709 BRAM36 equivalents, 304 URAM, 5,389 DSPs.
Final post-route utilization was not reported and is not inferred from placement.
Final timing: WNS +0.017 ns, WHS +0.002 ns, WPWS 0.000 ns; zero failing endpoints.
Routing: all 1,712,169 routable nets routed, zero routing errors.

[Original report excerpts and provenance](../../../../docs/evidence/final/resources_timing_manifest.json)
separate synthesis, placement and post-route timing.
[Fresh portable build status](../../../../docs/evidence/final/build_validation.json)
is independent from the original bitstream's physical and board results.

Portable Vivado 2025.2 validation PASS: 335.707 s, 3,210,412,032 B peak tree RSS.
Fresh project/IP/wrapper/configuration creation PASS: 432.649 s,
3,467,943,936 B peak tree RSS, no input changes. Full RTL elaboration,
synthesis, implementation and fresh bit generation were not run.
Two focused reader protocol XSim cases PASS in 20.825 s total.

The historical physical closure chain and optional portable hold stages are in
[PHYSICAL_CLOSURE.md](../../../../docs/PHYSICAL_CLOSURE.md). Later repair/selected-
checkpoint additions passed 27 CPU control-flow/wiring cases (11 methods);
no additional EDA run was performed.
