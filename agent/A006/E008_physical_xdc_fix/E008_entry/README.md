# E008 physical XDC export option compatibility repair

Same selected C01 and original contracts. Consumed AT002/45bbc remains immutable.
Only executable Tcl delta: in the actual `slr2::constrain_region`, change
`write_xdc -constraints physical <same-output>` to `write_xdc -type physical <same-output>`.
The installed Vivado2025.2 manual and actual native help both confirm this syntax.
No `-quiet`, `-force`, `-no_fixed_only`, XDC reload or constraint-policy change.
Native errors still propagate; all wrapper/ancestor/resource/Pblock/placement/global gates remain.

CT002 executes the actual region procedure in 9 finite native API mock cases.
CT001 is preserved: a harness tuple/scalar comparison error, not production behavior;
CT002 corrects that comparison and all cases pass. Unchanged policy26, collector,
index/logging and full pipeline evidence is reused without broad reruns.
Finite native API help opened no design and has separate source/log/status evidence.
This package has no new full-design native qualification or physical success yet.

Same C01 ordinary source retry uses the existing delegated execution binding after
actual predecessor terminal/PID/input/lane closure and applicable independent delta review.
No wall/no-output stop, bitstream, board, GPU, PPL or ACC. All original inputs unchanged.
