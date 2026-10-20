# GPU1 maintenance candidate — reviewable plan, no maintenance executed

Owner A012; M004/SM020/E010. Device GPU-d87ce710-76bf-872d-9739-f0d7c9b52533, PCI0000:d8:00.0, RTX A6000. This is a plan for the active controller, not an assertion that a reset or driver change repairs the fault.

Current evidence: AT001 reproduces raw byte errors without a model, including device memset. AT002 naturally completed all9modes/1440readbacks with kernel-matched libcuda580.159.03 and still reproduced errors. AT003 naturally completed device00/ff with validated native GPU controls: GPU-internal count/direction/first coordinate/value match all320complete CPU readbacks; device00 has212992wrong bytes on the first read, ff has0. This excludes a pure full-buffer D2H-only explanation for those observed faults. All three workers naturally exited, all allocations/context frees returned0 and GPU1 flock was independently available at04:46:25Z. See [final consistency check](final_consistency_check.json). CUDA virtual allocation indices do not identify fixed physical bad pages.

The low-risk process-local library candidate is insufficient on current evidence. Retaining a suspect allocation or moving a model to other addresses would be an avoidance workaround; it would not demonstrate hardware repair and is not a production release criterion. No unbounded scanning or further backend sweeps are proposed.

The last captured reset inventory has actual GPU1 graphics use: parent-captured matching-NVML evidence reports Xorg PID2653/38MiB. Reset eligibility must be rechecked at any maintenance window; A012 has not queried later device clients. See sibling `nvml_local_recovery_20261018/nvml_query_20261018T0425.xml`. Newer parent inventory [maintenance impact inventory](../nvml_local_recovery_20261018/maintenance_impact_inventory_20261018T0435.json), actually captured04:34:40Z, confirms both GPUs have SYS topology with no NVLink and the same Xorg PID2653 uses both. The official extracted `nvidia-smi.1.gz` requires root and no CUDA/Xorg/monitor client on the target for reset; changing ECC mode takes effect at the next reboot. Do not kill this process or run reset in the current experiment. GPU0 work and M003 EDA retain their owners and normal no-forced-stop policy.

If the controller chooses maintenance after reviewing completed evidence:

1. Keep GPU1 formal evaluation disabled. Collect terminal receipts and verify all diagnostic workers have naturally exited and released GPU1 flock. Preserve this entire evidence tree.
2. Arrange an explicit maintenance window with the display-session owner. Save interactive work and let affected GPU0/M003 tasks naturally finish or follow their separately authorized maintenance procedure. Xorg/display service changes may affect the whole graphical session; do not infer permission from this diagnostic task.
3. At that approved window, use matching-NVML read-only process/device inventory to establish whether GPU1 has any clients and whether the current topology still has no NVLink peer requirement. The04:34:40Z inventory has no NVLink, so there is currently no evidence that a peer reset is needed. If the target remains occupied, do not reset it. Reset eligibility is an actual precondition, not an assumption.
4. An administrator may then choose the specific GPU1-only reset if the tool reports eligibility. Alternatively perform a planned machine restart with a consistently packaged driver stack. System driver installation, unload/reload and reboot are separate administrator actions; none has been performed or authorized to A012 here.
5. After the chosen maintenance, reopen a new attempt with the same complete finite raw protocol and native observer controls. Only an observed all-byte pass may qualify the affected raw-memory scope. Then independently validate full checkpoint/GPU tensor identity, preservation across the exact native calls and original determinism gates before the controller resumes any model matrix or formal rows.
6. If corruption persists, preserve before/after evidence and escalate to offline device/platform service diagnostics. The present evidence by itself does not distinguish physical DRAM, memory controller, device driver/kernel or another device-side path, and it does not certify a hardware repair.

The concrete reset candidate, only for an administrator after all stated eligibility and maintenance conditions are satisfied, is:

```bash
sudo bash /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/nvml_local_recovery_20261018/nvidia_smi_local.sh --gpu-reset -i GPU-d87ce710-76bf-872d-9739-f0d7c9b52533
```

That existing read-only-inspected wrapper selects the extracted580.159.03 executable and matching NVML, and refuses a changed kernel version. This reset command has **not** been executed. Display-session termination, package operations and reboot require their responsible owners and separate maintenance authorization; no command for those changes is run here.
