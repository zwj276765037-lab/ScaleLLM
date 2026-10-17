# Missing physical stage continuation — private preparation

Prepared while AT009 is running. Nothing here is installed. No unit regression,
real source qualification, or additional EDA has run. Only Python syntax parsing
has run. Preserve the fixed AT009 deadline and the single EDA lane.

The original `review_snapshot_v1/` preserves seven reviewed candidate files. Its
manifest SHA is `460040b2013d81fa0d84f5be78dcb35f1389b5e2ef298c5e1d325b4320f02b56`.
After that snapshot, two small deltas remain in the mutable candidate: the same
divider/input frequency/530 endpoint set comparisons as the existing restore
guard, and test module imports/clock negative coverage. Do not call the current
candidate frozen or tested until the post-AT checks actually finish.

`--physical-report` is place-stage only and mutually exclusive with other restore
choices. It accepts a genuine bounded timeout only after successful native place
or physopt command evidence, generated/closed DCP package evidence, immutable
source closure, source identity, and no surviving owned identities are complete.
There is no place_design call in either new Tcl branch. A place point finishes
only missing place POST then physopt; a physopt point finishes only its missing
POST/finalization. Full original POST may be inherited only at the identical
closed checkpoint; partial reports are not promoted to complete POST.

After AT009 ends, independently inspect the original status and all owned PID
identities. If there is no genuine new closed physical checkpoint, stop this
placement recovery chain. Leave this preparation uninstalled and do not launch
another place attempt. If a closed point exists, run the necessary CPU tests and
the actual canonical parent qualification while the EDA lane is idle, archive
final source and evidence, verify all five live files against AT009 stage_sources
under the lane lock, install, and launch only missing stages with unchanged limits.

`freeze_closed_physical_source.py` observes original terminal evidence and seals
the exact original output files. It runs no EDA, rewrites no original EDA reports
or status, and refuses sources with no actual closed native physical output.
Its output is new post-termination evidence, never a retroactive launcher success.

`tests/test_m002_physical_resume.py` contains focused unit fixtures, Tcl branch
sequence checks, and current/history/finalize/route-parent checks. Fixtures mock
previously qualified upstream state; actual source qualification must separately
use the real AT009 evidence. Existing unchanged legacy coverage remains identified
as reused. Formal reset/CDC safety and physical signoff stay OPEN/false.
