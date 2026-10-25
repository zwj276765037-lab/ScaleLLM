# GU diagnostic entry

Complete production-shape nonzero diagnostics and independent integer gold for the M006 v7 engineering bit.

- [Protocol, numerical/wire authority and command](design.md)
- [CPU preparation evidence and limits](results.md)
- `generate.py`: fresh complete bundle; `verify.py`: independent full wire oracle.
- `run_gu.py`: unchanged GU backend plus a caller-owned session factory; full output/DONE persisted before ACK.
- `selfcheck_runner.py`: explicit CPU scripted driver fixtures, no board evidence.

Actual Dell operations belong to the host engineer. Readiness must pass before invoking the runner.
