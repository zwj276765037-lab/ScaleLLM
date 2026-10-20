# Device-holder preflight AT001 — results

35/35 CPU/mock tests passed, including nine new cases for hidden holders, lock-stage and post-stop races, missing identities/inventories, privileges, and fuser parsing/errors. No test invoked real GPU commands or changed services. See ../mock_results.json and ../mock_stdout.log for source hashes and AST comparison.

Read-only observations: Clash Verge WebKit PID11758 holds GPU1/GPU0/control; proxy core is in a separate active system service. LightDM active/running and seat0 greeter c4 now active. Driver reset failed because the device was in use; no completed reset or post-reset qualification. Xorg driver mismatch persists.
