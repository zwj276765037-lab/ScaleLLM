# Deploy the Resource_optimization version

The public deployment entry is `deploy/scalellm.py`; its default profile is **all-dsp**, using the tested 80 MHz VCU118 bitstream under `resource_optimization/hardware/bitstream/`.

Follow the complete [deployment and reproduction guide](../resource_optimization/deployment/README.md) for:

1. Public file and bitstream verification.
2. Windows, AMD tools and [fixed driver source preparation](../deploy/driver/README.md).
3. The exact licensed model revision and fresh full-model export.
4. Configuration, SRAM programming, preflight and ordinary inference.
5. The separate fixed-active16, 128-position benchmark and local capture generation.
6. [Portable seven-rail power measurement](../resource_optimization/deployment/power/README.md) and offline analysis.

The [deployment stage results](../resource_optimization/deployment/source/results.md) record actual qualification status. Published November 15 hardware and power records retain their original scope; they do not substitute for a new installation test. A compatible installed Windows driver and licensed tools/model remain external prerequisites. No driver binary, model weights, boot-policy changes or Flash programming are included.

The root historical `96df…` bitstream is still selectable with `deployment_profile: "legacy"`. Its [earlier KV128 results](evidence/kv128_chat16/README.md) do not establish a complete KV128 run on the new image. Ordinary inference retains its 32-token request limit and EOS retirement; the new `benchmark-kv128` command has an explicit independent execution policy. No cumulative wall-time limit is enabled by default.

The FPGA runs Attention and Gate/Up including scale recovery and SiLU × Up. The CPU performs embedding, normalization, residuals, post-product H32/A8, integer Down and the FP32 LM head. No GPU is required. Successful transport and agreement with published regression outputs do not establish an independent full-model mathematical oracle.

Hardware rebuilding is separate. Use the [all-DSP source closure and as-run implementation records](../resource_optimization/README.md); [BUILD_HARDWARE.md](BUILD_HARDWARE.md) describes the historical root hardware recipe. Neither guide promises identical placement or bitstream bytes from a new build.
