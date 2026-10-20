# Device-holder preflight AT001 — source

Scope: respond to the user's failed single-GPU1 reset; inspect and harden the helper without further GPU or service actions. Baseline: versions/2aa9ef1d. Real failure: execute_20261018T055934.103845Z_335510, command_087.json, exit255/in-use. Read-only evidence identifies Clash Verge WebKit PID11758 holding GPU device nodes despite no NVML entry.

Change: root-only fuser inventory on five existing NVIDIA nodes, process identity inclusion, and rejection before stop/after stop. No process termination, no reset-target or orchestration changes.
